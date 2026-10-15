from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE, Cell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from src.models import Vacancy

SHEET_TITLE = "Vacancies"

HEADER_FILL_COLOR = "1F4E78"
HEADER_FONT_COLOR = "FFFFFF"
BORDER_COLOR = "D9D9D9"
HEADER_ROW_HEIGHT = 28
SALARY_NUMBER_FORMAT = "#,##0"

CellValue = str | int | None


class Kind(Enum):
    TEXT = "text"
    NUMBER = "number"
    CODE = "code"


@dataclass(frozen=True)
class Column:
    header: str
    width: int
    kind: Kind
    get_value: Callable[[Vacancy], CellValue]


COLUMNS: tuple[Column, ...] = (
    Column("Vacancy", 32, Kind.TEXT, lambda v: v.name),
    Column("Company", 28, Kind.TEXT, lambda v: v.company),
    Column("Salary From", 14, Kind.NUMBER, lambda v: v.salary_from),
    Column("Salary To", 14, Kind.NUMBER, lambda v: v.salary_to),
    Column("Currency", 10, Kind.CODE, lambda v: v.salary_currency),
    Column("Salary", 32, Kind.TEXT, lambda v: v.salary_text),
    Column("Gross", 12, Kind.CODE, lambda v: _format_gross(v.salary_gross)),
    Column("City", 20, Kind.TEXT, lambda v: v.area),
    Column("Experience", 24, Kind.TEXT, lambda v: v.experience),
    Column("Employment", 22, Kind.TEXT, lambda v: v.employment),
    Column("Work Format", 28, Kind.TEXT, lambda v: v.work_format),
    Column("Published At", 24, Kind.TEXT, lambda v: v.published_at),
    Column("Link", 45, Kind.TEXT, lambda v: v.url),
)
HEADERS = tuple(column.header for column in COLUMNS)
LINK_COLUMN = HEADERS.index("Link") + 1

_THIN_SIDE = Side(style="thin", color=BORDER_COLOR)
_BORDER = Border(left=_THIN_SIDE, right=_THIN_SIDE, top=_THIN_SIDE, bottom=_THIN_SIDE)
_HEADER_FONT = Font(bold=True, color=HEADER_FONT_COLOR)
_HEADER_FILL = PatternFill(fill_type="solid", start_color=HEADER_FILL_COLOR, end_color=HEADER_FILL_COLOR)
_HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
_DATA_ALIGNMENTS = {
    Kind.TEXT: Alignment(horizontal="left", vertical="top", wrap_text=True),
    Kind.NUMBER: Alignment(horizontal="right", vertical="top"),
    Kind.CODE: Alignment(horizontal="center", vertical="top"),
}


def export_vacancies_to_excel(vacancies: Iterable[Vacancy], output_path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SHEET_TITLE
    sheet.append(HEADERS)

    for row, vacancy in enumerate(vacancies, start=2):
        for index, column in enumerate(COLUMNS, start=1):
            _write_cell(sheet.cell(row=row, column=index), column.get_value(vacancy))

        link = sheet.cell(row=row, column=LINK_COLUMN)
        if link.value:
            link.hyperlink = link.value
            link.style = "Hyperlink"
            # openpyxl's built-in Hyperlink style has the link color but no underline.
            link.font = Font(color=link.font.color, underline="single")

    _style_header(sheet)
    _style_data_rows(sheet)
    _configure_sheet(sheet)

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


def _style_header(sheet: Worksheet) -> None:
    for cell in sheet[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGNMENT
        cell.border = _BORDER
    sheet.row_dimensions[1].height = HEADER_ROW_HEIGHT


def _style_data_rows(sheet: Worksheet) -> None:
    for row in sheet.iter_rows(min_row=2, max_col=len(COLUMNS)):
        for cell, column in zip(row, COLUMNS):
            cell.alignment = _DATA_ALIGNMENTS[column.kind]
            cell.border = _BORDER
            if column.kind is Kind.NUMBER:
                cell.number_format = SALARY_NUMBER_FORMAT


def _configure_sheet(sheet: Worksheet) -> None:
    for index, column in enumerate(COLUMNS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = column.width
    last_column = get_column_letter(len(COLUMNS))
    sheet.auto_filter.ref = f"A1:{last_column}{sheet.max_row}"
    sheet.freeze_panes = "A2"
    sheet.sheet_view.showGridLines = False
