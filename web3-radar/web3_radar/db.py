from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from web3_radar.config import DB_PATH, DATA_DIR, MONTE_CARLO_SIMS, ensure_dirs, format_sim_count

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

CREATE TABLE IF NOT EXISTS copy_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key TEXT NOT NULL,
    symbol TEXT NOT NULL,
    chain TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    entry REAL NOT NULL,
    qty REAL NOT NULL,
    sl REAL NOT NULL,
    tp REAL NOT NULL,
    last_price REAL NOT NULL DEFAULT 0,
    unrealized_pnl REAL NOT NULL DEFAULT 0,
    pnl_usd REAL NOT NULL DEFAULT 0,
    exit_price REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',
    reason TEXT NOT NULL DEFAULT '',
    close_reason TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT 'paper',
    heat REAL,
    risk REAL,
    opened_at TEXT NOT NULL,
    closed_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    n_sims INTEGER NOT NULL,
    total INTEGER NOT NULL,
    up_count INTEGER NOT NULL DEFAULT 0,
    down_count INTEGER NOT NULL DEFAULT 0,
    wait_count INTEGER NOT NULL DEFAULT 0,
    payload TEXT NOT NULL DEFAULT '{}'
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


async def add_copy_position(row: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    conn = await connect()
    try:
        cur = await conn.execute(
            """
            INSERT INTO copy_positions
            (item_key, symbol, chain, url, entry, qty, sl, tp, last_price, status, reason, mode, heat, risk, opened_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
            """,
            (
                row["item_key"],
                row.get("symbol") or "?",
                row.get("chain") or "",
                row.get("url") or "",
                float(row["entry"]),
                float(row["qty"]),
                float(row["sl"]),
                float(row["tp"]),
                float(row.get("last_price") or row["entry"]),
                row.get("reason") or "",
                row.get("mode") or "paper",
                row.get("heat"),
                row.get("risk"),
                now,
            ),
        )
        await conn.commit()
        pid = cur.lastrowid
    finally:
        await conn.close()
    return {**row, "id": pid, "status": "open", "opened_at": now, "unrealized_pnl": 0}


async def list_copy_positions(status: str | None = None) -> list[dict[str, Any]]:
    conn = await connect()
    try:
        if status:
            cur = await conn.execute("SELECT * FROM copy_positions WHERE status=? ORDER BY id DESC", (status,))
        else:
            cur = await conn.execute("SELECT * FROM copy_positions ORDER BY id DESC LIMIT 200")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def update_copy_position(pid: int, **fields: Any) -> None:
    if not fields:
        return
    sets = [f"{k}=?" for k in fields]
    values = list(fields.values()) + [pid]
    conn = await connect()
    try:
        await conn.execute(f"UPDATE copy_positions SET {', '.join(sets)} WHERE id=?", values)
        await conn.commit()
    finally:
        await conn.close()


async def save_analysis_run(payload: dict[str, Any]) -> None:
    results = payload.get("results") or []
    slim = []
    for r in results:
        slim.append(
            {
                "symbol": r.get("symbol"),
                "name": r.get("name"),
                "decision": r.get("decision"),
                "score": r.get("score"),
                "price": r.get("price"),
                "entry": r.get("entry"),
                "stop_loss": r.get("stop_loss"),
                "take_profit": r.get("take_profit"),
                "mode": r.get("mode") or "",
                "n_sims": r.get("n_sims"),
                "weights_adjusted": r.get("weights_adjusted"),
                "sim_note": r.get("sim_note"),
                "market_cap_rank": r.get("market_cap_rank"),
                "venue": r.get("venue"),
                "indicators": r.get("indicators") or [],
            }
        )
    up = sum(1 for r in slim if r.get("decision") == "涨")
    down = sum(1 for r in slim if r.get("decision") == "跌")
    wait = sum(1 for r in slim if r.get("decision") == "观望")
    n_sims = 0
    for r in slim:
        if r.get("n_sims"):
            n_sims = int(r["n_sims"])
            break
    conn = await connect()
    try:
        await conn.execute(
            """
            INSERT INTO analysis_runs (created_at, status, n_sims, total, up_count, down_count, wait_count, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                payload.get("status") or "done",
                n_sims,
                len(slim),
                up,
                down,
                wait,
                json.dumps({"results": slim}, ensure_ascii=False),
            ),
        )
        await conn.commit()
    finally:
        await conn.close()


async def latest_analysis_run() -> dict[str, Any] | None:
    conn = await connect()
    try:
        cur = await conn.execute("SELECT * FROM analysis_runs ORDER BY id DESC LIMIT 1")
        row = await cur.fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            data["results"] = json.loads(data.pop("payload") or "{}").get("results") or []
        except json.JSONDecodeError:
            data["results"] = []
        fitted, ok_n, total_n = analysis_is_fitted(data["results"])
        data["fitted"] = fitted
        data["fitted_ok"] = ok_n
        data["fitted_total"] = total_n
        if fitted:
            data["fitted_note"] = (
                f"已完成拟合 {str(data['created_at'])[:19]} · {ok_n}/{total_n} 标的已有校准权重 · "
                f"涨{data['up_count']} / 跌{data['down_count']} / 观望{data['wait_count']}"
            )
        else:
            data["fitted_note"] = f"尚未完成权重拟合。拟合只需一次 {format_sim_count(MONTE_CARLO_SIMS)}模拟；之后刷新只套用模型出信号。"
        return data
    finally:
        await conn.close()


def analysis_is_fitted(
    results: list[dict[str, Any]],
    n_sims_required: int = MONTE_CARLO_SIMS,
    min_ratio: float = 0.8,
) -> tuple[bool, int, int]:
    """A board is fitted when enough rows carry 1B-calibrated (or infer-mode) weights."""
    total = len(results or [])
    ok = 0
    for r in results or []:
        if r.get("error"):
            continue
        if (r.get("mode") == "infer" and r.get("weights_adjusted")) or int(r.get("n_sims") or 0) >= n_sims_required:
            ok += 1
    if total <= 0:
        return False, 0, 0
    return (ok / total) >= min_ratio and ok > 0, ok, total


MODEL_PATH = DATA_DIR / "fitted_model.json"


async def save_fitted_model(model: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    MODEL_PATH.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    await cache_set("fitted_model", model, 365 * 24 * 3600)
    return model


async def load_fitted_model() -> dict[str, Any] | None:
    cached = await cache_get("fitted_model")
    if isinstance(cached, dict) and cached.get("weights"):
        return cached
    if MODEL_PATH.exists():
        try:
            model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            model = None
        if isinstance(model, dict) and model.get("weights"):
            await cache_set("fitted_model", model, 365 * 24 * 3600)
            return model
    return None


async def cache_delete(key: str) -> None:
    conn = await connect()
    try:
        await conn.execute("DELETE FROM cache WHERE cache_key=?", (key,))
        await conn.commit()
    finally:
        await conn.close()
