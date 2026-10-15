import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

# Values already set in the environment take precedence over the local .env file.
load_dotenv(PROJECT_ROOT / ".env")


def env_value(name: str) -> str | None:
    """Return a stripped environment variable, treating blank values as unset."""
    value = os.getenv(name, "").strip()
    return value or None


HH_API_BASE_URL = "https://api.hh.ru"
HH_TOKEN_URL = f"{HH_API_BASE_URL}/token"
HH_USER_AGENT = "HHVacanciesParser/1.0"
HH_REQUEST_TIMEOUT = 10.0
HH_MAX_PER_PAGE = 100
HH_MAX_SEARCH_RESULTS = 2000

HH_ACCESS_TOKEN = env_value("HH_ACCESS_TOKEN")
HH_CLIENT_ID = env_value("HH_CLIENT_ID")
HH_CLIENT_SECRET = env_value("HH_CLIENT_SECRET")
