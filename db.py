"""SQLite storage. One small file (lunch.db), created automatically."""
import json
import sqlite3
from contextlib import closing

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    user_id INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    active  INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS absences (
    date    TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (date, user_id)
);
CREATE TABLE IF NOT EXISTS runs (            -- one row per day /ready was used
    date       TEXT PRIMARY KEY,
    ready_at   TEXT NOT NULL,                -- ISO datetime
    channel_id INTEGER NOT NULL,
    message_id INTEGER,
    batches    TEXT NOT NULL,                -- JSON: [[user ids], ...]
    pinged     INTEGER NOT NULL DEFAULT 0    -- how many batches have been called
);
CREATE TABLE IF NOT EXISTS history (         -- feeds the weighted shuffle
    date        TEXT NOT NULL,
    user_id     INTEGER NOT NULL,
    batch_index INTEGER NOT NULL,
    num_batches INTEGER NOT NULL,
    PRIMARY KEY (date, user_id)
);
CREATE TABLE IF NOT EXISTS specials (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    date     TEXT NOT NULL,
    dish     TEXT NOT NULL,
    added_by INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS banners (date TEXT PRIMARY KEY);
"""


def _conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with closing(_conn()) as c, c:
        c.executescript(SCHEMA)


# ---------- employees ----------
def add_employee(user_id, name):
    with closing(_conn()) as c, c:
        c.execute(
            "INSERT INTO employees (user_id, name, active) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET name = excluded.name, active = 1",
            (user_id, name),
        )


def remove_employee(user_id):
    """Soft delete, so their history stays intact."""
    with closing(_conn()) as c, c:
        cur = c.execute("UPDATE employees SET active = 0 WHERE user_id = ? AND active = 1", (user_id,))
        return cur.rowcount > 0


def active_employees():
    with closing(_conn()) as c:
        return [dict(r) for r in c.execute("SELECT user_id, name FROM employees WHERE active = 1 ORDER BY name")]


# ---------- absences ----------
def add_absences(date, user_ids):
    with closing(_conn()) as c, c:
        c.executemany("INSERT OR IGNORE INTO absences VALUES (?, ?)", [(date, u) for u in user_ids])


def remove_absences(date, user_ids):
    with closing(_conn()) as c, c:
        c.executemany("DELETE FROM absences WHERE date = ? AND user_id = ?", [(date, u) for u in user_ids])


def absences(date):
    with closing(_conn()) as c:
        return [r["user_id"] for r in c.execute("SELECT user_id FROM absences WHERE date = ?", (date,))]


# ---------- daily runs ----------
def get_run(date):
    with closing(_conn()) as c:
        r = c.execute("SELECT * FROM runs WHERE date = ?", (date,)).fetchone()
    if not r:
        return None
    run = dict(r)
    run["batches"] = json.loads(run["batches"])
    return run


def save_run(date, ready_at, channel_id, batches):
    with closing(_conn()) as c, c:
        c.execute(
            "INSERT INTO runs (date, ready_at, channel_id, batches) VALUES (?, ?, ?, ?)",
            (date, ready_at, channel_id, json.dumps(batches)),
        )
    save_history(date, batches)


def update_run(date, **fields):
    if "batches" in fields:
        fields["batches"] = json.dumps(fields["batches"])
    cols = ", ".join(f"{k} = ?" for k in fields)
    with closing(_conn()) as c, c:
        c.execute(f"UPDATE runs SET {cols} WHERE date = ?", (*fields.values(), date))


def save_history(date, batches):
    rows = [(date, uid, i, len(batches)) for i, b in enumerate(batches) for uid in b]
    with closing(_conn()) as c, c:
        c.execute("DELETE FROM history WHERE date = ?", (date,))
        c.executemany("INSERT INTO history VALUES (?, ?, ?, ?)", rows)


def lateness(user_ids, days):
    """Average position over each person's last `days` lunches: 0 = first batch, 1 = last."""
    result = {}
    with closing(_conn()) as c:
        for uid in user_ids:
            rows = c.execute(
                "SELECT batch_index, num_batches FROM history WHERE user_id = ? ORDER BY date DESC LIMIT ?",
                (uid, days),
            ).fetchall()
            if rows:
                vals = [r["batch_index"] / (r["num_batches"] - 1) if r["num_batches"] > 1 else 0.5 for r in rows]
                result[uid] = sum(vals) / len(vals)
    return result


# ---------- specials ----------
def add_special(date, dish, added_by):
    with closing(_conn()) as c, c:
        c.execute("INSERT INTO specials (date, dish, added_by) VALUES (?, ?, ?)", (date, dish, added_by))


def specials_in_month(year_month):  # "2026-10"
    with closing(_conn()) as c:
        return [dict(r) for r in c.execute(
            "SELECT date, dish FROM specials WHERE date LIKE ? ORDER BY date, id", (f"{year_month}-%",)
        )]


# ---------- banner ----------
def banner_posted(date):
    with closing(_conn()) as c:
        return c.execute("SELECT 1 FROM banners WHERE date = ?", (date,)).fetchone() is not None


def mark_banner(date):
    with closing(_conn()) as c, c:
        c.execute("INSERT OR IGNORE INTO banners VALUES (?)", (date,))
