"""Taghyeer Lunch Bot.

Daily flow:
  12:00 PM      -> posts a big date banner (office days only)
  /absent       -> admin marks who's out today
  /ready        -> admin says the meal is ready: full batch list is posted, Batch 1 is pinged
  every 20 min  -> the next batch is pinged automatically
  /late         -> late arrivals join the last batch
"""
import datetime as dt
import logging
import re

import discord
from discord import app_commands
from discord.ext import tasks

import config
import db
from banner import render_date
from shuffle import make_batches

log = logging.getLogger("lunchbot")
MENTION_RE = re.compile(r"<@!?(\d+)>")
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
NO_PINGS = discord.AllowedMentions.none()
USER_PINGS = discord.AllowedMentions(users=True, roles=False, everyone=False)


# ---------------------------------------------------------------- helpers
def now():
    return dt.datetime.now(config.TIMEZONE)


def today():
    return now().date().isoformat()


def parse_mentions(text: str) -> list[int]:
    return list(dict.fromkeys(int(x) for x in MENTION_RE.findall(text or "")))


def mentions(ids):
    return " ".join(f"<@{i}>" for i in ids)


def batch_time(run, index):
    ready = dt.datetime.fromisoformat(run["ready_at"])
    return ready + dt.timedelta(minutes=config.BATCH_INTERVAL_MINUTES * index)


def list_message(run) -> str:
    ready = dt.datetime.fromisoformat(run["ready_at"])
    lines = [f"🍽️ **Lunch is ready!** · {ready.strftime('%a %d %b')}", ""]
    for i, batch in enumerate(run["batches"]):
        t = batch_time(run, i).strftime("%I:%M %p").lstrip("0")
        lines.append(f"**Batch {i + 1}** · {t}")
        lines.append(", ".join(f"<@{u}>" for u in batch))
        lines.append("")
    lines.append(f"_Each batch gets pinged when it's their turn (every {config.BATCH_INTERVAL_MINUTES} min)._")
    return "\n".join(lines)


def is_admin(member) -> bool:
    if not isinstance(member, discord.Member):
        return False
    return member.guild_permissions.administrator or any(r.name == config.ADMIN_ROLE_NAME for r in member.roles)


def admin_only():
    async def predicate(inter: discord.Interaction):
        if is_admin(inter.user):
            return True
        raise app_commands.CheckFailure(f"Only people with the **{config.ADMIN_ROLE_NAME}** role can use this.")
    return app_commands.check(predicate)


