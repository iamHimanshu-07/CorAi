"""
Heart Disease Prediction System - Model Training Pipeline
==========================================================

Trains, calibrates, and evaluates multiple classifiers on the UCI heart-disease
dataset (heart.csv). Picks the best model by mean 5-fold CV ROC-AUC and writes
a versioned artifact (models/hdps-<version>.pkl) along with a fitted scaler
and a JSON evaluation report.

Run:
    python -m ml.train --data heart.csv --version 1.0.0

Outputs:
    models/hdps-<version>.pkl
    models/hdps-<version>.scaler.pkl
    ml/evaluation/report.json
    ml/evaluation/<model>_confusion_matrix.png
    ml/evaluation/<model>_roc.png
    ml/evaluation/<model>_pr.png
    ml/evaluation/<model>_calibration.png
    ml/evaluation/shap_summary.png
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    PrecisionRecallDisplay,
    RocCurveDisplay,
    accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Optional heavy deps — degrade gracefully if absent
try:
    import lightgbm as lgb  # noqa: F401
    HAS_LIGHTGBM = True
except Exception:
    HAS_LIGHTGBM = False

try:
    import xgboost as xgb  # noqa: F401
    HAS_XGBOOST = True
except Exception:
    HAS_XGBOOST = False

try:
    import shap  # noqa: F401
    HAS_SHAP = True
except Exception:
    HAS_SHAP = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("hdps.train")

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_ROOT / "models"
EVAL_DIR = REPO_ROOT / "ml" / "evaluation"
DATA_FILE_DEFAULT = REPO_ROOT / "heart.csv"

NUMERIC_COLS = ["Age", "RestingBP", "Cholesterol", "FastingBS", "MaxHR", "Oldpeak"]
CATEGORICAL_COLS = ["Sex", "ChestPainType", "RestingECG", "ExerciseAngina", "ST_Slope"]
TARGET = "HeartDisease"


# -----------------------------------------------------------------------------#
# Data
# -----------------------------------------------------------------------------#
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = set(NUMERIC_COLS + CATEGORICAL_COLS + [TARGET])
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")
    return df


# -----------------------------------------------------------------------------#
# Preprocessing
# -----------------------------------------------------------------------------#
def make_preprocessor() -> ColumnTransformer:
    """StandardScaler for numerics, OneHotEncoder for categoricals."""
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_COLS),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_COLS),
        ]
    )


# -----------------------------------------------------------------------------#
# Models
# -----------------------------------------------------------------------------#
def candidate_models() -> dict[str, Any]:
    models: dict[str, Any] = {
        "logreg": LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0),
        "rf": RandomForestClassifier(
            n_estimators=400, max_depth=12, min_samples_leaf=2,
            class_weight="balanced", random_state=42, n_jobs=-1,
        ),
    }
    if HAS_XGBOOST:
        models["xgb"] = xgb.XGBClassifier(
            n_estimators=400, max_depth=4, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9,
            scale_pos_weight=1, eval_metric="logloss",
            random_state=42, n_jobs=-1,
        )
    if HAS_LIGHTGBM:
        models["lgbm"] = lgb.LGBMClassifier(
            n_estimators=400, max_depth=-1, num_leaves=31,
            learning_rate=0.05, class_weight="balanced",
            random_state=42, n_jobs=-1, verbose=-1,
        )
    return models


# -----------------------------------------------------------------------------#
# Evaluation
# -----------------------------------------------------------------------------#
@dataclass
class EvalResult:
    name: str
    metrics: dict[str, float]
    cv_roc_auc_mean: float
    cv_roc_auc_std: float
    brier: float


def evaluate(
    name: str,
    pipeline: ImbPipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    cv: StratifiedKFold,
) -> EvalResult:
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "brier": float(brier_score_loss(y_test, y_proba)),
    }

    cv_scores = cross_val_score(pipeline, X_test, y_test, cv=cv, scoring="roc_auc", n_jobs=-1)
    log.info(
        f"[{name}] test ROC-AUC={metrics['roc_auc']:.4f}  "
        f"cv ROC-AUC={cv_scores.mean():.4f}±{cv_scores.std():.4f}"
    )
    return EvalResult(
        name=name,
        metrics=metrics,
        cv_roc_auc_mean=float(cv_scores.mean()),
        cv_roc_auc_std=float(cv_scores.std()),
        brier=metrics["brier"],
    )


# -----------------------------------------------------------------------------#
# Plotting
# -----------------------------------------------------------------------------#
def _save_fig(fig, out: Path) -> None:
    fig.tight_layout()
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)


def plot_diagnostics(name: str, pipeline: ImbPipeline, X_test, y_test, y_proba: np.ndarray, out_dir: Path) -> None:
    ConfusionMatrixDisplay.from_estimator(pipeline, X_test, y_test)
    _save_fig(plt.gcf(), out_dir / f"{name}_confusion_matrix.png")

    RocCurveDisplay.from_estimator(pipeline, X_test, y_test)
    _save_fig(plt.gcf(), out_dir / f"{name}_roc.png")

    PrecisionRecallDisplay.from_estimator(pipeline, X_test, y_test)
    _save_fig(plt.gcf(), out_dir / f"{name}_pr.png")

    # Calibration plot
    fig, ax = plt.subplots()
    from sklearn.calibration import calibration_curve
    frac_pos, mean_pred = calibration_curve(y_test, y_proba, n_bins=10, strategy="quantile")
    ax.plot(mean_pred, frac_pos, "s-", label=name)
    ax.plot([0, 1], [0, 1], "k:", label="Perfect")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title(f"Calibration — {name}")
    ax.legend()
    _save_fig(fig, out_dir / f"{name}_calibration.png")


def shap_summary(pipeline: ImbPipeline, X_test: pd.DataFrame, out_dir: Path) -> list[str] | None:
    if not HAS_SHAP:
        log.warning("shap not installed; skipping SHAP summary")
        return None
    try:
        preprocessor = pipeline.named_steps["pre"]
        clf = pipeline.named_steps["calibrated"]
        # CalibratedClassifierCV wraps the estimator; pull the inner one.
        inner = clf.calibrated_classifiers_[0].estimator
        # Transform features
        Xt = preprocessor.transform(X_test)
        feature_names = preprocessor.get_feature_names_out().tolist()
        explainer = shap.TreeExplainer(inner) if HAS_XGBOOST or HAS_LIGHTGBM else shap.Explainer(inner, Xt)
        sv = explainer(Xt[:200])
        shap.summary_plot(sv, features=Xt[:200], feature_names=feature_names, show=False)
        _save_fig(plt.gcf(), out_dir / "shap_summary.png")
        return feature_names
    except Exception as exc:  # noqa: BLE001
        log.warning(f"SHAP summary failed: {exc}")
        return None


# -----------------------------------------------------------------------------#
# Main
# -----------------------------------------------------------------------------#
def train_pipeline(version: str, data_path: Path) -> dict[str, Any]:
    log.info(f"Loading data from {data_path}")
    df = load_data(data_path)
    X, y = df.drop(columns=[TARGET]), df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    preprocessor = make_preprocessor()
    models = candidate_models()
    results: list[EvalResult] = []
    fitted: dict[str, ImbPipeline] = {}

    for name, estimator in models.items():
        log.info(f"Training {name}")
        # Pipeline: preprocessor -> SMOTE -> calibrated classifier.
        # SMOTE only inside the training folds — applied via the pipeline so it
        # never sees the test set (leakage prevention).
        pipe = ImbPipeline(steps=[
            ("pre", preprocessor),
            ("smote", SMOTE(random_state=42)),
            ("calibrated", CalibratedClassifierCV(estimator, method="isotonic", cv=cv)),
        ])
        pipe.fit(X_train, y_train)

        y_proba = pipe.predict_proba(X_test)[:, 1]
        res = evaluate(name, pipe, X_test, y_test, cv)
        results.append(res)
        fitted[name] = pipe

        try:
            plot_diagnostics(name, pipe, X_test, y_test, y_proba, EVAL_DIR)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"plot_diagnostics failed for {name}: {exc}")

    # Best model by CV ROC-AUC (not single-split)
    best = max(results, key=lambda r: r.cv_roc_auc_mean)
    log.info(f"Best model: {best.name} (cv ROC-AUC={best.cv_roc_auc_mean:.4f})")

    feature_names = shap_summary(fitted[best.name], X_test, EVAL_DIR)

    # Persist artifacts
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    best_pipe = fitted[best.name]
    # Strip SMOTE for inference — use the calibrated classifier + preprocessor only
    inference_pipe = ImbPipeline(steps=[
        ("pre", best_pipe.named_steps["pre"]),
        ("calibrated", best_pipe.named_steps["calibrated"]),
    ])
    model_path = MODELS_DIR / f"hdps-{version}.pkl"
    joblib.dump(inference_pipe, model_path)
    log.info(f"Wrote {model_path}")

    # Standalone scaler for back-compat / debugging
    from sklearn.pipeline import Pipeline
    scaler_pipe = Pipeline([("pre", best_pipe.named_steps["pre"])])
    scaler_path = MODELS_DIR / f"hdps-{version}.scaler.pkl"
    joblib.dump(scaler_pipe, scaler_path)
    log.info(f"Wrote {scaler_path}")

    # Evaluation report
    report = {
        "version": version,
        "dataset": {
            "path": str(data_path),
            "rows": int(len(df)),
            "positive_rate": float(df[TARGET].mean()),
            "features": NUMERIC_COLS + CATEGORICAL_COLS,
            "target": TARGET,
        },
        "split": {
            "test_size": 0.2,
            "stratified": True,
            "random_state": 42,
            "train_rows": int(len(X_train)),
            "test_rows": int(len(X_test)),
        },
        "models": [
            {
                "name": r.name,
                "metrics": r.metrics,
                "cv_roc_auc_mean": r.cv_roc_auc_mean,
                "cv_roc_auc_std": r.cv_roc_auc_std,
            }
            for r in sorted(results, key=lambda x: x.cv_roc_auc_mean, reverse=True)
        ],
        "best_model": {
            "name": best.name,
            "selection_metric": "cv_roc_auc_mean",
            "cv_roc_auc_mean": best.cv_roc_auc_mean,
            "cv_roc_auc_std": best.cv_roc_auc_std,
        },
        "feature_names_after_preprocessing": feature_names,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "tools": {
            "sklearn": __import__("sklearn").__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "imbalanced_learn": __import__("imblearn").__version__,
            "xgboost": __import__("xgboost").__version__ if HAS_XGBOOST else None,
            "lightgbm": __import__("lightgbm").__version__ if HAS_LIGHTGBM else None,
        },
    }
    report_path = EVAL_DIR / "report.json"
    report_path.write_text(json.dumps(report, indent=2))
    log.info(f"Wrote {report_path}")

    return report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train & evaluate HDPS model")
    p.add_argument("--data", type=Path, default=DATA_FILE_DEFAULT)
    p.add_argument("--version", type=str, default="1.0.0")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        train_pipeline(args.version, args.data)
    except Exception as exc:  # noqa: BLE001
        log.exception(f"Training failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
