import asyncio
import sys

from src.api.client import HHApiClient, HHApiError
from src.models import parse_vacancies

SEARCH_QUERY = "Python developer"
MAX_VACANCIES = 200


async def run() -> None:
    async with HHApiClient() as client:
        raw_items = await client.search_all_vacancies(SEARCH_QUERY, max_vacancies=MAX_VACANCIES)

    vacancies = parse_vacancies(raw_items)

    print(f"Query: {SEARCH_QUERY}")
    print(f"Loaded: {len(raw_items)} vacancies")
    print(f"Parsed: {len(vacancies)} vacancies")


def main() -> None:
    try:
        asyncio.run(run())
    except HHApiError as exc:
        sys.exit(f"Error: {exc}")


if __name__ == "__main__":
    main()
