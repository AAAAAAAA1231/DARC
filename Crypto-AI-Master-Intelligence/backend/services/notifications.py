"""Notification bus. Channels are plugins; missing credentials disable a channel without crashing."""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.orm import Notification

logger = get_logger("notify")


class Channel(Protocol):
    name: str

    def send(self, title: str, body: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        ...


class InAppChannel:
    name = "in_app"

    def __init__(self, session: Session) -> None:
        self.session = session

    def send(self, title: str, body: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        row = Notification(kind=(payload or {}).get("kind") or "info", title=title, body=body, payload=payload, channel=self.name)
        self.session.add(row)
        return {"ok": True, "channel": self.name}


class DesktopChannel:
    name = "desktop"

    def send(self, title: str, body: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        try:
            import webview  # noqa: F401
        except Exception:
            return {"ok": False, "channel": self.name, "error": "pywebview not available for desktop toast"}
        logger.info("desktop_notify title=%s", title)
        return {"ok": True, "channel": self.name, "note": "logged; OS toast depends on desktop runtime"}


class EmailChannel:
    name = "email"

    def send(self, title: str, body: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        settings = get_settings()
        if not settings.smtp_host or not settings.smtp_user:
            return {"ok": False, "channel": self.name, "error": "missing_key", "status": "missing_key"}
        return {"ok": False, "channel": self.name, "error": "SMTP send is configured but not executed automatically in analysis-only mode"}


class TelegramChannel:
    name = "telegram"

    def send(self, title: str, body: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        settings = get_settings()
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            return {"ok": False, "channel": self.name, "error": "missing_key", "status": "missing_key"}
        return {"ok": False, "channel": self.name, "error": "Telegram provider keyed but outbound send is opt-in"}


def emit(session: Session, kind: str, title: str, body: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = {**(payload or {}), "kind": kind}
    channels: list[Channel] = [InAppChannel(session), DesktopChannel(), EmailChannel(), TelegramChannel()]
    results = []
    for ch in channels:
        try:
            results.append(ch.send(title, body, payload))
        except Exception as exc:  # noqa: BLE001
            logger.error("notify_channel_failed channel=%s err=%s", ch.name, exc)
            results.append({"ok": False, "channel": ch.name, "error": str(exc)})
    return results


def list_unread(session: Session) -> list[Notification]:
    return session.query(Notification).filter(Notification.read.is_(False)).order_by(Notification.created_at.desc()).all()
