from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

HH_API_BASE_URL = "https://api.hh.ru"
HH_USER_AGENT = "HHVacanciesParser/1.0 (hh-vacancies-parser@example.com)"
HH_REQUEST_TIMEOUT = 10.0
HH_MAX_PER_PAGE = 100
