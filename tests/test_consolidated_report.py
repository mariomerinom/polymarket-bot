"""Tests for consolidated_report.py — cross-pipeline aggregation."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import consolidated_report
import pipeline_control


# ── Pipeline discovery ───────────────────────────────────────────────


class TestPipelineDiscovery:

    def test_all_12_pipelines_resolve_to_existing_dbs(self):
        """Every pipeline in config/pipelines.json maps to an existing DB."""
        cfg_path = Path(__file__).parent.parent / "config" / "pipelines.json"
        cfg = json.loads(cfg_path.read_text())
        configured = set(cfg["pipelines"].keys())
        discovered = set(pipeline_control.discover_pipelines().keys())
        assert configured == discovered, \
            f"Missing DBs for: {configured - discovered}"
        assert len(discovered) == 12, \
            f"Expected 12 pipelines, got {len(discovered)}"

    def test_pipeline_to_asset_mapping(self):
        assert pipeline_control.pipeline_to_asset("btc_5m") == "BTC"
        assert pipeline_control.pipeline_to_asset("btc_15m") == "BTC"
        assert pipeline_control.pipeline_to_asset("bybit") == "BTC"
        assert pipeline_control.pipeline_to_asset("hl") == "BTC"
        assert pipeline_control.pipeline_to_asset("kalshi") == "BTC"
        assert pipeline_control.pipeline_to_asset("eth_5m") == "ETH"
        assert pipeline_control.pipeline_to_asset("eth_bybit") == "ETH"
        assert pipeline_control.pipeline_to_asset("eth_hl") == "ETH"
        assert pipeline_control.pipeline_to_asset("sol_bybit") == "SOL"
        assert pipeline_control.pipeline_to_asset("sol_hl") == "SOL"
        assert pipeline_control.pipeline_to_asset("doge_bybit") == "DOGE"
        assert pipeline_control.pipeline_to_asset("doge_hl") == "DOGE"


# ── Portfolio totals ─────────────────────────────────────────────────


def _mk_result(pipeline, bets=10, wins=6, pnl=100.0, wagered=250.0):
    """Helper: synthesize per-pipeline result shaped like analyze_pipeline."""
    return {
        "pipeline": pipeline,
        "summary": {
            "total_predictions": bets + 5,
            "bets": bets,
            "skips": 5,
            "resolved_bets": bets,
            "wins": wins,
            "losses": bets - wins,
            "wr": round(wins / bets * 100, 1) if bets else 0.0,
            "pnl": pnl,
            "wagered": wagered,
        },
        "ehr": None,
        "shadow_maker": None,
        "alerts": [],
    }


class TestPortfolioTotals:

    def test_empty_list_returns_zero_totals(self):
        totals = consolidated_report.compute_portfolio_totals([])
        assert totals["total_bets"] == 0
        assert totals["total_wins"] == 0
        assert totals["total_losses"] == 0
        assert totals["aggregate_wr_pct"] == 0.0
        assert totals["total_pnl_usd"] == 0.0
        assert totals["total_wagered_usd"] == 0.0
        assert totals["active_pipelines"] == 0

    def test_sums_across_pipelines(self):
        results = [
            _mk_result("btc_5m", bets=10, wins=7, pnl=100.0, wagered=250.0),
            _mk_result("eth_5m", bets=5, wins=3, pnl=50.0, wagered=125.0),
            _mk_result("bybit", bets=0, wins=0, pnl=0.0, wagered=0.0),
        ]
        totals = consolidated_report.compute_portfolio_totals(results)
        assert totals["total_bets"] == 15
        assert totals["total_wins"] == 10
        assert totals["total_losses"] == 5
        assert totals["aggregate_wr_pct"] == round(10 / 15 * 100, 1)
        assert totals["total_pnl_usd"] == 150.0
        assert totals["total_wagered_usd"] == 375.0
        # "bybit" had 0 bets so only 2 active pipelines
        assert totals["active_pipelines"] == 2
        assert totals["total_pipelines"] == 3

    def test_handles_missing_summary(self):
        """Pipelines with no predictions return None from analyze_pipeline."""
        results = [
            {"pipeline": "btc_5m", "summary": None},
            _mk_result("eth_5m", bets=5, wins=3, pnl=50.0, wagered=125.0),
        ]
        totals = consolidated_report.compute_portfolio_totals(results)
        assert totals["total_bets"] == 5
        assert totals["active_pipelines"] == 1

    def test_handles_error_rows(self):
        results = [
            {"pipeline": "btc_5m", "error": "DB locked"},
            _mk_result("eth_5m", bets=5, wins=3, pnl=50.0, wagered=125.0),
        ]
        totals = consolidated_report.compute_portfolio_totals(results)
        assert totals["total_bets"] == 5
        assert totals["active_pipelines"] == 1


# ── Asset roll-up ────────────────────────────────────────────────────


class TestAssetRollup:

    def test_groups_by_asset(self):
        results = [
            _mk_result("btc_5m", bets=10, wins=7, pnl=100.0, wagered=250.0),
            _mk_result("btc_15m", bets=4, wins=2, pnl=20.0, wagered=100.0),
            _mk_result("eth_5m", bets=5, wins=3, pnl=50.0, wagered=125.0),
            _mk_result("eth_bybit", bets=2, wins=1, pnl=10.0, wagered=50.0),
            _mk_result("sol_hl", bets=3, wins=2, pnl=15.0, wagered=75.0),
            _mk_result("doge_bybit", bets=1, wins=0, pnl=-25.0, wagered=25.0),
        ]
        rollup = consolidated_report.compute_asset_rollup(results)
        # BTC = btc_5m + btc_15m
        assert rollup["BTC"]["bets"] == 14
        assert rollup["BTC"]["wins"] == 9
        assert rollup["BTC"]["pnl"] == 120.0
        # ETH = eth_5m + eth_bybit
        assert rollup["ETH"]["bets"] == 7
        assert rollup["ETH"]["pnl"] == 60.0
        # SOL = sol_hl
        assert rollup["SOL"]["bets"] == 3
        # DOGE = doge_bybit
        assert rollup["DOGE"]["bets"] == 1
        assert rollup["DOGE"]["pnl"] == -25.0

    def test_empty_assets_absent(self):
        """No bets for an asset → it's not in the rollup."""
        results = [_mk_result("btc_5m", bets=10, wins=7, pnl=100.0, wagered=250.0)]
        rollup = consolidated_report.compute_asset_rollup(results)
        assert "BTC" in rollup
        assert "ETH" not in rollup  # no ETH pipelines in input
        assert "SOL" not in rollup
        assert "DOGE" not in rollup


