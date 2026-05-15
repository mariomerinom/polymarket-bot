"""
config.py — Centralized trading configuration.

Every hardcoded value that impacts whether money is risked, how much,
or signal quality lives here. Prototyping shortcuts that survived into
production are documented with their derivation (or lack thereof).

Categories:
  1. Risk controls — env-overridable, gate real money
  2. Signal tuning — per-asset regime/conviction/estimate parameters
  3. Operational — dates, API params, sizing dicts
  4. Candle patterns — shared between btc_data.py and eth_data.py

Decision #21 (2026-04-02): Dynamic estimates replaced hardcoded 0.62/0.38.
This file prevents a repeat by centralizing all magic numbers.
"""

import os


def _env(name, default):
    """Get env var, treating empty string same as unset."""
    val = os.getenv(name, "")
    return val if val else default


# ══════════════════════════════════════════════════════════════════════════════
# 1. RISK CONTROLS — env-overridable, gate real money
# ══════════════════════════════════════════════════════════════════════════════

BET_SIZE = float(_env("BET_SIZE", "25"))              # Flat $25 medium grind (Phase 1)
DAILY_LOSS_LIMIT = float(_env("DAILY_LOSS_LIMIT", "300"))  # Circuit breaker
CONSECUTIVE_LOSS_MAX = int(_env("CONSECUTIVE_LOSS_MAX", "5"))
MAX_LOSS_LOOKBACK = 50                                     # Orders history lookback
# MAX_DRAWDOWN_PCT removed — cold start bug tripped at 78.5% on $17 peak equity.
# Daily loss limit + consecutive loss breaker are sufficient protection.
MIN_CONVICTION = int(_env("MIN_CONVICTION", "3"))          # Conv < 3 = paper only
MAX_SLIPPAGE_PCT = float(_env("MAX_SLIPPAGE_PCT", "2.0"))  # 2% max
EDGE_THRESHOLD = float(_env("EDGE_THRESHOLD", "0.05"))     # 5% min edge to trade
MAX_SLIPPAGE_SPREAD = float(_env("MAX_SLIPPAGE_SPREAD", "0.05"))  # 5¢ max above market mid

# FAK/IOC execution layer (Phase 1): min_edge = spread + FOK_EDGE_BUFFER.
# The constant name is kept for backward compatibility with older tests/config.
FOK_EDGE_BUFFER = float(_env("FOK_EDGE_BUFFER", "0.02"))  # 2¢ above spread

# Lever B (spec_fill_adverse_selection.md): minimum edge that must remain
# AFTER the price cushion is applied. If applying any cushion would push the
# net edge below this floor, the bet is skipped instead of taken at worse EV.
# Reference: 2026-04-06 incident — naive 1¢ cushion would convert marginal
# +EV trades into losers when signal edge is small.
MIN_POST_CUSHION_EDGE = float(_env("MIN_POST_CUSHION_EDGE", "0.02"))  # 2¢ floor

# Lever B: maximum cushion above best_ask for FAK (IOC) orders. The actual
# cushion applied is min(this, spread/2, alpha-cap). 1¢ is enough to walk
# into the second level when the top-of-book gets pulled mid-flight.
MAX_FAK_CUSHION = float(_env("MAX_FAK_CUSHION", "0.01"))  # 1¢ ceiling

# Fee assumption for P&L.
# Source: Polymarket docs — 2% on winning side, ~0% on losing.
# 0.985 = (1 - 0.015) round-trip estimate. VERIFY if fee structure changes.
POLYMARKET_FEE_FACTOR = float(_env("POLYMARKET_FEE_FACTOR", "0.985"))

# Book depth: when CLOB is thin, use this fraction of max@2% slippage
BOOK_DEPTH_SAFETY_MARGIN = 0.9   # 90% of available depth
MIN_BET_SIZE = 5                 # Don't place orders below $5

# Fill priority: widen limit price by this amount to improve fill rate.
# At 53% fill rate (8/8 expired orders were winners → $165 missed profit),
# sacrificing 2¢ of edge per bet is massively +EV.
# Source: Reconciliation 2026-04-02 — 8 expired, all correct, all unfilled.
FILL_PRIORITY_SPREAD = float(_env("FILL_PRIORITY_SPREAD", "0.02"))  # 2¢

