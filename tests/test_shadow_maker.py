"""Tests for shadow_maker.py — Phase 1 shadow maker logging and fill simulation."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import shadow_maker


def _make_db():
    """Create an in-memory DB with shadow_maker table."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    shadow_maker.init_table(db)
    return db


# ── compute_shadow_price ─────────────────────────────────────────────


class TestComputeShadowPrice:

    def test_buy_direction_posts_inside_bid(self):
        """BUY: shadow_bid = mid - (spread * 0.25)"""
        # bid=0.50, ask=0.54, spread=0.04, mid=0.52
        # shadow_bid = 0.52 - (0.04 * 0.25) = 0.51
        price, side = shadow_maker.compute_shadow_price(
            "UP", best_bid=0.50, best_ask=0.54, spread=0.04, mid=0.52
        )
        assert side == "BUY"
        assert abs(price - 0.51) < 0.001

    def test_sell_direction_posts_inside_ask(self):
        """SELL: shadow_ask = mid + (spread * 0.25)"""
        # bid=0.46, ask=0.50, spread=0.04, mid=0.48
        # shadow_ask = 0.48 + (0.04 * 0.25) = 0.49
        price, side = shadow_maker.compute_shadow_price(
            "DOWN", best_bid=0.46, best_ask=0.50, spread=0.04, mid=0.48
        )
        assert side == "SELL"
        assert abs(price - 0.49) < 0.001

    def test_missing_book_returns_none(self):
        """Returns (None, None) when book data is missing."""
        price, side = shadow_maker.compute_shadow_price(
            "UP", best_bid=None, best_ask=None, spread=None, mid=None
        )
        assert price is None
        assert side is None

    def test_zero_spread_returns_mid(self):
        """Zero spread → shadow price = mid (no spread to capture)."""
        price, side = shadow_maker.compute_shadow_price(
            "UP", best_bid=0.50, best_ask=0.50, spread=0.0, mid=0.50
        )
        assert side == "BUY"
        assert abs(price - 0.50) < 0.001

    def test_wide_spread(self):
        """Wide spread (8¢) → shadow posts 2¢ inside."""
        # bid=0.46, ask=0.54, spread=0.08, mid=0.50
        # shadow_bid = 0.50 - 0.02 = 0.48
        price, side = shadow_maker.compute_shadow_price(
            "UP", best_bid=0.46, best_ask=0.54, spread=0.08, mid=0.50
        )
        assert abs(price - 0.48) < 0.001


# ── record + init_table ──────────────────────────────────────────────


class TestRecord:

    def test_init_table_idempotent(self):
        """Calling init_table twice doesn't crash."""
        db = _make_db()
        shadow_maker.init_table(db)  # second call
        db.close()

    def test_record_inserts_row(self):
        db = _make_db()
        shadow_maker.record(
            db,
            prediction_id=1,
            market_id="mkt_abc",
            pipeline="btc_5m",
            cycle=42,
            direction="UP",
            estimate=0.62,
            conviction=4,
            regime="MEDIUM_VOL / NEUTRAL",
            best_bid=0.50,
            best_ask=0.54,
            spread=0.04,
            mid=0.52,
            shadow_price=0.51,
            shadow_side="BUY",
            taker_price=0.54,
            taker_action="placed",
        )
        row = db.execute("SELECT * FROM shadow_maker WHERE id = 1").fetchone()
        assert row is not None
        assert row["market_id"] == "mkt_abc"
        assert row["shadow_price"] == 0.51
        assert row["shadow_side"] == "BUY"
        assert row["filled"] is None  # pending
        db.close()

    def test_record_without_taker(self):
        """Shadow records work when taker was skipped (order_params=None)."""
        db = _make_db()
        shadow_maker.record(
            db,
            prediction_id=2,
            market_id="mkt_xyz",
            pipeline="btc_5m",
            cycle=43,
            direction="DOWN",
            estimate=0.38,
            conviction=3,
            regime="HIGH_VOL / NEUTRAL",
            best_bid=0.46,
            best_ask=0.50,
            spread=0.04,
            mid=0.48,
            shadow_price=0.49,
            shadow_side="SELL",
            taker_price=None,
            taker_action="skipped_low_edge",
        )
        row = db.execute("SELECT * FROM shadow_maker WHERE id = 1").fetchone()
        assert row["taker_price"] is None
        assert row["taker_action"] == "skipped_low_edge"
        db.close()


