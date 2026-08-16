# 🫀 CorAi

> Open-source heart-disease risk calculator. Calibrated ensemble. SHAP explanations.
> Per-prediction audit log. FHIR-friendly API.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-Web%20Framework-black?style=for-the-badge&logo=flask)
![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-ML-orange?style=for-the-badge&logo=scikitlearn)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite)
![MIT License](https://img.shields.io/badge/License-MIT-success?style=for-the-badge)
[![Deploy to Render](https://img.shields.io/badge/Deploy-Render-46e3b7?style=for-the-badge&logo=render)](https://render.com/deploy?repo=https://github.com/iamHimanshu-07/CorAi)

</div>


---

## What it does

CorAi takes 11 routine clinical measurements, runs them through a calibrated
ensemble classifier trained on the UCI heart-disease dataset, and returns a
probability (0–100%) plus a Low / Moderate / High band. Every prediction is
logged with the input features, the model version, and the user that
triggered it — auditable, not a black box.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐    ┌──────────┐
│ 11 features  │ →  │ preprocessor │ →  │ calibrated LR /  │    │ 37–92%   │
│              │    │ (scaler +    │    │ RF / XGB / LGBM  │ →  │ + risk   │
│              │    │  one-hot)    │    │ (best by CV AUC) │    │ + SHAP   │
└──────────────┘    └──────────────┘    └──────────────────┘    └──────────┘
```

**Features**

- 11-feature manual prediction form (doctor / patient / admin roles)
- Real PDF analysis report (cover page, drawn risk gauge, SHAP table)
- PDF medical-record upload → auto-parse features → predict
- Doctor map (Leaflet + OpenStreetMap) for cardiologist lookup
- HeartAI Copilot — floating chat widget backed by Gemini + a local FAISS
  RAG index over the CorAi knowledge base (optional, falls back to OpenAI)
- FHIR R4 Patient import stub
- Bootstrap doctor account + audit log

---

## Quick start

### Local (Python)

```bash
git clone https://github.com/iamHimanshu-07/CorAi.git
cd CorAi
python -m venv .venv && source .venv/bin/activate   # or: .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Train the model artifact (one-time)
python -m ml.train --data heart.csv --version 1.0.0

# Initialize the database (one-time)
flask --app app:create_app init-db

# Run
flask --app app:create_app run
```

Open <http://127.0.0.1:5000> and sign in with the bootstrap doctor account:

| field    | value              |
|----------|--------------------|
| username | `doctor`           |
| password | `corai2026`        |

> **Change the bootstrap password in production** via the
> `BOOTSTRAP_DOCTOR_PASSWORD` env var, or by signing in and rotating it.

---

## Deploy to Render (free, recommended)

The repo ships with a Render Blueprint (`render.yaml`) + Dockerfile that
provisions everything in one click.

### 1. Create the service
1. Sign in at <https://dashboard.render.com/> (free account).
2. Click **New +** → **Blueprint**.
3. Pick the GitHub repo `iamHimanshu-07/CorAi`.
4. Render reads `render.yaml` and shows a single `corai` web service on the
   **Free** plan.
5. Click **Apply**. Render builds the Docker image (5–8 min on first build).

### 2. Auto-generated secrets
On the first deploy, Render generates two secrets for you:
- `SECRET_KEY`
- `BOOTSTRAP_DOCTOR_PASSWORD`

You'll see them once under **Environment → Environment Group**, copy and
save them somewhere safe.

### 3. Read the bootstrap password
Until you set `BOOTSTRAP_DOCTOR_PASSWORD` to something memorable, Render
randomly generated one for you (see step 2) — get it from the dashboard.

### 4. Optional: enable HeartAI Copilot
1. Get a Gemini API key from <https://aistudio.google.com/apikey>.
2. In Render: **Environment → Add Environment Variable** →
   - Key: `GOOGLE_API_KEY`
   - Value: your key
3. Click **Save Changes** → Render redeploys.

### 5. URL
Your live URL will be `https://corai.onrender.com`. Sign in with the
bootstrap doctor account set above.

### Known free-tier behaviors
- **Spins down after 15 min idle** — first request after sleep takes ~30 s
  to wake + retrain (~10 s) + warm FAISS.
- **No persistent disk** — boot retrains from `heart.csv` and re-seeds the
  DB; on first boot you'll land on the bootstrap doctor login.
- **750 free instance-hours/month** — well within hobby/demo limits.

### Auto-deploy
A GitHub Actions workflow (`.github/workflows/render-deploy.yml`) pings
Render on every push to `main` once you add the `RENDER_DEPLOY_HOOK` secret
(see [Render docs](https://docs.render.com/configure-deploy-hook)).

---

## Configuration

All knobs are environment variables (no code changes needed). See
[`.env.example`](.env.example) for the full list. Highlights:

| env var | default | purpose |
|---|---|---|
| `SECRET_KEY` | dev-only fallback | session signing — **set in prod** |
| `DATABASE_URL` | `sqlite:///corai.db` | SQLAlchemy URI |
| `MODEL_PATH` | `models/corai-1.0.0.pkl` | inference artifact |
| `BOOTSTRAP_DOCTOR_USERNAME` | `doctor` | seeded on first request if missing |
| `BOOTSTRAP_DOCTOR_PASSWORD` | `corai2026` | **change in production** |
| `GOOGLE_API_KEY` | empty | enable HeartAI Copilot (Gemini + FAISS RAG) |
| `GEMINI_API_KEY` | empty | legacy alias for `GOOGLE_API_KEY` |
| `LLM_API_KEY` | empty | OpenAI fallback for the chatbot |
| `PORT` | `5000` (dev) / `10000` (Render) | gunicorn bind port |

---

## Architecture

```
.
├── app/
│   ├── __init__.py        # app factory — wires blueprints + RAG config
│   ├── config.py          # dev / test / prod configs (env-driven)
│   ├── extensions.py      # db, login, migrate, limiter
│   ├── models.py          # User, Patient, Prediction, PdfReport, Doctor
│   ├── predict.py         # Predictor service (loads model, SHAP)
│   ├── shap_utils.py      # SHAP explainer dispatch (LR vs tree models)
│   ├── cli.py             # flask CLI: init-db, create-user
│   ├── errors.py          # JSON / HTML error handlers
│   ├── health.py          # /healthz, /readyz (DB + model checks)
│   ├── seed.py            # default doctor + sample doctor roster
│   ├── demo_data.py       # opt-in demo patient seeder
│   ├── services/
│   │   └── pdf_report.py  # ReportLab PDF build (gauge + SHAP table)
│   └── blueprints/
│       ├── auth/          # login, register, logout
│       ├── main/          # home, dashboard
│       ├── patients/      # CRUD + per-patient history
│       ├── predict/       # form + run + SHAP view
│       ├── api/           # /v1/predict (JSON in/out, Pydantic)
│       ├── admin/         # user management, audit log
│       ├── fhir/          # FHIR R4 Patient import stub
│       ├── metrics/       # evaluation dashboard
│       ├── chatbot/       # /chat endpoint (RAG → OpenAI fallback)
│       ├── report/        # PDF upload + parse + download
│       ├── map/           # doctor map (Leaflet)
│       └── about/         # WHO / CVD info (scraped, cached)
├── ml/
│   ├── train.py           # multi-model training + SHAP
│   ├── evaluation/        # report.json + plots (generated)
│   └── README.md          # methodology
├── models/
│   └── corai-1.0.0.pkl    # generated at boot; gitignored
├── tests/                 # pytest, in-memory SQLite
├── rag_engine.py          # Gemini + FAISS RAG for HeartAI Copilot
├── Dockerfile             # production image (Render / any Docker host)
├── render.yaml            # Render Blueprint (free plan)
├── pyproject.toml         # ruff config
├── requirements.txt       # pinned versions
├── MODEL_CARD.md          # intended use, limitations
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── CHANGELOG.md
└── LICENSE
```

---

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

---

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

---

## Security

- Set a real `SECRET_KEY` in any non-dev deployment.
- Set `SESSION_COOKIE_SECURE=1` so cookies are HTTPS-only.
- Rotate the bootstrap doctor password on first login.

See [SECURITY.md](SECURITY.md) for the full policy.

---

## License

MIT — see [LICENSE](LICENSE).

## Credits

Built by [Himanshu Singh Yadav](https://github.com/iamHimanshu-07).
Trained on the [UCI Heart Disease dataset](https://archive.ics.uci.edu/ml/datasets/heart+disease).
