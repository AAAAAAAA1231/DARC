import logging
import sys

from backend.core.logging import setup_logging


def test_setup_logging_survives_missing_stdio(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    logging.getLogger("cami").handlers.clear()
    log = setup_logging()
    log.info("windowed_exe_must_not_crash_on_log")
    assert log.handlers
