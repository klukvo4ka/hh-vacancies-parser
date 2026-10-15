import asyncio
import sys

from src.api.client import HHApiClient, HHApiError
from src.config import OUTPUT_DIR
from src.exporters import export_vacancies_to_excel
from src.models import parse_vacancies

SEARCH_QUERY = "Python developer"
MAX_VACANCIES = 200
OUTPUT_FILENAME = "vacancies.xlsx"


async def run() -> None:
    async with HHApiClient() as client:
        raw_items = await client.search_all_vacancies(SEARCH_QUERY, max_vacancies=MAX_VACANCIES)

    vacancies = parse_vacancies(raw_items)
    output_path = export_vacancies_to_excel(vacancies, OUTPUT_DIR / OUTPUT_FILENAME)

    print(f"Query: {SEARCH_QUERY}")
    print(f"Loaded: {len(raw_items)} vacancies")
    print(f"Parsed: {len(vacancies)} vacancies")
    print(f"Saved to: {output_path}")


def main() -> None:
    try:
        asyncio.run(run())
    except HHApiError as exc:
        sys.exit(f"Error: {exc}")
    except OSError as exc:
        sys.exit(f"Error: could not save Excel file: {exc}")


if __name__ == "__main__":
    main()