# ETH-specific sizing (thinner book)
# Source: ETH avg spread 3.98%, max bet @2% slippage: $149
ETH_BET_SIZES = {3: 25, 4: 50, 5: 75}
ETH_MAX_BET_CEILING_PCT = 0.50   # Never exceed 50% of available liquidity @2%


# ══════════════════════════════════════════════════════════════════════════════
# 2. SIGNAL TUNING — per-asset regime/conviction/estimate parameters
# ══════════════════════════════════════════════════════════════════════════════

# ── Regime classification thresholds ─────────────────────────────────────────

# BTC volatility buckets (per-candle range %).
# Source: empirical from 227+ paper bets. NOT derived from percentile analysis.
# TODO: Derive from P25/P75 like ETH thresholds were.
BTC_VOL_LOW = 0.05              # < 0.05% = LOW_VOL
BTC_VOL_HIGH = 0.12             # >= 0.12% = HIGH_VOL, else MEDIUM_VOL

# ETH volatility buckets.
# Source: P25=0.096, P75=0.195 from 99 historical predictions. Well-justified.
ETH_VOL_LOW = 0.10              # Rounded P25
ETH_VOL_HIGH = 0.20             # Rounded P75

# Autocorrelation thresholds
AUTOCORR_TRENDING = 0.15        # > 0.15 = TRENDING
AUTOCORR_MEAN_REVERTING_5M = -0.15   # < -0.15 = MEAN_REVERTING (5m default)
AUTOCORR_MEAN_REVERTING_15M = -0.20  # < -0.20 = MEAN_REVERTING (15m, relaxed)

# ── Price gates ──────────────────────────────────────────────────────────────
# Skip markets at extreme prices where risk/reward is mathematically terrible.
# At price 0.95, need 95% WR to break even. Our signal hits ~66%.
PRICE_GATE_UPPER = 0.85         # Skip YES > 85%
PRICE_GATE_LOWER = 0.15         # Skip YES < 15%

# Extreme estimate override: estimates beyond these thresholds bypass
# dead hour, price gate, and mean-reversion gates (80%+ WR, Phase 1 analysis).
EXTREME_ESTIMATE_UPPER = 0.65    # estimate > 0.65 → bypass skip gates
EXTREME_ESTIMATE_LOWER = 0.35    # estimate < 0.35 → bypass skip gates

# UP conviction "sweet spot" — boost to conv=4 when market price in this range.
# Source: empirical observation from 5m paper data. Needs formal validation.
# TODO: Validate with 50+ bets in/out of sweet spot.
PRICE_SWEET_SPOT_LOW = 0.20
PRICE_SWEET_SPOT_HIGH = 0.70

# ── Conviction scoring ───────────────────────────────────────────────────────
# Streak length where confidence label changes
CONFIDENCE_HIGH_STREAK = 5      # abs(streak) >= 5 → "high" confidence

# Max conviction with consensus boost
MAX_CONVICTION = 5
ESTIMATE_FALLBACK_UP = 0.55
ESTIMATE_FALLBACK_DOWN = 0.45

CONVICTION_WEIGHT_CONTRARIAN = 0.55
CONVICTION_WEIGHT_VOLUME = 0.45
CONVICTION_BLENDED_UP = 0.52
CONVICTION_BLENDED_DN = 0.48
CONVICTION_MAGNITUDE = 0.04

AGENT_PIPELINE_MAP = {
    "eth": "eth_5m",
    "bybit": "bybit",
    "kalshi": "kalshi",
    "hl": "hl_5m",
    "eth_bybit": "eth_bybit_5m",
    "eth_hl": "eth_hl_5m",
    "sol_bybit": "sol_bybit_5m",
    "sol_hl": "sol_hl_5m",
    "doge_bybit": "doge_bybit_5m",
    "doge_hl": "doge_hl_5m",
}

# ── Shadow conviction scorer configs ─────────────────────────────────────────
# CRITICAL: max_edge MUST produce edge > EDGE_THRESHOLD at min_streak.
# Example: BTC max_edge=0.14, streak=3, log(3)/log(8)=0.528 → edge≈0.074 > 0.05 ✓
# Example: ETH max_edge=0.10, streak=3, log(3)/log(6)=0.613 → edge≈0.061 > 0.05 ✓
# If you change max_edge or EDGE_THRESHOLD, verify this invariant!

