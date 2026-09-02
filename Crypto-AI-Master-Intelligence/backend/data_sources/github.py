"""GitHub repository activity. Token optional; unauthenticated is rate-limited."""

from __future__ import annotations

from backend.core.config import get_settings
from backend.core.enums import DataQuality, SourceStatus
from backend.data_sources.base import DataProvider, QualityEnvelope, envelope
from backend.data_sources.http import HttpClient


class GitHubProvider(DataProvider):
    name = "github"

    def __init__(self) -> None:
        settings = get_settings()
        cfg = settings.yaml_config.get("providers", {}).get("github", {})
        self.base = str(cfg.get("base", "https://api.github.com")).rstrip("/")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "Crypto-AI-Master-Intelligence"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        self.http = HttpClient(self.name, float(cfg.get("timeout_sec", 20)), headers)

    def required_keys(self) -> list[str]:
        return []

    async def health(self) -> QualityEnvelope:
        return await self.http.get_json(f"{self.base}/rate_limit", expect=dict)

    async def repo(self, owner: str, name: str) -> QualityEnvelope:
        raw = await self.http.get_json(f"{self.base}/repos/{owner}/{name}", expect=dict)
        if not raw.ok:
            return raw
        item = raw.payload
        parsed = {
            "full_name": item.get("full_name"),
            "html_url": item.get("html_url"),
            "stars": item.get("stargazers_count"),
            "forks": item.get("forks_count"),
            "open_issues": item.get("open_issues_count"),
            "pushed_at": item.get("pushed_at"),
            "created_at": item.get("created_at"),
            "language": item.get("language"),
            "subscribers": item.get("subscribers_count"),
        }
        return envelope(self.name, status=SourceStatus.OK, payload=parsed, data_quality=DataQuality.OK, confidence=1.0)
