from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from suite.boot import setup_sys_path

setup_sys_path()

from suite.football_api import prediction_to_dict, status as football_status
from suite.radar_api import status as radar_status


class SuiteTests(unittest.TestCase):
    def test_prediction_to_dict_formats_probs(self):
        result = SimpleNamespace(
            league_cn="西甲",
            kickoff="周日 21:00",
            home_cn="巴塞罗那",
            away_cn="马竞",
            pred_1x2_90="主胜",
            final_1x2="主胜",
            final_score="2-1",
            p_home=0.52,
            p_draw=0.26,
            p_away=0.22,
            confidence=0.61,
            factors=["主场", "状态"],
            final_note="",
            weather="晴",
        )
        row = prediction_to_dict(result)
        self.assertEqual(row["match"], "巴塞罗那 vs 马竞")
        self.assertEqual(row["probs"], "52% / 26% / 22%")
        self.assertEqual(row["league_cn"], "西甲")

    def test_modules_start_idle(self):
        self.assertIn(football_status()["status"], {"idle", "running", "done", "error"})
        self.assertIn(radar_status()["status"], {"idle", "running", "done", "error"})


class HubHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from fastapi.testclient import TestClient
        from suite.server import app

        cls.client = TestClient(app)

    def test_health_lists_modules(self):
        payload = self.client.get("/api/health").json()
        self.assertEqual(payload["app"], "工作台")
        self.assertEqual(payload["modules"], ["radar", "football", "contracts", "airdrops", "launches"])

    def test_hub_page_has_tabs(self):
        page = self.client.get("/").text
        self.assertIn("50 倍雷达", page)
        self.assertIn("三大联赛", page)
        self.assertIn("合约分析", page)
        self.assertIn("空投推荐", page)
        self.assertIn("打新", page)
        self.assertIn("刷新打新", page)
        self.assertIn("四年周期", page)
        self.assertIn("刷新开单", page)
        self.assertIn("持仓时长", page)
        self.assertNotIn("历史四轮周期", page)

    def test_airdrop_status_starts_idle(self):
        payload = self.client.get("/api/airdrops/status").json()
        self.assertIn(payload["status"], {"idle", "running", "done", "error"})

    def test_launch_status_starts_idle(self):
        payload = self.client.get("/api/launches/status").json()
        self.assertIn(payload["status"], {"idle", "running", "done", "error"})
        self.assertEqual(payload.get("lookback_days"), 30)

    def test_empty_launch_scan_keeps_previous_rows(self):
        from unittest.mock import patch

        from suite import launch_api

        sample = [{"rank": 1, "id": "keep", "score": 40, "handle": "alpha", "text": "crypto presale"}]
        with launch_api._lock:
            launch_api._job.update(items=sample, count=1, status="done")

        async def empty_hunt(lookback_days: int = 30):
            return {
                "count": 0,
                "items": [],
                "errors": [],
                "sources": [],
                "since": "2026-08-01",
                "lookback_days": lookback_days,
                "disclaimer": "",
            }

        with patch("suite.launch_api.hunt_launches", empty_hunt):
            launch_api._run()
        payload = launch_api.status()
        self.assertEqual(payload["status"], "done")
        self.assertEqual(payload["items"][0]["id"], "keep")
        self.assertIn("上次", payload["phase"])

    def test_contract_module_is_mounted(self):
        payload = self.client.get("/chain/api/health").json()
        self.assertEqual(payload["app"], "链上雷达")
        self.assertEqual(self.client.get("/chain/static/css/app.css").status_code, 200)

    def test_cycle_endpoint_returns_phase(self):
        from datetime import datetime, timezone
        from unittest.mock import patch

        from web3_radar.engine.cycle import MarketSnapshot, assess_cycle

        snap = MarketSnapshot(
            price=72000,
            ath=120000,
            ath_date=datetime(2025, 10, 6, tzinfo=timezone.utc),
            source="test",
        )
        view = assess_cycle(snap, datetime(2026, 9, 1, tzinfo=timezone.utc))
        with patch("web3_radar.engine.cycle.current_cycle", return_value=view):
            payload = self.client.get("/api/cycle").json()
        self.assertEqual(payload["phase"], "熊市中期")
        self.assertEqual(payload["hold"], "持U为主")
        self.assertTrue(payload["hold_days"] > 0)
        self.assertTrue(payload["hold_until"])


if __name__ == "__main__":
    unittest.main()
