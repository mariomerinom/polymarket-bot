# Synthesizing Execution Constants into `config.py`

This plan details the cleanup of legacy and inline anomalous variables flagged in our previous audit covering `trade.py` and `conviction.py`.

## User Review Required

> [!WARNING]
> `conviction.py` appears to be a legacy module largely utilized by visualization tools (`dashboard.py`) and older model tests (`backtest.py`), as V4 natively handles its own conviction gating inline via `predict.py`. Are we safe to modify `conviction.py`'s internal data to trace from `config.py` mappings, or should we just formally deprecate the file?

## Proposed Changes

---

### config.py

We will ingest the stray hardwired identifiers into the config file so they can be globally tuned.

#### [MODIFY] [config.py](file:///Users/mrmrnm-max/polymarket-bot/src/config.py)
Add the following fields: 
- `MAX_LOSS_LOOKBACK = 50`
- `API_TIMEOUT_SUBMIT = 10`
- `POLYMARKET_CHAIN_ID = 137`
- `CONVICTION_WEIGHT_CONTRARIAN = 0.55` and `CONVICTION_WEIGHT_VOLUME = 0.45` 
- Add dynamic model thresholds (`CONVICTION_BLENDED_UP=0.52`, `CONVICTION_BLENDED_DN=0.48`, `CONVICTION_MAGNITUDE=0.04`).

---

### trade.py

#### [MODIFY] [trade.py](file:///Users/mrmrnm-max/polymarket-bot/src/trade.py)
- Replace `LIMIT 50` query inside `_check_consecutive_losses` with `config.MAX_LOSS_LOOKBACK`.
- Replace `signal.alarm(10)` with `config.API_TIMEOUT_SUBMIT`.
- Replace `chain_id=137` with `config.POLYMARKET_CHAIN_ID`.
- Restructure the string parsing inside `_agent_to_pipeline` to rely on a dynamic dict from config rather than `if "eth" in agent... elif...`.

---

### conviction.py

#### [MODIFY] [conviction.py](file:///Users/mrmrnm-max/polymarket-bot/src/conviction.py)
- Import `config.py`.
- Reassign the `weights` dictionary to pull `CONVICTION_WEIGHT_CONTRARIAN` and `CONVICTION_WEIGHT_VOLUME`.
- Parameterize the `< 0.48` and `> 0.52` thresholds.
- Rip out the internal `bet_sizes = {"NO_BET": 0, "LOW": 0, "MEDIUM": 75, "HIGH": 200}` mapping and replace it by dynamically pointing `get_bet_size` logic to `config.PAPER_BTC_CONVICTION_BETS` or `config.LIVE_BTC_CONVICTION_BETS` equivalents. 

## Open Questions

1. Same as highlighted above: Do we even need `conviction.py` anymore? If the live V4 `predict.py` operates without it, perhaps `dashboard.py` should be updated to not rely on an outdated scoring layout. I will clean it up for now, but consider its necessity.

## Verification Plan

### Automated Tests
1. Dry-run `python3 src/ci_run.py --cycle 1` similar to the previous task. Run the pipeline again.
2. Check `dashboard.py` execution generation if applicable, to ensure no legacy dependencies broke.
