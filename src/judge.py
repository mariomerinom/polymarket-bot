"""
judge.py — ML Judge meta-classifier for the momentum signal.

The Judge is a veto: it predicts P(momentum_signal_is_correct) from contextual
features the rules ignore (TA indicators, daily regime, funding, OI, temporal).
The signal proposes. The Judge vetoes.

Usage:
    from judge import get_judge
    judge = get_judge()  # cached singleton
    result = judge.evaluate(features)
    # result = {"p_success": 0.63, "should_bet": True}

Fail-open: if the model file is missing or inference errors, returns None.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, Optional

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_MODEL = _ROOT / "models" / "judge_btc_5m.joblib"

_singleton: Optional["Judge"] = None


class Judge:
    """Thin inference wrapper around the trained XGBoost Judge model."""

    def __init__(self, model_path: str | Path | None = None):
        import joblib

        path = Path(model_path) if model_path else _DEFAULT_MODEL
        if not path.exists():
            raise FileNotFoundError(f"Judge model not found: {path}")

        t0 = time.time()
        artifact = joblib.load(path)
        self._load_ms = round((time.time() - t0) * 1000, 1)

        self.model = artifact["model"]
        self.feature_cols: list[str] = artifact["feature_cols"]
        self.threshold: float = artifact.get("threshold", 0.55)
        self.trained_at: str = artifact.get("trained_at", "unknown")
        self.ship_decision: str = artifact.get("ship_decision", "unknown")

    def evaluate(self, features: Dict[str, float]) -> Dict:
        """Score a prediction candidate.

        Args:
            features: dict with keys matching self.feature_cols.
                      Missing keys default to NaN (XGBoost handles natively).

        Returns:
            {"p_success": float, "should_bet": bool, "threshold": float}
        """
        arr = np.array(
            [[features.get(c, float("nan")) for c in self.feature_cols]],
            dtype=np.float32,
        )
        prob = float(self.model.predict_proba(arr)[0][1])
        return {
            "p_success": round(prob, 4),
            "should_bet": prob >= self.threshold,
            "threshold": self.threshold,
        }

    def __repr__(self) -> str:
        return (
            f"Judge(features={len(self.feature_cols)}, "
            f"threshold={self.threshold}, "
            f"trained={self.trained_at}, "
            f"load_ms={self._load_ms})"
        )


def get_judge(model_path: str | Path | None = None) -> Optional[Judge]:
    """Get cached Judge singleton. Returns None on any error (fail-open)."""
    global _singleton
    if _singleton is not None:
        return _singleton
    try:
        _singleton = Judge(model_path)
        return _singleton
    except Exception as e:
        # Fail-open: model missing or broken → return None
        return None
