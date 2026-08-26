from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from web3_radar.collectors.ecosystem import airdrop_eco_label, classify_btc_eth
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


def score_airdrop(
    amount: float,
    famous_n: int,
    token_status: str,
    valuation: float | None,
    eco: str = "",
) -> tuple[int, str]:
    score = 0
    if amount >= 100_000_000:
        score += 40
    elif amount >= 50_000_000:
        score += 32
    elif amount >= 20_000_000:
        score += 24
    elif amount >= 5_000_000:
        score += 16
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
    if eco in {"bitcoin", "ethereum", "btc-eth"}:
        score += 18
        expect += " · " + airdrop_eco_label(eco)
    elif eco == "other":
        score -= 28
        expect += " · 非 BTC/ETH 生态，已降权"
    score = max(0, min(100, score))
    return score, expect


def _decorate_airdrop(item: dict[str, Any]) -> dict[str, Any]:
    eco = classify_btc_eth(
        item.get("name"),
        item.get("sector"),
        item.get("token_expect"),
        chains=item.get("chains"),
    )
    item["ecosystem"] = eco
    item["ecosystem_label"] = airdrop_eco_label(eco)
    score, expect = score_airdrop(
        float(item.get("total_funding_usd") or 0),
        int(item.get("famous_count") or 0),
        str(item.get("token_status") or ""),
        item.get("valuation"),
        eco=eco,
    )
    item["score"] = score
    item["token_expect"] = expect
    return item


def _funding_ok(item: dict[str, Any], min_eth: float, min_btc: float) -> bool:
    eco = str(item.get("ecosystem") or "other")
    total = float(item.get("total_funding_usd") or 0)
    if eco == "bitcoin":
        return total >= min_btc
    if eco in {"ethereum", "btc-eth"}:
        return total >= min_eth
    return total >= max(min_eth, 100_000_000)


def _keep_airdrop_focus(item: dict[str, Any]) -> bool:
    eco = item.get("ecosystem") or "other"
    if eco != "other":
        return True
    return float(item.get("total_funding_usd") or 0) >= 100_000_000 and int(item.get("famous_count") or 0) >= 2


async def scan_airdrops(
    min_funding_usd: float = 20_000_000,
    btc_min_funding_usd: float = 5_000_000,
    twitter_bearer: str = "",
) -> dict[str, Any]:
    errors: list[str] = []
    items: list[dict[str, Any]] = []
    floor = min(float(min_funding_usd), float(btc_min_funding_usd))
    try:
        items = await _scan_llama(floor, errors, min_eth=min_funding_usd, min_btc=btc_min_funding_usd)
    except Exception as exc:
        errors.append(f"defillama: {exc}")
    if len(items) < 5:
        try:
            cr = await _scan_cryptorank(floor, errors, min_eth=min_funding_usd, min_btc=btc_min_funding_usd)
            seen = {i["key"] for i in items}
            for row in cr:
                if row["key"] not in seen:
                    items.append(row)
                    seen.add(row["key"])
        except Exception as exc:
            errors.append(f"cryptorank: {exc}")
    items.sort(key=lambda x: (x["score"], x["total_funding_usd"], x["famous_count"]), reverse=True)
    items = merge_items(items, load_fallback().get("airdrops") or [])
    items = [_decorate_airdrop(dict(x)) for x in items]
    focused = [
        x for x in items
        if _keep_airdrop_focus(x) and _funding_ok(x, min_funding_usd, btc_min_funding_usd)
    ]
    dropped = len(items) - len(focused)
    focused = await _attach_kol_mentions(focused, twitter_bearer, errors)
    focused.sort(
        key=lambda x: (
            0 if x.get("ecosystem") == "bitcoin" else 1,
            0 if int(x.get("mention_count") or 0) else 1,
            -int(x.get("mention_count") or 0),
            -(x.get("score") or 0),
            -(x.get("total_funding_usd") or 0),
        )
    )
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "min_funding_usd": min_funding_usd,
        "btc_min_funding_usd": btc_min_funding_usd,
        "count": len(focused),
        "items": focused[:150],
        "errors": errors,
        "note": (
            "空投雷达：近一周 KOL/推特提及优先整理，比特币生态排最前，其余按提及次数、融资、团队打分。"
            + (f" 已过滤 {dropped} 条其他链或金额不够的项目。" if dropped else "")
        ),
    }


AIRDROP_QUERIES = [
    "airdrop (points OR testnet OR TGE) (crypto OR web3) -giveaway",
    "空投 (交互 OR 测试网 OR 积分)",
    "(bitcoin OR btc OR babylon OR stacks OR bitvm) airdrop",
]