# ── Rendering ────────────────────────────────────────────────────────


class TestRender:

    def test_overview_section_has_required_tables(self):
        """The inline overview block has Consolidated Overview + By Asset."""
        results = [
            _mk_result("btc_5m", bets=10, wins=7, pnl=100.0, wagered=250.0),
            _mk_result("eth_5m", bets=5, wins=3, pnl=50.0, wagered=125.0),
        ]
        md = consolidated_report.render_overview_block(results, "2026-04-15")
        assert "Consolidated Overview" in md
        assert "By Asset" in md
        assert "Total P&L" in md
        assert "+$150" in md  # sum of 100+50
        assert "consolidated-2026-04-15.md" in md  # link to detail
        assert "Pipelines with resolved bets | 2 of 2" in md
        assert "Active pipelines" not in md
        # Table rows render
        assert "BTC" in md
        assert "ETH" in md

    def test_detail_file_has_all_sections(self):
        results = [
            _mk_result("btc_5m", bets=10, wins=7, pnl=100.0, wagered=250.0),
            _mk_result("eth_5m", bets=5, wins=3, pnl=50.0, wagered=125.0),
        ]
        md = consolidated_report.render_consolidated_detail(results, "2026-04-15")
        # Required sections
        for section in [
            "Portfolio Totals",
            "Leaderboard",
            "Per-Asset Roll-up",
            "Pipeline Config Snapshot",
        ]:
            assert section in md, f"Missing section: {section}"
        # Every pipeline from input appears in leaderboard
        assert "btc_5m" in md
        assert "eth_5m" in md

    def test_orderbook_diagnostics_render_reconnect_churn_cause(self):
        metrics = {
            "orderbook_age_ms": {"p95": 70000},
            "orderbook_cache": {
                "book_events_24h": 0,
                "price_change_events_24h": 0,
                "ignored_event_types": {"last_trade_price": 3},
                "fresh_tokens_now": 0,
                "stale_tokens_now": 24,
                "tokens_updated_last_60s": 0,
                "tokens_updated_last_5m": 0,
                "stale_reasons": {"rest_snapshot_missing": 24},
                "rest_snapshot_seed_attempts": 24,
                "rest_snapshot_seed_success": 0,
                "resubscribe_debounced": 40,
                "resubscribe_executed": 12,
            },
        }

        lines = consolidated_report._orderbook_diagnostic_lines(metrics)
        text = "\n".join(lines)
        assert "Polymarket events" in text
        assert "fresh/stale tokens: 0/24" in text
        assert "resubscribe debounced/executed: 40/12" in text
        assert "dominant cause: no websocket book/price_change events" in text

    def test_btc5m_readiness_section_renders_blockers(self, monkeypatch):
        monkeypatch.setattr(
            consolidated_report.pipeline_control,
            "discover_pipelines",
            lambda: {"btc_5m": ":memory:"},
        )
        monkeypatch.setattr(
            "canary_readiness.btc5m_live_canary_blockers",
            lambda db: ["metrics_schema_stale (None)"],
        )
        monkeypatch.setattr(
            "canary_readiness.btc5m_delayed_policy_blockers",
            lambda db: ["delayed_ehr_insufficient_sample (0/50)"],
        )

        lines = consolidated_report._render_btc5m_readiness_section()
        text = "\n".join(lines)

        assert "BTC 5m Production Readiness" in text
        assert "Verdict: BLOCKED" in text
        assert "metrics_schema_stale" in text
        assert "delayed_ehr_insufficient_sample" in text

    def test_circuit_breaker_false_renders_untripped_plainly(self):
        results = [
            {
                **_mk_result("btc_5m", bets=4, wins=2),
                "orders": {
                    "daily_loss": 125.0,
                    "breaker_limit": 300.0,
                    "breaker_tripped": False,
                },
            },
            {
                **_mk_result("eth_5m", bets=4, wins=1),
                "orders": {
                    "daily_loss": 325.0,
                    "breaker_limit": 300.0,
                    "breaker_tripped": True,
                },
            },
        ]
        md = consolidated_report.render_consolidated_detail(results, "2026-04-15")

        assert "| btc_5m | $125.00 | $300.0 | No |" in md
        assert "| eth_5m | $325.00 | $300.0 | YES |" in md
        assert "| btc_5m | $125.00 | $300.0 | ✅ |" not in md

    def test_zero_bets_day_does_not_crash(self):
        """No-activity day still renders."""
        results = []
        md = consolidated_report.render_overview_block(results, "2026-04-15")
        assert "Consolidated Overview" in md
        md2 = consolidated_report.render_consolidated_detail(results, "2026-04-15")
        assert "Portfolio Totals" in md2

    def test_error_pipelines_shown_in_leaderboard(self):
        results = [
            _mk_result("btc_5m", bets=10, wins=7, pnl=100.0, wagered=250.0),
            {"pipeline": "kalshi", "error": "DB locked"},
        ]
        md = consolidated_report.render_consolidated_detail(results, "2026-04-15")
        assert "kalshi" in md
        assert "error" in md.lower() or "DB locked" in md