SHADOW_CONFIGS = {
    "btc_5m": {
        "min_streak": 3,
        "baseline_streak": 8,       # Log curve denominator. Source: empirical tuning.
        "magnitude_multiplier": 2.0, # Sensitivity to price moves. Source: empirical.
        "max_edge": 0.14,           # Caps estimate at 0.36–0.64 range.
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],  # edge → tier 2/3/4/5
    },
    "btc_15m": {
        "min_streak": 3,            # Now using 5m candles — same as btc_5m
        "baseline_streak": 8,       # Match btc_5m (was 5)
        "magnitude_multiplier": 2.0, # Match btc_5m (was 2.5)
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],
    },
    "eth_5m": {
        # Recalibrated 2026-04-02: max_edge bumped 0.08→0.10 so streak=3
        # clears EDGE_THRESHOLD=0.05 (was 0.049, now 0.061).
        "min_streak": 3,
        "baseline_streak": 6,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.10,
        "high_confidence_threshold": 0.85,
        "conv_thresholds": [0.03, 0.04, 0.05, 0.07],
    },
    "kalshi": {
        "min_streak": 2,
        "baseline_streak": 5,
        "magnitude_multiplier": 2.5,
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],
    },
    "bybit_5m": {
        "min_streak": 3,
        "baseline_streak": 8,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],
    },
    "hl_5m": {
        "min_streak": 3,
        "baseline_streak": 8,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],
    },
    # ── Multi-pair perp shadow configs ──────────────────────────────────
    "eth_bybit_5m": {
        "min_streak": 3,
        "baseline_streak": 6,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.10,
        "high_confidence_threshold": 0.85,
        "conv_thresholds": [0.03, 0.04, 0.05, 0.07],
    },
    "eth_hl_5m": {
        "min_streak": 3,
        "baseline_streak": 6,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.10,
        "high_confidence_threshold": 0.85,
        "conv_thresholds": [0.03, 0.04, 0.05, 0.07],
    },
    "sol_bybit_5m": {
        "min_streak": 3,
        "baseline_streak": 8,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],
    },
    "sol_hl_5m": {
        "min_streak": 3,
        "baseline_streak": 8,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],
    },
    "doge_bybit_5m": {
        "min_streak": 3,
        "baseline_streak": 8,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],
    },
    "doge_hl_5m": {
        "min_streak": 3,
        "baseline_streak": 8,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],
    },
}

VOL_FLOOR = 0.02  # Prevent division by near-zero volatility

# ── VWAP mean-reversion thresholds ───────────────────────────────────────────
# Validated: 42/50 shadow bets at 78.6% WR (Decision #23)
VWAP_ZSCORE_STRONG = 2.0        # |z| >= 2.0 → conv=3 (live bet)
VWAP_ZSCORE_MODERATE = 1.5      # 1.5 <= |z| < 2.0 → conv=2 (tracked)
VWAP_EDGE_MULTIPLIER = 0.03     # edge = min(|z| × 0.03, max_edge)
VWAP_MAX_EDGE = 0.14            # Cap consistent with BTC shadow config

# ── Dead hours ───────────────────────────────────────────────────────────────
FALLBACK_DEAD_HOURS = {3, 21}        # UTC hours skipped when DB has insufficient data
# Note: Hour 16 removed — was added by hour_16_dead_gate optimization (closed, no edge).
DEAD_HOUR_LOOKBACK_DAYS = 90
DEAD_HOUR_MIN_BETS = 30
DEAD_HOUR_MAX_WR = 0.50

# ── OBV shadow indicator ────────────────────────────────────────────────────
OBV_WINDOW = 10                 # Linear regression window for OBV slope
OBV_PRICE_BUCKET_LOW = 0.50     # Only attach OBV for markets in this price range
OBV_PRICE_BUCKET_HIGH = 0.70


# ══════════════════════════════════════════════════════════════════════════════
# 3. OPERATIONAL — dates, API params, sizing dicts
# ══════════════════════════════════════════════════════════════════════════════

LIVE_START_DATE = "2026-04-01"  # Date boundary for paper→live bet sizing
POLYMARKET_CHAIN_ID = 137       # Polygon mainnet

# Date-aware bet sizing for P&L reporting (daily_report + optimization_tracker)
PAPER_BTC_CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 75, 4: 200, 5: 300}
PAPER_ETH_CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 25, 4: 50, 5: 75}
LIVE_BTC_CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 25, 4: 25, 5: 25}
LIVE_ETH_CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 25, 4: 25, 5: 25}
LIVE_KALSHI_CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 25, 4: 25, 5: 25}

