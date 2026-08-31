"""100x genome scorer.

The model is not a price predictor. It ranks tokens whose *current* on-chain
structure matches the shape that historical memecoin 100x runners had at the
last moment a non-sniper could still enter.

Empirical priors (2023-2026 pump.fun / Solana / Base runners):
- Almost every 100x was bought below ~$80k MC; the densest band is $8k-$35k.
- First 5 minutes are sniper/bundle dump territory, not a human 100x entry.
- Unique buyers accelerating while MC is still micro beats raw volume.
- Bonding-curve / burned LP is the only structure that routinely survives
  long enough for a second wave. Unlocked LP at micro-cap is usually a rug.
- If the token has already done 30x+ from a ~$5k launch print, another 100x
  from *here* implies a multi-hundred-million fully diluted fantasy.

A score of 80+ means "this still has a geometrically plausible 100x path",
not "this will 100x". Most candidates still go to zero.
"""
from __future__ import annotations

import time
from typing import Iterable

from .models import Gene, ScoreCard, TokenSnapshot, TxWindow

MIN_MC = 5_000.0
MAX_MC = 220_000.0
MIN_AGE_SEC = 6 * 60
MAX_AGE_SEC = 36 * 3600
TYPICAL_LAUNCH_MC = 5_000.0
CONSERVATIVE_TOP = 1_500_000.0
BASE_RUNNER_TOP = 5_000_000.0
STRETCH_TOP = 20_000_000.0
PUMP_GRADUATE_SOL = 85.0

