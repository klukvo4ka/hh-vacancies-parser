# HH Vacancies Parser

A Python command-line tool that searches vacancies through the official [HeadHunter API](https://api.hh.ru) and exports the results to a formatted Excel workbook.

```bash
python -m src.main "Python developer"
# -> output/vacancies.xlsx
```

## Features

- Vacancy search through the official HeadHunter API (`GET /vacancies`)
- Asynchronous HTTP client built on `httpx`
- Sequential pagination with a configurable result limit
- Normalization of raw API items into a typed `Vacancy` model, tolerant of missing or malformed fields
- Readable salary text, e.g. `150 000–250 000 ₽, на руки`, alongside the raw numeric values
- Removal of duplicate vacancies before export
- Excel export with `openpyxl`:
  - numeric salary columns that sort and filter correctly
  - clickable vacancy links
  - styled header, frozen header row and filters
  - fixed, readable column widths
  - protection against formula injection from API text
- Safe output file names: files are always written inside `output/`
- Clear error messages and exit codes for API, network and file errors

## Tech Stack

- Python 3.12+
- [httpx](https://www.python-httpx.org/) — async HTTP client
- [openpyxl](https://openpyxl.readthedocs.io/) — Excel workbook generation
- `asyncio`, `argparse` from the standard library
- [HeadHunter API](https://api.hh.ru) — public vacancy search

## Installation

```bash
git clone https://github.com/klukvo4ka/hh-vacancies-parser.git
cd hh-vacancies-parser

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the virtual environment with `.venv\Scripts\activate`.

No API key or token is configured; the tool uses anonymous public vacancy search (see [HeadHunter API Notes](#headhunter-api-notes)).

## Usage

```bash
python -m src.main "Python developer"
```

With the defaults this loads up to 200 vacancies, 100 per request, and saves `output/vacancies.xlsx`.

More examples:

```bash
python -m src.main "Data analyst" --max 300
python -m src.main "Backend developer" --per-page 50
python -m src.main "Python developer" --output python_jobs.xlsx
python -m src.main "Data engineer" \
  --max 500 \
  --per-page 100 \
  --output data_engineer.xlsx
```

Run `python -m src.main --help` for the full option list.

### Options

| Argument | Description | Default |
|---|---|---|
| `query` | Vacancy search text | required |
| `--max N` | Maximum number of vacancies to load | `200` |
| `--per-page N` | Vacancies per API request (1–100) | `100` |
| `--output FILE` | Output Excel file name | `vacancies.xlsx` |

`--output` accepts a plain file name only. Files are always written inside `output/`; directories, absolute paths and `..` are rejected. `.xlsx` is added when no extension is given, and other extensions are rejected.

### Example output

Illustrative numbers, not a real search result:

```text
Query: Python developer
Loaded: 200 vacancies
Parsed: 200 vacancies
Unique: 194 vacancies
Removed duplicates: 6
Saved to: /.../output/vacancies.xlsx
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success, including a search with no results |
| `1` | Runtime error: HH API, network or Excel save failure |
| `2` | Invalid command-line usage |
| `130` | Interrupted by the user |

Expected runtime errors are printed to stderr as a short `Error: ...` message without a traceback. If any page fails to load, no workbook is written.

## Excel Output

The workbook has one sheet, `Vacancies`, with these columns:

| Column | Content |
|---|---|
| Vacancy | Vacancy title |
| Company | Employer name |
| Salary From | Lower salary bound (number) |
| Salary To | Upper salary bound (number) |
| Currency | Currency code as returned by HH, e.g. `RUR`, `USD` |
| Salary | Readable salary text, e.g. `от 120 000 ₽, до вычета налогов` |
| Gross | `Да` if the salary is before tax, `Нет` if after tax, blank if unknown |
| City | Vacancy area |
| Experience | Required experience |
| Employment | Employment type |
| Work Format | Work format, e.g. remote or hybrid |
| Published At | Publication timestamp as returned by HH |
| Link | Clickable link to the vacancy on hh.ru |

`Salary From` and `Salary To` stay numeric cells, so they can be sorted, filtered and used in formulas. Missing values are left blank rather than written as zero. Missing text fields are shown as `Не указано`, and a missing salary as `Не указана`.

<!--
## Demo

![Excel export example](docs/screenshots/excel-export.png)
-->

## Processing Flow

```text
CLI query
→ HH API requests (one page at a time)
→ raw JSON parsing into Vacancy objects
→ salary normalization
→ deduplication
→ Excel export
```

### Deduplication

- A non-empty HH vacancy ID is authoritative: records with the same ID are duplicates, records with different IDs are not.
- The first occurrence is kept; records are never merged.
- Records without an ID are compared by exact title, company and link, ignoring case and surrounding whitespace. Records with only placeholder values are never treated as duplicates.
- No fuzzy matching is performed.

## Project Structure

```text
hh-vacancies-parser/
├── docs/
│   └── screenshots/
│       └── .gitkeep
├── output/
│   └── .gitkeep
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   └── client.py          # async HH API client and pagination
│   ├── exporters/
│   │   ├── __init__.py
│   │   └── excel.py           # workbook export and formatting
│   ├── models/
│   │   ├── __init__.py
│   │   ├── deduplication.py   # duplicate removal
│   │   ├── parser.py          # raw JSON -> Vacancy
│   │   ├── salary.py          # salary text formatting
│   │   └── vacancy.py         # Vacancy dataclass
│   ├── __init__.py
│   ├── config.py              # API and output constants
│   └── main.py                # CLI entry point
├── tests/                     # pytest suite (offline, mocked HTTP)
│   ├── __init__.py
│   ├── helpers.py
│   ├── test_client.py
│   ├── test_deduplication.py
│   ├── test_excel.py
│   ├── test_main.py
│   ├── test_parser.py
│   └── test_salary.py
├── .gitignore
├── pytest.ini
├── README.md
├── requirements-dev.txt
└── requirements.txt
```

The API client only handles HTTP and returns raw dictionaries; parsing, deduplication and export live in separate modules.

## HeadHunter API Notes

- Search pages are zero-based (`page=0` is the first page).
- Vacancy search returns at most 100 items per page.
- Search depth is limited to 2000 results per query. The tool never requests pages beyond this limit, so `--max` values above 2000 load at most 2000 vacancies.
- Results change over time as vacancies are published and closed, so repeated runs can differ.
- Requests send a project-specific `User-Agent`, as HH requires.
- HeadHunter's documentation notes that anonymous vacancy search (without an authorization token) may require a captcha after the first request, and HH may apply other access or anti-abuse checks to anonymous traffic. This tool does not handle captchas or authorization.

During development, live requests from the development network returned HTTP 403, so functional validation was performed with mocked API responses.

## Testing

The test suite uses `pytest` and runs fully offline: HTTP calls go through `httpx.MockTransport`, and workbooks are written to temporary directories and reopened with `openpyxl`.

```bash
pip install -r requirements-dev.txt
pytest
```

It covers:

- API request construction, error handling and pagination limits
- parsing of missing and malformed fields
- salary formatting
- deduplication rules
- Excel content, styling, hyperlinks and empty exports
- CLI argument validation, output messages and exit codes

Live API access from the development network was restricted, so behaviour against the real HeadHunter API is covered by mocked responses rather than live requests.

## Status

The core functionality is complete. Possible next steps include example screenshots.
