from __future__ import annotations

import unittest
from datetime import datetime, timezone

from unittest.mock import patch

from radar.__main__ import build_parser, run, use_browser_ui
from radar.report import render_scanning_html
from radar.models import TokenSnapshot
from radar.models import SecurityReport
from radar.report import render_html
from radar.scoring import score_many, score_token, summarize_venues
from radar.security import apply_security, parse_goplus_evm, parse_goplus_solana
from radar.sources import pools_to_snapshots


def make_token(**kwargs) -> TokenSnapshot:
    defaults = dict(
        chain="robinhood",
        dex="pons",
        name="Pons",
        symbol="PONS",
        address="0xabc",
        pair_address="0xpair",
        price_usd=0.4,
        fdv_usd=8_000_000,
        mcap_usd=8_000_000,
        liquidity_usd=600_000,
        volume_h24=4_000_000,
        buys_h24=2000,
        sells_h24=1800,
        buyers_h24=900,
        sellers_h24=800,
        price_change_h24=12.0,
        pool_created_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        url="https://example.com",
        description="Robinhood launchpad token",
        source="test",
    )
    defaults.update(kwargs)
    return TokenSnapshot(**defaults)


class ScoringTests(unittest.TestCase):
    def test_launchpad_own_token_on_new_chain_is_focus(self):
        score = score_token(make_token())
        self.assertGreaterEqual(score.venue, 16)
        self.assertGreaterEqual(score.narrative, 12)
        self.assertTrue(score.watch)
        self.assertIn(score.priority, {"focus", "watch"})
        self.assertTrue(any("发射台" in r or "新场子" in r for r in score.reasons))

    def test_copycat_on_old_pool_is_skipped(self):
        token = make_token(
            chain="eth",
            dex="uniswap",
            name="Baby Doge 2.0",
            symbol="BABYDOGE",
            description="baby doge 2.0 .site",
            fdv_usd=200_000_000,
            mcap_usd=200_000_000,
            liquidity_usd=80_000_000,
            volume_h24=10_000,
            buyers_h24=10,
            sellers_h24=10,
            pool_created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        score = score_token(token)
        self.assertEqual(score.priority, "skip")
        self.assertTrue(any("仿盘" in w for w in score.warnings))

    def test_large_cap_gets_too_late_warning(self):
        token = make_token(mcap_usd=120_000_000, fdv_usd=120_000_000, liquidity_usd=6_000_000)
        score = score_token(token)
        self.assertTrue(any("已偏大" in w for w in score.warnings))
        self.assertIn("已过大", score.tags)
        self.assertLessEqual(score.total, 68)

    def test_stablecoin_zeroed(self):
        score = score_token(make_token(symbol="USDC", name="USD Coin"))
        self.assertEqual(score.total, 0)
        self.assertFalse(score.watch)

    def test_cultural_narrative_and_shallow_pool(self):
        token = make_token(
            chain="bsc",
            dex="fourmeme",
            name="牛来 (Niu Lai)",
            symbol="牛来",
            description="viral chinese film niu lai",
            mcap_usd=3_000_000,
            fdv_usd=3_000_000,
            liquidity_usd=180_000,
            volume_h24=2_200_000,
            pool_created_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
        )
        score = score_token(token)
        self.assertTrue("独占叙事" in score.tags or any("文化" in r for r in score.reasons))
        self.assertIn("浅开盘", score.tags)
        self.assertTrue(score.watch)

    def test_venue_summary_flags_new_chain(self):
        tokens = [
            make_token(symbol="CASHCAT", name="Cash Cat"),
            make_token(symbol="JOHN", name="Little John", address="0x2"),
        ]
        pulses = summarize_venues(tokens)
        self.assertTrue(pulses)
        self.assertEqual(pulses[0].chain, "robinhood")
        self.assertNotEqual(pulses[0].label, "普通场")

    def test_score_many_orders_by_total(self):
        weak = make_token(name="Baby Pepe", symbol="PEPE", chain="eth", dex="uniswap", mcap_usd=1_000)
        strong = make_token()
        ranked = score_many([weak, strong])
        self.assertEqual(ranked[0].token.symbol, "PONS")


class SecurityTests(unittest.TestCase):
    def test_honeypot_and_hidden_owner_are_backdoors(self):
        report = parse_goplus_evm(
            {
                "is_honeypot": "1",
                "hidden_owner": "1",
                "buy_tax": "0",
                "sell_tax": "0",
                "owner_address": "0xabc",
            }
        )
        self.assertTrue(report.has_backdoor)
        self.assertEqual(report.verdict, "backdoor")
        self.assertTrue(any("蜜罐" in f for f in report.findings))

    def test_mint_authority_not_renounced_is_backdoor(self):
        report = parse_goplus_evm(
            {
                "is_mintable": "1",
                "owner_address": "0x1111111111111111111111111111111111111111",
                "is_honeypot": "0",
            }
        )
        self.assertTrue(report.has_backdoor)
        self.assertTrue(any("增发" in f for f in report.findings))

    def test_clean_renounced_token(self):
        report = parse_goplus_evm(
            {
                "is_honeypot": "0",
                "is_mintable": "0",
                "owner_address": "0x0000000000000000000000000000000000000000",
                "buy_tax": "3",
                "sell_tax": "3",
            }
        )
        self.assertFalse(report.has_backdoor)
        self.assertEqual(report.verdict, "clean")

    def test_solana_freeze_authority_is_backdoor(self):
        report = parse_goplus_solana({"freezable": {"status": "1", "authority": [{"address": "So1"}]}})
        self.assertTrue(report.has_backdoor)
        self.assertTrue(any("冻结" in f for f in report.findings))

    def test_backdoor_token_is_removed_from_recommendations(self):
        ranked = score_many([make_token()])
        self.assertTrue(ranked[0].score.watch)
        reports = {
            ("robinhood", "0xabc"): SecurityReport(
                checked=True,
                has_backdoor=True,
                verdict="backdoor",
                source="test",
                findings=["管理员可改地址余额"],
            )
        }
        apply_security(ranked, reports)
        self.assertFalse(ranked[0].score.watch)
        self.assertEqual(ranked[0].score.priority, "skip")
        page = render_html([], [], datetime(2026, 9, 1, tzinfo=timezone.utc), rejected=ranked)
        self.assertIn("因合约后门剔除", page)
        self.assertIn("管理员可改地址余额", page)


class SourceParseTests(unittest.TestCase):
    def test_pools_to_snapshots_skips_quote_tokens(self):
        payload = {
            "data": [
                {
                    "id": "solana_1",
                    "attributes": {
                        "address": "pair1",
                        "base_token_price_usd": "0.01",
                        "fdv_usd": "1000000",
                        "market_cap_usd": "900000",
                        "reserve_in_usd": "80000",
                        "pool_created_at": "2026-08-20T00:00:00Z",
                        "volume_usd": {"h24": "500000"},
                        "price_change_percentage": {"h24": "12.5"},
                        "transactions": {
                            "h24": {"buys": 10, "sells": 8, "buyers": 9, "sellers": 7}
                        },
                    },
                    "relationships": {
                        "base_token": {"data": {"id": "solana_a", "type": "token"}},
                        "quote_token": {"data": {"id": "solana_sol", "type": "token"}},
                        "dex": {"data": {"id": "pumpswap", "type": "dex"}},
                    },
                }
            ],
            "included": [
                {
                    "id": "solana_a",
                    "type": "token",
                    "attributes": {"address": "TokenA", "name": "Hookr.fun", "symbol": "HOOKR"},
                },
                {
                    "id": "solana_sol",
                    "type": "token",
                    "attributes": {"address": "So111", "name": "Solana", "symbol": "SOL"},
                },
                {"id": "pumpswap", "type": "dex", "attributes": {"name": "PumpSwap"}},
            ],
        }
        snaps = pools_to_snapshots(payload, chain="solana", source="test")
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0].symbol, "HOOKR")
        self.assertEqual(snaps[0].dex, "pumpswap")
        self.assertEqual(snaps[0].volume_h24, 500000)
        self.assertIsNotNone(snaps[0].age_days)


