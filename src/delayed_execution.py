"""Delayed BTC 5m timing candidates routed through FAK execution."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


MAX_ORDERBOOK_AGE_MS = 2_000
DELAYED_POLICIES = {
    "delay_180_shadow": (180, "shadow"),
    "delay_240_shadow": (240, "shadow"),
    "delay_180_paper": (180, "paper"),
    "delay_240_paper": (240, "paper"),
    "delay_180_live_canary": (180, "live_canary"),
    "delay_240_live_canary": (240, "live_canary"),
}


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS btc5m_timing_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_poll_id INTEGER NOT NULL,
    cycle INTEGER,
    market_id TEXT NOT NULL,
    offset_seconds INTEGER,
    policy TEXT NOT NULL,
    state TEXT NOT NULL,
    would_fire INTEGER DEFAULT 0,
    skip_reason TEXT,
    prediction_id INTEGER,
    order_id INTEGER,
    estimate REAL,
    conviction_score INTEGER,
    direction TEXT,
    entry_price REAL,
    orderbook_age_ms INTEGER,
    pnl REAL,
    ehr REAL,
    created_at TEXT NOT NULL,
    UNIQUE(source_poll_id, policy)
);
"""


def init_table(db: sqlite3.Connection) -> None:
    db.execute(SCHEMA_SQL)
    db.commit()


def should_suppress_immediate(pipeline_name: str = "btc_5m") -> bool:
    if pipeline_name != "btc_5m":
        return False
    try:
        from pipeline_control import get_timing_policy
        policy = get_timing_policy(pipeline_name)
    except Exception:
        return False
    mode = DELAYED_POLICIES.get(policy, (None, None))[1]
    return mode in {"paper", "live_canary"}


def process_delayed_poll(
    db: sqlite3.Connection,
    poll_id: int,
    *,
    pipeline_name: str = "btc_5m",
) -> dict | None:
    """Evaluate one multi-poll row as a delayed execution candidate."""
    if pipeline_name != "btc_5m":
        return None
    try:
        from pipeline_control import get_timing_policy
        policy = get_timing_policy(pipeline_name)
    except Exception:
        policy = "immediate"
    if policy not in DELAYED_POLICIES:
        return None
    wanted_offset, mode = DELAYED_POLICIES[policy]

    init_table(db)
    try:
        import trade
        trade.ensure_orders_table(db)
    except Exception:
        pass
    row = _load_poll(db, poll_id)
    if row is None or int(row["offset_seconds"]) != wanted_offset:
        return None

    evaluation = _evaluate_candidate(db, row, policy)
    if evaluation["skip_reason"]:
        evaluation["state"] = "shadow_skipped" if mode == "shadow" else "blocked"
        return _store_candidate(db, evaluation)

    if mode == "shadow":
        evaluation["state"] = "shadow_would_place"
        evaluation["would_fire"] = 1
        return _store_candidate(db, evaluation)

    if _existing_order(db, row["market_id"], row["cycle"]):
        evaluation["state"] = "blocked"
        evaluation["skip_reason"] = "duplicate_immediate_order"
        return _store_candidate(db, evaluation)

    trading_enabled = False
    if mode == "live_canary":
        blockers = _readiness_blockers(db)
        if blockers:
            evaluation["state"] = "blocked"
            evaluation["skip_reason"] = "readiness_blocked: " + "; ".join(blockers[:3])
            return _store_candidate(db, evaluation)
        trading_enabled = True

    import trade
    order = trade.place_order(
        db,
        row["market_id"],
        evaluation["prediction_id"],
        evaluation.pop("_order_params"),
        row["cycle"],
        clob_token_id=evaluation.get("_clob_token_id"),
        trading_enabled=trading_enabled,
        pipeline_name=pipeline_name,
    )
    local_order_id = db.execute("SELECT MAX(id) FROM orders").fetchone()[0]
    evaluation["order_id"] = local_order_id
    evaluation["state"] = "live_ordered" if trading_enabled else "paper_ordered"
    evaluation["would_fire"] = 1
    evaluation["entry_price"] = order.get("price_limit")
    return _store_candidate(db, evaluation)


def _load_poll(db: sqlite3.Connection, poll_id: int):
    try:
        return db.execute(
            """
            SELECT mpp.*, m.price_yes, m.price_no, m.resolved, m.outcome
            FROM multi_poll_predictions mpp
            JOIN markets m ON m.id = mpp.market_id
            WHERE mpp.id = ?
            """,
            (poll_id,),
        ).fetchone()
    except sqlite3.Error:
        return None


