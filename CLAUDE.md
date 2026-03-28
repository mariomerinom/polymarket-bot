# Project Rules

## GitHub Is the Source of Truth

1. **Always `git pull` before reading any data file** (especially `data/predictions.db`). The CI pipeline auto-commits every ~5 minutes — local state goes stale fast.
2. **Never analyze local DB without pulling first.** If you report numbers, they must match what the live dashboard shows.
3. **Always push after making changes.** A change that isn't on GitHub doesn't exist.
4. **Expect CI conflicts on push.** The self-rescheduling pipeline commits constantly. Always `git pull --rebase` before pushing. If the DB conflicts, our code changes win (CI will regenerate the DB).
5. **The dashboard (GitHub Pages) is the canonical view.** If the dashboard shows different numbers than a local query, the dashboard is right and your local data is stale.

## Development Process

- Run `pytest tests/ -v` before every commit. Tests gate CI — a broken push stops the pipeline.
- Never skip pre-commit hooks.
- Document production incidents in `docs/BREAK_FIX_LOG.md`.
- Add a regression test for every fix.

## Bot Design

- **No agent bias.** The bot must not have built-in directional bias (UP or DOWN). All bias comes from human macro config, not prompts or code.
- **The strategy is MOMENTUM (ride streaks), not contrarian (fade).** V3 contrarian lost at 37% WR on live Polymarket. Inverting to momentum validated at 63% WR. Do NOT revert the signal direction. Streak UP + exhaustion → predict UP. Streak DOWN + exhaustion → predict DOWN.
- **Paper trade first.** Every new signal must accumulate 200+ resolved predictions in paper trading before risking real capital.
- **Conviction gates real money.** Only conviction >= 3 places bets. Conviction 0-2 = skip.

## Project Health Check

When asked "how are we doing?", "check the project", "what's the status", or similar:

1. `git pull` — always first
2. Read the latest file in `docs/daily/` — yesterday's WR, P&L, alerts
3. `python3 src/optimization_tracker.py summary` — are active optimizations improving or regressing?
4. Read `docs/decisions.md` — has anything moved to READY?
5. Read `docs/ROADMAP.md` — what's the current phase, what's next?
6. `python3 -m pytest tests/ -v` — are tests passing?

Report findings concisely. Flag anything that needs a decision.