JUNK_BASE = {
    "sol",
    "wsol",
    "eth",
    "weth",
    "bnb",
    "wbnb",
    "usdc",
    "usdt",
    "dai",
    "usd1",
    "wbtc",
    "btc",
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _safe(v: float | int | None) -> float:
    try:
        if v is None:
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _ratio(a: float, b: float) -> float:
    if b <= 0:
        return 0.0
    return a / b


def _tx_buy_pressure(tx: TxWindow) -> tuple[float, int]:
    buys = tx.buys + tx.sells
    if buys <= 0:
        return 0.0, tx.buyers
    return tx.buys / buys, tx.buyers


def _already_extended(mc: float) -> float:
    """How many times the token already ran from a typical micro launch."""
    return _ratio(mc, TYPICAL_LAUNCH_MC)


def age_seconds(token: TokenSnapshot, now_ms: int | None = None) -> float:
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    if token.created_at_ms <= 0:
        return 0.0
    return max(0.0, (now - token.created_at_ms) / 1000.0)


def _band(mc: float) -> str:
    if mc <= 25_000:
        return "激进百倍仓"
    if mc <= 80_000:
        return "标准百倍仓"
    return "长尾百倍仓"


def _grade(total: int, passed: bool) -> str:
    if not passed:
        return "X"
    if total >= 82:
        return "S"
    if total >= 70:
        return "A"
    if total >= 58:
        return "B"
    if total >= 45:
        return "C"
    return "D"


def _pump_progress(token: TokenSnapshot) -> float | None:
    if not token.pump:
        return None
    if token.pump.complete:
        return 1.0
    if token.pump.real_sol > 0:
        return _clamp(token.pump.real_sol / PUMP_GRADUATE_SOL, 0.0, 1.0)
    mc = token.cap()
    if mc > 0:
        return _clamp(mc / 69_000.0, 0.0, 1.0)
    return None


def _hard_kills(token: TokenSnapshot, age_sec: float) -> list[str]:
    reasons: list[str] = []
    mc = token.cap()
    symbol = (token.symbol or "").strip().lower()
    name = (token.name or "").strip().lower()

    if symbol in JUNK_BASE or name in JUNK_BASE:
        reasons.append("报价资产/稳定币，不是迷因标的")
    if mc < MIN_MC:
        reasons.append(f"市值 ${mc:,.0f} 过低，更像空池或骗量，不是可执行的百倍入口")
    if mc > MAX_MC:
        reasons.append(
            f"市值 ${mc:,.0f} 再 100x 需要 ${mc * 100:,.0f}，超出迷因币常态终点"
        )
    if age_sec and age_sec < MIN_AGE_SEC:
        reasons.append("开盘不足 6 分钟，仍在狙击/捆绑抛压带，不作为百倍入口")
    if age_sec > MAX_AGE_SEC:
        reasons.append("已超过 36 小时仍是微型盘，百倍窗口大概率已经关闭")
    if token.liquidity_usd is not None and token.liquidity_usd < 0:
        reasons.append("池子储备异常（负流动性），数据不可交易")
    if token.pump and token.pump.nsfw:
        reasons.append("标记 NSFW，排除")

    sec = token.security
    if sec:
        if sec.rugged:
            reasons.append("RugCheck 标记 rugged")
        if sec.freeze_authority:
            reasons.append("冻账户权限未丢，可一键锁卖")
        if sec.mint_authority and not (token.pump and not token.pump.complete):
            reasons.append("增发权限未丢，可无限稀释")
        if sec.lp_locked_pct is not None and sec.lp_locked_pct < 80 and not token.pump:
            reasons.append(f"LP 仅锁定 {sec.lp_locked_pct:.0f}%，微型盘可直接撤池")
        severe = [r for r in sec.risks if any(k in r.lower() for k in ("honeypot", "scam", "rug", "freeze", "mint"))]
        if severe:
            reasons.append("安全扫描命中高危项: " + ", ".join(severe[:3]))
        if sec.top_holder_pct and sec.top_holder_pct >= 35 and not token.pump:
            reasons.append(f"最大持仓 {sec.top_holder_pct:.0f}%（非曲线仓），筹码过于集中")

    buyers = max(token.tx_m5.buyers, token.tx_m15.buyers, token.tx_h1.buyers)
    buys = max(token.tx_m5.buys, token.tx_m15.buys, token.tx_h1.buys)
    crowd = buyers or buys
    if crowd < 5 and token.volume_h1 < 400:
        reasons.append("几乎没有真实买盘，更像死盘或自买自卖")

    if token.volume_h1 > 0 and mc > 0:
        if token.volume_h1 > mc * 40 and buyers < 12:
            reasons.append("成交额相对市值夸张且独立买家过少，骗量特征")

    if token.change_m5 <= -40 and token.tx_m5.sells > token.tx_m5.buys:
        reasons.append("5 分钟暴跌且卖盘主导，正在出货")

    if _already_extended(mc) >= 40:
        reasons.append(
            f"相对典型开盘市值已涨约 {_already_extended(mc):.0f}x，从此处再 100x 需要百亿级终点"
        )

    return reasons


def _gene_room(mc: float) -> Gene:
    """Geometric room for a 100x from the current print."""
    # Peak score when 100x lands between $0.8M and $4M (common local tops).
    x100 = mc * 100
    if 8_000 <= mc <= 35_000:
        score = 24
        reason = f"现价市值 ${mc:,.0f}，100x 只需到 ${x100:,.0f}，落在迷因币最常见的局部顶部带"
    elif 5_000 <= mc < 8_000:
        score = 18
        reason = f"市值 ${mc:,.0f} 极早，100x 空间最大，但空池/砸盘概率同步升高"
    elif 35_000 < mc <= 80_000:
        score = 16
        reason = f"市值 ${mc:,.0f}，100x 对应 ${x100:,.0f}，需要成为出圈 runner"
    elif 80_000 < mc <= 150_000:
        score = 9
        reason = f"市值 ${mc:,.0f}，100x 对应 ${x100:,.0f}，只有强叙事/CEX 级传播才够得到"
    else:
        score = 4
        reason = f"市值 ${mc:,.0f} 对 100x 已经偏贵"
    return Gene("room", "百倍空间", score, 24, reason)


def _gene_window(age_sec: float) -> Gene:
    minutes = age_sec / 60
    if 12 <= minutes <= 90:
        score, reason = 14, f"已开盘 {minutes:.0f} 分钟：狙击盘出完，第二波发现盘通常在这一段"
    elif 8 <= minutes < 12:
        score, reason = 10, f"开盘 {minutes:.0f} 分钟，刚离开捆绑区，仍要防第一波砸盘"
    elif 90 < minutes <= 360:
        score, reason = 11, f"开盘 {minutes:.0f} 分钟，若买盘仍在加速，属于延续型百倍窗口"
    elif 6 <= minutes < 8:
        score, reason = 7, f"开盘仅 {minutes:.0f} 分钟，时间窗边缘"
    elif 360 < minutes <= 720:
        score, reason = 7, f"开盘 {minutes:.1f} 小时，窗口在收，必须看到持续独立买家"
    else:
        score, reason = 3, f"开盘 {minutes:.0f} 分钟，不在黄金发现带"
    return Gene("window", "黄金时间窗", score, 14, reason)


def _gene_flow(token: TokenSnapshot) -> Gene:
    p5, b5 = _tx_buy_pressure(token.tx_m5)
    p15, b15 = _tx_buy_pressure(token.tx_m15)
    p1, b1 = _tx_buy_pressure(token.tx_h1)
    unique_known = max(b5, b15, b1) > 0
    fills = max(token.tx_m5.buys, token.tx_m15.buys, token.tx_h1.buys)
    buyers = max(b5, b15, b1) if unique_known else fills
    unique_vs_fills = _ratio(buyers, max(fills, 1)) if unique_known else 0.45
    score = 0.0
    bits: list[str] = []

    if buyers >= 40:
        score += 7
        bits.append(f"{buyers} 个独立买家，像扩散而不是对倒")
    elif buyers >= 18:
        score += 5
        bits.append(f"{buyers} 个独立买家，初步扩散")
    elif buyers >= 8:
        score += 3
        bits.append(f"仅 {buyers} 个独立买家，热度刚起")
    else:
        bits.append(f"独立买家 {buyers}，热度不足")

    pressure = p5 or p15 or p1
    if pressure >= 0.68:
        score += 6
        bits.append(f"买盘占比 {pressure:.0%}，主动买入")
    elif pressure >= 0.55:
        score += 4
        bits.append(f"买盘占比 {pressure:.0%}，略偏多")
    elif pressure >= 0.45:
        score += 2
        bits.append(f"买盘占比 {pressure:.0%}，拉锯")
    else:
        bits.append(f"买盘占比 {pressure:.0%}，卖压占优")

    if unique_vs_fills >= 0.55:
        score += 5
        bits.append("成交笔数和独立地址接近，更像真人")
    elif unique_vs_fills >= 0.3:
        score += 3
        bits.append("部分地址多次成交，轻度刷量可能")
    else:
        bits.append("少量地址贡献大量成交，刷量嫌疑")

    mc = token.cap()
    if 0.05 <= _ratio(token.volume_h1, mc) <= 1.2 and token.volume_h1 >= 800:
        score += 2
        bits.append("换手健康，既有成交又没有离奇放量")

    return Gene("flow", "真实买盘", _clamp(score, 0, 20), 20, "；".join(bits))


def _gene_liquidity(token: TokenSnapshot) -> Gene:
    mc = token.cap()
    liq = token.liquidity_usd
    bits: list[str] = []
    score = 0.0
    progress = _pump_progress(token)

    if token.pump and not token.pump.complete:
        if progress is None:
            score += 5
            bits.append("Pump.fun 内盘，曲线本身锁死撤池")
        elif 0.18 <= progress <= 0.72:
            score += 12
            bits.append(f"内盘进度 {progress:.0%}，既不是刚开的死盘，也还没到毕业砸盘点")
        elif 0.08 <= progress < 0.18:
            score += 7
            bits.append(f"内盘进度 {progress:.0%}，偏早，需要买盘继续跟上")
        elif progress > 0.72:
            score += 6
            bits.append(f"内盘进度 {progress:.0%}，临近毕业，注意毕业瞬间抛压")
        else:
            score += 3
            bits.append("内盘几乎没进度")
    elif token.pump and token.pump.complete:
        score += 8
        bits.append("刚毕业/已外盘，LP 由协议打出，结构好于手建池")
        if liq and mc and 0.12 <= _ratio(liq, mc) <= 0.7:
            score += 3
            bits.append(f"流动性/市值 { _ratio(liq, mc):.0%}，可进出")
    else:
        if liq is None or liq < 2500:
            bits.append("外盘流动性过薄或缺失")
        else:
            ratio = _ratio(liq, mc) if mc else 0
            if 0.18 <= ratio <= 0.55:
                score += 8
                bits.append(f"流动性 ${liq:,.0f}，占市值 {ratio:.0%}，结构健康")
            elif 0.08 <= ratio < 0.18:
                score += 5
                bits.append(f"流动性偏薄（{ratio:.0%}），滑点会吃掉小资金优势")
            elif ratio > 0.55:
                score += 4
                bits.append("流动性相对市值过厚，要么是锁仓叙事，要么是出货垫子")
            else:
                bits.append("流动性与市值不匹配")
        sec = token.security
        if sec and sec.lp_locked_pct is not None:
            if sec.lp_locked_pct >= 99:
                score += 4
                bits.append("LP 接近全锁")
            elif sec.lp_locked_pct >= 80:
                score += 2
                bits.append(f"LP 锁定 {sec.lp_locked_pct:.0f}%")

    return Gene("liq", "曲线/流动性", _clamp(score, 0, 12), 12, "；".join(bits) or "流动性信息不足")


def _gene_security(token: TokenSnapshot) -> Gene:
    sec = token.security
    bits: list[str] = []
    score = 8.0  # baseline when no report yet (pump curve is structurally safer)
    if token.pump and not token.pump.complete:
        score = 11
        bits.append("内盘由协议托管，无法传统撤池")
    if sec is None:
        bits.append("尚未拉到持仓/权限报告，安全分按结构给基数")
        return Gene("sec", "安全结构", score if token.pump else 6, 16, "；".join(bits))

    score = 0.0
    if not sec.mint_authority:
        score += 5
        bits.append("铸造权已丢")
    else:
        bits.append("铸造权仍在")
    if not sec.freeze_authority:
        score += 4
        bits.append("冻结权已丢")
    else:
        bits.append("冻结权仍在")
    if sec.lp_locked_pct is not None and sec.lp_locked_pct >= 99:
        score += 3
        bits.append("LP 全锁")
    elif token.pump:
        score += 3
        bits.append("曲线仓位不可被创建者抽走")
    if sec.holders:
        if 40 <= sec.holders <= 900:
            score += 2
            bits.append(f"{sec.holders} 个持仓地址，处于扩散前期")
        elif sec.holders > 900:
            score += 1
            bits.append(f"持仓地址 {sec.holders}，可能已经较散")
        else:
            bits.append(f"持仓地址仅 {sec.holders}")
    if sec.top_holder_pct is not None:
        # Pump bonding curve itself often sits at ~50%+; ignore that.
        if token.pump and not token.pump.complete:
            score += 1
            bits.append("最大仓是曲线本身，不记作庄")
        elif sec.top_holder_pct < 8:
            score += 2
            bits.append(f"最大持仓 {sec.top_holder_pct:.1f}%")
        elif sec.top_holder_pct < 18:
            score += 1
            bits.append(f"最大持仓 {sec.top_holder_pct:.1f}%，可接受")
        else:
            bits.append(f"最大持仓 {sec.top_holder_pct:.1f}%，需防砸")
    if sec.score_normalised is not None:
        if sec.score_normalised <= 1:
            score += 0  # rugcheck: lower is safer in some reports; observed 1 = clean
            bits.append(f"RugCheck 归一分 {sec.score_normalised}")
        elif sec.score_normalised >= 10:
            bits.append(f"RugCheck 风险分偏高 ({sec.score_normalised})")
            score = max(0, score - 3)
    if sec.insider_networks and sec.insider_networks >= 8:
        bits.append(f"检测到 {sec.insider_networks} 个内幕关联簇")
        score = max(0, score - 2)
    return Gene("sec", "安全结构", _clamp(score, 0, 16), 16, "；".join(bits))


def _gene_momentum(token: TokenSnapshot) -> Gene:
    bits: list[str] = []
    score = 0.0
    ch5, ch1 = token.change_m5, token.change_h1
    if 8 <= ch1 <= 180:
        score += 4
        bits.append(f"1h {ch1:+.0f}% ，需求已被市场确认，但还没走成垂直泡沫")
    elif 180 < ch1 <= 400:
        score += 2
        bits.append(f"1h {ch1:+.0f}% ，偏热，追高会压缩剩余百倍空间")
    elif ch1 > 400:
        bits.append(f"1h {ch1:+.0f}% ，过热")
    elif -12 <= ch1 < 8:
        score += 3
        bits.append(f"1h {ch1:+.0f}% 横盘吸筹，若买盘仍在属于更好的入口")
    else:
        bits.append(f"1h {ch1:+.0f}% 偏弱")

    if ch5 >= 3 and token.tx_m5.buys >= token.tx_m5.sells:
        score += 3
        bits.append(f"5m {ch5:+.0f}% 且买盘占优，第二波可能正在起")
    elif -8 <= ch5 < 3 and token.tx_m5.buyers >= 4:
        score += 2
        bits.append("5m 回踩但买家还在")
    elif ch5 < -20:
        bits.append("5m 急跌")

    if token.pump and token.pump.ath_mc and token.cap() > 0:
        drawdown = 1 - token.cap() / max(token.pump.ath_mc, 1)
        if 0.15 <= drawdown <= 0.45:
            score += 3
            bits.append(f"相对内盘 ATH 回撤 {drawdown:.0%}，像洗盘而不是死亡")
        elif drawdown > 0.7:
            bits.append("相对 ATH 深回撤，可能已经死")
        elif drawdown < 0.1:
            score += 1
            bits.append("接近内盘 ATH")

    return Gene("mom", "动量结构", _clamp(score, 0, 10), 10, "；".join(bits) or "动量中性")


def _gene_ignition(token: TokenSnapshot) -> Gene:
    score = 0.0
    bits: list[str] = []
    if token.has_profile or token.image:
        score += 1
        bits.append("有基础资料")
    if token.socials or token.websites:
        score += 1
        bits.append("有外链/社交")
    if token.boost_amount > 0:
        score += 1
        bits.append(f"Dex 助推 {token.boost_amount}")
    if token.pump and token.pump.reply_count >= 15:
        score += 1
        bits.append(f"内盘评论 {token.pump.reply_count}")
    elif token.pump and token.pump.livestream:
        score += 1
        bits.append("正在直播")
    if score == 0:
        bits.append("链上热度尚未被社交点燃（不一定是坏事）")
    return Gene("ignite", "传播点火", _clamp(score, 0, 4), 4, "；".join(bits))


def feasibility_of_100x(mc: float) -> float:
    target = mc * 100
    if target <= CONSERVATIVE_TOP:
        return 0.92
    if target <= BASE_RUNNER_TOP:
        return 0.72
    if target <= 10_000_000:
        return 0.45
    if target <= STRETCH_TOP:
        return 0.22
    return 0.08


def score_token(token: TokenSnapshot, now_ms: int | None = None) -> ScoreCard:
    mc = max(token.cap(), 0.0)
    age_sec = age_seconds(token, now_ms)
    kills = _hard_kills(token, age_sec)
    genes = [
        _gene_room(mc),
        _gene_window(age_sec),
        _gene_flow(token),
        _gene_liquidity(token),
        _gene_security(token),
        _gene_momentum(token),
        _gene_ignition(token),
    ]
    raw = sum(g.score for g in genes)
    total = int(round(_clamp(raw, 0, 100)))
    passed = not kills
    if not passed:
        total = min(total, 44)

    x100 = mc * 100
    feas = feasibility_of_100x(mc) if passed else 0.0
    if passed and feas >= 0.7 and total >= 70:
        verdict = "结构接近历史百倍入口，仍可能归零"
        thesis = (
            f"现在买，100x 只要求市值到 ${x100:,.0f}。"
            f"这落在迷因币常见终点下沿，时间窗和买盘结构也还没走完。"
        )
    elif passed and feas >= 0.4:
        verdict = "有百倍几何空间，需要成为出圈盘"
        thesis = (
            f"100x 目标市值 ${x100:,.0f}。空间还在，但必须靠第二波传播，"
            f"不能只靠开盘情绪。"
        )
    elif passed:
        verdict = "空间勉强够，路径很窄"
        thesis = f"100x 需要冲到 ${x100:,.0f}，这已经接近迷因币异常终点。"
    else:
        verdict = "未通过百倍入口门禁"
        thesis = "；".join(kills)

    return ScoreCard(
        total=total,
        grade=_grade(total, passed),
        passed=passed,
        kill_reasons=kills,
        genes=genes,
        x100_target_mc=x100,
        x_if_1m5=_ratio(CONSERVATIVE_TOP, mc) if mc else 0,
        x_if_5m=_ratio(BASE_RUNNER_TOP, mc) if mc else 0,
        x_if_20m=_ratio(STRETCH_TOP, mc) if mc else 0,
        feasibility=round(feas, 3),
        band=_band(mc) if mc else "—",
        verdict=verdict,
        thesis=thesis,
    )


def rank(tokens: Iterable[TokenSnapshot], now_ms: int | None = None) -> list[tuple[TokenSnapshot, ScoreCard, float]]:
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    out = []
    for t in tokens:
        card = score_token(t, now)
        out.append((t, card, age_seconds(t, now) / 60.0))
    out.sort(key=lambda row: (row[1].passed, row[1].total, row[1].feasibility), reverse=True)
    return out