def _evaluate_candidate(db: sqlite3.Connection, row, policy: str) -> dict:
    direction = None
    if row["estimate"] is not None and row["estimate"] != 0.5:
        direction = "UP" if row["estimate"] > 0.5 else "DOWN"
    now = datetime.now(timezone.utc).isoformat()
    result = {
        "source_poll_id": row["id"],
        "cycle": row["cycle"],
        "market_id": row["market_id"],
        "offset_seconds": row["offset_seconds"],
        "policy": policy,
        "state": "blocked",
        "would_fire": 0,
        "skip_reason": None,
        "prediction_id": None,
        "order_id": None,
        "estimate": row["estimate"],
        "conviction_score": row["conviction_score"],
        "direction": direction,
        "entry_price": None,
        "orderbook_age_ms": row["orderbook_age_ms"],
        "pnl": None,
        "ehr": None,
        "created_at": now,
    }

    skip = _basic_skip(row)
    if skip:
        result["skip_reason"] = skip
        return result

    pred_id = _prediction_id(db, row["market_id"], row["cycle"])
    if pred_id is None:
        result["skip_reason"] = "missing_prediction_link"
        return result
    result["prediction_id"] = pred_id

    pred = {
        "id": pred_id,
        "market_id": row["market_id"],
        "estimate": row["estimate"],
        "conviction_score": row["conviction_score"],
        "reasoning": "{}",
        "agent": "momentum_rule",
        "price_yes": row["mkt_mid"] or row["price_yes"] or 0.5,
        "price_no": 1 - (row["mkt_mid"] or row["price_yes"] or 0.5),
    }
    try:
        import trade
        ok, reason = trade.should_trade(pred, db, pipeline_name="btc_5m")
    except Exception as exc:
        ok, reason = False, f"readiness_error ({exc})"
    if not ok:
        result["skip_reason"] = reason
        return result

    market_row = _market_row(row)
    try:
        import trade
        order_params, order_reason = trade.compute_order(pred, market_row, None)
    except Exception as exc:
        order_params, order_reason = None, f"compute_order_error ({exc})"
    if order_params is None:
        result["skip_reason"] = order_reason
        return result
    if order_params.get("order_type") != "fak":
        result["skip_reason"] = "non_fak_order"
        return result
    tokens = _get_tokens(row["market_id"])
    token_id = tokens.get(order_params["token"]) if tokens else None
    result["_order_params"] = order_params
    result["_clob_token_id"] = token_id
    return result


def _basic_skip(row) -> str | None:
    if not row["poll_succeeded"]:
        return "poll_failed"
    if row["conviction_score"] is None:
        return "missing_conviction"
    if int(row["conviction_score"]) < 3:
        return "low_conviction"
    if row["estimate"] is None or row["estimate"] == 0.5:
        return "neutral_estimate"
    if row["orderbook_age_ms"] is None:
        return "missing_book"
    if int(row["orderbook_age_ms"]) >= MAX_ORDERBOOK_AGE_MS:
        return "stale_book"
    if row["mkt_best_bid"] is None or row["mkt_best_ask"] is None:
        return "missing_book"
    return None


def _market_row(row) -> dict:
    mid = row["mkt_mid"] or row["price_yes"] or 0.5
    bid = row["mkt_best_bid"]
    ask = row["mkt_best_ask"]
    spread = row["mkt_spread"]
    return {
        "price_yes": mid,
        "price_no": 1 - mid,
        "_clob_verified": {"yes": True, "no": True},
        "_yes_best_bid": bid,
        "_yes_best_ask": ask,
        "_yes_spread": spread,
        "_no_best_bid": 1 - ask if ask is not None else None,
        "_no_best_ask": 1 - bid if bid is not None else None,
        "_no_spread": spread,
    }


def _prediction_id(db: sqlite3.Connection, market_id: str, cycle: int) -> int | None:
    row = db.execute(
        "SELECT id FROM predictions WHERE market_id = ? AND cycle = ? "
        "ORDER BY id DESC LIMIT 1",
        (market_id, cycle),
    ).fetchone()
    return row[0] if row else None


def _existing_order(db: sqlite3.Connection, market_id: str, cycle: int) -> bool:
    try:
        row = db.execute(
            "SELECT 1 FROM orders WHERE market_id = ? AND cycle = ? LIMIT 1",
            (market_id, cycle),
        ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False


def _store_candidate(db: sqlite3.Connection, data: dict) -> dict:
    clean = {k: v for k, v in data.items() if not k.startswith("_")}
    db.execute(
        """
        INSERT OR REPLACE INTO btc5m_timing_candidates
        (source_poll_id, cycle, market_id, offset_seconds, policy, state,
         would_fire, skip_reason, prediction_id, order_id, estimate,
         conviction_score, direction, entry_price, orderbook_age_ms, pnl, ehr,
         created_at)
        VALUES (:source_poll_id, :cycle, :market_id, :offset_seconds, :policy,
                :state, :would_fire, :skip_reason, :prediction_id, :order_id,
                :estimate, :conviction_score, :direction, :entry_price,
                :orderbook_age_ms, :pnl, :ehr, :created_at)
        """,
        clean,
    )
    db.commit()
    return clean


def _get_tokens(market_id: str) -> dict | None:
    try:
        from clob_depth import get_clob_tokens_safe
        return get_clob_tokens_safe(market_id)
    except Exception:
        return None


def _readiness_blockers(db: sqlite3.Connection) -> list[str]:
    try:
        from canary_readiness import (
            btc5m_delayed_policy_blockers,
            btc5m_live_canary_blockers,
        )
        return btc5m_live_canary_blockers(db) + btc5m_delayed_policy_blockers(db)
    except Exception as exc:
        return [f"readiness_unavailable ({exc})"]