# ── resolve_shadow_fills ─────────────────────────────────────────────


class TestFillSimulation:

    def _insert_shadow(self, db, id, shadow_price, shadow_side, direction, cycle=1):
        """Helper to insert a pending shadow order."""
        shadow_maker.record(
            db,
            prediction_id=id,
            market_id=f"mkt_{id}",
            pipeline="btc_5m",
            cycle=cycle,
            direction=direction,
            estimate=0.62 if direction == "UP" else 0.38,
            conviction=4,
            regime="MEDIUM_VOL / NEUTRAL",
            best_bid=0.50,
            best_ask=0.54,
            spread=0.04,
            mid=0.52,
            shadow_price=shadow_price,
            shadow_side=shadow_side,
        )

    def test_buy_filled_when_low_reaches_price(self):
        """Shadow BUY at 0.51, candle low=0.50 → filled."""
        db = _make_db()
        self._insert_shadow(db, 1, 0.51, "BUY", "UP", cycle=1)
        shadow_maker.resolve_shadow_fills(db, "btc_5m", candle_low=0.50,
                                          candle_high=0.55, candle_close=0.53,
                                          cycle=2)
        row = db.execute("SELECT * FROM shadow_maker WHERE id = 1").fetchone()
        assert row["filled"] == 1
        assert row["adverse"] == 0  # close > shadow_price → favorable for BUY
        db.close()

    def test_buy_not_filled_when_low_above_price(self):
        """Shadow BUY at 0.51, candle low=0.52 → not filled."""
        db = _make_db()
        self._insert_shadow(db, 1, 0.51, "BUY", "UP", cycle=1)
        shadow_maker.resolve_shadow_fills(db, "btc_5m", candle_low=0.52,
                                          candle_high=0.55, candle_close=0.53,
                                          cycle=2)
        row = db.execute("SELECT * FROM shadow_maker WHERE id = 1").fetchone()
        assert row["filled"] == 0
        db.close()

    def test_sell_filled_when_high_reaches_price(self):
        """Shadow SELL at 0.49, candle high=0.50 → filled."""
        db = _make_db()
        self._insert_shadow(db, 1, 0.49, "SELL", "DOWN", cycle=1)
        shadow_maker.resolve_shadow_fills(db, "btc_5m", candle_low=0.45,
                                          candle_high=0.50, candle_close=0.47,
                                          cycle=2)
        row = db.execute("SELECT * FROM shadow_maker WHERE id = 1").fetchone()
        assert row["filled"] == 1
        assert row["adverse"] == 0  # close < shadow_price → favorable for SELL
        db.close()

    def test_adverse_selection_buy(self):
        """Shadow BUY at 0.51 filled, candle close=0.49 → adverse."""
        db = _make_db()
        self._insert_shadow(db, 1, 0.51, "BUY", "UP", cycle=1)
        shadow_maker.resolve_shadow_fills(db, "btc_5m", candle_low=0.48,
                                          candle_high=0.52, candle_close=0.49,
                                          cycle=2)
        row = db.execute("SELECT * FROM shadow_maker WHERE id = 1").fetchone()
        assert row["filled"] == 1
        assert row["adverse"] == 1  # close < shadow_price → adverse for BUY
        db.close()

    def test_adverse_selection_sell(self):
        """Shadow SELL at 0.49 filled, candle close=0.51 → adverse."""
        db = _make_db()
        self._insert_shadow(db, 1, 0.49, "SELL", "DOWN", cycle=1)
        shadow_maker.resolve_shadow_fills(db, "btc_5m", candle_low=0.47,
                                          candle_high=0.52, candle_close=0.51,
                                          cycle=2)
        row = db.execute("SELECT * FROM shadow_maker WHERE id = 1").fetchone()
        assert row["filled"] == 1
        assert row["adverse"] == 1  # close > shadow_price → adverse for SELL
        db.close()

    def test_only_resolves_pending(self):
        """Already-resolved shadows are not re-resolved."""
        db = _make_db()
        self._insert_shadow(db, 1, 0.51, "BUY", "UP", cycle=1)
        # First resolve
        shadow_maker.resolve_shadow_fills(db, "btc_5m", candle_low=0.50,
                                          candle_high=0.55, candle_close=0.53,
                                          cycle=2)
        # Second resolve with different candle should NOT change result
        shadow_maker.resolve_shadow_fills(db, "btc_5m", candle_low=0.60,
                                          candle_high=0.65, candle_close=0.62,
                                          cycle=3)
        row = db.execute("SELECT * FROM shadow_maker WHERE id = 1").fetchone()
        assert row["fill_candle_close"] == 0.53  # still the first resolve
        db.close()


