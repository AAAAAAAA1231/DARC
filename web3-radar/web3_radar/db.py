from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from web3_radar.config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    item_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'watching',
    note TEXT NOT NULL DEFAULT '',
    extra TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    UNIQUE(category, item_key)
);

CREATE TABLE IF NOT EXISTS wallet_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    item_key TEXT NOT NULL,
    title TEXT NOT NULL,
    action TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    tx_hash TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cache (
    cache_key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    expires_at REAL NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def connect() -> aiosqlite.Connection:
    ensure_dirs()
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA)
    await conn.commit()
    return conn


async def upsert_mark(
    category: str,
    item_key: str,
    status: str,
    note: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conn = await connect()
    try:
        await conn.execute(
            """
            INSERT INTO marks (category, item_key, status, note, extra, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(category, item_key) DO UPDATE SET
                status=excluded.status,
                note=excluded.note,
                extra=excluded.extra,
                updated_at=excluded.updated_at
            """,
            (category, item_key, status, note, json.dumps(extra or {}, ensure_ascii=False), _now()),
        )
        await conn.commit()
    finally:
        await conn.close()
    return {"category": category, "item_key": item_key, "status": status, "note": note, "extra": extra or {}}


async def list_marks(category: str | None = None) -> list[dict[str, Any]]:
    conn = await connect()
    try:
        if category:
            cur = await conn.execute("SELECT * FROM marks WHERE category=? ORDER BY updated_at DESC", (category,))
        else:
            cur = await conn.execute("SELECT * FROM marks ORDER BY updated_at DESC")
        rows = await cur.fetchall()
        return [_row_to_mark(r) for r in rows]
    finally:
        await conn.close()


async def marks_map(category: str) -> dict[str, dict[str, Any]]:
    items = await list_marks(category)
    return {m["item_key"]: m for m in items}


def _row_to_mark(row: aiosqlite.Row) -> dict[str, Any]:
    extra = {}
    try:
        extra = json.loads(row["extra"] or "{}")
    except json.JSONDecodeError:
        extra = {}
    return {
        "id": row["id"],
        "category": row["category"],
        "item_key": row["item_key"],
        "status": row["status"],
        "note": row["note"],
        "extra": extra,
        "updated_at": row["updated_at"],
    }


async def add_wallet_task(
    category: str,
    item_key: str,
    title: str,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    now = _now()
    conn = await connect()
    try:
        cur = await conn.execute(
            """
            INSERT INTO wallet_tasks
            (category, item_key, title, action, payload, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (category, item_key, title, action, json.dumps(payload, ensure_ascii=False), now, now),
        )
        await conn.commit()
        task_id = cur.lastrowid
    finally:
        await conn.close()
    return {
        "id": task_id,
        "category": category,
        "item_key": item_key,
        "title": title,
        "action": action,
        "payload": payload,
        "status": "pending",
        "tx_hash": "",
        "error": "",
        "created_at": now,
        "updated_at": now,
    }


async def list_wallet_tasks() -> list[dict[str, Any]]:
    conn = await connect()
    try:
        cur = await conn.execute("SELECT * FROM wallet_tasks ORDER BY id DESC LIMIT 200")
        rows = await cur.fetchall()
        out = []
        for row in rows:
            payload = {}
            try:
                payload = json.loads(row["payload"] or "{}")
            except json.JSONDecodeError:
                payload = {}
            out.append(
                {
                    "id": row["id"],
                    "category": row["category"],
                    "item_key": row["item_key"],
                    "title": row["title"],
                    "action": row["action"],
                    "payload": payload,
                    "status": row["status"],
                    "tx_hash": row["tx_hash"],
                    "error": row["error"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return out
    finally:
        await conn.close()


async def update_wallet_task(task_id: int, **fields: Any) -> None:
    allowed = {"status", "tx_hash", "error", "payload"}
    sets = []
    values: list[Any] = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "payload" and not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        sets.append(f"{key}=?")
        values.append(value)
    if not sets:
        return
    sets.append("updated_at=?")
    values.append(_now())
    values.append(task_id)
    conn = await connect()
    try:
        await conn.execute(f"UPDATE wallet_tasks SET {', '.join(sets)} WHERE id=?", values)
        await conn.commit()
    finally:
        await conn.close()


async def cache_get(key: str) -> Any | None:
    conn = await connect()
    try:
        cur = await conn.execute("SELECT payload, expires_at FROM cache WHERE cache_key=?", (key,))
        row = await cur.fetchone()
        if not row:
            return None
        if row["expires_at"] < datetime.now(timezone.utc).timestamp():
            await conn.execute("DELETE FROM cache WHERE cache_key=?", (key,))
            await conn.commit()
            return None
        return json.loads(row["payload"])
    finally:
        await conn.close()


async def cache_set(key: str, payload: Any, ttl_seconds: int) -> None:
    expires = datetime.now(timezone.utc).timestamp() + ttl_seconds
    conn = await connect()
    try:
        await conn.execute(
            """
            INSERT INTO cache (cache_key, payload, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload, expires_at=excluded.expires_at
            """,
            (key, json.dumps(payload, ensure_ascii=False), expires),
        )
        await conn.commit()
    finally:
        await conn.close()
