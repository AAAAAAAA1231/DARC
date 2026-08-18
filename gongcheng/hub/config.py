from __future__ import annotations

import sys
from pathlib import Path


def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def _writable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = _bundle_dir()
ROOT_DIR = _writable_root()
DATA_DIR = ROOT_DIR / "data"
_STATIC = [
    Path(__file__).resolve().parent / "static",
    APP_DIR / "hub" / "static",
    APP_DIR / "static",
]
STATIC_DIR = next((p for p in _STATIC if p.exists()), _STATIC[0])

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8788

MODULES = [
    {"id": "qingbiao", "name": "清标", "desc": "经济标 / 技术标比对、图纸工程量", "path": "/qingbiao/"},
    {"id": "anquan", "name": "安全", "desc": "隐患台账、整改闭环、纠偏", "path": "/anquan/"},
    {"id": "jindu", "name": "进度", "desc": "WBS、横道图、施工日志", "path": "/jindu/"},
    {"id": "zhiliang", "name": "质量", "desc": "问题台账、整改复查、通病纠偏", "path": "/zhiliang/"},
    {"id": "chengben", "name": "成本", "desc": "目标/动态/已发生、节超纠偏", "path": "/chengben/"},
    {"id": "jishubiao", "name": "技术标", "desc": "按现行规范生成施工组织设计初稿", "path": "/jishubiao/"},
]


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for item in MODULES:
        (DATA_DIR / item["id"]).mkdir(parents=True, exist_ok=True)
