"""All settings come from the .env file (see .env.example)."""
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _ids(value: str) -> list[int]:
    return [int(x) for x in value.replace(" ", "").split(",") if x]


DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
LUNCH_CHANNEL_ID = int(os.environ["LUNCH_CHANNEL_ID"])

ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Lunch Admin")
PAIR_USER_IDS = _ids(os.getenv("PAIR_USER_IDS", ""))

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))
BATCH_INTERVAL_MINUTES = int(os.getenv("BATCH_INTERVAL_MINUTES", "20"))

TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Asia/Dhaka"))
BANNER_TIME = os.getenv("BANNER_TIME", "12:00")  # 24h, local time
OFFICE_DAYS = [d.strip().lower()[:3] for d in os.getenv("OFFICE_DAYS", "sun,mon,tue,wed,thu").split(",")]

FAIRNESS_STRENGTH = float(os.getenv("FAIRNESS_STRENGTH", "0.5"))
FAIRNESS_HISTORY_DAYS = int(os.getenv("FAIRNESS_HISTORY_DAYS", "10"))

DB_PATH = os.getenv("DB_PATH", "lunch.db")
