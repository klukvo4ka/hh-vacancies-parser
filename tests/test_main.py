import errno
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from openpyxl import load_workbook

import src.main
from src.api.client import HHApiClient
from tests.helpers import FakeHH, make_raw_item

Handler = Callable[[httpx.Request], httpx.Response]


@dataclass
class Result:
    code: int
    out: str
    err: str


@pytest.fixture
def output_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "output"
    monkeypatch.setattr(src.main, "OUTPUT_DIR", directory)
    return directory


@pytest.fixture
def run_cli(output_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """Run main() against a fake HH handler and capture exit code and streams."""

    def run(argv: list[str], handler: Handler) -> Result:
        monkeypatch.setattr(
            src.main, "HHApiClient", lambda **kwargs: HHApiClient(transport=httpx.MockTransport(handler), **kwargs)
        )
        try:
            code = src.main.main(argv)
        except SystemExit as exc:
            code = exc.code
        captured = capsys.readouterr()
        return Result(code, captured.out, captured.err)

    return run


class TestArgumentParsing:
    def test_defaults(self) -> None:
        args = src.main.parse_args(["  Python developer  "])
        assert (args.query, args.max_vacancies, args.per_page, args.output) == (
            "Python developer",
            200,
            100,
            "vacancies.xlsx",
        )

    def test_explicit_values(self) -> None:
        args = src.main.parse_args(["Data analyst", "--max", "300", "--per-page", "50", "--output", "jobs"])
        assert (args.max_vacancies, args.per_page, args.output) == (300, 50, "jobs.xlsx")

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("jobs.xlsx", "jobs.xlsx"), ("jobs", "jobs.xlsx"), ("Jobs.XLSX", "Jobs.XLSX"), (" hh-results.xlsx ", "hh-results.xlsx")],
    )
    def test_valid_output_names(self, value: str, expected: str) -> None:
        assert src.main.parse_args(["q", "--output", value]).output == expected

    @pytest.mark.parametrize(
        ("argv", "message"),
        [
            ([], "required: query"),
            (["   "], "search query must not be empty"),
            (["q", "--max", "0"], "--max: must be >= 1"),
            (["q", "--max=-5"], "--max: must be >= 1"),
            (["q", "--max", "abc"], "--max: expected an integer"),
            (["q", "--per-page", "0"], "--per-page: must be between 1 and 100"),
            (["q", "--per-page", "101"], "--per-page: must be between 1 and 100"),
            (["q", "--per-page", "1.5"], "--per-page: expected an integer"),
            (["q", "--output", "report.csv"], ".xlsx extension"),
            (["q", "--output", "../jobs.xlsx"], "without directories"),
            (["q", "--output", "/tmp/jobs.xlsx"], "without directories"),
            (["q", "--output", "sub/jobs.xlsx"], "without directories"),
            (["q", "--output", "..\\jobs.xlsx"], "without directories"),
            (["q", "--output", "C:jobs.xlsx"], "without directories"),
            (["q", "--output", "   "], "must not be empty"),
            (["q", "--output", "."], "--output"),
            (["q", "--output", ".."], "--output"),
            (["q", "--output", ".xlsx"], "must not start with '.'"),
        ],
    )
    def test_invalid_usage_exits_2_without_requests(self, run_cli, argv: list[str], message: str) -> None:
        fake = FakeHH(10)
        result = run_cli(argv, fake)
        assert result.code == 2
        assert "usage:" in result.err and message in result.err
        assert result.out == ""
        assert fake.requests == []

    def test_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as excinfo:
            src.main.parse_args(["--help"])
        out = capsys.readouterr().out
        assert excinfo.value.code == 0
        assert "Search HeadHunter vacancies and export them to Excel." in out
        for option in ("query", "--max", "--per-page", "--output"):
            assert option in out


class TestSuccessfulRun:
    def test_summary_and_workbook(self, run_cli, output_dir: Path) -> None:
        fake = FakeHH(5000)
        result = run_cli(["  Data analyst ", "--max", "150", "--per-page", "50", "--output", "analyst"], fake)

        path = output_dir / "analyst.xlsx"
        assert result.code == 0 and result.err == ""
        assert result.out.splitlines() == [
            "Query: Data analyst",
            "Loaded: 150 vacancies",
            "Parsed: 150 vacancies",
            "Unique: 150 vacancies",
            "Removed duplicates: 0",
            f"Saved to: {path}",
        ]
        assert [request.url.params["per_page"] for request in fake.requests] == ["50", "50", "50"]
        assert {request.url.params["text"] for request in fake.requests} == {"Data analyst"}
        assert list(output_dir.iterdir()) == [path]
        assert load_workbook(path).active.max_row == 151

    def test_duplicates_are_removed_before_export(self, run_cli, output_dir: Path) -> None:
        pages = {0: [make_raw_item(1), make_raw_item(2), make_raw_item(3)], 1: [make_raw_item(3, name="Again"), make_raw_item(4)]}

        def handler(request: httpx.Request) -> httpx.Response:
            page = int(request.url.params["page"])
            return httpx.Response(200, json={"found": 5, "page": page, "pages": 2, "per_page": 3, "items": pages[page]})

        result = run_cli(["Python", "--per-page", "3"], handler)

        assert result.code == 0
        assert "Unique: 4 vacancies" in result.out and "Removed duplicates: 1" in result.out
        sheet = load_workbook(output_dir / "vacancies.xlsx").active
        assert sheet.max_row == 5
        assert sheet["A4"].value == "Python Developer 3"

    def test_no_results_still_writes_header_only_workbook(self, run_cli, output_dir: Path) -> None:
        result = run_cli(["impossible query"], FakeHH(0))
        assert result.code == 0 and result.err == ""
        assert "Unique: 0 vacancies" in result.out and "Removed duplicates: 0" in result.out
        assert load_workbook(output_dir / "vacancies.xlsx").active.max_row == 1


