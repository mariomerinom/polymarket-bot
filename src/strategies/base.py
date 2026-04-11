"""
Strategy Lab base types.

Strategies are plain functions with signature:
    def signal(ctx: StrategyContext) -> StrategySignal | None

Returns None when there's no signal this cycle.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StrategyContext:
    """Market state passed to every strategy function.

    Built from data already in memory (candle buffer, TA engine output).
    No data is copied — candles and indicators are references.
    """
    symbol: str              # "BTCUSDT"
    timeframe: str           # "5"
    pipeline: str            # "btc_5m" — which production pipeline triggered this
    candles: list            # from candle_buffer (already in memory)
    indicators: dict | None  # from TAEngine (already computed)
    regime: dict | None      # from compute_regime_from_candles
    current_price: float
    timestamp: datetime
    # Optional enrichment (not always available):
    orderbook: dict | None = None
    funding_rate: float | None = None
    consensus: dict | None = None


@dataclass
class StrategySignal:
    """Output from a strategy function."""
    direction: str           # "UP" or "DOWN"
    estimate: float          # 0.0 - 1.0
    conviction: int          # 0-5
    reason: str
    metadata: dict = field(default_factory=dict)
