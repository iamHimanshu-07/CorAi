# ML Pipeline

This directory owns the modeling side of the CorAi
(CorAi). Everything that produces the artifact served by the Flask app lives
here.

## What it does

`ml/train.py` runs a fully reproducible pipeline:

1. Loads `heart.csv` (UCI-style heart-disease dataset, 918 records, 11 features).
2. Builds a `ColumnTransformer` that scales numerics and one-hot-encodes
   categoricals. The exact column list and category names match the inference
   schema in `app/predict.py` — drift between training and serving is the most
   common ML production failure, and is mitigated by sharing `NUMERIC_COLS` / `CATEGORICAL_COLS`.
3. Trains and calibrates four candidate classifiers (Logistic Regression,
   Random Forest, XGBoost, LightGBM — XGB/LGBM degrade gracefully if
   uninstalled). Each is wrapped in:
   - **SMOTE** (only on training folds) to address class imbalance,
   - **CalibratedClassifierCV** (isotonic, 5-fold) so predicted probabilities
     mean something.
4. Evaluates on a stratified 20% hold-out and reports accuracy, precision,
   recall, F1, ROC-AUC, Brier score, and 5-fold CV ROC-AUC.
5. Picks the best model by **mean CV ROC-AUC**, not single-split performance.
6. Generates per-model diagnostic plots (confusion matrix, ROC, PR,
   calibration) and a SHAP summary plot for the winning model.
7. Persists a versioned inference pipeline at `models/corai-<version>.pkl`
   (preprocessor + calibrated classifier, no SMOTE) plus a matching scaler.

## Running

```bash
python -m ml.train --data heart.csv --version 1.0.0
```

Outputs:
- `models/corai-1.0.0.pkl`
- `models/corai-1.0.0.scaler.pkl`
- `ml/evaluation/report.json`
- `ml/evaluation/<model>_*.png`
- `ml/evaluation/shap_summary.png`

## Methodology notes

- **Why calibration:** a raw tree-based model's `predict_proba` is rarely
  calibrated. We use isotonic regression with 5-fold CV — slow at train time
  but the cost is paid once.
- **Why SMOTE in a pipeline, not in the data:** leakage. SMOTE applied before
  train/test split leaks synthetic minority samples into the test set.
- **Why we score on CV ROC-AUC:** single-split AUC is noisy with 184 test
  rows; CV averages across folds and is the metric the README commits to.
- **Class imbalance:** the dataset is roughly balanced (~55% positive), so
  SMOTE is belt-and-braces. We also pass `class_weight='balanced'` to LR and
  RF where the estimator supports it.
- **Explainability:** SHAP is run on the winning model. We slice to the first
  200 test rows for tractability — the summary plot shows global feature
  importance and effect direction.

## Limitations

- 918 rows is small. Confidence intervals on every metric are wide. Treat
  AUC values as directional, not authoritative.
- The dataset is from one source (Cleveland variant via Kaggle). External
  validity across populations is unknown. See `MODEL_CARD.md`.
- We did not collect prospective data; performance is in-sample / hold-out
  only. No deployment-time drift monitoring is configured.
- All models in this pipeline are static. There is no online learning, no
  feedback loop from clinicians, and no fairness audit across demographic
  subgroups.

## What is intentionally NOT here

- Hyperparameter search (Optuna / GridSearch). The defaults are deliberately
  conservative. A second pass with proper tuning is on the roadmap.
- Threshold selection by business cost. We default to `predict_proba >= 0.5`.
  Clinical risk bands in the UI (Low / Moderate / High) use 30/60 thresholds
  for human-readability, not for clinical decision-making.

## References

- UCI Heart Disease dataset: https://archive.ics.uci.edu/ml/datasets/heart+disease
- imbalanced-learn: https://imbalanced-learn.org/
- SHAP: https://shap.readthedocs.io/
