import asyncio
import sys

from src.api.client import HHApiClient, HHApiError

SEARCH_QUERY = "Python developer"


async def run() -> None:
    async with HHApiClient() as client:
        data = await client.search_vacancies(SEARCH_QUERY)

    print(f"Query: {SEARCH_QUERY}")
    print(f"Found: {data.get('found', 0)} vacancies")
    print(f"Loaded: {len(data['items'])} vacancies")
    if data.get("pages"):
        print(f"Page: {data.get('page', 0) + 1}/{data['pages']}")


def main() -> None:
    try:
        asyncio.run(run())
    except HHApiError as exc:
        sys.exit(f"Error: {exc}")


if __name__ == "__main__":
    main()
