"""Tests for arb_divergence.py — Phase 0 cross-venue arb logger."""
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import arb_divergence as ad


# ── parse_polymarket_market ─────────────────────────────────────────


class TestParseMarket:

    def test_5m_btc_market(self):
        """Bitcoin Up or Down 5-minute window parses correctly."""
        result = ad.parse_polymarket_market(
            question="Bitcoin Up or Down - April 23, 10:55AM-11:00AM ET",
            end_date="2026-04-23T15:00:00Z",
        )
        assert result is not None
        assert result["asset"] == "BTC"
        assert result["market_class"] == "5m"
        assert result["window_total_seconds"] == 300
        assert result["window_close_at"] == datetime(
            2026, 4, 23, 15, 0, 0, tzinfo=timezone.utc
        )
        assert result["window_open_at"] == datetime(
            2026, 4, 23, 14, 55, 0, tzinfo=timezone.utc
        )

    def test_15m_eth_market(self):
        """Ethereum 15-minute window."""
        result = ad.parse_polymarket_market(
            question="Ethereum Up or Down - April 23, 10:00AM-10:15AM ET",
            end_date="2026-04-23T14:15:00Z",
        )
        assert result is not None
        assert result["asset"] == "ETH"
        assert result["market_class"] == "15m"
        assert result["window_total_seconds"] == 900

    def test_pm_market(self):
        """PM window parses correctly."""
        result = ad.parse_polymarket_market(
            question="Bitcoin Up or Down - April 23, 3:00PM-3:05PM ET",
            end_date="2026-04-23T19:05:00Z",
        )
        assert result is not None
        assert result["market_class"] == "5m"
        assert result["window_open_at"].hour == 19  # 3PM ET = 19 UTC

    def test_12am_12pm_handling(self):
        """12AM is 00:00, 12PM is 12:00 — standard US conventions."""
        result = ad.parse_polymarket_market(
            question="Bitcoin Up or Down - April 23, 12:00AM-12:05AM ET",
            end_date="2026-04-23T04:05:00Z",  # 12:05 AM ET = 04:05 UTC
        )
        assert result is not None
        assert result["window_open_at"].hour == 4

    def test_unparseable_question_returns_none(self):
        """Non-standard question format returns None."""
        result = ad.parse_polymarket_market(
            question="Will BTC reach $100k in 2026?",
            end_date="2026-12-31T23:59:59Z",
        )
        assert result is None

    def test_missing_end_date_returns_none(self):
        result = ad.parse_polymarket_market(
            question="Bitcoin Up or Down - April 23, 10:55AM-11:00AM ET",
            end_date=None,
        )
        assert result is None

    def test_missing_question_returns_none(self):
        assert ad.parse_polymarket_market(
            question=None, end_date="2026-04-23T15:00:00Z"
        ) is None

    def test_garbage_end_date_returns_none(self):
        assert ad.parse_polymarket_market(
            question="Bitcoin Up or Down - April 23, 10:55AM-11:00AM ET",
            end_date="not-a-date",
        ) is None


# ── compute_realized_vol ────────────────────────────────────────────


class TestRealizedVol:

    def test_flat_closes_returns_none(self):
        """No variance → None."""
        assert ad.compute_realized_vol([100.0] * 10) is None

    def test_nonzero_variance_returns_positive(self):
        closes = [100.0, 101.0, 99.5, 100.5, 99.0, 101.5, 100.0, 102.0]
        rv = ad.compute_realized_vol(closes)
        assert rv is not None
        assert rv > 0

    def test_insufficient_data_returns_none(self):
        assert ad.compute_realized_vol([100.0, 101.0]) is None

    def test_filters_nonpositive_closes(self):
        """Zero/negative closes are filtered out."""
        closes = [100.0, 0, -5, 101.0, 99.5, 100.5, 99.0, 101.5, 100.0, 102.0]
        rv = ad.compute_realized_vol(closes)
        assert rv is not None
        assert rv > 0


