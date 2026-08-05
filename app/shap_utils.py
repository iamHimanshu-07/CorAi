"""Shared SHAP explainer dispatcher.

Picks the right explainer based on the inner estimator's class name. Falls back
gracefully through TreeExplainer → LinearExplainer → KernelExplainer so SHAP
works for logistic regression as well as the tree boosters.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

try:
    import shap  # noqa: F401
    HAS_SHAP = True
except Exception:  # noqa: BLE001
    shap = None  # type: ignore[assignment]
    HAS_SHAP = False

try:
    import xgboost  # noqa: F401
    HAS_XGBOOST = True
except Exception:  # noqa: BLE001
    HAS_XGBOOST = False

try:
    import lightgbm  # noqa: F401
    HAS_LIGHTGBM = True
except Exception:  # noqa: BLE001
    HAS_LIGHTGBM = False


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


def make_explainer(inner: Any, Xt: Any):
    """Return a SHAP explainer appropriate for ``inner`` fitted on ``Xt``.

    Tries TreeExplainer (boosters + sklearn trees), then LinearExplainer for
    linear models, then a predict_proba-based masker explainer.
    """
    if not HAS_SHAP:
        raise RuntimeError("shap is not installed")
    cls_name = type(inner).__name__
    if HAS_XGBOOST and cls_name in {"XGBClassifier", "XGBRegressor"}:
        return shap.TreeExplainer(inner)
    if HAS_LIGHTGBM and cls_name in {"LGBMClassifier", "LGBMRegressor"}:
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
