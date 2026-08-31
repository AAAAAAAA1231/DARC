from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .models import RankedToken, TokenSnapshot
from .scoring import MIN_MC, MAX_MC, rank
from .sources.dexscreener import fetch_discovery_lists, fetch_pairs_for_tokens, overlay_dex
from .sources.geckoterminal import fetch_geckoterminal
from .sources.httputil import client_kwargs, gather_limited
from .sources.pumpfun import fetch_pump
from .sources.rugcheck import enrich_security

CACHE_TTL = 40.0
RUGCHECK_TOP = 18


THESIS = {
    "title": "百倍金狗基因",
    "promise": "不预测谁会涨，只捕捉“现在买、100x 在几何上还做得到”的链上结构。",
    "disclaimer": "迷因币默认归零。高分只说明结构像历史百倍入口，不说明接下来会 100x。本工具不是投资建议。",
    "gates": [
        f"市值 ${MIN_MC:,.0f}–${MAX_MC:,.0f}：100x 后仍落在迷因币可实现终点（约 $50万–$2200万）",
        "开盘 6 分钟–36 小时：避开狙击带，也丢掉已经冷掉的微型盘",
        "必须看到真实独立买家；成交额畸高但地址极少视为骗量",
        "铸造/冻结权仍在、LP 未锁、或正在 5 分钟崩盘的直接淘汰",
        "相对典型 $5k 开盘已涨超过约 40x 的，从此处再 100x 视为幻想",
    ],
    "genes": [
        {"id": "room", "name": "百倍空间", "why": "现价越低，100x 所需终点越接近真实 runner 顶部。最密的历史入口在 $8k–$35k。"},
        {"id": "window", "name": "黄金时间窗", "why": "12–90 分钟是人类可执行的发现盘；更早是捆绑，更晚要靠第二波叙事。"},
        {"id": "flow", "name": "真实买盘", "why": "独立买家增加且买卖比偏多，才是扩散；对倒只堆 volume。"},
        {"id": "liq", "name": "曲线/流动性", "why": "Pump 内盘 18%–72% 或外盘 LP 锁定，才能活到第二波。"},
        {"id": "sec", "name": "安全结构", "why": "丢铸造/冻结、LP 锁、持仓不过分集中，否则涨幅不属于你。"},
        {"id": "mom", "name": "动量结构", "why": "温和确认（1h +8%～+180%）优于垂直泡沫，也优于自由落体。"},
        {"id": "ignite", "name": "传播点火", "why": "社交/助推/评论只是乘数，不是入场理由。"},
    ],
    "targets": {
        "conservative": 1_500_000,
        "runner": 5_000_000,
        "stretch": 20_000_000,
    },
}


@dataclass
class ScanCache:
    at: float = 0.0
    payload: dict[str, Any] | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_cache = ScanCache()


def _merge_universe(parts: list[list[TokenSnapshot]]) -> dict[str, TokenSnapshot]:
    universe: dict[str, TokenSnapshot] = {}
    for batch in parts:
        for snap in batch:
            prev = universe.get(snap.key)
            if not prev:
                universe[snap.key] = snap
                continue
            if snap.volume_h1 > prev.volume_h1 or snap.tx_h1.buyers > prev.tx_h1.buyers:
                snap.pump = snap.pump or prev.pump
                snap.security = snap.security or prev.security
                if not snap.created_at_ms:
                    snap.created_at_ms = prev.created_at_ms
                if prev.image and not snap.image:
                    snap.image = prev.image
                universe[snap.key] = snap
            else:
                if snap.pump and not prev.pump:
                    prev.pump = snap.pump
                if snap.image and not prev.image:
                    prev.image = snap.image
                if snap.socials and not prev.socials:
                    prev.socials = snap.socials
    return universe


async def _enrich_dex(client: httpx.AsyncClient, universe: dict[str, TokenSnapshot]) -> None:
    by_chain: dict[str, list[str]] = {}
    for snap in universe.values():
        by_chain.setdefault(snap.chain, []).append(snap.address)
    # Prefer solana — that is where 100x density lives.
    order = ["solana", "base", "bsc", "ethereum"]
    chains = [c for c in order if c in by_chain] + [c for c in by_chain if c not in order]
    for chain in chains[:4]:
        addrs = by_chain[chain][:80]
        snaps = await fetch_pairs_for_tokens(client, chain, addrs)
        for ds in snaps:
            if ds.key in universe:
                overlay_dex(universe[ds.key], ds)
            else:
                universe[ds.key] = ds


