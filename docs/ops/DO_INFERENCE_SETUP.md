# DigitalOcean Serverless Inference Setup

**Purpose:** configure the LLM client (`src/llm_inference.py`) used by
`arb_classifier` (Phase 0 arb decision-gate helper) and `v4_diagnosis`
(one-shot V4 decay analysis). Single shared client, structured-output only,
no directional bias.

## What it is

- OpenAI-compatible endpoint hosted on DigitalOcean's GenAI platform
- Pay-per-token; llama3.3-70b-instruct by default
- Same AMS3 region as the droplet → near-zero latency, no egress cost

## Provisioning

1. DO Console → GenAI Platform → **Serverless Inference** → Create API key
2. Copy the key (shown once)
3. Add to the systemd unit environment (VPS):

```bash
sudo systemctl edit botsy  # or edit /etc/systemd/system/botsy.service.d/override.conf
```

Add:

```
[Service]
Environment="DO_INFERENCE_API_KEY=sk-..."
# Optional overrides:
# Environment="DO_INFERENCE_ENDPOINT=https://inference.do-ai.run"
# Environment="DO_INFERENCE_MODEL=llama3.3-70b-instruct"
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart botsy
```

Neither analysis module runs on the hot path, so a restart is only needed
when you actually want to run one of them. The runtime engine does not
call the LLM layer today.

## Local development

Export the key in your shell before running either tool:

```bash
export DO_INFERENCE_API_KEY=sk-...
python3 -m v4_diagnosis 2026-03-15 2026-04-23 --agent btc
python3 -m arb_classifier --n 50 --min-edge 0.02
```

If the key is missing, both tools raise `LLMError` on first call — nothing
else in the codebase depends on the key being set.

## Cost discipline

- All calls use `response_format: json_object` and `temperature: 0.1`
- `max_tokens` capped at 1024 (v4_diagnosis) / 512 (arb_classifier per row)
- `v4_diagnosis`: 1 call per run, effectively one-shot (~$0.01)
- `arb_classifier`: 50 calls per decision-gate run (~$0.30)
- Combined projected spend: **<$10/month** assuming 2–3 Phase 0 gate
  evaluations and a handful of V4 reruns

## Calibration audit

Every LLM call is logged to `llm_calibration_log` in `predictions.db`:

```sql
SELECT task_name, COUNT(*), MIN(logged_at), MAX(logged_at)
FROM llm_calibration_log
GROUP BY task_name;
```

Ground-truth outcomes (market resolution for arb_classifier,
retrospective quant read for v4_diagnosis) are back-filled later and
compared against LLM output to measure calibration. See
`docs/optimizations.json` entries `arb_llm_classifier` and
`v4_decay_llm_diagnosis` for pre-registered revert criteria.

## No-bias invariant

The schemas for both tools explicitly exclude buy/sell/direction/
conviction outputs. The LLM names causes, classifies regimes, and
proposes onset dates. All directional decisions remain in the quant/
human config layer (`CLAUDE.md` — "No agent bias" rule).

## Troubleshooting

- `LLMError: DO_INFERENCE_API_KEY not set` — export the env var
- `LLMError: LLM HTTP call failed: ...` — check DO status page, network
- `LLMError: LLM returned non-JSON content` — one retry is automatic;
  persistent failure usually means the model has been swapped or the
  prompt triggered a refusal. Inspect `llm_calibration_log` and iterate
  the system prompt.
