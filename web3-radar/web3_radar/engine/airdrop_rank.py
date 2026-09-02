from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from web3_radar.config import APP_DIR, FAMOUS_VCS

TIER1 = (
    "a16z",
    "andreessen horowitz",
    "paradigm",
    "sequoia",
    "founders fund",
    "coinbase ventures",
    "binance labs",
    "ynzi labs",
    "polychain",
    "pantera",
    "jump",
    "dragonfly",
    "multicoin",
    "electric capital",
    "lightspeed",
)

SECTOR_ALIASES = {
    "l2": "l2",
    "layer2": "l2",
    "rollup": "l2",
    "高性能链": "l2",
    "l1": "l1",
    "layer1": "l1",
    "perps": "perps",
    "perp": "perps",
    "dex": "dex",
    "defi": "defi",
    "nft": "nft",
    "infra": "infra",
    "oracle": "oracle",
    "modular": "modular",
    "restaking": "restaking",
    "solana": "solana",
    "exchange": "exchange",
    "payments": "l1",
    "稳定币": "l1",
}

CONFIRMED_LABEL = {
    "official": "明确有空投",
    "points": "积分计划（偏明确）",
    "rumored": "未明确，仅有预期",
    "none": "未见空投信号",
    "tge": "已发币 / 空投窗口已过",
}

DIFF_LABEL = {"easy": "低", "medium": "中", "hard": "高", "expert": "很高"}
DIFF_SCORE = {"easy": 16, "medium": 20, "hard": 12, "expert": 6}


def _norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def sector_key(text: str) -> str:
    raw = (text or "").lower()
    for key, mapped in SECTOR_ALIASES.items():
        if key in raw:
            return mapped
    return "other"


def _money(n: float | None) -> str:
    if not n:
        return "—"
    if n >= 1_000_000_000:
        return f"${n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"${n / 1_000_000:.0f}M"
    return f"${n:,.0f}"


def _is_tier1(name: str) -> bool:
    inv = name.lower()
    return any(vc in inv for vc in TIER1)


def _is_famous(name: str) -> bool:
    inv = name.lower()
    return any(vc in inv for vc in FAMOUS_VCS) or _is_tier1(name)


@dataclass
class HistoryAirdrop:
    name: str
    year: int
    sector: str
    funding_usd: float
    airdrop_usd: float
    fdv_tge_usd: float
    famous: list[str]
    difficulty: str
    confirmed: bool


@dataclass
class AirdropCandidate:
    name: str
    sector: str = ""
    funding_usd: float = 0.0
    valuation_usd: Optional[float] = None
    famous_investors: list[str] = field(default_factory=list)
    confirmed: str = "none"
    difficulty: str = "medium"
    token_live: bool = False
    url: str = ""
    chains: list[str] = field(default_factory=list)
    note: str = ""
    source: str = ""
    key: str = ""

    def __post_init__(self) -> None:
        if not self.key:
            self.key = _norm(self.name)


