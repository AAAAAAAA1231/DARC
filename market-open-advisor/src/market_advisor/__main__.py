from __future__ import annotations

import os
import sys
import traceback


def _crash_log_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "openadvisor-crash.log")


def _excepthook(exc_type, exc, tb) -> None:
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        with open(_crash_log_path(), "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        pass
    sys.__excepthook__(exc_type, exc, tb)


def main() -> int:
    sys.excepthook = _excepthook
    from market_advisor.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