# ── Bybit perpetual futures ─────────────────────────────────────────────────
# Position size in BTC (0.005 = ~$420 at $84k). No leverage (1x).
BYBIT_BET_SIZE = float(_env("BYBIT_BET_SIZE", "0.005"))
BYBIT_DAILY_LOSS_LIMIT = float(_env("BYBIT_DAILY_LOSS_LIMIT", "50"))
BYBIT_MAX_HOLD_CYCLES = int(_env("BYBIT_MAX_HOLD_CYCLES", "6"))
BYBIT_STOP_ATR_MULT = float(_env("BYBIT_STOP_ATR_MULT", "1.5"))
BYBIT_FEE_RATE = 0.0002    # 0.02% maker (limit orders per bybit_trade.py)
BYBIT_MIN_CONVICTION = int(_env("BYBIT_MIN_CONVICTION", "3"))
API_TIMEOUT_BYBIT = 10
LIVE_BYBIT_CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 0.005, 4: 0.005, 5: 0.005}

# ── Hyperliquid perpetual futures ──────────────────────────────────────────
# Same position size as Bybit. Maker REBATE (negative fee = credit).
# No KYC required — on-chain settlement on Arbitrum.
HL_BET_SIZE = float(_env("HL_BET_SIZE", "0.005"))
HL_DAILY_LOSS_LIMIT = float(_env("HL_DAILY_LOSS_LIMIT", "50"))
HL_MAX_HOLD_CYCLES = int(_env("HL_MAX_HOLD_CYCLES", "6"))
HL_STOP_ATR_MULT = float(_env("HL_STOP_ATR_MULT", "1.5"))
HL_FEE_RATE = -0.0002     # -0.02% maker REBATE (negative = credit)
HL_MIN_CONVICTION = int(_env("HL_MIN_CONVICTION", "3"))
LIVE_HL_CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 0.005, 4: 0.005, 5: 0.005}

# ── Multi-pair perpetual futures ───────────────────────────────────────────
# ETH perps (signal validated at ~60% WR, same momentum strategy)
PERP_ETH_BET_SIZE = float(_env("PERP_ETH_BET_SIZE", "0.05"))  # ~$180 at $3600

# SOL perps (new pair, paper validation needed)
PERP_SOL_BET_SIZE = float(_env("PERP_SOL_BET_SIZE", "1.0"))  # ~$150 at $150

# DOGE perps (retail momentum, paper validation needed)
PERP_DOGE_BET_SIZE = float(_env("PERP_DOGE_BET_SIZE", "1000"))  # ~$170 at $0.17

# API timeouts (seconds)
API_TIMEOUT_EXCHANGE = 10       # Kraken, Coinbase candle fetches
API_TIMEOUT_CLOB = 5            # CLOB book depth queries
API_TIMEOUT_SUBMIT = 10         # CLOB order submission timeout
API_TIMEOUT_GAMMA = 5           # Polymarket Gamma API
API_TIMEOUT_BULK = 15           # Multi-interval rolling bias fetches
API_TIMEOUT_KALSHI = 10
API_TIMEOUT_BYBIT = 10
API_TIMEOUT_LLM = 30            # DO Serverless Inference (LLM calls)
DEFAULT_CANDLE_LIMIT = 20
SHADOW_CANDLE_LIMIT = 30
CONTEXT_LOOKBACK_MINUTES = 60
DB_BUSY_TIMEOUT_MS = 5000
SETTLEMENT_DELAY_S = 120
DASHBOARD_RECENT_LIMIT = 50


# ══════════════════════════════════════════════════════════════════════════════
# 4. CANDLE PATTERNS — shared between btc_data.py and eth_data.py
# ══════════════════════════════════════════════════════════════════════════════
# Source: standard technical analysis conventions. Not validated on our data.
# TODO: AB test these against live predictions once 200+ pattern-tagged bets resolve.

DOJI_BODY_FRACTION = 0.15       # body < 15% of full range = doji
DOJI_WICK_RATIO = 0.7           # wick_ratio > 70% confirms doji
HAMMER_WICK_RATIO = 2           # lower_wick > 2× body = hammer
ENGULFING_BODY_RATIO = 1.1      # last_body > 110% of prev_body = engulfing
TREND_FILTER_OFFSET = 2         # trend = "up" if ups > downs + 2
STREAK_AGREEMENT_MIN = 2        # Both exchanges streak >= 2 for consensus