def _resource(name: str) -> Path:
    candidates = [
        Path(__file__).resolve().parents[1] / "resources" / name,
        APP_DIR / "web3_radar" / "resources" / name,
        APP_DIR / "resources" / name,
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def load_history() -> list[HistoryAirdrop]:
    path = _resource("airdrop_history.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for row in payload.get("items") or []:
        out.append(
            HistoryAirdrop(
                name=row["name"],
                year=int(row.get("year") or 0),
                sector=sector_key(row.get("sector") or ""),
                funding_usd=float(row.get("funding_usd") or 0),
                airdrop_usd=float(row.get("airdrop_usd") or 0),
                fdv_tge_usd=float(row.get("fdv_tge_usd") or 0),
                famous=list(row.get("famous") or []),
                difficulty=str(row.get("difficulty") or "medium"),
                confirmed=bool(row.get("confirmed")),
            )
        )
    return out


def load_watchlist() -> list[AirdropCandidate]:
    path = _resource("airdrop_watch.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for row in payload.get("items") or []:
        items.append(
            AirdropCandidate(
                name=row["name"],
                sector=row.get("sector") or "",
                funding_usd=float(row.get("funding_usd") or 0),
                valuation_usd=row.get("valuation_usd"),
                famous_investors=list(row.get("famous_investors") or []),
                confirmed=str(row.get("confirmed") or "none"),
                difficulty=str(row.get("difficulty") or "medium"),
                token_live=bool(row.get("token_live")),
                url=row.get("url") or "",
                chains=list(row.get("chains") or []),
                note=row.get("note") or "",
                source=row.get("url") or "观察池",
            )
        )
    return items


def _median(values: list[float], default: float) -> float:
    nums = sorted(v for v in values if v and v > 0)
    if not nums:
        return default
    mid = len(nums) // 2
    if len(nums) % 2:
        return nums[mid]
    return (nums[mid - 1] + nums[mid]) / 2


def sector_stats(history: list[HistoryAirdrop]) -> dict[str, dict[str, float]]:
    buckets: dict[str, list[HistoryAirdrop]] = {}
    for row in history:
        buckets.setdefault(row.sector, []).append(row)
    out: dict[str, dict[str, float]] = {}
    for sector, rows in buckets.items():
        shares = [r.airdrop_usd / r.fdv_tge_usd for r in rows if r.fdv_tge_usd > 0]
        multiples = [r.fdv_tge_usd / r.funding_usd for r in rows if r.funding_usd > 0 and r.fdv_tge_usd > 0]
        out[sector] = {
            "airdrop_share": _median(shares, 0.12),
            "fdv_multiple": _median(multiples, 25.0),
        }
    out.setdefault("other", {"airdrop_share": 0.10, "fdv_multiple": 20.0})
    return out


def institution_score(investors: Iterable[str]) -> tuple[int, list[str]]:
    reasons: list[str] = []
    seen: set[str] = set()
    t1 = 0
    t2 = 0
    names = []
    for raw in investors:
        name = str(raw).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
        if _is_tier1(name):
            t1 += 1
        elif _is_famous(name):
            t2 += 1
    score = min(25, t1 * 8 + t2 * 4)
    if t1:
        reasons.append(f"一线机构 {t1} 家")
    elif t2:
        reasons.append(f"知名机构 {t2} 家")
    else:
        reasons.append("未见一线机构")
    return score, reasons


def confirmed_score(flag: str) -> tuple[int, str]:
    mapping = {"official": 25, "points": 20, "rumored": 10, "none": 4, "tge": 0}
    pts = mapping.get(flag, 4)
    return pts, CONFIRMED_LABEL.get(flag, CONFIRMED_LABEL["none"])


def difficulty_score(level: str) -> tuple[int, str]:
    lvl = level if level in DIFF_SCORE else "medium"
    return DIFF_SCORE[lvl], DIFF_LABEL[lvl]


def naive_expected(candidate: AirdropCandidate, stats: dict[str, dict[str, float]]) -> float:
    sec = stats.get(sector_key(candidate.sector), stats["other"])
    fdv = candidate.valuation_usd or 0.0
    if fdv <= 0 and candidate.funding_usd > 0:
        fdv = candidate.funding_usd * sec["fdv_multiple"]
    if fdv <= 0:
        fdv = 200_000_000
    return fdv * sec["airdrop_share"]


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa = {_norm(x) for x in a if x}
    sb = {_norm(x) for x in b if x}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def similarity(candidate: AirdropCandidate, hist: HistoryAirdrop) -> float:
    same = 1.0 if sector_key(candidate.sector) == hist.sector else 0.25
    fa = math.log10(max(candidate.funding_usd, 1.0))
    fb = math.log10(max(hist.funding_usd, 1.0))
    fund = max(0.0, 1.0 - abs(fa - fb) / 3.0)
    vc = _jaccard(candidate.famous_investors, hist.famous)
    return 0.45 * same + 0.30 * fund + 0.25 * vc


def historical_correction(
    candidate: AirdropCandidate,
    history: list[HistoryAirdrop],
    naive: float,
    stats: dict[str, dict[str, float]],
) -> tuple[float, int, list[str], list[str]]:
    scored = sorted(((similarity(candidate, h), h) for h in history), key=lambda x: x[0], reverse=True)
    neighbors = [(sim, h) for sim, h in scored if sim >= 0.35][:3]
    if not neighbors:
        neighbors = scored[:2]
    ratios: list[float] = []
    names: list[str] = []
    for sim, hist in neighbors:
        expected = naive_expected(
            AirdropCandidate(
                name=hist.name,
                sector=hist.sector,
                funding_usd=hist.funding_usd,
                famous_investors=hist.famous,
            ),
            stats,
        )
        if expected <= 0:
            continue
        ratios.append(hist.airdrop_usd / expected)
        names.append(hist.name)
    if not ratios:
        return naive, 0, names, ["历史样本不足，未做修正"]
    ratio = _median(ratios, 1.0)
    ratio = min(1.8, max(0.4, ratio))
    adj = 0
    note = f"对照 { '、'.join(names[:3]) }"
    if ratio >= 1.25:
        adj = 8
        note += f"，同类实际空投约为模型的 {ratio:.1f} 倍，上修"
    elif ratio >= 1.05:
        adj = 4
        note += f"，同类略超预期（{ratio:.1f}x）"
    elif ratio <= 0.6:
        adj = -8
        note += f"，同类实际只有模型的 {ratio:.1f} 倍，下修（如部分高融资 L2）"
    elif ratio <= 0.9:
        adj = -4
        note += f"，同类略低于模型（{ratio:.1f}x）"
    else:
        note += "，同类接近模型中位，几乎不修正"
    return naive * ratio, adj, names, [note]


def amount_score(expected: float) -> tuple[int, str]:
    if expected >= 1_000_000_000:
        return 20, f"预计总盘 {_money(expected)}"
    if expected >= 300_000_000:
        return 16, f"预计总盘 {_money(expected)}"
    if expected >= 100_000_000:
        return 12, f"预计总盘 {_money(expected)}"
    if expected >= 30_000_000:
        return 8, f"预计总盘 {_money(expected)}"
    return 4, f"预计总盘 {_money(expected)}，体量偏小"


def score_candidate(candidate: AirdropCandidate, history: list[HistoryAirdrop] | None = None) -> dict[str, Any]:
    history = history if history is not None else load_history()
    stats = sector_stats(history)
    inst, inst_why = institution_score(candidate.famous_investors)
    conf, conf_label = confirmed_score(candidate.confirmed)
    diff, diff_label = difficulty_score(candidate.difficulty)
    naive = naive_expected(candidate, stats)
    expected, hist_adj, similar, hist_why = historical_correction(candidate, history, naive, stats)
    amt, amt_why = amount_score(expected)
    total = inst + conf + diff + amt + hist_adj
    if candidate.token_live or candidate.confirmed == "tge":
        total = min(total, 48)
        hist_why.append("已发币，不再当新空投主推荐")
    total = int(max(0, min(100, total)))
    reasons = inst_why + [conf_label, f"参与难度{diff_label}", amt_why] + hist_why
    if candidate.note:
        reasons.append(candidate.note)
    return {
        "key": candidate.key,
        "name": candidate.name,
        "score": total,
        "parts": {
            "institutions": inst,
            "confirmed": conf,
            "difficulty": diff,
            "expected_amount": amt,
            "history_adj": hist_adj,
        },
        "confirmed": candidate.confirmed,
        "confirmed_label": conf_label,
        "difficulty": candidate.difficulty,
        "difficulty_label": diff_label,
        "expected_airdrop_usd": round(expected),
        "expected_airdrop": _money(expected),
        "funding_usd": candidate.funding_usd,
        "funding": _money(candidate.funding_usd),
        "famous_investors": candidate.famous_investors[:10],
        "famous_count": len(candidate.famous_investors),
        "sector": candidate.sector,
        "chains": candidate.chains,
        "token_live": candidate.token_live,
        "similar": similar[:3],
        "reasons": reasons,
        "url": candidate.url,
        "source": candidate.source,
        "recommend": total >= 55 and not candidate.token_live and candidate.confirmed != "tge",
    }


def rank_candidates(candidates: Iterable[AirdropCandidate], history: list[HistoryAirdrop] | None = None) -> list[dict[str, Any]]:
    history = history if history is not None else load_history()
    ranked = [score_candidate(c, history) for c in candidates]
    ranked.sort(key=lambda x: (x["score"], x["expected_airdrop_usd"], x["famous_count"]), reverse=True)
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i
    return ranked


def candidate_from_live(row: dict[str, Any]) -> AirdropCandidate:
    status = str(row.get("token_status") or "")
    token_live = (not status.startswith("未发币")) and "疑似" not in status
    if token_live:
        confirmed = "tge"
    elif status.startswith("未发币"):
        confirmed = "rumored"
    else:
        confirmed = "none"
    sector = str(row.get("sector") or "")
    difficulty = "hard" if sector_key(sector) == "l1" else "medium"
    return AirdropCandidate(
        name=str(row.get("name") or "unknown"),
        sector=sector,
        funding_usd=float(row.get("total_funding_usd") or 0),
        valuation_usd=row.get("valuation"),
        famous_investors=list(row.get("famous_investors") or []),
        confirmed=confirmed,
        difficulty=difficulty,
        token_live=token_live,
        url=str(row.get("source") or ""),
        chains=list(row.get("chains") or []),
        source=str(row.get("source") or ""),
        key=str(row.get("key") or _norm(str(row.get("name") or ""))),
    )


def merge_candidates(live: list[dict[str, Any]], watch: list[AirdropCandidate]) -> list[AirdropCandidate]:
    by_key: dict[str, AirdropCandidate] = {}
    for row in live:
        cand = candidate_from_live(row)
        by_key[cand.key] = cand
    for item in watch:
        prev = by_key.get(item.key)
        if not prev:
            by_key[item.key] = item
            continue
        prev.confirmed = item.confirmed or prev.confirmed
        prev.difficulty = item.difficulty or prev.difficulty
        prev.token_live = item.token_live or prev.token_live
        prev.note = item.note or prev.note
        prev.url = item.url or prev.url
        if item.funding_usd and item.funding_usd > prev.funding_usd:
            prev.funding_usd = item.funding_usd
        if item.valuation_usd:
            prev.valuation_usd = item.valuation_usd
        if item.famous_investors:
            prev.famous_investors = list(dict.fromkeys(prev.famous_investors + item.famous_investors))
        if item.sector:
            prev.sector = item.sector
    return list(by_key.values())