# ── shadow_stats ─────────────────────────────────────────────────────


class TestShadowStats:

    def test_stats_from_resolved_fills(self):
        """Verify fill_rate, adverse_pct, shadow_ehr from synthetic data."""
        db = _make_db()
        # Create markets table for outcome resolution
        db.execute("""CREATE TABLE markets (
            id TEXT PRIMARY KEY, resolved INTEGER, outcome INTEGER, price_yes REAL)""")

        # 4 shadow orders: 3 filled (2 wins, 1 loss), 1 unfilled
        for i, (sp, ss, d, est) in enumerate([
            (0.51, "BUY", "UP", 0.62),     # will fill, win
            (0.49, "SELL", "DOWN", 0.38),   # will fill, win
            (0.51, "BUY", "UP", 0.62),      # will fill, lose
            (0.51, "BUY", "UP", 0.62),      # won't fill
        ], start=1):
            shadow_maker.record(
                db, prediction_id=i, market_id=f"m{i}", pipeline="btc_5m",
                cycle=1, direction=d, estimate=est, conviction=4,
                regime="MEDIUM_VOL / NEUTRAL",
                best_bid=0.50, best_ask=0.54, spread=0.04, mid=0.52,
                shadow_price=sp, shadow_side=ss,
            )

        # Resolve fills: first 3 filled, last not
        db.execute("UPDATE shadow_maker SET filled=1, adverse=0, fill_candle_close=0.53 WHERE id IN (1,2,3)")
        db.execute("UPDATE shadow_maker SET filled=0 WHERE id = 4")
        # adverse on #3
        db.execute("UPDATE shadow_maker SET adverse=1, fill_candle_close=0.49 WHERE id = 3")

        # Market outcomes: m1=YES(1), m2=NO(0), m3=NO(0), m4=YES(1)
        db.execute("INSERT INTO markets VALUES ('m1', 1, 1, 0.52)")  # UP wins
        db.execute("INSERT INTO markets VALUES ('m2', 1, 0, 0.48)")  # DOWN wins
        db.execute("INSERT INTO markets VALUES ('m3', 1, 0, 0.52)")  # UP loses
        db.execute("INSERT INTO markets VALUES ('m4', 1, 1, 0.52)")  # unfilled
        db.commit()

        stats = shadow_maker.shadow_stats(db, "btc_5m", days=90)
        assert stats["n_logged"] == 4
        assert stats["n_filled"] == 3
        assert abs(stats["fill_rate"] - 0.75) < 0.01  # 3/4
        assert abs(stats["adverse_pct"] - 1/3) < 0.01  # 1 of 3 fills
        # shadow_ehr: for filled orders:
        # #1 BUY at 0.51, outcome=1 → (1 - 0.51) = +0.49
        # #2 SELL at 0.49, outcome=0 → (1 - 0.49) = +0.51 (buying NO, NO wins)
        # #3 BUY at 0.51, outcome=0 → (0 - 0.51) = -0.51
        # EHR = avg(0.49, 0.51, -0.51) = 0.163
        assert stats["shadow_ehr"] is not None
        db.close()


# ── resolve_shadow_fills_polymarket ──────────────────────────────────


