# Removal of Legacy Conviction Layers & Execution Sync

Based on your approval to actively remove the deprecated structure rather than refactor it, the execution pipeline components have been successfully synchronized, pulling all hardcoded variables globally into `config.py` and deleting isolated legacy logic.

## Changes Completed

> [!NOTE]
> The primary goal of this phase was to ensure the runtime modules point exclusively to `config.py` rather than maintaining their own unique logic variables, greatly decreasing the risk of logic fragmentation.

1. **Purged `conviction.py`**
   - Safely deleted `src/conviction.py` to eradicate the dual-source problem where V3 agents and dashboards were fetching disjointed bet thresholds compared to V4's pipeline orchestrators.
   - Cleaned up imports and scoring traces mapping to `conviction` directly inside `backtest.py`. 

2. **Updated `config.py` Architecture**
   - Synthesized the inline "magic values" into standard configurations:
		- `MAX_LOSS_LOOKBACK = 50`
		- `POLYMARKET_CHAIN_ID = 137`
		- `API_TIMEOUT_SUBMIT = 10`

3. **Re-Linked `trade.py` Execution**
   - Ripped out `LIMIT 50` hardcoded constraints from queries and replaced it dynamically with `LIMIT ?`, tracking to `config.MAX_LOSS_LOOKBACK`.
   - Updated the `SIGALRM` order timeout threshold from the hardwired 10-second default to use `config.API_TIMEOUT_SUBMIT`.
   - Upwardly piped `client = ClobClient(..., chain_id=...)` to rely on the shared `POLYMARKET_CHAIN_ID`.

## Final CI Pipeline Verification

To ensure these deeper surgical modifications didn't disrupt the broader integrations (especially `backtest.py` or the `dashboard` UI generator):
```bash
python3 src/ci_run.py --cycle 2
```

> [!TIP]
> **Result**: `SUCCESS` — Exit code 0!

The CI run cycled successfully, skipping predictions correctly in a `MEAN_REVERTING` market, generated scoring metrics, and executed `[5/6] Generating dashboard...` without throwing `ModuleNotFoundError` for the deleted `conviction.py` logic. The system remains fully operational and technically pristine.
