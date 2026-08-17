from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from web3_radar.config import FAMOUS_VCS
from web3_radar.fallback import load_fallback, merge_items

LLAMA_RAISES = "https://api.llama.fi/raises"
LLAMA_PROTOCOLS = "https://api.llama.fi/protocols"
CRYPTORANK_COINS = "https://api.cryptorank.io/v0/coins"
CRYPTORANK_FUNDS = "https://api.cryptorank.io/v0/funds"


def parse_raise_text(text: str | None) -> float | None:
    if not text:
        return None
    plain = re.sub(r"<[^>]+>", " ", text)
    patterns = [
        r"raised\s*\$?\s*([\d.,]+)\s*(billion|million|B|M)\b",
        r"\$\s*([\d.,]+)\s*(billion|million|B|M)\b",
        r"融资[^\d]*([\d.,]+)\s*(亿|百万|万)",
    ]
    for pat in patterns:
        m = re.search(pat, plain, re.I)
        if not m:
            continue
        n = float(m.group(1).replace(",", ""))
        unit = m.group(2).lower()
        if unit in {"billion", "b", "亿"}:
            n *= 1_000_000_000
        elif unit in {"million", "m", "百万"}:
            n *= 1_000_000
        elif unit == "万":
            n *= 10_000
        return n
    return None


def _norm(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _is_famous(investor: str) -> bool:
    inv = investor.lower()
    return any(vc in inv for vc in FAMOUS_VCS)


def _parse_money(value: Any) -> float | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    if val < 10_000:
        return val * 1_000_000
    return val


def _amount_usd(row: dict[str, Any]) -> float:
    amount = row.get("amount")
    if amount is None:
        return 0.0
    try:
        val = float(amount)
    except (TypeError, ValueError):
        return 0.0
    # DefiLlama stores millions
    if val < 10_000:
        return val * 1_000_000
    return val


def _investors(row: dict[str, Any]) -> list[str]:
    leads = row.get("leadInvestors") or []
    others = row.get("otherInvestors") or []
    out = []
    for x in list(leads) + list(others):
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
        elif isinstance(x, dict) and x.get("name"):
            out.append(str(x["name"]))
    return out


def _token_status(name: str, gecko_ids: set[str], protocol_names: set[str]) -> str:
    n = _norm(name)
    if n in protocol_names:
        return "可能已有协议/代币"
    for gid in gecko_ids:
        if n and n in gid:
            return "疑似已发币"
    return "未发币（待核验）"


def score_airdrop(amount: float, famous_n: int, token_status: str, valuation: float | None) -> tuple[int, str]:
    score = 0
    if amount >= 100_000_000:
        score += 40
    elif amount >= 50_000_000:
        score += 32
    elif amount >= 20_000_000:
        score += 24
    else:
        score += 8
    score += min(30, famous_n * 8)
    if token_status.startswith("未发币"):
        score += 20
        expect = "未发币，空投预期较高"
    elif "疑似" in token_status:
        score += 5
        expect = "可能已有代币，空投不确定"
    else:
        expect = "已有协议痕迹，空投预期一般"
    if valuation and valuation >= 500_000_000:
        score += 10
        expect += " · 高估值"
    score = min(100, score)
    return score, expect


async def scan_airdrops(min_funding_usd: float = 20_000_000) -> dict[str, Any]:
    errors: list[str] = []
    items: list[dict[str, Any]] = []
    try:
        items = await _scan_llama(min_funding_usd, errors)
    except Exception as exc:
        errors.append(f"defillama: {exc}")
    if len(items) < 5:
        try:
            cr = await _scan_cryptorank(min_funding_usd, errors)
            seen = {i["key"] for i in items}
            for row in cr:
                if row["key"] not in seen:
                    items.append(row)
                    seen.add(row["key"])
        except Exception as exc:
            errors.append(f"cryptorank: {exc}")
    items.sort(key=lambda x: (x["score"], x["total_funding_usd"], x["famous_count"]), reverse=True)
    items = merge_items(items, load_fallback().get("airdrops") or [])
    items.sort(key=lambda x: (x.get("score") or 0, x.get("total_funding_usd") or 0), reverse=True)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "min_funding_usd": min_funding_usd,
        "count": len(items),
        "items": items[:150],
        "errors": errors,
    }


