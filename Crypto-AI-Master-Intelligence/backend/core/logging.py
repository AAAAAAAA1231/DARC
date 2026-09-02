"""Structured logging with secret redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.config import PROJECT_ROOT, get_settings

_SECRET_PATTERN = re.compile(
    r"(api[_-]?key|api[_-]?secret|token|password|private[_-]?key|seed|mnemonic|authorization)",
    re.IGNORECASE,
)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        return _SECRET_PATTERN.sub("[REDACTED_KEY]", message)


def setup_logging() -> logging.Logger:
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    if not log_dir.is_absolute():
        log_dir = PROJECT_ROOT / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("cami")
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    formatter = RedactingFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    file_handler = logging.FileHandler(log_dir / "cami.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"cami.{name}")


def log_event(logger: logging.Logger, level: str, event: str, **payload: Any) -> None:
    body = {
        "event": event,
        "ts": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    safe = json.dumps(body, default=str)
    getattr(logger, level.lower(), logger.info)(safe)
