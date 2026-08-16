"""Shared SHAP explainer dispatcher.

Picks the right explainer based on the inner estimator's class name. Falls back
gracefully through TreeExplainer → LinearExplainer → KernelExplainer so SHAP
works for logistic regression as well as the tree boosters.

IMPORTANT: Heavy ML imports (shap, xgboost, lightgbm) are lazy-loaded inside
functions to avoid memory issues during app startup on restricted environments
like Render's free tier (512 MB RAM cap).
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

# Flags to track availability - actual imports happen lazily
_HAS_SHAP = None
_HAS_XGBOOST = None
_HAS_LIGHTGBM = None

_LINEAR_TYPES = {
    "LogisticRegression",
    "LinearRegression",
    "RidgeClassifier",
    "Ridge",
    "SGDClassifier",
    "LinearSVC",
}

_TREE_TYPES = {
    "XGBClassifier",
    "XGBRegressor",
    "LGBMClassifier",
    "LGBMRegressor",
    "RandomForestClassifier",
    "RandomForestRegressor",
    "ExtraTreesClassifier",
    "ExtraTreesRegressor",
    "GradientBoostingClassifier",
    "GradientBoostingRegressor",
}


def _check_shap():
    """Check if shap is available, importing lazily."""
    global _HAS_SHAP, shap
    if _HAS_SHAP is None:
        try:
            import shap  # noqa: F401
            _HAS_SHAP = True
        except Exception:  # noqa: BLE001
            shap = None  # type: ignore[assignment]
            _HAS_SHAP = False
    return _HAS_SHAP


def _check_xgboost():
    """Check if xgboost is available, importing lazily."""
    global _HAS_XGBOOST
    if _HAS_XGBOOST is None:
        try:
            import xgboost  # noqa: F401
            _HAS_XGBOOST = True
        except Exception:  # noqa: BLE001
            _HAS_XGBOOST = False
    return _HAS_XGBOOST


def _check_lightgbm():
    """Check if lightgbm is available, importing lazily."""
    global _HAS_LIGHTGBM
    if _HAS_LIGHTGBM is None:
        try:
            import lightgbm  # noqa: F401
            _HAS_LIGHTGBM = True
        except Exception:  # noqa: BLE001
            _HAS_LIGHTGBM = False
    return _HAS_LIGHTGBM


def make_explainer(inner: Any, Xt: Any):
    """Return a SHAP explainer appropriate for ``inner`` fitted on ``Xt``.

    Tries TreeExplainer (boosters + sklearn trees), then LinearExplainer for
    linear models, then a predict_proba-based masker explainer.
    """
    if not _check_shap():
        raise RuntimeError("shap is not installed")

    # Import shap now that we know it's available
    global shap
    if shap is None:
        import shap  # noqa: F401

    cls_name = type(inner).__name__
    if _check_xgboost() and cls_name in {"XGBClassifier", "XGBRegressor"}:
        return shap.TreeExplainer(inner)
    if _check_lightgbm() and cls_name in {"LGBMClassifier", "LGBMRegressor"}:
        return shap.TreeExplainer(inner)
    if cls_name in _TREE_TYPES:
        try:
            return shap.TreeExplainer(inner)
        except Exception:  # noqa: BLE001
            pass
    if cls_name in _LINEAR_TYPES:
        try:
            return shap.LinearExplainer(inner, Xt)
        except Exception:  # noqa: BLE001
            pass
    try:
        return shap.Explainer(inner.predict_proba, Xt)
    except Exception:  # noqa: BLE001
        return shap.Explainer(inner, Xt)