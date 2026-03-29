# Optimization Tracker API Reference

File: `src/optimization_tracker.py`
Data: `docs/optimizations.json`

## Python Functions

### `register(name, description, revert_condition, min_sample=50, pipeline="5m")`
Create a new optimization entry. Computes baseline stats from the full DB at registration time.
- `name`: snake_case identifier (must be unique among active optimizations)
- `description`: human-readable explanation of what changed
- `revert_condition`: Python expression evaluated when min_sample is reached
  - Available vars: `post_wr`, `baseline_wr`, `post_bets`, `post_pnl`, `baseline_pnl`
- `min_sample`: minimum post-change bets before evaluation (default 50)
- `pipeline`: `"5m"` or `"15m"`
- Returns the entry dict, or None if duplicate/error

### `check_all()`
Check all active optimizations. Computes post-change stats, evaluates revert conditions if sample met.
- Returns list of alert strings (progress, validation, or revert alerts)
- Side effect: updates `optimizations.json` with latest stats

### `close(name, status="validated", reason=None)`
Close an active optimization.
- `status`: `"validated"`, `"reverted"`, or `"deferred"`
- `reason`: human-readable explanation
- Returns the closed entry dict, or None if not found

### `compute_stats(db_path, since=None)`
Aggregate stats from DB. Filters to resolved predictions with conviction >= 3.
- `since`: ISO timestamp to filter predictions after this date
- Returns: `{"bets": int, "wins": int, "wr": float, "pnl": float, "wagered": float}`

### `summary()`
Print formatted summary of active and closed optimizations to stdout.

### `load_optimizations()` / `save_optimizations(data)`
Read/write `docs/optimizations.json`. Schema:
```json
{
  "optimizations": [
    {
      "name": "string",
      "description": "string",
      "registered_at": "ISO timestamp",
      "pipeline": "5m|15m",
      "status": "active|validated|reverted|deferred",
      "min_sample": 50,
      "revert_condition": "python expression string",
      "baseline": {"bets": 0, "wins": 0, "wr": 0, "pnl": 0, "wagered": 0},
      "latest_check": "ISO timestamp|null",
      "post_stats": {"bets": 0, "wins": 0, "wr": 0, "pnl": 0, "wagered": 0},
      "closed_at": "ISO timestamp|null",
      "close_reason": "string|null"
    }
  ]
}
```

## CLI Commands

```bash
# Register
python3 src/optimization_tracker.py register \
  --name NAME --description DESC --revert-if EXPR \
  [--min-sample 50] [--pipeline 5m]

# Check all active
python3 src/optimization_tracker.py check

# Close
python3 src/optimization_tracker.py close \
  --name NAME --status validated|reverted|deferred [--reason REASON]

# Summary
python3 src/optimization_tracker.py summary
```

## DB Paths

- 5m: `data/predictions.db`
- 15m: `data/predictions_15m.db`