async def _attach_kol_mentions(
    items: list[dict[str, Any]],
    twitter_bearer: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    from web3_radar.collectors.kol_calls import KOL_WATCH
    from web3_radar.collectors.social import collect_social

    tweets: list[dict[str, Any]] = []
    try:
        tweets = await asyncio.wait_for(collect_social(AIRDROP_QUERIES, twitter_bearer, 7), timeout=12)
    except Exception as exc:
        errors.append(f"twitter_airdrop: {exc}")
        tweets = []
    kol = {str(k.get("handle") or "").lower() for k in KOL_WATCH}
    for item in items:
        name = str(item.get("name") or "").strip()
        needle = name.lower()
        n = 0
        if needle:
            for tw in tweets:
                blob = f"{tw.get('text') or ''} {tw.get('name') or ''}".lower()
                if needle not in blob:
                    continue
                n += 1
                if str(tw.get("username") or "").lower() in kol:
                    n += 2
        item["mention_count"] = n
        if n:
            item["mention_note"] = f"近一周推特提及 {n} 次"
    seen = {_norm(str(x.get("name") or "")) for x in items}
    extra_map: dict[str, dict[str, Any]] = {}
    for tw in tweets:
        text = tw.get("text") or ""
        blob = f"{text} {tw.get('name') or ''}"
        if "airdrop" not in blob.lower() and "空投" not in blob:
            continue
        eco = classify_btc_eth(text, tw.get("name") or "")
        title = (text.strip().split("\n")[0][:72] or tw.get("name") or "空投讨论")
        key = _norm(title)[:40]
        if not key or key in seen:
            continue
        row = extra_map.get(key)
        bump = 2 if str(tw.get("username") or "").lower() in kol else 1
        if row:
            row["mention_count"] = int(row.get("mention_count") or 0) + bump
            continue
        extra_map[key] = _decorate_airdrop(
            {
                "key": f"tw:{key}",
                "name": title,
                "total_funding_usd": 0,
                "latest_round": "",
                "latest_date": "",
                "sector": "BTC 生态 · 近一周讨论" if eco == "bitcoin" else "近一周 KOL/推特讨论",
                "chains": ["Bitcoin"] if eco == "bitcoin" else [],
                "famous_investors": [],
                "famous_count": 1 if str(tw.get("username") or "").lower() in kol else 0,
                "investor_count": 0,
                "token_status": "未发币（待核验）",
                "source": tw.get("url") or "",
                "mention_count": bump,
                "mention_note": "近一周推特提及",
                "source_kind": "twitter",
            }
        )
    extra = list(extra_map.values())
    combined = items + extra[:18]
    combined.sort(
        key=lambda x: (
            0 if x.get("ecosystem") == "bitcoin" else 1,
            0 if int(x.get("mention_count") or 0) else 1,
            -int(x.get("mention_count") or 0),
            -(x.get("score") or 0),
            -(x.get("total_funding_usd") or 0),
        )
    )
    return combined


async def _scan_llama(
    min_funding_usd: float,
    errors: list[str],
    min_eth: float | None = None,
    min_btc: float | None = None,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": "ChainRadar/1.0"}) as client:
        raises_resp = await client.get(LLAMA_RAISES)
        if raises_resp.status_code in {401, 402, 403}:
            errors.append("DefiLlama raises 需付费/受限，已改用公开源与观察池")
            return []
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

    min_eth = float(min_eth if min_eth is not None else min_funding_usd)
    min_btc = float(min_btc if min_btc is not None else min_funding_usd)
    items = []
    for key, g in grouped.items():
        total = g["total_amount"]
        if total < min(min_eth, min_btc):
            continue
        famous_n = len(g["famous_investors"])
        eco = classify_btc_eth(g["name"], g.get("sector"), chains=g.get("chains"))
        need = min_btc if eco == "bitcoin" else min_eth
        if total < need:
            continue
        if famous_n <= 0 and total < need * 2:
            continue
        token_status = _token_status(g["name"], gecko_ids, proto_names)
        if not token_status.startswith("未发币") and "疑似" not in token_status and total < 80_000_000:
            continue
        score, expect = score_airdrop(total, famous_n, token_status, g.get("valuation"), eco=eco)
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
                "ecosystem": eco,
                "ecosystem_label": airdrop_eco_label(eco),
            }
        )
    return items


async def _scan_cryptorank(
    min_funding_usd: float,
    errors: list[str],
    min_eth: float | None = None,
    min_btc: float | None = None,
) -> list[dict[str, Any]]:
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
            min_eth_v = float(min_eth if min_eth is not None else min_funding_usd)
            min_btc_v = float(min_btc if min_btc is not None else min_funding_usd)
            cat = detail.get("category")
            chains = [e.get("name") for e in (detail.get("coreEcosystems") or []) if isinstance(e, dict) and e.get("name")]
            eco = classify_btc_eth(detail.get("name") or key, cat, chains=chains)
            need = min_btc_v if eco == "bitcoin" else min_eth_v
            inferred = amount <= 0 and len(famous) >= 1
            if inferred:
                amount = need
            if amount < need:
                return None
            if not famous and amount < need * 2:
                return None
            token_status = "未发币（待核验）" if detail.get("lifeCycle") == "funding" else "疑似已发币"
            score, expect = score_airdrop(amount, len(famous), token_status, None, eco=eco)
            if inferred:
                expect += " · 金额未披露，按知名机构覆盖计入"
            return {
                "key": _norm(detail.get("name") or key),
                "name": detail.get("name") or key,
                "total_funding_usd": amount,
                "latest_round": "funding",
                "latest_date": "",
                "sector": cat.get("name") if isinstance(cat, dict) else str(cat or ""),
                "chains": chains,
                "famous_investors": famous[:12],
                "famous_count": len(famous),
                "investor_count": len(investors),
                "token_status": token_status,
                "token_expect": expect,
                "score": score,
                "source": f"https://cryptorank.io/price/{key}",
                "valuation": None,
                "ecosystem": eco,
                "ecosystem_label": airdrop_eco_label(eco),
            }

        details = await asyncio.gather(*[detail_one(c) for c in coins[:48]])
        return [x for x in details if x]
