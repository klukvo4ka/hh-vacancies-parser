import pytest

import src.main


@pytest.fixture(autouse=True)
def anonymous_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests independent of credentials in the developer's environment or .env."""
    for name in ("HH_ACCESS_TOKEN", "HH_CLIENT_ID", "HH_CLIENT_SECRET"):
        monkeypatch.setattr(src.main, name, None)
        monkeypatch.delenv(name, raising=False)
