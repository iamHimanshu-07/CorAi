# Model Card — CorAi

Following the [Google Model Card template](https://modelcards.withgoogle.com/about).

## Model details

- **Person or organization**: Himanshu Singh Yadav
- **Model date**: 2026-08-05
- **Model version**: 1.0.0
- **Model type**: Binary classifier (presence of heart disease)
- **Training algorithm**: Scikit-Learn `LogisticRegression`, `RandomForest`, `XGBoost`, `LightGBM` (final: best by CV ROC-AUC)
- **Calibration**: `CalibratedClassifierCV(method="isotonic", cv=5)`
- **Class imbalance**: `SMOTE` (training folds only) + `class_weight="balanced"` where supported
- **Cross-validation**: 5-fold StratifiedKFold
- **Persisted artifact**: `models/corai-1.0.0.pkl` (joblib)

## Intended use

- **Primary**: educational demonstration of an end-to-end ML-in-Flask pipeline,
  including calibration, audit logging, SHAP explainability, and a public
  read-only API.
- **Secondary**: research baseline for heart-disease risk prediction on the
  UCI Cleveland dataset.
- **Out of scope**:
  - Clinical decision-making. This system does **not** meet regulatory
    requirements for a medical device.
  - Use on populations outside the training distribution (different
    demographics, comorbidities, measurement protocols).
  - Deployment on real patient data without institutional review.

## Training data

- **Source**: UCI Machine Learning Repository — Heart Disease (Cleveland variant, distributed via Kaggle).
- **Size**: 918 rows, 11 input features, 1 target.
- **Class balance**: ~55% positive (heart disease present).
- **Features**: age, resting BP, cholesterol, fasting blood sugar, max heart
  rate, ST depression (oldpeak), sex, chest pain type, resting ECG, exercise
  angina, ST slope.
- **Splits**: 80/20 stratified train/hold-out, `random_state=42`.

## Evaluation

Run `python -m ml.train --data heart.csv --version 1.0.0`. The pipeline
writes `ml/evaluation/report.json` with per-model metrics and
`ml/evaluation/*.png` for confusion matrix, ROC, PR, calibration, and SHAP
summary.

Metrics reported:

- accuracy, precision, recall, F1
- ROC-AUC (single-split and 5-fold CV)
- Brier score (probability calibration)

Selection criterion: best **mean 5-fold CV ROC-AUC** (not single-split).

> ⚠️ The dataset is small (918 rows). Confidence intervals are wide. AUC
> values are directional, not authoritative.

## Ethical considerations

- The model was trained on a single-source dataset of unclear demographic
  representativeness. Subgroup performance (by sex, age band, ethnicity) has
  not been audited. We do **not** recommend deployment to populations that
  differ materially from the training distribution.
- False negatives (missed cases of heart disease) are clinically more
  expensive than false positives. The default 30/60 risk-band thresholds are
  for human readability, not for clinical sensitivity. **No threshold
  optimization against clinical cost has been performed.**
- No protected attributes are used in training. `Sex` is a clinical feature
  (biological, not identity) and is included because it's medically relevant.
- The model has no concept of time or disease progression beyond what the
  features encode. It is a snapshot classifier.

## Limitations

- 918 training rows is small. Performance estimates have wide confidence
  intervals.
- Single dataset. External validity is unknown.
- No deployment-time drift monitoring.
- No prospective evaluation.
- No subgroup fairness audit.

## Recommendations

- Treat outputs as a triage hint, not a diagnosis.
- Pair predictions with a clinician's review.
- If you re-train on your own data, regenerate this card.
- For regulated use, run a full clinical validation study and a subgroup
  fairness audit before deployment.

## Contact

Open an issue on GitHub for questions about training data, methodology, or
this card.