# ── compute_fair_p_up_down ──────────────────────────────────────────


class TestFairP:

    def test_at_open_returns_half(self):
        """At window open (ttm_remaining == window_total), fair_p = 0.5."""
        # Slight numeric tolerance; open and current are equal
        p = ad.compute_fair_p_up_down(
            open_spot=75000, current_spot=75000,
            ttm_remaining_seconds=300, window_total_seconds=300,
            realized_vol_annual=0.5,
        )
        assert p == 0.5  # exactly per our short-circuit

    def test_after_close_step_function(self):
        """Past window close (ttm_remaining <= 0), returns step function."""
        p_up = ad.compute_fair_p_up_down(
            open_spot=75000, current_spot=75100,
            ttm_remaining_seconds=-5, window_total_seconds=300,
            realized_vol_annual=0.5,
        )
        assert p_up == 1.0
        p_down = ad.compute_fair_p_up_down(
            open_spot=75000, current_spot=74900,
            ttm_remaining_seconds=-5, window_total_seconds=300,
            realized_vol_annual=0.5,
        )
        assert p_down == 0.0

    def test_mid_window_already_up_high_p(self):
        """Half-window in and already +0.3%, fair_p should be well above 0.5."""
        p = ad.compute_fair_p_up_down(
            open_spot=75000, current_spot=75225,  # +0.3%
            ttm_remaining_seconds=150, window_total_seconds=300,
            realized_vol_annual=0.5,  # annual 50% vol (high for crypto)
        )
        # sigma for 150s window: 0.5 * sqrt(150/31536000) ~ 0.00109
        # r = log(75225/75000) = 0.003
        # z = 2.75 → Φ(z) ≈ 0.997
        assert p is not None
        assert p > 0.9

    def test_symmetric_at_zero_return(self):
        """If current_spot == open_spot mid-window, fair_p should be 0.5."""
        p = ad.compute_fair_p_up_down(
            open_spot=75000, current_spot=75000,
            ttm_remaining_seconds=150, window_total_seconds=300,
            realized_vol_annual=0.5,
        )
        assert p == 0.5

    def test_clipped_to_nondegenerate_range(self):
        """Extreme inputs clipped to [0.001, 0.999]."""
        p = ad.compute_fair_p_up_down(
            open_spot=75000, current_spot=80000,  # +6.7% in a 5m window
            ttm_remaining_seconds=1, window_total_seconds=300,
            realized_vol_annual=0.5,
        )
        assert p is not None
        assert p <= 0.999

    def test_degenerate_inputs_return_none(self):
        assert ad.compute_fair_p_up_down(
            open_spot=0, current_spot=75000,
            ttm_remaining_seconds=150, window_total_seconds=300,
            realized_vol_annual=0.5,
        ) is None
        assert ad.compute_fair_p_up_down(
            open_spot=75000, current_spot=75000,
            ttm_remaining_seconds=150, window_total_seconds=300,
            realized_vol_annual=-1,
        ) is None


# ── compute_arb_side_and_edge ───────────────────────────────────────


class TestArbSide:

    def test_yes_underpriced_buy_poly(self):
        """fair_p = 0.60, mkt_mid = 0.45, spread = 0.02, fee = 0.02
        → edge = 0.15 - 0.01 - 0.02 = 0.12 > 0 → buy_poly."""
        side, edge = ad.compute_arb_side_and_edge(
            fair_p=0.60, mkt_mid=0.45, mkt_spread=0.02
        )
        assert side == "buy_poly"
        assert edge == ad.compute_arb_side_and_edge.__defaults__ or abs(edge - 0.12) < 1e-6

    def test_yes_overpriced_sell_poly(self):
        """fair_p = 0.40, mkt_mid = 0.55 → sell YES."""
        side, edge = ad.compute_arb_side_and_edge(
            fair_p=0.40, mkt_mid=0.55, mkt_spread=0.02
        )
        assert side == "sell_poly"

    def test_not_actionable_within_fees(self):
        """Diff smaller than fees+spread → None."""
        side, edge = ad.compute_arb_side_and_edge(
            fair_p=0.51, mkt_mid=0.50, mkt_spread=0.02
        )
        assert side is None

    def test_none_fair_returns_none(self):
        side, edge = ad.compute_arb_side_and_edge(
            fair_p=None, mkt_mid=0.50, mkt_spread=0.02
        )
        assert side is None
        assert edge is None