async def _scan_llama(min_funding_usd: float, errors: list[str]) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=40.0, headers={"User-Agent": "ChainRadar/1.0"}) as client:
        raises_resp = await client.get(LLAMA_RAISES)
        if raises_resp.status_code >= 400:
            raise RuntimeError(f"HTTP {raises_resp.status_code}")
        raises = raises_resp.json()
        try:
            proto_resp = await client.get(LLAMA_PROTOCOLS)
            proto_resp.raise_for_status()
            protocols = proto_resp.json()
        except Exception as exc:
            errors.append(f"protocols: {exc}")
            protocols = []

    gecko_ids = set()
    proto_names = set()
    for p in protocols:
        if p.get("geckoId"):
            gecko_ids.add(_norm(p["geckoId"]))
            gecko_ids.add(_norm(p.get("name") or ""))
        if p.get("symbol") and p.get("symbol") not in ("-", ""):
            proto_names.add(_norm(p.get("name") or ""))

    grouped: dict[str, dict[str, Any]] = {}
    rows = raises.get("raises") if isinstance(raises, dict) else raises
    for row in rows or []:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        amount = _amount_usd(row)
        investors = _investors(row)
        famous = [i for i in investors if _is_famous(i)]
        key = _norm(name)
        rec = {
            "name": name,
            "amount": amount,
            "round": row.get("round") or "",
            "date": row.get("date"),
            "sector": row.get("sector") or row.get("category") or "",
            "chains": row.get("chains") or [],
            "source": row.get("source") or "",
            "investors": investors,
            "famous_investors": famous,
            "valuation": _parse_money(row.get("valuation")),
        }
        cur = grouped.get(key)
        if not cur:
            grouped[key] = rec
            grouped[key]["total_amount"] = amount
        else:
            cur["total_amount"] += amount
            cur["investors"] = list(dict.fromkeys(cur["investors"] + investors))
            cur["famous_investors"] = list(dict.fromkeys(cur["famous_investors"] + famous))
            if amount >= cur.get("amount", 0):
                cur.update({k: rec[k] for k in ("round", "date", "source", "amount")})

    items = []
    for key, g in grouped.items():
        total = g["total_amount"]
        if total < min_funding_usd:
            continue
        famous_n = len(g["famous_investors"])
        if famous_n <= 0 and total < min_funding_usd * 2:
            continue
        token_status = _token_status(g["name"], gecko_ids, proto_names)
        if not token_status.startswith("未发币") and "疑似" not in token_status and total < 80_000_000:
            continue
        score, expect = score_airdrop(total, famous_n, token_status, g.get("valuation"))
        date = g.get("date")
        date_iso = (
            datetime.fromtimestamp(date, tz=timezone.utc).date().isoformat()
            if isinstance(date, (int, float))
            else str(date or "")
        )
        items.append(
            {
                "key": key,
                "name": g["name"],
                "total_funding_usd": total,
                "latest_round": g.get("round"),
                "latest_date": date_iso,
                "sector": g.get("sector"),
                "chains": g.get("chains") or [],
                "famous_investors": g["famous_investors"][:12],
                "famous_count": famous_n,
                "investor_count": len(g["investors"]),
                "token_status": token_status,
                "token_expect": expect,
                "score": score,
                "source": g.get("source") or "https://defillama.com/raises",
                "valuation": g.get("valuation"),
            }
        )
    return items


async def _scan_cryptorank(min_funding_usd: float, errors: list[str]) -> list[dict[str, Any]]:
    headers = {"User-Agent": "ChainRadar/1.0", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        funds_resp = await client.get(CRYPTORANK_FUNDS, params={"limit": 200})
        funds_resp.raise_for_status()
        fund_map = {f["id"]: f for f in funds_resp.json().get("data") or []}
        coins: list[dict[str, Any]] = []
        for skip in (0, 30, 60):
            resp = await client.get(CRYPTORANK_COINS, params={"lifeCycle": "funding", "limit": 30, "skip": skip})
            if resp.status_code >= 400:
                errors.append(f"cryptorank coins skip={skip}: HTTP {resp.status_code}")
                break
            batch = resp.json().get("data") or []
            if not batch:
                break
            coins.extend(batch)
        sem = asyncio.Semaphore(8)

        async def detail_one(coin: dict[str, Any]) -> dict[str, Any] | None:
            key = coin.get("key")
            if not key:
                return None
            async with sem:
                try:
                    detail = (await client.get(f"{CRYPTORANK_COINS}/{key}")).json().get("data") or {}
                except Exception as exc:
                    errors.append(f"{key}: {exc}")
                    return None
            ico = detail.get("icoData") or {}
            amount = (
                _parse_money((ico.get("raised") or {}).get("USD"))
                or _parse_money((ico.get("raisedPrivate") or {}).get("USD"))
                or parse_raise_text(ico.get("description") or "")
                or 0.0
            )
            fund_ids = detail.get("fundIds") or []
            investors = []
            famous = []
            for fid in fund_ids:
                fund = fund_map.get(fid)
                if not fund:
                    continue
                investors.append(fund["name"])
                if fund.get("tier") == 1 or _is_famous(fund["name"]):
                    famous.append(fund["name"])
            famous = list(dict.fromkeys(famous))
            inferred = amount <= 0 and len(famous) >= 1
            if inferred:
                amount = min_funding_usd
            if amount < min_funding_usd:
                return None
            if not famous and amount < min_funding_usd * 2:
                return None
            token_status = "未发币（待核验）" if detail.get("lifeCycle") == "funding" else "疑似已发币"
            score, expect = score_airdrop(amount, len(famous), token_status, None)
            if inferred:
                expect += " · 金额未披露，按知名机构覆盖计入"
            cat = detail.get("category")
            return {
                "key": _norm(detail.get("name") or key),
                "name": detail.get("name") or key,
                "total_funding_usd": amount,
                "latest_round": "funding",
                "latest_date": "",
                "sector": cat.get("name") if isinstance(cat, dict) else str(cat or ""),
                "chains": [e.get("name") for e in (detail.get("coreEcosystems") or []) if isinstance(e, dict) and e.get("name")],
                "famous_investors": famous[:12],
                "famous_count": len(famous),
                "investor_count": len(investors),
                "token_status": token_status,
                "token_expect": expect,
                "score": score,
                "source": f"https://cryptorank.io/price/{key}",
                "valuation": None,
            }

        details = await asyncio.gather(*[detail_one(c) for c in coins[:48]])
        return [x for x in details if x]