async def _enrich_security(client: httpx.AsyncClient, ranked: list[RankedToken]) -> None:
    targets = [row for row in ranked if row.score.passed and row.token.chain == "solana"][:RUGCHECK_TOP]
    if not targets:
        targets = [row for row in ranked if row.token.chain == "solana"][:8]
    reports = await gather_limited(
        [enrich_security(client, row.token) for row in targets],
        limit=4,
    )
    for row, sec in zip(targets, reports):
        if sec:
            row.token.security = sec
            from .scoring import score_token

            row.score = score_token(row.token)


ALLOWED_CHAINS = {
    "solana",
    "base",
    "bsc",
    "ethereum",
    "arbitrum",
    "blast",
    "sonic",
    "abstract",
    "hyperevm",
    "monad",
}


def _prefilter(snap: TokenSnapshot) -> bool:
    mc = snap.cap()
    if mc <= 0:
        return False
    if snap.chain not in ALLOWED_CHAINS:
        return False
    # Keep a slightly wider net than the scorer so near-misses still show as rejected.
    if mc < MIN_MC * 0.5 or mc > MAX_MC * 1.6:
        return False
    return True


async def run_scan(force: bool = False) -> dict[str, Any]:
    async with _cache.lock:
        now = time.time()
        if not force and _cache.payload and now - _cache.at < CACHE_TTL:
            return _cache.payload

        t0 = time.time()
        errors: list[str] = []
        universe: dict[str, TokenSnapshot] = {}
        candidates: list[TokenSnapshot] = []
        ranked: list[RankedToken] = []
        async with httpx.AsyncClient(**client_kwargs()) as client:
            pump_task = fetch_pump(client)
            gt_task = fetch_geckoterminal(client)
            ds_task = fetch_discovery_lists(client)
            pump, gt, discover = await asyncio.gather(pump_task, gt_task, ds_task, return_exceptions=True)
            batches: list[list[TokenSnapshot]] = []
            if isinstance(pump, Exception):
                errors.append(f"pump.fun: {pump}")
            else:
                batches.append(pump)
            if isinstance(gt, Exception):
                errors.append(f"geckoterminal: {gt}")
            else:
                batches.append(gt)
            discover_items: list[dict] = []
            if isinstance(discover, Exception):
                errors.append(f"dexscreener lists: {discover}")
            else:
                discover_items = discover

            universe = _merge_universe(batches)

            # Dexscreener discovery addresses → pair snapshots
            ds_addrs: dict[str, list[str]] = {}
            for item in discover_items:
                chain = item.get("chainId")
                addr = item.get("tokenAddress")
                if chain and addr:
                    ds_addrs.setdefault(chain, []).append(addr)
            for chain, addrs in list(ds_addrs.items())[:5]:
                try:
                    extra = await fetch_pairs_for_tokens(client, chain, addrs[:30])
                    for snap in extra:
                        snap.has_profile = True
                        universe.setdefault(snap.key, snap)
                except Exception as exc:
                    errors.append(f"dexscreener {chain}: {exc}")

            try:
                await _enrich_dex(client, universe)
            except Exception as exc:
                errors.append(f"dex overlay: {exc}")

            candidates = [s for s in universe.values() if _prefilter(s)]
            ranked_raw = rank(candidates)
            ranked = [RankedToken(token=t, score=s, age_min=age) for t, s, age in ranked_raw]

            try:
                await _enrich_security(client, ranked)
            except Exception as exc:
                errors.append(f"rugcheck: {exc}")

            ranked.sort(key=lambda r: (r.score.passed, r.score.total, r.score.feasibility), reverse=True)

        passed = [r for r in ranked if r.score.passed]
        payload = {
            "scanned_at": int(time.time() * 1000),
            "elapsed_ms": int((time.time() - t0) * 1000),
            "universe": len(universe),
            "considered": len(candidates),
            "passed": len(passed),
            "top_score": passed[0].score.total if passed else 0,
            "top_grade": passed[0].score.grade if passed else "—",
            "errors": errors,
            "thesis": THESIS,
            "tokens": [r.to_api() for r in ranked[:80]],
        }
        _cache.at = time.time()
        _cache.payload = payload
        return payload
