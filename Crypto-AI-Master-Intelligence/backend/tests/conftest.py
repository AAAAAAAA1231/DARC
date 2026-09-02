import os
from pathlib import Path

TEST_DB = Path("/tmp/cami-test.db")
os.environ.setdefault("CAMI_SCHEDULER_ENABLED", "false")
os.environ.setdefault("CAMI_DATABASE_URL", f"sqlite:///{TEST_DB}")

for suffix in ("", "-wal", "-shm"):
    path = Path(str(TEST_DB) + suffix) if suffix else TEST_DB
    if path.exists():
        path.unlink()

from backend.database.session import init_db  # noqa: E402


def pytest_configure() -> None:
    init_db()
