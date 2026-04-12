"""
Momentum Lab strategy — the production momentum signal, replicated in
the Strategy Lab for parameter optimization.

ALWAYS fires. Uses streak-based momentum (same as production BTC 5m)
but logs ALL indicators so we can optimize which features should
gate/boost the momentum signal.

Post-hoc analysis answers:
- Does RSI > 70 during UP streaks predict continuation or exhaustion?
- Does BB bandwidth < 2 during streaks predict breakout or reversal?
- Which regime × streak combinations have the best WR?
- Should conviction scale with z-score? RVOL? Stochastic crossover?
"""

from strategies.base import StrategySignal, indicator_snapshot


def signal(ctx):
    """Momentum signal with full indicator logging.

    Same core logic as production: streak direction = prediction direction.
    But stores everything for parameter optimization.
    """
    if not ctx.candles or len(ctx.candles) < 3:
        return None

    # Streak detection — same as production
    last_dir = "UP" if ctx.candles[-1]["close"] >= ctx.candles[-1]["open"] else "DOWN"
    streak = 0
    for candle in reversed(ctx.candles):
        candle_dir = "UP" if candle["close"] >= candle["open"] else "DOWN"
        if candle_dir == last_dir:
            streak += 1
        else:
            break

    # Momentum: ride the streak
    direction = last_dir

    # Conviction from streak length (production uses this)
    if streak >= 4:
        conviction = 4
    elif streak >= 3:
        conviction = 3
    elif streak >= 2:
        conviction = 2
    else:
        conviction = 1

    estimate = 0.50 + min(streak * 0.02, 0.15)
    if direction == "DOWN":
        estimate = 1.0 - estimate

    # Full indicator snapshot
    meta = indicator_snapshot(ctx)
    meta.update({
        "streak_length": streak,
        "streak_direction": direction,
        "production_would_bet": streak >= 3,  # production needs conv >= 3
    })

    return StrategySignal(
        direction=direction,
        estimate=round(estimate, 4),
        conviction=conviction,
        reason=f"momentum_lab streak={streak} {direction}",
        metadata=meta,
    )