class CliTests(unittest.TestCase):
    def test_parser_accepts_html_flag(self):
        args = build_parser().parse_args(["--html", "out.html", "--min-score", "60"])
        self.assertEqual(args.html, "out.html")
        self.assertEqual(args.min_score, 60)

    def test_default_uses_browser_ui(self):
        args = build_parser().parse_args([])
        self.assertTrue(use_browser_ui(args))

    def test_text_and_json_skip_browser_ui(self):
        self.assertFalse(use_browser_ui(build_parser().parse_args(["--text"])))
        self.assertFalse(use_browser_ui(build_parser().parse_args(["--json"])))
        self.assertFalse(use_browser_ui(build_parser().parse_args(["--html", "out.html"])))

    def test_serve_uses_browser_ui(self):
        self.assertTrue(use_browser_ui(build_parser().parse_args(["--serve"])))

    def test_scanning_html_auto_refreshes(self):
        page = render_scanning_html()
        self.assertIn("refresh", page)
        self.assertIn("正在扫描", page)

    def test_default_run_opens_browser(self):
        class DummyHttpd:
            def shutdown(self) -> None:
                return None

        with (
            patch("radar.__main__.collect_snapshots", return_value=[]),
            patch("radar.__main__.open_in_browser", return_value=True) as opener,
            patch("radar.__main__.keep_window_open") as waiter,
            patch(
                "radar.__main__._serve_in_background",
                return_value=(DummyHttpd(), 8765, None),
            ),
        ):
            code = run([])
        self.assertEqual(code, 0)
        self.assertTrue(opener.called)
        self.assertTrue(waiter.called)
        target = opener.call_args[0][0]
        self.assertEqual(target, "http://127.0.0.1:8765/fiftyx-radar-report.html")

    def test_text_run_does_not_open_browser(self):
        with (
            patch("radar.__main__.collect_snapshots", return_value=[]),
            patch("radar.__main__.open_in_browser") as opener,
            patch("radar.__main__.keep_window_open") as waiter,
        ):
            code = run(["--text"])
        self.assertEqual(code, 0)
        opener.assert_not_called()
        waiter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
