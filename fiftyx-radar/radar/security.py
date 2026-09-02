from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable, Optional

from .models import ScoredToken, SecurityReport

GOPLUS = "https://api.gopluslabs.io/api/v1"
HONEYPOT_IS = "https://api.honeypot.is/v2/IsHoneypot"
RUGCHECK = "https://api.rugcheck.xyz/v1/tokens"
USER_AGENT = "fiftyx-radar/0.2 (contract backdoor screen; not investment advice)"

EVM_CHAIN_IDS = {
    "eth": "1",
    "ethereum": "1",
    "bsc": "56",
    "bnb": "56",
    "polygon": "137",
    "matic": "137",
    "arbitrum": "42161",
    "optimism": "10",
    "avalanche": "43114",
    "avax": "43114",
    "fantom": "250",
    "base": "8453",
    "cronos": "25",
    "gnosis": "100",
    "linea": "59144",
    "scroll": "534352",
    "zksync": "324",
    "blast": "81457",
    "mantle": "5000",
    "opbnb": "204",
    "unichain": "130",
    "abstract": "2741",
    "hyperevm": "999",
    "hyperliquid": "999",
    "hype": "999",
    "ink": "57073",
    "soneium": "1868",
    "worldchain": "480",
    "sei": "1329",
    "taiko": "167000",
}

SOLANA_CHAINS = {"solana", "sol"}
RENOUNCED_OWNERS = {
    "",
    "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dead",
    "0x000000000000000000000000000000000000dEaD",
}

# Confirmed trap / admin-kill switches. Owner-exists alone is not enough.
EVM_BACKDOOR_FLAGS = (
    ("is_honeypot", "蜜罐：买入后无法正常卖出"),
    ("cannot_sell_all", "限制卖出数量，典型出货后门"),
    ("cannot_buy", "买入被合约拦截"),
    ("owner_change_balance", "管理员可改地址余额"),
    ("hidden_owner", "隐藏管理员，可随时接管"),
    ("selfdestruct", "合约可自毁"),
    ("is_blacklisted", "可拉黑地址，等于定向冻结"),
    ("transfer_pausable", "可暂停转账"),
    ("slippage_modifiable", "管理员可改税率，可调到 100%"),
    ("personal_slippage_modifiable", "可对单个地址改税"),
    ("is_airdrop_scam", "被标记为空投骗局"),
    ("trading_cooldown", "交易冷却，可锁死卖出窗口"),
)

SOLANA_STATUS_BACKDOORS = (
    ("mintable", "铸币权未放弃，可无限增发"),
    ("freezable", "冻结权未放弃，可冻钱包"),
    ("closable", "可关闭代币账户"),
    ("transfer_fee_upgradable", "转账税率可被管理员改写"),
    ("default_account_state_upgradable", "默认账户状态可改，可批量冻结"),
    ("balance_mutable_authority", "可改持仓余额"),
    ("transfer_hook_upgradable", "Transfer Hook 可升级，能劫持转账"),
)


def _get_json(url: str, timeout: int = 18) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        return None


