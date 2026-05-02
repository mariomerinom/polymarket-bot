import json
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_prediction_db(path: Path, predicted_at: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE predictions (predicted_at TEXT)")
    conn.execute(
        "INSERT INTO predictions (predicted_at) VALUES (?)",
        (predicted_at.isoformat(),),
    )
    conn.commit()
    conn.close()


def test_engine_health_checks_all_unpaused_pipeline_dbs(tmp_path):
    """A fresh BTC DB must not mask a stale unpaused pipeline DB."""
    root = tmp_path / "repo"
    data = root / "data"
    config = root / "config"
    fake_bin = tmp_path / "bin"
    data.mkdir(parents=True)
    config.mkdir()
    fake_bin.mkdir()

    (config / "pipelines.json").write_text(json.dumps({
        "pipelines": {
            "btc_5m": {"mode": "paper"},
            "eth_5m": {"mode": "paper"},
            "btc_15m": {"mode": "paused"},
        }
    }))

    now = datetime.now(timezone.utc).replace(microsecond=0)
    _write_prediction_db(data / "predictions.db", now - timedelta(minutes=2))
    _write_prediction_db(data / "predictions_eth.db", now - timedelta(minutes=120))
    _write_prediction_db(data / "predictions_15m.db", now - timedelta(days=30))

    systemctl = fake_bin / "systemctl"
    systemctl.write_text("#!/bin/sh\nexit 0\n")
    systemctl.chmod(0o755)

    env = {
        **os.environ,
        "BOTSY_ROOT": str(root),
        "BOTSY_HEALTH_NOW": now.isoformat(),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "tools" / "check_engine_health.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 2
    summary = (data / "engine_health.txt").read_text()
    assert "CRIT" in summary
    assert "preds=max=120m-CRIT" in summary
    assert "stale=eth_5m:120m" in summary
    assert "btc_15m" not in summary
