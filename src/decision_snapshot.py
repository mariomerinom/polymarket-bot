"""Immutable per-cycle decision state object for the BTC 5m execution path.

Architecture (plan Increment C)
--------------------------------
A single `DecisionSnapshot` is created at the start of each prediction in
`execute_trades` and advanced through well-defined states via `advance()`.
Because the dataclass is frozen, each state transition produces a new object;
the previous state is never mutated.  This makes the full decision chain
auditable and testable without an ORM or a new table.

DecisionState values are defined in forward-progress order (lower = earlier),
making it easy to assert ``snapshot.state.value >= DecisionState.BOOK_FRESH.value``
in promotion or audit code.

Three fields survive into the `orders` table:
  orderbook_age_ms    — `book_age_ms` at the time of final state
  snapshot_verified   — carried from the book evidence
  decision_at         — the `decision_at` field (set before `place_order`)

These are written by `trade._store_order` after `ensure_orders_table` adds
the columns via its ALTER loop.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum
from typing import Optional


class DecisionState(IntEnum):
    """Forward-progress states for a single BTC 5m order decision.

    Values are monotonically increasing so ``state.value >= X.value`` is a
    valid "at-least-as-far" predicate.
    """
    ELIGIBLE            = 10  # Prediction qualifies by conviction/edge
    RESOLVED            = 20  # CLOB tokens resolved
    EVIDENCE_SELECTED   = 30  # Side evidence (yes/no book) chosen
    BOOK_FRESH          = 40  # Book passed the freshness gate
    ORDER_COMPUTED      = 50  # compute_order() returned params
    SUBMITTED           = 60  # place_order() called (paper or live)
    SKIPPED             = 65  # Stopped before submission (book stale, low edge, …)
    TERMINAL_CLASSIFIED = 70  # Order fill/reject classified
    RECONCILED          = 80  # P&L settled against resolved market


@dataclass(frozen=True)
class DecisionSnapshot:
    """Immutable snapshot of one BTC 5m order decision.

    Use `advance(new_state, **field_overrides)` to produce the next state;
    the original is never mutated.
    """
    cycle: int
    market_id: str
    side: str                          # "yes" | "no"
    token_id: Optional[str]
    best_bid: Optional[float]
    best_ask: Optional[float]
    spread: Optional[float]
    book_age_ms: Optional[int]         # last_event_ms age at read time
    snapshot_verified: bool            # True iff WS book / REST seed applied
    computed_size: Optional[float]
    limit_price: Optional[float]
    edge: Optional[float]
    state: DecisionState
    skip_reason: Optional[str]
    submitted_at: Optional[str]        # ISO timestamp
    terminal_result: Optional[str]     # "filled" | "rejected" | "expired" …
    pnl: Optional[float]
    decision_at: str                   # ISO timestamp; set before place_order

    def advance(self, state: DecisionState, **changes) -> "DecisionSnapshot":
        """Return a new snapshot with `state` advanced and optional field overrides.

        Example::

            snap = snap.advance(DecisionState.BOOK_FRESH)
            snap = snap.advance(
                DecisionState.ORDER_COMPUTED,
                computed_size=25.0,
                limit_price=0.63,
                edge=0.05,
            )
        """
        return replace(self, state=state, **changes)
