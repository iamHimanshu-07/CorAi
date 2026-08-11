# 🫀 CorAi

> Open-source heart-disease risk calculator. Calibrated ensemble. SHAP explanations.
> Per-prediction audit log. FHIR-friendly API.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-Web%20Framework-black?style=for-the-badge&logo=flask)
![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-ML-orange?style=for-the-badge&logo=scikitlearn)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite)
![MIT License](https://img.shields.io/badge/License-MIT-success?style=for-the-badge)

</div>

> ⚠️ **Educational use only.** Not a clinical diagnosis. See [MODEL_CARD.md](MODEL_CARD.md).

---

## What it does

CorAi takes 11 routine clinical measurements, runs them through a calibrated
ensemble classifier trained on the UCI heart-disease dataset, and returns a
probability (0–100%) plus a Low / Moderate / High band. Every prediction is
logged with the input features, the model version, and the user that
triggered it — auditable, not a black box.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐    ┌──────────┐
│ 11 features  │ →  │ preprocessor │ →  │ calibrated LR /  │ →  │ 37–92%   │
│              │    │ (scaler +    │    │ RF / XGB / LGBM  │    │ + risk   │
│              │    │  one-hot)    │    │ (best by CV AUC) │    │ + SHAP   │
└──────────────┘    └──────────────┘    └──────────────────┘    └──────────┘
```

## Quick start

```bash
git clone <repo>
cd CorAi
pip install -r requirements.txt
$env:LOKY_MAX_CPU_COUNT = "4"  # Replace 4 with your desired core count
python -m ml.train --data heart.csv --version 1.0.0   # one-time
$env:PYTHONWARNINGS="ignore"
$env:GEMINI_API_KEY="<your-gemini-api-key>"
flask --app wsgi:app init-db                          # one-time
flask --app wsgi:app run
```

Open <http://127.0.0.1:5000>. Sign in with the bootstrap doctor credentials
(see Configuration below).

### Or Docker

```bash
docker compose up --build
```

## Architecture

```
.
├── app/
│   ├── __init__.py        # app factory
│   ├── config.py          # dev / test / prod configs
│   ├── extensions.py      # db, login, migrate, limiter
│   ├── models.py          # User, Patient, Prediction
│   ├── predict.py         # Predictor service (loads model)
│   ├── cli.py             # flask CLI
│   ├── errors.py          # JSON / HTML error handlers
│   ├── health.py          # /healthz, /readyz
│   ├── seed.py            # default doctor account
│   ├── blueprints/
│   │   ├── auth/          # login, register, logout
│   │   ├── main/          # home, dashboard
│   │   ├── patients/      # CRUD + per-patient history
│   │   ├── predict/       # form + run + PDF report
│   │   ├── api/           # /v1/predict (JSON in/out)
│   │   ├── admin/         # user management, audit log
│   │   └── fhir/          # FHIR R4 Patient import stub
│   ├── templates/         # Jinja templates
│   └── static/            # CSS + JS
├── ml/
│   ├── train.py           # multi-model training + SHAP
│   ├── evaluation/        # report.json + plots (generated)
│   └── README.md          # methodology
├── models/
│   └── corai-1.0.0.pkl     # generated; gitignored
├── tests/                 # pytest, in-memory SQLite
├── wsgi.py                # gunicorn entrypoint
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml         # ruff config
├── requirements.txt       # pinned versions
├── .python-version        # 3.11
├── MODEL_CARD.md          # intended use, limitations
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── CHANGELOG.md
```

## API

```http
POST /v1/predict
Content-Type: application/json

{
  "name": "Jane Doe",
  "Age": 54,
  "RestingBP": 130,
  "Cholesterol": 250,
  "FastingBS": 0,
  "MaxHR": 145,
  "Oldpeak": 1.5,
  "Sex": "F",
  "ChestPainType": "ASY",
  "RestingECG": "Normal",
  "ExerciseAngina": "N",
  "ST_Slope": "Flat"
}
```

```json
{
  "prediction_id": 17,
  "patient_id": 42,
  "probability": 62.4,
  "risk": "Moderate",
  "model_version": "1.0.0",
  "timestamp": "2026-08-05T10:42:11.123456+00:00"
}
```

Validation is strict (Pydantic v2). Bad input → `400 validation_error`.

## Model

| metric          | value |
|-----------------|-------|
| Dataset         | UCI heart disease (918 rows, 11 features) |
| Models trained  | LR, RF, XGBoost, LightGBM |
| Selection rule  | best by mean 5-fold CV ROC-AUC |
| Calibration     | isotonic, 5-fold |
| Class imbalance | SMOTE (training only) + class_weight='balanced' |
| Explainability  | SHAP per-prediction summary |
| Persisted as    | `models/corai-<version>.pkl` (preprocessor + calibrated classifier) |

See [MODEL_CARD.md](MODEL_CARD.md) for intended use, ethical considerations,
and limitations. See [ml/README.md](ml/README.md) for methodology details.
The eval report (with charts) is regenerated every time you run training:
`ml/evaluation/report.json` + `ml/evaluation/*.png`.

## Configuration

| env var                        | default                                | purpose                              |
|--------------------------------|----------------------------------------|--------------------------------------|
| `SECRET_KEY`                   | dev-only fallback                      | session signing                      |
| `DATABASE_URL`                 | `sqlite:///corai.db`                    | SQLAlchemy URI                       |
| `MODEL_PATH`                   | `models/corai-1.0.0.pkl`                | inference artifact                   |
| `MODEL_VERSION`                | `1.0.0`                                | stamped on every audit record        |
| `RATELIMIT_STORAGE_URI`        | `memory://`                            | swap to `redis://...` in prod        |
| `BOOTSTRAP_DOCTOR_USERNAME`    | `doctor`                               | seeded on first request if missing   |
| `BOOTSTRAP_DOCTOR_PASSWORD`    | `corai2026`                             | **change immediately in prod**       |
| `GEMINI_API_KEY`               | empty                                  | reserved for future use              |

## License

MIT — see [LICENSE](LICENSE).

## Credits

Built by Himanshu Singh Yadav. Trained on the UCI Heart Disease dataset.