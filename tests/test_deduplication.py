import pytest

from src.models import deduplicate_vacancies
from tests.helpers import NOT_SPECIFIED, make_vacancy


def ids(vacancies: list) -> list[str]:
    return [vacancy.id for vacancy in vacancies]


def test_empty_input() -> None:
    assert deduplicate_vacancies([]) == []


def test_first_occurrence_wins_and_order_is_kept() -> None:
    vacancies = [make_vacancy(id=i) for i in "12132"]
    assert ids(deduplicate_vacancies(vacancies)) == ["1", "2", "3"]


def test_same_id_is_duplicate_even_when_other_fields_differ() -> None:
    first = make_vacancy(id="7", name="First", company="A", url="u1")
    later = make_vacancy(id="7", name="Later", company="B", url="u2")

    result = deduplicate_vacancies([first, later])

    assert len(result) == 1 and result[0] is first


def test_different_ids_are_kept_even_when_identical_otherwise() -> None:
    assert ids(deduplicate_vacancies([make_vacancy(id="111"), make_vacancy(id="222")])) == ["111", "222"]


def test_id_record_never_matches_record_without_id() -> None:
    assert len(deduplicate_vacancies([make_vacancy(id="5"), make_vacancy(id="")])) == 2


@pytest.mark.parametrize(
    "other",
    [
        {},
        {"name": "  python developer ", "company": "acme ", "url": "HTTPS://HH.RU/VACANCY/1"},
    ],
)
def test_missing_id_falls_back_to_normalized_name_company_url(other: dict) -> None:
    vacancies = [make_vacancy(id=""), make_vacancy(id="", **other)]
    assert len(deduplicate_vacancies(vacancies)) == 1


@pytest.mark.parametrize(
    "other",
    [
        {"name": "Java Developer"},
        {"company": "Other Co"},
        {"url": "https://hh.ru/vacancy/2"},
        {"name": "Python Developer!"},
    ],
)
def test_missing_id_with_any_differing_field_is_kept(other: dict) -> None:
    vacancies = [make_vacancy(id=""), make_vacancy(id="", **other)]
    assert len(deduplicate_vacancies(vacancies)) == 2


def test_placeholder_only_records_are_never_collapsed() -> None:
    junk = [make_vacancy(id="", name=NOT_SPECIFIED, company=" не указано ", url="") for _ in range(3)]
    blank = [make_vacancy(id="", name="", company="", url="") for _ in range(2)]
    assert len(deduplicate_vacancies(junk + blank)) == 5


@pytest.mark.parametrize(
    "fields",
    [
        {"company": NOT_SPECIFIED, "url": ""},
        {"name": NOT_SPECIFIED, "url": ""},
        {"name": NOT_SPECIFIED, "company": NOT_SPECIFIED, "url": "https://hh.ru/vacancy/9"},
    ],
)
def test_one_meaningful_fallback_field_is_enough(fields: dict) -> None:
    vacancies = [make_vacancy(id="", **fields), make_vacancy(id="", **fields)]
    assert len(deduplicate_vacancies(vacancies)) == 1


def test_accepts_generators_and_returns_original_objects() -> None:
    vacancies = [make_vacancy(id=i) for i in "313"]
    original = list(vacancies)

    result = deduplicate_vacancies(vacancy for vacancy in vacancies)

    assert isinstance(result, list)
    assert result[0] is vacancies[0] and result[1] is vacancies[1]
    assert vacancies == original