# ── record + init_table ─────────────────────────────────────────────


class TestRecord:

    def _make_db(self):
        db = sqlite3.connect(":memory:")
        ad.init_table(db)
        return db

    def test_init_table_idempotent(self):
        db = self._make_db()
        ad.init_table(db)  # second call should not raise
        ad.init_table(db)
        row = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='arb_divergence'"
        ).fetchone()
        assert row is not None
        db.close()

    def test_record_inserts_row(self):
        db = self._make_db()
        ad.record(
            db,
            timestamp="2026-04-23T15:00:00Z",
            cycle=1,
            pipeline="btc_5m",
            market_id="m1",
            market_class="5m",
            asset="BTC",
            direction_sense="up_or_down",
            window_open_at="2026-04-23T14:55:00Z",
            window_close_at="2026-04-23T15:00:00Z",
            window_total_seconds=300,
            time_to_expiry_seconds=120,
            window_has_opened=1,
            bybit_spot=75100,
            bybit_source="pending",
            open_spot=75000,
            r_so_far=0.00133,
            realized_vol_annual=0.5,
            sigma_window=0.00087,
            fair_p=0.92,
            mkt_mid=0.60,
            mkt_best_bid=0.58,
            mkt_best_ask=0.62,
            mkt_spread=0.04,
            orderbook_age_ms=1200,
            divergence=0.32,
            abs_divergence=0.32,
            would_arb_side="buy_poly",
            would_arb_edge=0.28,
            regime_label="MEDIUM_VOL / NEUTRAL",
            regime_autocorr=-0.05,
            regime_vol=0.12,
            daily_regime_label="up",
            daily_range_zscore=0.35,
        )
        rows = db.execute("SELECT COUNT(*) FROM arb_divergence").fetchone()
        assert rows[0] == 1
        # Spot-check a few fields
        row = db.execute(
            "SELECT fair_p, mkt_mid, would_arb_side, regime_label "
            "FROM arb_divergence WHERE market_id='m1'"
        ).fetchone()
        assert row[0] == 0.92
        assert row[1] == 0.60
        assert row[2] == "buy_poly"
        assert row[3] == "MEDIUM_VOL / NEUTRAL"
        db.close()

    def test_record_handles_null_fields(self):
        """Partial rows (e.g., unparseable market with nulls) still insert."""
        db = self._make_db()
        ad.record(
            db,
            timestamp="2026-04-23T15:00:00Z",
            cycle=1,
            pipeline="btc_5m",
            market_id="m_unparseable",
        )
        n = db.execute("SELECT COUNT(*) FROM arb_divergence").fetchone()[0]
        assert n == 1
        db.close()


# ── End-to-end: _norm_cdf sanity ────────────────────────────────────


class TestNormCdf:

    def test_at_zero_returns_half(self):
        assert abs(ad._norm_cdf(0.0) - 0.5) < 1e-9

    def test_at_plus_inf_returns_one(self):
        assert ad._norm_cdf(10) > 0.9999

    def test_at_minus_inf_returns_zero(self):
        assert ad._norm_cdf(-10) < 0.0001

    def test_symmetric(self):
        for x in [0.5, 1.0, 1.96, 2.0]:
            a = ad._norm_cdf(x)
            b = ad._norm_cdf(-x)
            assert abs(a + b - 1.0) < 1e-9
