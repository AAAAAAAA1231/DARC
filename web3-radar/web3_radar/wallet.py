from __future__ import annotations

from typing import Any

from web3_radar import db
from web3_radar.config import load_settings

# Conservative spend presets per category. Actual on-chain send always happens
# in the browser wallet page after the user (or explicit auto-confirm) approves.
ACTION_SPECS = {
    "airdrop": {
        "action": "interact",
        "title": "空投交互",
        "description": "打开项目页面/合约交互，不自动授权无限额度。",
    },
    "launch": {
        "action": "presale",
        "title": "打新认购",
        "description": "按设置中的单笔上限生成认购意图，需钱包确认。不会使用私钥。",
    },
    "watch": {
        "action": "presale",
        "title": "自动打新",
        "description": "盯盘到发射时间后生成认购意图，需钱包确认。不会索取或使用私钥。",
    },
    "meme": {
        "action": "swap",
        "title": "妖币买入",
        "description": "按流动性与上限生成买入意图，需钱包确认。",
    },
    "contract": {
        "action": "futures_note",
        "title": "合约信号跟单备注",
        "description": "链上钱包无法直接下币安合约单；生成交易备忘并等待手动/API 执行。",
    },
    "ambassador": {
        "action": "open_apply",
        "title": "打开大使申请",
        "description": "记录申请动作，不发起链上交易。",
    },
}


def wallet_status() -> dict[str, Any]:
    s = load_settings()
    return {
        "address": s.get("wallet_address") or "",
        "chain": s.get("wallet_chain") or "ethereum",
        "connected": bool(s.get("wallet_address")),
        "auto_participate": bool(s.get("auto_participate")),
        "auto_require_confirm": bool(s.get("auto_require_confirm", True)),
        "auto_max_spend_usd": float(s.get("auto_max_spend_usd") or 50),
        "supported_wallets": ["OKX Wallet", "MetaMask", "Rabby", "WalletConnect 兼容注入钱包"],
    }


def build_intent(category: str, item: dict[str, Any]) -> dict[str, Any]:
    spec = ACTION_SPECS.get(category) or ACTION_SPECS["airdrop"]
    settings = load_settings()
    max_spend = float(settings.get("auto_max_spend_usd") or 50)
    chain = item.get("chain") or item.get("chain_id") or settings.get("wallet_chain") or "ethereum"
    token = item.get("token_address") or ""
    return {
        "category": category,
        "action": spec["action"],
        "title": f"{spec['title']} · {item.get('symbol') or item.get('name') or item.get('title') or item.get('key')}",
        "description": spec["description"],
        "chain": chain,
        "to": token,
        "max_spend_usd": max_spend,
        "item": {
            "key": item.get("key"),
            "name": item.get("name") or item.get("symbol"),
            "url": item.get("url"),
            "price_usd": item.get("price_usd") or item.get("price") or item.get("entry"),
            "decision": item.get("decision"),
        },
        "requires_wallet": spec["action"] in {"swap", "presale", "interact"},
        "warning": "所有链上交易必须由 OKX 等钱包二次确认。本程序不会索取助记词或私钥。",
    }


async def enqueue_participate(category: str, item: dict[str, Any], auto: bool = False) -> dict[str, Any]:
    settings = load_settings()
    intent = build_intent(category, item)
    if auto and not settings.get("auto_participate"):
        raise ValueError("未开启自动参加。请在设置中打开，且默认仍需钱包确认。")
    status = "pending"
    if settings.get("auto_require_confirm", True) or not auto:
        status = "pending"
    task = await db.add_wallet_task(
        category=category,
        item_key=str(item.get("key") or item.get("symbol") or item.get("name")),
        title=intent["title"],
        action=intent["action"],
        payload=intent,
    )
    if status != task["status"]:
        await db.update_wallet_task(task["id"], status=status)
        task["status"] = status
    return task
