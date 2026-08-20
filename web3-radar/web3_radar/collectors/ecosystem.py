from __future__ import annotations

import re
from typing import Any, Iterable

# Short tokens need word boundaries so "eth" does not match "something".
BTC_WORDS = (
    "bitcoin",
    "btc",
    "lightning",
    "stacks",
    "stx",
    "sbtc",
    "babylon",
    "bitvm",
    "rgb",
    "runes",
    "brc-20",
    "brc20",
    "ordinals",
    "botanix",
    "citrea",
    "merlin",
    "bouncebit",
    "bitlayer",
    "rootstock",
    "rsk",
    "mezo",
    "bevm",
    "nubit",
    "lombard",
    "fractal bitcoin",
    "bsquared",
    "b^2",
    "b2 network",
)
ETH_WORDS = (
    "ethereum",
    "eth",
    "arbitrum",
    "optimism",
    "zksync",
    "zk sync",
    "scroll",
    "linea",
    "starknet",
    "polygon",
    "manta",
    "blast",
    "taiko",
    "mantle",
    "megaeth",
    "eigenlayer",
    "ether.fi",
    "etherfi",
    "restaking",
    "rollup",
    "layer2",
    "layer 2",
    "op stack",
    "op-stack",
    "zkevm",
    "zk-evm",
    "unichain",
    "worldchain",
    "swellchain",
    "base l2",
    "on base",
    "coinbase l2",
)
SOL_WORDS = (
    "solana",
    "sol",
    "svm",
    "pump.fun",
    "pumpfun",
    "raydium",
    "jupiter",
    "jup.ag",
    "orca",
    "jito",
    "kamino",
    "marinade",
    "metaplex",
    "helius",
    "launchlab",
    "pump fun",
    "sol 生态",
    "sol生态",
)

BTC_CHAINS = {
    "bitcoin",
    "btc",
    "stacks",
    "rootstock",
    "merlin",
    "bitlayer",
    "bob",
    "core",
    "btr",
    "bouncebit",
    "botanix",
    "citrea",
    "fractal bitcoin",
    "b2",
    "bsquared",
    "lightning",
    "mezo",
    "bevm",
}
ETH_CHAINS = {
    "ethereum",
    "arbitrum",
    "optimism",
    "base",
    "zksync",
    "zksync era",
    "scroll",
    "linea",
    "starknet",
    "polygon",
    "polygon zkevm",
    "manta",
    "blast",
    "mode",
    "taiko",
    "mantle",
    "op mainnet",
    "unichain",
    "world chain",
    "ink",
    "swellchain",
    "megaeth",
    "etherlink",
}
SOL_CHAINS = {
    "solana",
    "eclipse",
    "soon",
    "sonic",
    "sonic svm",
    "soon svm",
}

_AIRDROP_LABEL = {
    "bitcoin": "比特币生态",
    "ethereum": "ETH 生态",
    "btc-eth": "BTC+ETH",
    "other": "非重点",
}


def _blob(*parts: Any) -> str:
    bits: list[str] = []
    for part in parts:
        if part in (None, ""):
            continue
        if isinstance(part, (list, tuple, set)):
            bits.extend(str(x) for x in part if x not in (None, ""))
        elif isinstance(part, dict):
            bits.extend(str(v) for v in part.values() if v not in (None, ""))
        else:
            bits.append(str(part))
    return " ".join(bits).lower()


def _chain_names(chains: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(chains, str):
        chains = [chains]
    for item in chains or []:
        if isinstance(item, dict):
            item = item.get("name") or item.get("chain") or ""
        text = str(item or "").strip().lower()
        if text:
            names.add(text)
    return names


def _has_word(text: str, word: str) -> bool:
    w = word.lower().strip()
    if not w:
        return False
    if " " in w or "-" in w or "." in w or len(w) >= 5:
        return w in text
    return re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text) is not None


def _has_any(text: str, words: Iterable[str]) -> bool:
    return any(_has_word(text, w) for w in words)


def classify_btc_eth(*parts: Any, chains: Any = None) -> str:
    names = _chain_names(chains)
    btc = bool(names & BTC_CHAINS) or _has_any(_blob(*parts, *names), BTC_WORDS)
    eth = bool(names & ETH_CHAINS) or _has_any(_blob(*parts, *names), ETH_WORDS)
    # "base" as a chain name is ETH L2; as free text it is too noisy.
    if "base" in names:
        eth = True
    if btc and eth:
        return "btc-eth"
    if btc:
        return "bitcoin"
    if eth:
        return "ethereum"
    return "other"


def airdrop_eco_label(code: str) -> str:
    return _AIRDROP_LABEL.get(code or "other", "非重点")


def is_btc_or_eth(*parts: Any, chains: Any = None) -> bool:
    return classify_btc_eth(*parts, chains=chains) != "other"


def is_solana(*parts: Any, chains: Any = None) -> bool:
    names = _chain_names(chains)
    if names & SOL_CHAINS:
        return True
    return _has_any(_blob(*parts, *names), SOL_WORDS)
