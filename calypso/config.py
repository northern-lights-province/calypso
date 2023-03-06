import os

DB_URI = os.getenv("DB_URI", f"sqlite+aiosqlite:///data/calypso.db")
TOKEN = os.getenv("TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
GOOGLE_SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH")
AVRAE_API_KEY = os.getenv("AVRAE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
