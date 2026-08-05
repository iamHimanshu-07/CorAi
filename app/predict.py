"""Inference layer: load the model once, expose a typed Predictor.

Anything that needs to score heart-disease features goes through here.
Kept separate from Flask so it can be reused in batch scripts and tests.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib

log = logging.getLogger(__name__)

NUMERIC_COLS = ["Age", "RestingBP", "Cholesterol", "FastingBS", "MaxHR", "Oldpeak"]
CATEGORICAL_COLS = ["Sex", "ChestPainType", "RestingECG", "ExerciseAngina", "ST_Slope"]
ALL_COLS = NUMERIC_COLS + CATEGORICAL_COLS


@dataclass(frozen=True)
class HeartFeatures:
    Age: float
    RestingBP: float
    Cholesterol: float
    FastingBS: int
    MaxHR: float
    Oldpeak: float
    Sex: str
    ChestPainType: str
    RestingECG: str
    ExerciseAngina: str
    ST_Slope: str

    def to_dataframe_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PredictionResult:
    probability: float
    risk: str
    risk_color: str
    model_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Predictor:
    """Lazy-loaded, thread-safe model wrapper."""

    _instance: Predictor | None = None
    _lock = threading.Lock()

    def __init__(self, model_path: str | Path) -> None:
        self.model_path = Path(model_path)
        self._pipeline = None
        self._version = self.model_path.stem.replace("hdps-", "")

    @classmethod
    def instance(cls, model_path: str | Path | None = None) -> Predictor:
        with cls._lock:
            if cls._instance is None:
                if model_path is None:
                    raise RuntimeError("First call to Predictor.instance requires a model_path")
                cls._instance = cls(model_path)
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    @property
    def version(self) -> str:
        return self._version

    def _load(self) -> None:
        if self._pipeline is None:
            if not self.model_path.exists():
                raise FileNotFoundError(
                    f"Model artifact not found at {self.model_path}. "
                    f"Run `python -m ml.train` first."
                )
            self._pipeline = joblib.load(self.model_path)
            log.info(f"Loaded model from {self.model_path}")

    def predict(self, features: HeartFeatures) -> PredictionResult:
        self._load()
        import pandas as pd
        row = features.to_dataframe_row()
        df = pd.DataFrame([row], columns=ALL_COLS)
        proba = float(self._pipeline.predict_proba(df)[0][1])
        proba_pct = round(proba * 100, 2)
        if proba_pct <= 30:
            risk, color = "Low", "success"
        elif proba_pct <= 60:
            risk, color = "Moderate", "warning"
        else:
            risk, color = "High", "danger"
        return PredictionResult(
            probability=proba_pct,
            risk=risk,
            risk_color=color,
            model_version=self.version,
        )

    def explain(self, features: HeartFeatures) -> dict[str, float] | None:
        """SHAP-based feature contribution for a single prediction.

        Returns dict of feature_name -> shap_value, or None if SHAP is unavailable.
        """
        self._load()
        try:
            import shap
        except Exception:
            return None
        try:
            import pandas as pd
            df = pd.DataFrame([features.to_dataframe_row()], columns=ALL_COLS)
            pre = self._pipeline.named_steps["pre"]
            Xt = pre.transform(df)
            names = pre.get_feature_names_out().tolist()
            inner = self._pipeline.named_steps["calibrated"].calibrated_classifiers_[0].estimator
            explainer = shap.TreeExplainer(inner) if hasattr(inner, "estimators_") else shap.Explainer(inner)
            sv = explainer(Xt)
            values = sv.values[0] if hasattr(sv, "values") else sv[0].values
            return {n: float(v) for n, v in zip(names, values, strict=False)}
        except Exception as exc:  # noqa: BLE001
            log.warning(f"SHAP explain failed: {exc}")
            return None


def features_from_form(form) -> HeartFeatures:
    """Build HeartFeatures from a Flask request.form-like object."""
    return HeartFeatures(
        Age=float(form["age"]),
        RestingBP=float(form["restingbp"]),
        Cholesterol=float(form["cholesterol"]),
        FastingBS=int(form["fastingbs"]),
        MaxHR=float(form["maxhr"]),
        Oldpeak=float(form["oldpeak"]),
        Sex=form["sex"],
        ChestPainType=form["cp"],
        RestingECG=form["restecg"],
        ExerciseAngina=form["exang"],
        ST_Slope=form["slope"],
    )