class TestRuntimeErrors:
    @pytest.mark.parametrize(
        ("handler", "message"),
        [
            (
                lambda r: httpx.Response(403, json={"errors": [{"type": "forbidden"}]}),
                "Error: HH API returned HTTP 403 for /vacancies (forbidden). Anonymous access may be restricted; "
                "configure HH_ACCESS_TOKEN or HH_CLIENT_ID/HH_CLIENT_SECRET",
            ),
            (lambda r: httpx.Response(500, text="x" * 5000), "Error: HH API returned HTTP 500 for /vacancies"),
            (lambda r: httpx.Response(200, text="<html>"), "Error: HH API returned invalid JSON for /vacancies"),
        ],
        ids=["403", "500", "bad-json"],
    )
    def test_api_errors_exit_1_on_stderr(self, run_cli, output_dir: Path, handler: Handler, message: str) -> None:
        result = run_cli(["Python"], handler)
        assert result.code == 1
        assert result.out == ""
        assert result.err == message + "\n"
        assert not output_dir.exists()

    def test_network_error(self, run_cli) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        result = run_cli(["Python"], handler)
        assert (result.code, result.err) == (1, "Error: Network error while requesting /vacancies: refused\n")

    def test_failure_mid_pagination_writes_nothing(self, run_cli, output_dir: Path) -> None:
        fake = FakeHH(5000, fail_on_page=1)
        result = run_cli(["Python", "--max", "300"], fake)
        assert result.code == 1 and result.out == ""
        assert "HTTP 503" in result.err
        assert fake.pages_requested == [0, 1]
        assert not output_dir.exists()

    def test_save_error_exits_1(self, run_cli, monkeypatch: pytest.MonkeyPatch) -> None:
        def disk_full(vacancies, path):
            raise OSError(errno.ENOSPC, "No space left on device", str(path))

        monkeypatch.setattr(src.main, "export_vacancies_to_excel", disk_full)
        result = run_cli(["Python"], FakeHH(10))
        assert result.code == 1 and result.out == ""
        assert result.err.startswith("Error: could not save Excel file: No space left on device: ")

    def test_output_location_that_is_a_file_exits_1(self, run_cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        not_a_dir = tmp_path / "file"
        not_a_dir.write_text("x")
        monkeypatch.setattr(src.main, "OUTPUT_DIR", not_a_dir)
        result = run_cli(["Python"], FakeHH(10))
        assert result.code == 1 and "could not save Excel file" in result.err

    def test_keyboard_interrupt_exits_130(self, run_cli, monkeypatch: pytest.MonkeyPatch) -> None:
        async def interrupted(args):
            raise KeyboardInterrupt

        monkeypatch.setattr(src.main, "run", interrupted)
        result = run_cli(["Python"], FakeHH(10))
        assert (result.code, result.out, result.err) == (130, "", "Interrupted\n")

    def test_unexpected_bugs_are_not_swallowed(self, run_cli, monkeypatch: pytest.MonkeyPatch) -> None:
        def broken(items):
            raise ZeroDivisionError("bug")

        monkeypatch.setattr(src.main, "parse_vacancies", broken)
        with pytest.raises(ZeroDivisionError):
            run_cli(["Python"], FakeHH(10))


FAKE_TOKEN = "fake-access-token-for-tests"
FAKE_APP_TOKEN = "fake-application-token-for-tests"
FAKE_SECRET = "fake-client-secret-do-not-leak"


class FakeHHWithTokenEndpoint(FakeHH):
    """/vacancies plus a POST /token endpoint, sharing one request log."""

    def __init__(self, found: int, *, token_status: int = 200, vacancy_status: int | None = None) -> None:
        super().__init__(found)
        self.token_status = token_status
        self.vacancy_status = vacancy_status
        self.token_requests: list[httpx.Request] = []

    @property
    def vacancy_requests(self) -> list[httpx.Request]:
        return [request for request in self.requests if request.url.path == "/vacancies"]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            self.token_requests.append(request)
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "invalid_client"})
            return httpx.Response(200, json={"access_token": FAKE_APP_TOKEN, "token_type": "bearer"})
        if self.vacancy_status is not None:
            self.requests.append(request)
            return httpx.Response(self.vacancy_status, json={"errors": [{"type": "forbidden"}]})
        return super().__call__(request)


