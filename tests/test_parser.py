import copy

import pytest

from src.models import Vacancy, parse_vacancies, parse_vacancy
from tests.helpers import NOT_SPECIFIED, make_raw_item


def test_complete_item_maps_every_field() -> None:
    vacancy = parse_vacancy(make_raw_item(123456, some_future_field={"x": 1}))

    assert vacancy == Vacancy(
        id="123456",
        name="Python Developer 123456",
        company="ACME",
        salary_from=150000,
        salary_to=250000,
        salary_currency="RUR",
        salary_gross=False,
        area="Москва",
        experience="От 1 года до 3 лет",
        employment="Полная занятость",
        work_format="Удалённо",
        published_at="2026-10-15T10:30:00+0300",
        url="https://hh.ru/vacancy/123456",
    )


def test_url_is_the_public_page_not_the_api_link() -> None:
    assert parse_vacancy(make_raw_item(7)).url == "https://hh.ru/vacancy/7"


@pytest.mark.parametrize("employer", [None, {}, {"name": None}, {"name": "  "}, "ACME", ["ACME"]])
def test_unusable_employer_falls_back_to_placeholder(employer: object) -> None:
    assert parse_vacancy(make_raw_item(employer=employer)).company == NOT_SPECIFIED


@pytest.mark.parametrize("field", ["area", "experience", "employment"])
def test_missing_nested_name_falls_back_to_placeholder(field: str) -> None:
    item = make_raw_item()
    del item[field]
    assert getattr(parse_vacancy(item), field) == NOT_SPECIFIED


def test_missing_scalar_fields_use_fallbacks() -> None:
    item = make_raw_item()
    for key in ("id", "name", "published_at", "alternate_url"):
        del item[key]

    vacancy = parse_vacancy(item)

    assert (vacancy.id, vacancy.name, vacancy.published_at, vacancy.url) == ("", NOT_SPECIFIED, "", "")


@pytest.mark.parametrize("salary", [None, {}, [1, 2], "150000"])
def test_absent_salary_becomes_none_not_zero(salary: object) -> None:
    vacancy = parse_vacancy(make_raw_item(salary=salary))
    assert (vacancy.salary_from, vacancy.salary_to, vacancy.salary_currency, vacancy.salary_gross) == (
        None,
        None,
        None,
        None,
    )


def test_partial_salary_keeps_present_bound() -> None:
    vacancy = parse_vacancy(make_raw_item(salary={"from": None, "to": 300000, "currency": "USD", "gross": True}))
    assert (vacancy.salary_from, vacancy.salary_to, vacancy.salary_currency, vacancy.salary_gross) == (
        None,
        300000,
        "USD",
        True,
    )


def test_zero_salary_stays_zero() -> None:
    assert parse_vacancy(make_raw_item(salary={"from": 0})).salary_from == 0


@pytest.mark.parametrize("value", ["150000", True, False, 123.4])
def test_non_integer_salary_bounds_are_rejected(value: object) -> None:
    vacancy = parse_vacancy(make_raw_item(salary={"from": value, "to": value}))
    assert vacancy.salary_from is None and vacancy.salary_to is None


@pytest.mark.parametrize("value", ["false", "true", 1, 0])
def test_gross_accepts_only_real_booleans(value: object) -> None:
    assert parse_vacancy(make_raw_item(salary={"gross": value})).salary_gross is None


def test_integer_id_is_stringified_but_bool_is_not() -> None:
    assert parse_vacancy(make_raw_item(id=42)).id == "42"
    assert parse_vacancy(make_raw_item(id=True)).id == ""


def test_multiple_work_formats_are_joined_in_api_order_without_duplicates() -> None:
    formats = [
        {"id": "REMOTE", "name": "Удалённо"},
        {"id": "ON_SITE", "name": "На месте работодателя"},
        {"id": "REMOTE_AGAIN", "name": "Удалённо"},
        {"id": "EMPTY", "name": ""},
        None,
    ]
    assert parse_vacancy(make_raw_item(work_format=formats)).work_format == "Удалённо, На месте работодателя"


@pytest.mark.parametrize("work_format", [[], "REMOTE", [{"name": None}]])
def test_unusable_work_format_falls_back_to_schedule(work_format: object) -> None:
    assert parse_vacancy(make_raw_item(work_format=work_format)).work_format == "Удаленная работа"


def test_work_format_without_schedule_uses_placeholder() -> None:
    item = make_raw_item()
    del item["work_format"], item["schedule"]
    assert parse_vacancy(item).work_format == NOT_SPECIFIED


def test_empty_and_malformed_items_do_not_crash() -> None:
    malformed = {"id": None, "name": 123, "salary": [1], "area": ["Москва"], "published_at": 20261010}
    assert parse_vacancy({}).name == NOT_SPECIFIED
    assert parse_vacancy(malformed).area == NOT_SPECIFIED


def test_parse_vacancies_preserves_order_and_accepts_generators() -> None:
    items = [make_raw_item(i) for i in range(5)]
    assert [v.id for v in parse_vacancies(item for item in items)] == ["0", "1", "2", "3", "4"]
    assert parse_vacancies([]) == []


def test_source_items_are_not_mutated() -> None:
    items = [make_raw_item(1), make_raw_item(2, salary=None, employer=None)]
    snapshot = copy.deepcopy(items)
    parse_vacancies(items)
    assert items == snapshot