# ---------------------------------------------------------------- bot
class LunchBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        db.init()
        guild = discord.Object(id=config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        ping_loop.start()
        banner_loop.start()

    async def lunch_channel(self):
        return self.get_channel(config.LUNCH_CHANNEL_ID) or await self.fetch_channel(config.LUNCH_CHANNEL_ID)


bot = LunchBot()


@bot.tree.error
async def on_app_command_error(inter: discord.Interaction, error):
    msg = str(error) if isinstance(error, app_commands.CheckFailure) else "Something went wrong. Check the bot logs."
    if not isinstance(error, app_commands.CheckFailure):
        log.exception("Command failed", exc_info=error)
    if inter.response.is_done():
        await inter.followup.send(msg, ephemeral=True)
    else:
        await inter.response.send_message(msg, ephemeral=True)


# ---------------------------------------------------------------- batch pings
async def call_due_batches():
    """Ping every batch whose turn has come and hasn't been pinged yet."""
    run = db.get_run(today())
    if not run:
        return
    channel = bot.get_channel(run["channel_id"]) or await bot.fetch_channel(run["channel_id"])
    current = now()
    pinged = run["pinged"]
    while pinged < len(run["batches"]) and batch_time(run, pinged) <= current:
        late_by = current - batch_time(run, pinged)
        # If the bot was offline for a long time, don't spam old pings.
        if late_by <= dt.timedelta(minutes=config.BATCH_INTERVAL_MINUTES):
            batch = run["batches"][pinged]
            await channel.send(
                f"🔔 **Batch {pinged + 1}, your turn!** {mentions(batch)}",
                allowed_mentions=USER_PINGS,
            )
        pinged += 1
        db.update_run(run["date"], pinged=pinged)


@tasks.loop(seconds=20)
async def ping_loop():
    try:
        await call_due_batches()
    except Exception:
        log.exception("Ping loop error")


@ping_loop.before_loop
async def _wait_ping():
    await bot.wait_until_ready()


# ---------------------------------------------------------------- date banner
def _banner_time():
    h, m = (int(x) for x in config.BANNER_TIME.split(":"))
    return dt.time(hour=h, minute=m, tzinfo=config.TIMEZONE)


@tasks.loop(time=_banner_time())
async def banner_loop():
    d = now().date()
    if WEEKDAYS[d.weekday()] not in config.OFFICE_DAYS or db.banner_posted(d.isoformat()):
        return
    channel = await bot.lunch_channel()
    await channel.send(f"```\n{render_date(d.day, d.month)}\n```")
    db.mark_banner(d.isoformat())


@banner_loop.before_loop
async def _wait_banner():
    await bot.wait_until_ready()


# ---------------------------------------------------------------- commands
@bot.tree.command(name="absent", description="Mark people as absent today (mention them).")
@app_commands.describe(users="Mention everyone who's out, e.g. @Rahat @Toky")
@admin_only()
async def absent(inter: discord.Interaction, users: str):
    ids = parse_mentions(users)
    if not ids:
        return await inter.response.send_message("Mention at least one person.", ephemeral=True)
    db.add_absences(today(), ids)
    note = ""
    if db.get_run(today()):
        note = "\n_Today's list is already posted, so their spots will just stay open._"
    all_out = db.absences(today())
    await inter.response.send_message(
        f"Marked absent: {mentions(ids)}\nOut today ({len(all_out)}): {mentions(all_out)}{note}",
        ephemeral=True, allowed_mentions=NO_PINGS,
    )


@bot.tree.command(name="present", description="Undo an absent mark (mention them).")
@app_commands.describe(users="Mention the people who are actually in")
@admin_only()
async def present(inter: discord.Interaction, users: str):
    ids = parse_mentions(users)
    if not ids:
        return await inter.response.send_message("Mention at least one person.", ephemeral=True)
    db.remove_absences(today(), ids)
    note = "\n_Today's list is already posted. Use /late to add them to it._" if db.get_run(today()) else ""
    await inter.response.send_message(f"No longer absent: {mentions(ids)}{note}",
                                      ephemeral=True, allowed_mentions=NO_PINGS)


@bot.tree.command(name="ready", description="The meal is ready: post today's batches.")
@admin_only()
async def ready(inter: discord.Interaction):
    date = today()
    existing = db.get_run(date)
    if existing:
        t = dt.datetime.fromisoformat(existing["ready_at"]).strftime("%I:%M %p").lstrip("0")
        return await inter.response.send_message(f"Today's list was already posted at {t}.", ephemeral=True)

    out = set(db.absences(date))
    people = [e["user_id"] for e in db.active_employees() if e["user_id"] not in out]
    if not people:
        return await inter.response.send_message(
            "Nobody to schedule. Add employees with /employees add first.", ephemeral=True)

    batches = make_batches(
        people,
        db.lateness(people, config.FAIRNESS_HISTORY_DAYS),
        config.PAIR_USER_IDS,
        max_size=config.BATCH_SIZE,
        strength=config.FAIRNESS_STRENGTH,
    )
    channel = await bot.lunch_channel()
    db.save_run(date, now().isoformat(), channel.id, batches)
    run = db.get_run(date)

    await inter.response.send_message("Posted! Batch 1 is being called now.", ephemeral=True)
    msg = await channel.send(list_message(run), allowed_mentions=NO_PINGS)
    db.update_run(date, message_id=msg.id)
    await call_due_batches()  # pings Batch 1 right away


@bot.tree.command(name="late", description="Add late arrivals to today's list (mention them).")
@app_commands.describe(users="Mention the people who arrived late")
@admin_only()
async def late(inter: discord.Interaction, users: str):
    ids = parse_mentions(users)
    if not ids:
        return await inter.response.send_message("Mention at least one person.", ephemeral=True)
    date = today()
    db.remove_absences(date, ids)
    run = db.get_run(date)
    if not run:
        return await inter.response.send_message(
            f"{mentions(ids)} will be included when you run /ready.", ephemeral=True, allowed_mentions=NO_PINGS)

    batches = run["batches"]
    already = {u for b in batches for u in b}
    pair = set(config.PAIR_USER_IDS)
    added = []  # (user_id, batch_index)
    for uid in ids:
        if uid in already:
            continue
        target = len(batches) - 1  # default: last batch
        if uid in pair:
            partner = next((p for p in pair if p != uid), None)
            for i, b in enumerate(batches):
                if partner in b and i >= run["pinged"]:  # partner's batch not called yet
                    target = i
        batches[target].append(uid)
        already.add(uid)
        added.append((uid, target))

    if not added:
        return await inter.response.send_message("They're already on today's list.", ephemeral=True)

    db.update_run(date, batches=batches)
    db.save_history(date, batches)
    run = db.get_run(date)
    channel = bot.get_channel(run["channel_id"]) or await bot.fetch_channel(run["channel_id"])
    if run["message_id"]:
        try:
            msg = await channel.fetch_message(run["message_id"])
            await msg.edit(content=list_message(run), allowed_mentions=NO_PINGS)
        except discord.NotFound:
            pass

    await inter.response.send_message("Added.", ephemeral=True)
    for uid, i in added:
        when = "they're eating now, go join them!" if i < run["pinged"] else "you'll be pinged when it's time."
        await channel.send(f"➕ <@{uid}> joins **Batch {i + 1}**: {when}", allowed_mentions=USER_PINGS)


@bot.tree.command(name="special", description="Log today's special lunch, e.g. /special kacchi biriyani")
@app_commands.describe(dish="What was served")
@admin_only()
async def special(inter: discord.Interaction, dish: str):
    dish = dish.strip()
    db.add_special(today(), dish, inter.user.id)
    await inter.response.send_message(f"⭐ Logged special lunch: **{dish}** ({now().strftime('%d / %m')})",
                                      ephemeral=True)


count = app_commands.Group(name="count", description="Counts and stats")


@count.command(name="special", description="How many special lunches this month")
@admin_only()
async def count_special(inter: discord.Interaction):
    n = now()
    rows = db.specials_in_month(n.strftime("%Y-%m"))
    header = f"**{n.strftime('%B %Y')}: {len(rows)} special lunch{'es' if len(rows) != 1 else ''}**"
    body = "\n".join(
        f"{dt.date.fromisoformat(r['date']).strftime('%d / %m')}: {r['dish']}" for r in rows
    )
    await inter.response.send_message(header + ("\n" + body if body else ""), ephemeral=True)


bot.tree.add_command(count)

employees = app_commands.Group(name="employees", description="Manage who is on the lunch roster")


@employees.command(name="add", description="Add people to the roster (mention them)")
@app_commands.describe(users="Mention everyone to add, e.g. @Rahat @Toky")
@admin_only()
async def employees_add(inter: discord.Interaction, users: str):
    ids = parse_mentions(users)
    if not ids:
        return await inter.response.send_message("Mention at least one person.", ephemeral=True)
    await inter.response.defer(ephemeral=True)
    names = []
    for uid in ids:
        try:
            member = await inter.guild.fetch_member(uid)
            name = member.display_name
        except discord.NotFound:
            name = str(uid)
        db.add_employee(uid, name)
        names.append(name)
    await inter.followup.send(f"Added {len(names)}: {', '.join(names)}", ephemeral=True)


@employees.command(name="remove", description="Remove people from the roster (mention them)")
@app_commands.describe(users="Mention everyone to remove")
@admin_only()
async def employees_remove(inter: discord.Interaction, users: str):
    ids = parse_mentions(users)
    removed = [u for u in ids if db.remove_employee(u)]
    await inter.response.send_message(f"Removed: {mentions(removed) or 'nobody'}",
                                      ephemeral=True, allowed_mentions=NO_PINGS)


@employees.command(name="list", description="Show everyone on the roster")
@admin_only()
async def employees_list(inter: discord.Interaction):
    people = db.active_employees()
    pair = set(config.PAIR_USER_IDS)
    lines = [f"{'👭 ' if p['user_id'] in pair else ''}{p['name']}" for p in people]
    await inter.response.send_message(f"**Roster ({len(people)})**\n" + "\n".join(lines), ephemeral=True)


bot.tree.add_command(employees)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    bot.run(config.DISCORD_TOKEN, log_handler=None)
