from collections.abc import Callable, Iterable
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE, Cell

from src.models import Vacancy

SHEET_TITLE = "Vacancies"

CellValue = str | int | None

COLUMNS: tuple[tuple[str, Callable[[Vacancy], CellValue]], ...] = (
    ("Vacancy", lambda v: v.name),
    ("Company", lambda v: v.company),
    ("Salary From", lambda v: v.salary_from),
    ("Salary To", lambda v: v.salary_to),
    ("Currency", lambda v: v.salary_currency),
    ("Salary", lambda v: v.salary_text),
    ("Gross", lambda v: _format_gross(v.salary_gross)),
    ("City", lambda v: v.area),
    ("Experience", lambda v: v.experience),
    ("Employment", lambda v: v.employment),
    ("Work Format", lambda v: v.work_format),
    ("Published At", lambda v: v.published_at),
    ("Link", lambda v: v.url),
)
HEADERS = tuple(header for header, _ in COLUMNS)
LINK_COLUMN = HEADERS.index("Link") + 1


def export_vacancies_to_excel(vacancies: Iterable[Vacancy], output_path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SHEET_TITLE
    sheet.append(HEADERS)

    for row, vacancy in enumerate(vacancies, start=2):
        for column, (_, get_value) in enumerate(COLUMNS, start=1):
            _write_cell(sheet.cell(row=row, column=column), get_value(vacancy))

        link = sheet.cell(row=row, column=LINK_COLUMN)
        if link.value:
            link.hyperlink = link.value
            link.style = "Hyperlink"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path


def _write_cell(cell: Cell, value: CellValue) -> None:
    if isinstance(value, str):
        value = ILLEGAL_CHARACTERS_RE.sub("", value) or None
    cell.value = value
    # API text starting with "=" must stay text, not become a formula.
    if cell.data_type == "f":
        cell.data_type = "s"


def _format_gross(gross: bool | None) -> str | None:
    if gross is None:
        return None
    return "Да" if gross else "Нет"
