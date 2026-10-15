from collections.abc import Iterable, Mapping
from typing import Any

from src.models.vacancy import Vacancy

NOT_SPECIFIED = "Не указано"


def parse_vacancy(item: Mapping[str, Any]) -> Vacancy:
    salary = item.get("salary")
    if not isinstance(salary, Mapping):
        salary = {}

    return Vacancy(
        id=_optional_id(item.get("id")),
        name=_optional_str(item.get("name")) or NOT_SPECIFIED,
        company=_nested_name(item.get("employer")),
        salary_from=_optional_int(salary.get("from")),
        salary_to=_optional_int(salary.get("to")),
        salary_currency=_optional_str(salary.get("currency")),
        salary_gross=_optional_bool(salary.get("gross")),
        area=_nested_name(item.get("area")),
        experience=_nested_name(item.get("experience")),
        employment=_nested_name(item.get("employment")),
        work_format=_work_format(item),
        published_at=_optional_str(item.get("published_at")) or "",
        url=_optional_str(item.get("alternate_url")) or "",
    )


def parse_vacancies(items: Iterable[Mapping[str, Any]]) -> list[Vacancy]:
    return [parse_vacancy(item) for item in items]


def _work_format(item: Mapping[str, Any]) -> str:
    """Prefer the work_format list, fall back to the legacy schedule name."""
    formats = item.get("work_format")
    if isinstance(formats, list):
        names = (_optional_str(entry.get("name")) for entry in formats if isinstance(entry, Mapping))
        unique_names = dict.fromkeys(name for name in names if name)
        if unique_names:
            return ", ".join(unique_names)
    return _nested_name(item.get("schedule"))


def _nested_name(value: object) -> str:
    if isinstance(value, Mapping):
        return _optional_str(value.get("name")) or NOT_SPECIFIED
    return NOT_SPECIFIED


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _optional_id(value: object) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return _optional_str(value) or ""


def _optional_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None
