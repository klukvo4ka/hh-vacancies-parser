from collections.abc import Hashable, Iterable

from src.models.parser import NOT_SPECIFIED
from src.models.vacancy import Vacancy


def deduplicate_vacancies(vacancies: Iterable[Vacancy]) -> list[Vacancy]:
    """Keep the first occurrence of each vacancy, matching by HH ID or a conservative fallback."""
    seen: set[Hashable] = set()
    unique: list[Vacancy] = []
    for vacancy in vacancies:
        key = _identity_key(vacancy)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        unique.append(vacancy)
    return unique


def _identity_key(vacancy: Vacancy) -> Hashable | None:
    """Return None when a vacancy has no reliable identity, so it is never treated as a duplicate."""
    if vacancy.id.strip():
        return ("id", vacancy.id.strip())

    name = _normalize(vacancy.name)
    company = _normalize(vacancy.company)
    url = _normalize(vacancy.url)
    if not (url or _is_meaningful(name) or _is_meaningful(company)):
        return None
    return ("fallback", name, company, url)


def _normalize(value: str) -> str:
    return value.strip().casefold()


def _is_meaningful(value: str) -> bool:
    return bool(value) and value != NOT_SPECIFIED.casefold()