def _truthy(value: Any) -> bool:
    if isinstance(value, dict):
        return _truthy(value.get("status")) or _truthy(value.get("value")) or _truthy(value.get("malicious_address"))
    if isinstance(value, list):
        return any(_truthy(item) for item in value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def _tax_pct(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).replace("%", "").strip()
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _owner_renounced(owner: Any) -> bool:
    text = str(owner or "").strip()
    return text.lower() in {x.lower() for x in RENOUNCED_OWNERS}


def evm_chain_id(chain: str) -> Optional[str]:
    return EVM_CHAIN_IDS.get((chain or "").lower())


def is_solana(chain: str) -> bool:
    return (chain or "").lower() in SOLANA_CHAINS


def parse_goplus_evm(result: dict[str, Any]) -> SecurityReport:
    findings: list[str] = []
    flags: list[str] = []
    for key, label in EVM_BACKDOOR_FLAGS:
        if _truthy(result.get(key)):
            findings.append(label)
            flags.append(key)

    buy_tax = _tax_pct(result.get("buy_tax"))
    sell_tax = _tax_pct(result.get("sell_tax"))
    if buy_tax >= 15 or sell_tax >= 15:
        findings.append(f"买卖税过高（买 {buy_tax:.0f}% / 卖 {sell_tax:.0f}%），可当后门锁仓")
        flags.append("high_tax")

    owner = result.get("owner_address")
    if _truthy(result.get("is_mintable")) and not _owner_renounced(owner):
        findings.append("铸币权仍在管理员手里，可无限增发砸盘")
        flags.append("mintable_owner")

    if _truthy(result.get("can_take_back_ownership")):
        findings.append("所有权已放弃也可被收回")
        flags.append("can_take_back_ownership")

    if _truthy(result.get("is_proxy")) and not _truthy(result.get("is_open_source")):
        findings.append("未开源代理合约，逻辑可被随时替换")
        flags.append("opaque_proxy")

    note = str(result.get("other_potential_risks") or result.get("note") or "")
    lowered = note.lower()
    if any(word in lowered for word in ("honeypot", "蜜罐", "后门", "backdoor", "hidden mint")):
        findings.append(note[:80])
        flags.append("provider_note")

    has_backdoor = bool(findings)
    return SecurityReport(
        checked=True,
        has_backdoor=has_backdoor,
        verdict="backdoor" if has_backdoor else "clean",
        source="goplus",
        findings=findings,
        flags=flags,
    )


def parse_goplus_solana(result: dict[str, Any]) -> SecurityReport:
    findings: list[str] = []
    flags: list[str] = []
    for key, label in SOLANA_STATUS_BACKDOORS:
        node = result.get(key)
        if _truthy(node):
            findings.append(label)
            flags.append(key)
    hooks = result.get("transfer_hook")
    if isinstance(hooks, list) and hooks:
        findings.append("带 Transfer Hook，转账可被第三方合约劫持")
        flags.append("transfer_hook")
    if _truthy(result.get("default_account_state")) or str(result.get("default_account_state") or "") == "frozen":
        findings.append("默认账户冻结，新买家可能无法卖出")
        flags.append("default_frozen")
    if _truthy(result.get("non_transferable")):
        findings.append("代币不可转让")
        flags.append("non_transferable")
    has_backdoor = bool(findings)
    return SecurityReport(
        checked=True,
        has_backdoor=has_backdoor,
        verdict="backdoor" if has_backdoor else "clean",
        source="goplus-solana",
        findings=findings,
        flags=flags,
    )


def parse_honeypot_is(payload: dict[str, Any]) -> Optional[SecurityReport]:
    summary = payload.get("summary") or payload
    honeypot = False
    if isinstance(summary, dict):
        honeypot = bool(summary.get("honeypot") or summary.get("isHoneypot"))
        risk = str(summary.get("risk") or summary.get("riskLevel") or "").lower()
        if risk in {"honeypot", "high"}:
            honeypot = True
    if payload.get("honeypotResult", {}).get("isHoneypot"):
        honeypot = True
    simulation = payload.get("simulationResult") or {}
    sell_ok = simulation.get("sellTax")
    if simulation.get("isHoneypot") or payload.get("isHoneypot"):
        honeypot = True
    findings = []
    if honeypot:
        findings.append("Honeypot.is 模拟卖出失败，判定蜜罐后门")
    if isinstance(sell_ok, (int, float)) and sell_ok >= 15:
        findings.append(f"模拟卖出税 {sell_ok:.0f}%")
        honeypot = True
    if not findings:
        return SecurityReport(checked=True, has_backdoor=False, verdict="clean", source="honeypot.is")
    return SecurityReport(
        checked=True,
        has_backdoor=True,
        verdict="backdoor",
        source="honeypot.is",
        findings=findings,
        flags=["honeypot"],
    )


def parse_rugcheck(payload: dict[str, Any]) -> Optional[SecurityReport]:
    risks = payload.get("risks") or payload.get("risk") or []
    findings: list[str] = []
    flags: list[str] = []
    danger = {"danger", "warn", "high", "critical"}
    for risk in risks if isinstance(risks, list) else []:
        if not isinstance(risk, dict):
            continue
        level = str(risk.get("level") or risk.get("risk") or "").lower()
        name = str(risk.get("name") or risk.get("id") or "")
        desc = str(risk.get("description") or name)
        lowered = f"{name} {desc}".lower()
        if level in danger or any(
            word in lowered
            for word in ("mint", "freeze", "honeypot", "rugged", "lp", "authority")
        ):
            if any(word in lowered for word in ("mint", "freeze", "honeypot", "rugged", "close", "hook")):
                findings.append(desc[:80] or name)
                flags.append(name or level)
    score = payload.get("score")
    if isinstance(score, (int, float)) and score >= 80 and not findings:
        # rugcheck: higher score is riskier on some versions; keep conservative.
        pass
    if not findings:
        return None
    return SecurityReport(
        checked=True,
        has_backdoor=True,
        verdict="backdoor",
        source="rugcheck",
        findings=findings,
        flags=flags,
    )


def merge_reports(*reports: Optional[SecurityReport]) -> SecurityReport:
    found = [r for r in reports if r and r.checked]
    if not found:
        return SecurityReport()
    findings: list[str] = []
    flags: list[str] = []
    sources: list[str] = []
    has_backdoor = False
    for report in found:
        sources.append(report.source)
        has_backdoor = has_backdoor or report.has_backdoor
        for item in report.findings:
            if item not in findings:
                findings.append(item)
        for item in report.flags:
            if item not in flags:
                flags.append(item)
    return SecurityReport(
        checked=True,
        has_backdoor=has_backdoor,
        verdict="backdoor" if has_backdoor else "clean",
        source="+".join(dict.fromkeys(sources)),
        findings=findings,
        flags=flags,
    )


def _fetch_goplus_evm(chain_id: str, addresses: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(addresses), 20):
        chunk = addresses[i : i + 20]
        joined = ",".join(chunk)
        url = f"{GOPLUS}/token_security/{chain_id}?contract_addresses={urllib.parse.quote(joined)}"
        payload = _get_json(url)
        if not isinstance(payload, dict):
            continue
        result = payload.get("result") or {}
        if isinstance(result, dict):
            for addr, row in result.items():
                if isinstance(row, dict):
                    out[addr.lower()] = row
    return out


def _fetch_goplus_solana(addresses: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(addresses), 10):
        chunk = addresses[i : i + 10]
        joined = ",".join(chunk)
        url = f"{GOPLUS}/solana/token_security?contract_addresses={urllib.parse.quote(joined)}"
        payload = _get_json(url)
        if not isinstance(payload, dict):
            continue
        result = payload.get("result") or {}
        if isinstance(result, dict):
            for addr, row in result.items():
                if isinstance(row, dict):
                    out[addr] = row
                    out[addr.lower()] = row
    return out


def _fetch_honeypot(chain_id: str, address: str) -> Optional[SecurityReport]:
    url = f"{HONEYPOT_IS}?address={urllib.parse.quote(address)}&chainID={chain_id}"
    payload = _get_json(url, timeout=12)
    if not isinstance(payload, dict):
        return None
    return parse_honeypot_is(payload)


def _fetch_rugcheck(address: str) -> Optional[SecurityReport]:
    payload = _get_json(f"{RUGCHECK}/{urllib.parse.quote(address)}/report", timeout=12)
    if not isinstance(payload, dict):
        return None
    return parse_rugcheck(payload)


def token_key(chain: str, address: str) -> tuple[str, str]:
    return ((chain or "").lower(), (address or "").lower())


def scan_security(tokens: Iterable[ScoredToken], *, min_score: int = 50) -> dict[tuple[str, str], SecurityReport]:
    """Check contracts that are close to being recommended. Unknown chain = unchecked, not a reject."""
    candidates = [
        item
        for item in tokens
        if item.score.total >= min_score and (item.token.address or "").strip()
    ]
    reports: dict[tuple[str, str], SecurityReport] = {}
    evm_groups: dict[str, list[str]] = {}
    solana_addrs: list[str] = []
    for item in candidates:
        chain = (item.token.chain or "").lower()
        address = item.token.address.strip()
        if is_solana(chain):
            solana_addrs.append(address)
            continue
        chain_id = evm_chain_id(chain)
        if not chain_id:
            reports[token_key(chain, address)] = SecurityReport(
                checked=False,
                verdict="unchecked",
                source="none",
                findings=["该链暂无公开后门检测覆盖，未当作通过，也不直接剔除"],
            )
            continue
        evm_groups.setdefault(chain_id, []).append(address)

    goplus_evm: dict[tuple[str, str], dict[str, Any]] = {}
    for chain_id, addrs in evm_groups.items():
        unique = list(dict.fromkeys(a.lower() for a in addrs))
        fetched = _fetch_goplus_evm(chain_id, unique)
        for addr, row in fetched.items():
            goplus_evm[(chain_id, addr)] = row

    goplus_sol: dict[str, dict[str, Any]] = {}
    if solana_addrs:
        goplus_sol = _fetch_goplus_solana(list(dict.fromkeys(solana_addrs)))

    extras: dict[tuple[str, str], SecurityReport] = {}

    def extra_job(item: ScoredToken) -> tuple[tuple[str, str], Optional[SecurityReport]]:
        chain = (item.token.chain or "").lower()
        address = item.token.address.strip()
        key = token_key(chain, address)
        if is_solana(chain) and address not in goplus_sol and address.lower() not in goplus_sol:
            return key, _fetch_rugcheck(address)
        chain_id = evm_chain_id(chain)
        if chain_id and (chain_id, address.lower()) not in goplus_evm:
            return key, _fetch_honeypot(chain_id, address)
        return key, None

    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(extra_job, item) for item in candidates]
        for fut in as_completed(futs):
            try:
                key, extra = fut.result()
            except Exception:
                continue
            if extra:
                extras[key] = extra

    for item in candidates:
        chain = (item.token.chain or "").lower()
        address = item.token.address.strip()
        key = token_key(chain, address)
        if key in reports:
            continue
        primary = None
        if is_solana(chain):
            row = goplus_sol.get(address) or goplus_sol.get(address.lower())
            if row:
                primary = parse_goplus_solana(row)
        else:
            chain_id = evm_chain_id(chain)
            row = goplus_evm.get((chain_id or "", address.lower())) if chain_id else None
            if row:
                primary = parse_goplus_evm(row)
        reports[key] = merge_reports(primary, extras.get(key))
        if not reports[key].checked:
            reports[key] = SecurityReport(
                checked=False,
                verdict="unchecked",
                source="none",
                findings=["安全接口没有返回结果，未完成后门确认"],
            )
    return reports


def apply_security(
    items: Iterable[ScoredToken],
    reports: dict[tuple[str, str], SecurityReport],
) -> list[ScoredToken]:
    scored = list(items)
    for item in scored:
        key = token_key(item.token.chain, item.token.address)
        report = reports.get(key)
        if report is None:
            continue
        item.security = report
        if report.has_backdoor:
            item.score.priority = "skip"
            item.score.watch = False
            if "合约后门" not in item.score.tags:
                item.score.tags.append("合约后门")
            item.score.warnings.insert(0, "合约留有后门，不再推荐")
            for finding in report.findings[:3]:
                if finding not in item.score.warnings:
                    item.score.warnings.append(finding)
        elif report.checked and report.verdict == "clean":
            if "未见后门" not in item.score.tags:
                item.score.tags.append("未见后门")
        elif report.verdict == "unchecked":
            if "未验合约" not in item.score.tags:
                item.score.tags.append("未验合约")
    return scored


def rejected_backdoors(items: Iterable[ScoredToken]) -> list[ScoredToken]:
    return [item for item in items if item.security and item.security.has_backdoor]
