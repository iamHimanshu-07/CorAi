"""Slow smoke test for the full training pipeline.

Run explicitly:
    pytest -q -m slow
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


def test_train_pipeline_end_to_end(tmp_path):
    pytest.importorskip("sklearn")
    pytest.importorskip("joblib")
    pytest.importorskip("pandas")

    from ml.train import train_pipeline
    repo = Path(__file__).resolve().parents[1]
    heart_csv = repo / "heart.csv"
    if not heart_csv.exists():
        pytest.skip("heart.csv missing")

    report = train_pipeline("test", heart_csv)
    assert "best_model" in report
    assert report["best_model"]["cv_roc_auc_mean"] > 0.7

    # Artifacts written under repo / models / ml/evaluation
    assert (repo / "models" / "hdps-test.pkl").exists()
    assert (repo / "models" / "hdps-test.scaler.pkl").exists()
    assert (repo / "ml" / "evaluation" / "report.json").exists()
