CURRENCY_SYMBOLS = {
    "RUR": "₽",
    "RUB": "₽",
    "USD": "$",
    "EUR": "€",
    "KZT": "₸",
    "BYR": "Br",
    "BYN": "Br",
    "UZS": "сум",
    "GEL": "₾",
    "KGS": "сом",
    "AZN": "₼",
}

SALARY_NOT_SPECIFIED = "Не указана"


def format_currency(code: str | None) -> str:
    """Return a display symbol for known codes, the code itself otherwise."""
    if code is None or not code.strip():
        return ""
    code = code.strip()
    return CURRENCY_SYMBOLS.get(code.upper(), code)


def format_amount(amount: int) -> str:
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError(f"Salary amount must be int, got {type(amount).__name__}")
    return f"{amount:,}".replace(",", " ")


def format_tax_label(gross: bool | None) -> str:
    if gross is True:
        return "до вычета налогов"
    if gross is False:
        return "на руки"
    return ""


def format_salary(
    salary_from: int | None,
    salary_to: int | None,
    currency: str | None,
    gross: bool | None,
) -> str:
    amount = _format_range(salary_from, salary_to)
    if not amount:
        return SALARY_NOT_SPECIFIED

    text = " ".join(part for part in (amount, format_currency(currency)) if part)
    tax_label = format_tax_label(gross)
    return f"{text}, {tax_label}" if tax_label else text


def _format_range(salary_from: int | None, salary_to: int | None) -> str:
    if salary_from is not None and salary_to is not None:
        if salary_from == salary_to:
            return format_amount(salary_from)
        return f"{format_amount(salary_from)}–{format_amount(salary_to)}"
    if salary_from is not None:
        return f"от {format_amount(salary_from)}"
    if salary_to is not None:
        return f"до {format_amount(salary_to)}"
    return ""