class TestPolymarketResolver:

    def _setup_db(self):
        db = _make_db()
        db.execute("""CREATE TABLE markets (
            id TEXT PRIMARY KEY, resolved INTEGER, outcome INTEGER,
            price_yes REAL)""")
        return db

    def test_resolves_only_resolved_markets(self):
        """Shadow rows for unresolved markets stay pending."""
        db = self._setup_db()
        shadow_maker.record(
            db, prediction_id=1, market_id="m1", pipeline="btc_5m",
            cycle=1, direction="UP", estimate=0.62, conviction=3,
            regime="MEDIUM_VOL / NEUTRAL",
            best_bid=0.50, best_ask=0.54, spread=0.04, mid=0.52,
            shadow_price=0.51, shadow_side="BUY",
        )
        # Market NOT resolved
        db.execute("INSERT INTO markets VALUES ('m1', 0, NULL, 0.52)")
        db.commit()

        n_resolved, n_filled = shadow_maker.resolve_shadow_fills_polymarket(
            db, "btc_5m")
        assert n_resolved == 0
        # Row still pending
        row = db.execute("SELECT filled FROM shadow_maker").fetchone()
        assert row[0] is None
        db.close()

    def test_buy_fills_and_wins_when_yes_resolves_yes(self):
        """BUY shadow at 0.51 when mid=0.52; market resolves YES (outcome=1)."""
        db = self._setup_db()
        shadow_maker.record(
            db, prediction_id=1, market_id="m1", pipeline="btc_5m",
            cycle=1, direction="UP", estimate=0.62, conviction=3,
            regime="MEDIUM_VOL / NEUTRAL",
            best_bid=0.50, best_ask=0.54, spread=0.04, mid=0.52,
            shadow_price=0.51, shadow_side="BUY",
        )
        db.execute("INSERT INTO markets VALUES ('m1', 1, 1, 0.52)")
        db.commit()

        n_resolved, n_filled = shadow_maker.resolve_shadow_fills_polymarket(
            db, "btc_5m")
        assert n_resolved == 1
        assert n_filled == 1
        row = db.execute(
            "SELECT filled, adverse, fill_candle_close FROM shadow_maker"
        ).fetchone()
        assert row[0] == 1
        assert row[1] == 0  # not adverse — we bought YES, YES won
        assert row[2] == 1.0
        db.close()

    def test_buy_fills_and_loses_when_yes_resolves_no(self):
        """BUY shadow when NO wins → filled + adverse."""
        db = self._setup_db()
        shadow_maker.record(
            db, prediction_id=1, market_id="m1", pipeline="btc_5m",
            cycle=1, direction="UP", estimate=0.62, conviction=3,
            regime="MEDIUM_VOL / NEUTRAL",
            best_bid=0.50, best_ask=0.54, spread=0.04, mid=0.52,
            shadow_price=0.51, shadow_side="BUY",
        )
        db.execute("INSERT INTO markets VALUES ('m1', 1, 0, 0.52)")
        db.commit()

        n_resolved, n_filled = shadow_maker.resolve_shadow_fills_polymarket(
            db, "btc_5m")
        assert n_resolved == 1
        assert n_filled == 1
        row = db.execute(
            "SELECT filled, adverse FROM shadow_maker"
        ).fetchone()
        assert row[0] == 1
        assert row[1] == 1  # adverse — we bought YES, NO won
        db.close()

    def test_idempotent(self):
        """Second call does not re-resolve already-resolved rows."""
        db = self._setup_db()
        shadow_maker.record(
            db, prediction_id=1, market_id="m1", pipeline="btc_5m",
            cycle=1, direction="UP", estimate=0.62, conviction=3,
            regime="MEDIUM_VOL / NEUTRAL",
            best_bid=0.50, best_ask=0.54, spread=0.04, mid=0.52,
            shadow_price=0.51, shadow_side="BUY",
        )
        db.execute("INSERT INTO markets VALUES ('m1', 1, 1, 0.52)")
        db.commit()

        n1, _ = shadow_maker.resolve_shadow_fills_polymarket(db, "btc_5m")
        n2, _ = shadow_maker.resolve_shadow_fills_polymarket(db, "btc_5m")
        assert n1 == 1
        assert n2 == 0  # already resolved, no-op
        db.close()
