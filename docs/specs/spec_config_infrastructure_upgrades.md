# Configuration Architecture Improvements

> **Status:** STILL RELEVANT — Pydantic validation, hot-reload not implemented

## Goal
To outline future structural and operational improvements following the centralization of pipeline parameters into `config.py` (completed 2026-04-03). As the platform migrates to a continuous DigitalOcean VPS droplet, the configuration layer should evolve to support long-polling logic and dynamic scaling requirements seamlessly.

## Improvement Opportunities

### 1. Hot-Reloading Configuration (Dynamic State)
**Problem:** Currently, `config.py` is evaluated and initialized once at python runtime. In the upcoming VPS deployment running continuous infinite loops (`scripts/vps-loop.sh`), modifying configuration states manually requires repeatedly restarting the entire predictive tracking application.
**Solution:** Transition `config.py` into a robust singleton instance or YAML/JSON ingestion pipeline that periodically polls its source mapping asynchronously. This allows variables like `CONVICTION_WEIGHT_CONTRARIAN` or `SHADOW_CANDLE_LIMIT` to dynamically hot-reload mid-cycle without interrupting active trades.

### 2. Pydantic Type Validations & Boundary Security
**Problem:** By relying entirely on naked Python variables inside `config.py`, the system is technically vulnerable to type drift or erroneous macro modifications (e.g., accidentally configuring `"137"` as a string instead of an int, or setting conviction blending rates `<0` or `>1`) which silently bypass Git CI workflows and cause production runtime `TypeErrors`.
**Solution:** Implement `Pydantic` `BaseModels` natively wrapping `config.py`. Enforce strict boundary properties (e.g., locking `CONVICTION_BLENDED_UP` strictly to floats between `0` and `1.0`) forcing hard validation checks immediately.

### 3. Environment Variable Injection (12-Factor Strategy)
**Problem:** Hardcoding operational timings natively to variables (`API_TIMEOUT_CLOB`, `DB_BUSY_TIMEOUT_MS`) restricts infrastructure to only representing one single unified baseline.
**Solution:** Wrap `os.getenv` hooks dynamically as priority fallbacks inside config integrations allowing distinct environments (Staging droplets vs Local Debugging) to aggressively boost delays or shrink thresholds directly through `.env` arguments without committing temporary noise variables directly into GitHub.

### 4. Adaptive API Rate Tolerance & Exponential Backoffs
**Problem:** Expanding configuration abstractions to properties like `API_TIMEOUT_KALSHI` is excellent linearly, but network endpoints still rely directly on rigid logic handling without progressive elasticity during high load conditions. 
**Solution:** Integrate dynamic scaling algorithms configuring an aggressive threshold (e.g., `MAX_RETRY_BACKOFF`) enabling pipelines mapping from `config.py` to seamlessly throttle up and down rather than rigidly triggering `TimeoutErrors` upon static failures.