class TestAuthorization:
    @pytest.fixture
    def configure(self, monkeypatch: pytest.MonkeyPatch):
        """Set auth config on src.main and route the token request through the same fake transport."""

        def apply(fake: FakeHHWithTokenEndpoint, **values: str | None) -> None:
            for name, value in values.items():
                monkeypatch.setattr(src.main, name, value)
            resolve = src.main.resolve_access_token

            async def resolve_with_fake(*args):
                return await resolve(*args, transport=httpx.MockTransport(fake))

            monkeypatch.setattr(src.main, "resolve_access_token", resolve_with_fake)

        return apply

    def test_direct_access_token_skips_token_endpoint(self, run_cli, configure) -> None:
        fake = FakeHHWithTokenEndpoint(500)
        configure(fake, HH_ACCESS_TOKEN=FAKE_TOKEN)

        result = run_cli(["Python", "--max", "300"], fake)

        assert result.code == 0
        assert fake.token_requests == []
        assert {request.headers["Authorization"] for request in fake.vacancy_requests} == {f"Bearer {FAKE_TOKEN}"}

    def test_application_credentials_request_one_token_for_all_pages(self, run_cli, configure) -> None:
        fake = FakeHHWithTokenEndpoint(500)
        configure(fake, HH_CLIENT_ID="fake-client-id", HH_CLIENT_SECRET=FAKE_SECRET)

        result = run_cli(["Python", "--max", "300"], fake)

        assert result.code == 0
        assert len(fake.token_requests) == 1
        assert len(fake.vacancy_requests) == 3
        assert {request.headers["Authorization"] for request in fake.vacancy_requests} == {f"Bearer {FAKE_APP_TOKEN}"}

    def test_success_output_is_unchanged_and_token_free(self, run_cli, configure, output_dir: Path) -> None:
        fake = FakeHHWithTokenEndpoint(500)
        configure(fake, HH_CLIENT_ID="fake-client-id", HH_CLIENT_SECRET=FAKE_SECRET)

        result = run_cli(["Python", "--max", "100"], fake)

        assert result.out.splitlines()[:5] == [
            "Query: Python",
            "Loaded: 100 vacancies",
            "Parsed: 100 vacancies",
            "Unique: 100 vacancies",
            "Removed duplicates: 0",
        ]
        assert result.err == ""
        assert FAKE_APP_TOKEN not in result.out and FAKE_SECRET not in result.out

    def test_token_failure_stops_before_any_vacancy_request(self, run_cli, configure, output_dir: Path) -> None:
        fake = FakeHHWithTokenEndpoint(500, token_status=400)
        configure(fake, HH_CLIENT_ID="fake-client-id", HH_CLIENT_SECRET=FAKE_SECRET)

        result = run_cli(["Python"], fake)

        assert result.code == 1
        assert result.out == ""
        assert result.err == "Error: Failed to obtain HH application token: HTTP 400 (invalid_client)\n"
        assert "Traceback" not in result.err and FAKE_SECRET not in result.err
        assert fake.vacancy_requests == []
        assert not output_dir.exists()

    def test_half_configured_credentials_exit_1_without_requests(self, run_cli, configure) -> None:
        fake = FakeHHWithTokenEndpoint(500)
        configure(fake, HH_CLIENT_ID="fake-client-id")

        result = run_cli(["Python"], fake)

        assert result.code == 1
        assert result.err == "Error: Incomplete HH credentials: set both HH_CLIENT_ID and HH_CLIENT_SECRET\n"
        assert fake.token_requests == [] and fake.vacancy_requests == []

    def test_authenticated_403_does_not_blame_anonymous_access(self, run_cli, configure) -> None:
        fake = FakeHHWithTokenEndpoint(500, vacancy_status=403)
        configure(fake, HH_ACCESS_TOKEN=FAKE_TOKEN)

        result = run_cli(["Python"], fake)

        assert result.code == 1
        assert result.err == "Error: HH API returned HTTP 403 for /vacancies (forbidden)\n"
        assert FAKE_TOKEN not in result.err

    def test_invalid_cli_input_makes_no_token_request(self, run_cli, configure) -> None:
        fake = FakeHHWithTokenEndpoint(500)
        configure(fake, HH_CLIENT_ID="fake-client-id", HH_CLIENT_SECRET=FAKE_SECRET)

        result = run_cli(["Python", "--max", "0"], fake)

        assert result.code == 2
        assert fake.token_requests == [] and fake.vacancy_requests == []
