"""Shared builders and a fake HH endpoint for the test suite."""

import math
from typing import Any

import httpx

from src.models import Vacancy

NOT_SPECIFIED = "Не указано"


def make_vacancy(**overrides: Any) -> Vacancy:
    fields: dict[str, Any] = {
        "id": "1",
        "name": "Python Developer",
        "company": "ACME",
        "salary_from": 150000,
        "salary_to": 250000,
        "salary_currency": "RUR",
        "salary_gross": False,
        "area": "Москва",
        "experience": "От 1 года до 3 лет",
        "employment": "Полная занятость",
        "work_format": "Удалённо",
        "published_at": "2026-10-15T10:30:00+0300",
        "url": "https://hh.ru/vacancy/1",
    }
    fields.update(overrides)
    return Vacancy(**fields)


def make_raw_item(vacancy_id: int | str = 1, **overrides: Any) -> dict[str, Any]:
    """A raw /vacancies item shaped like the HH API response."""
    item: dict[str, Any] = {
        "id": str(vacancy_id),
        "name": f"Python Developer {vacancy_id}",
        "employer": {"id": "10", "name": "ACME"},
        "salary": {"from": 150000, "to": 250000, "currency": "RUR", "gross": False},
        "area": {"id": "1", "name": "Москва"},
        "experience": {"id": "between1And3", "name": "От 1 года до 3 лет"},
        "employment": {"id": "full", "name": "Полная занятость"},
        "schedule": {"id": "remote", "name": "Удаленная работа"},
        "work_format": [{"id": "REMOTE", "name": "Удалённо"}],
        "published_at": "2026-10-15T10:30:00+0300",
        "alternate_url": f"https://hh.ru/vacancy/{vacancy_id}",
        "url": f"https://api.hh.ru/vacancies/{vacancy_id}",
    }
    item.update(overrides)
    return item


class FakeHH:
    """In-memory /vacancies endpoint backed by `found` results.

    Records every request and answers 400 for pages beyond HH's 2000-result depth,
    like the real API, so tests notice if the client asks for them.
    """

    def __init__(self, found: int, *, fail_on_page: int | None = None) -> None:
        self.found = found
        self.fail_on_page = fail_on_page
        self.requests: list[httpx.Request] = []

    @property
    def pages_requested(self) -> list[int]:
        return [int(request.url.params["page"]) for request in self.requests]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        page = int(request.url.params["page"])
        per_page = int(request.url.params["per_page"])
        if page == self.fail_on_page:
            return httpx.Response(503, json={"errors": [{"type": "unavailable"}]})
        if (page + 1) * per_page > 2000:
            return httpx.Response(400, json={"errors": [{"type": "bad_argument"}]})

        available = min(self.found, 2000)
        start = page * per_page
        items = [make_raw_item(i) for i in range(start, min(start + per_page, available))]
        return httpx.Response(
            200,
            json={
                "found": self.found,
                "page": page,
                "pages": math.ceil(available / per_page),
                "per_page": per_page,
                "items": items,
            },
        )

