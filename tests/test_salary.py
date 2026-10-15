import pytest

from src.models import format_salary
from src.models.salary import format_amount, format_currency, format_tax_label
from tests.helpers import make_vacancy


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("RUR", "₽"),
        ("RUB", "₽"),
        ("USD", "$"),
        ("EUR", "€"),
        ("KZT", "₸"),
        ("BYN", "Br"),
        ("UZS", "сум"),
        (" rur ", "₽"),
        ("ABC", "ABC"),
        (None, ""),
        ("", ""),
        ("   ", ""),
    ],
)
def test_format_currency(code: str | None, expected: str) -> None:
    assert format_currency(code) == expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [(0, "0"), (1, "1"), (999, "999"), (1000, "1 000"), (150000, "150 000"), (2500000, "2 500 000")],
)
def test_format_amount_groups_thousands_with_spaces(amount: int, expected: str) -> None:
    assert format_amount(amount) == expected


@pytest.mark.parametrize("amount", [1.5, True, "100"])
def test_format_amount_rejects_non_integers(amount: object) -> None:
    with pytest.raises(TypeError):
        format_amount(amount)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("gross", "expected"),
    [(True, "до вычета налогов"), (False, "на руки"), (None, "")],
)
def test_format_tax_label(gross: bool | None, expected: str) -> None:
    assert format_tax_label(gross) == expected


@pytest.mark.parametrize(
    ("salary_from", "salary_to", "currency", "gross", "expected"),
    [
        (150000, 250000, "RUR", False, "150 000–250 000 ₽, на руки"),
        (150000, None, "RUR", True, "от 150 000 ₽, до вычета налогов"),
        (None, 200000, "RUR", False, "до 200 000 ₽, на руки"),
        (180000, 180000, "RUR", None, "180 000 ₽"),
        (150000, 250000, None, None, "150 000–250 000"),
        (150000, None, "ABC", None, "от 150 000 ABC"),
        (150000, None, "   ", False, "от 150 000, на руки"),
        (0, 0, "RUR", None, "0 ₽"),
        (0, 1000, "RUR", None, "0–1 000 ₽"),
        (None, None, "RUR", False, "Не указана"),
        (None, None, None, None, "Не указана"),
    ],
)
def test_format_salary(
    salary_from: int | None, salary_to: int | None, currency: str | None, gross: bool | None, expected: str
) -> None:
    assert format_salary(salary_from, salary_to, currency, gross) == expected


def test_vacancy_salary_text_uses_raw_fields() -> None:
    vacancy = make_vacancy(salary_from=120000, salary_to=None, salary_currency="RUR", salary_gross=True)
    assert vacancy.salary_text == "от 120 000 ₽, до вычета налогов"
    assert vacancy.salary_from == 120000 and vacancy.salary_currency == "RUR"
