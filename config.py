import os
from datetime import timezone, timedelta

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "yordamchi_SQ_bot")

# Mini App manzili (Render bergan manzil). Bot shu manzilni ochadi.
APP_URL = os.getenv("APP_URL", "")

PORT = int(os.getenv("PORT", "8080"))

# Mahalliy sinov: initData tekshiruvisiz ?dev_id=123 bilan kirish
DEV_MODE = os.getenv("DEV_MODE", "0") == "1"

# O'zbekiston vaqti
TZ = timezone(timedelta(hours=5))

APP_NAME = "Yordamchi AI"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
