import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path, PureWindowsPath

from src.api.client import HHApiClient, HHApiError
from src.config import HH_MAX_PER_PAGE, OUTPUT_DIR
from src.exporters import export_vacancies_to_excel
from src.models import parse_vacancies

DEFAULT_MAX_VACANCIES = 200
DEFAULT_OUTPUT_FILENAME = "vacancies.xlsx"
EXCEL_SUFFIX = ".xlsx"

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_INTERRUPTED = 130


def query_text(value: str) -> str:
    query = value.strip()
    if not query:
        raise argparse.ArgumentTypeError("search query must not be empty")
    return query


def positive_int(value: str) -> int:
    number = _parse_int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {number}")
    return number


def per_page_value(value: str) -> int:
    number = _parse_int(value)
    if not 1 <= number <= HH_MAX_PER_PAGE:
        raise argparse.ArgumentTypeError(f"must be between 1 and {HH_MAX_PER_PAGE}, got {number}")
    return number


def output_filename(value: str) -> str:
    """Accept a bare file name inside OUTPUT_DIR; add .xlsx if no extension is given."""
    name = value.strip()
    if not name:
        raise argparse.ArgumentTypeError("output file name must not be empty")
    windows_path = PureWindowsPath(name)
    if (
        "/" in name
        or "\\" in name
        or Path(name).name != name
        or Path(name).is_absolute()
        or windows_path.drive
    ):
        raise argparse.ArgumentTypeError(f"expected a file name without directories, got {value!r}")
    if name.startswith("."):
        raise argparse.ArgumentTypeError(f"output file name must not start with '.', got {value!r}")

    suffix = Path(name).suffix
    if not suffix:
        return name + EXCEL_SUFFIX
    if suffix.lower() != EXCEL_SUFFIX:
        raise argparse.ArgumentTypeError(f"output file must have {EXCEL_SUFFIX} extension, got {suffix!r}")
    return name


def _parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer, got {value!r}") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Search HeadHunter vacancies and export them to Excel.",
    )
    parser.add_argument("query", type=query_text, help='search text, e.g. "Python developer"')
    parser.add_argument(
        "--max",
        dest="max_vacancies",
        type=positive_int,
        default=DEFAULT_MAX_VACANCIES,
        metavar="N",
        help=f"maximum number of vacancies to load (default: {DEFAULT_MAX_VACANCIES})",
    )
    parser.add_argument(
        "--per-page",
        type=per_page_value,
        default=HH_MAX_PER_PAGE,
        metavar="N",
        help=f"vacancies per API request, 1-{HH_MAX_PER_PAGE} (default: {HH_MAX_PER_PAGE})",
    )
    parser.add_argument(
        "--output",
        type=output_filename,
        default=DEFAULT_OUTPUT_FILENAME,
        metavar="FILE",
        help=f"Excel file name inside output/ (default: {DEFAULT_OUTPUT_FILENAME})",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


async def run(args: argparse.Namespace) -> None:
    async with HHApiClient() as client:
        raw_items = await client.search_all_vacancies(
            args.query,
            per_page=args.per_page,
            max_vacancies=args.max_vacancies,
        )

    vacancies = parse_vacancies(raw_items)
    output_path = export_vacancies_to_excel(vacancies, OUTPUT_DIR / args.output)

    print(f"Query: {args.query}")
    print(f"Loaded: {len(raw_items)} vacancies")
    print(f"Parsed: {len(vacancies)} vacancies")
    print(f"Saved to: {output_path}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return an exit code; argparse exits with 2 on invalid usage."""
    args = parse_args(argv)
    coroutine = run(args)
    try:
        asyncio.run(coroutine)
    except HHApiError as exc:
        return _fail(str(exc))
    except OSError as exc:
        return _fail(f"could not save Excel file: {_describe_os_error(exc)}")
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED
    finally:
        coroutine.close()
    return EXIT_OK


def _fail(message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return EXIT_FAILURE


def _describe_os_error(exc: OSError) -> str:
    if exc.strerror and exc.filename:
        return f"{exc.strerror}: {exc.filename}"
    return exc.strerror or str(exc)


if __name__ == "__main__":
    raise SystemExit(main())
