# Deploying CorAi to Render

> ⚠️ **Heads up:** CorAi's ML/RAG stack (scikit-learn, lightgbm, shap, langchain,
> faiss-cpu, sentence-transformers) does **not fit on Render's free plan** —
> 512 MB RAM is too small to build or run it, and free instances can't attach
> a persistent disk (so the trained model and SQLite DB are wiped on every
> redeploy). For a **free** deployment, see
> [`DEPLOY_HF_SPACES.md`](DEPLOY_HF_SPACES.md) (Hugging Face Spaces Docker).
>
> The guide below covers the **paid** Render Starter plan ($7.50/mo), which is
> a clean always-on deploy with a 2 GB persistent disk.

This is the full, copy-paste deployment guide for getting CorAi live on
[Render](https://render.com). The whole process takes about **10 minutes**
if you already have a Render account.

---

## 1. Prerequisites

- A GitHub account that owns [`iamHimanshu-07/CorAi`](https://github.com/iamHimanshu-07/CorAi).
- A free Render account (<https://render.com/signup>).
- (Optional) A **Google AI Studio** key if you want the HeartAI Copilot
  chatbot to work. **The app boots and serves predictions without it.**

---

## 2. One-time repo setup

The repo is already Render-ready, but you need to:

1. Push the latest commit to `main` on `iamHimanshu-07/CorAi`.
2. In Render → **New** → **Blueprint**, point at this repo.
3. Render reads `render.yaml` and provisions the `corai` web service + a
   2 GB persistent disk mounted at `/data`.

That's it. Render will:

- Build the Docker image (`Dockerfile`).
- Train the model artifact on first boot (it lives on the disk, so
  subsequent deploys skip retraining).
- Initialize the SQLite database.
- Seed the default doctor account (`doctor` / auto-generated password —
  see below).
- Start gunicorn on `$PORT`.

---

## 3. Get the bootstrap admin password

Render **autogenerates** `BOOTSTRAP_DOCTOR_PASSWORD` (see `render.yaml`).
To find it:

1. Render dashboard → **corai** → **Environment** → look for
   `BOOTSTRAP_DOCTOR_PASSWORD`. (Click the eye icon to reveal.)
2. **Change it immediately** by signing in as `doctor` and rotating the
   password from the admin profile page — OR override the env var with
   your own value.

> Demo credentials (printed by the app on the login page in dev mode):
> `doctor` / `corai2026`. **Replace before sharing the URL.**

---

## 4. (Optional) Enable the HeartAI Copilot chatbot

If you want the floating chatbot widget to actually answer questions:

1. Get a Google Gemini API key from <https://aistudio.google.com/app/apikey>.
2. Render dashboard → **corai** → **Environment** → add:
   - `GOOGLE_API_KEY` = your key
3. Save → Render triggers a redeploy. The RAG index is built lazily on
   the first chat message and cached on the persistent disk.

If you don't set this, the rest of the app works normally and the
chatbot will show a friendly "needs an API key" message.

---

## 5. Verify the deployment

After the first deploy finishes (build takes ~3–5 min, mostly for
`pip install scikit-learn shap langchain`):

```bash
# Health check
curl https://corai.onrender.com/healthz
# → {"status":"ok"}

# Readiness check (DB + model)
curl https://corai.onrender.com/readyz
# → {"status":"ok","checks":{"db":"ok","model":"ok"}}
```

Open `https://corai.onrender.com`, sign in with the bootstrap
credentials, and run a prediction.

---

## 6. Custom domain (optional)

Render dashboard → **corai** → **Settings** → **Custom Domain** →
add a CNAME pointing to `corai.onrender.com`. Free TLS is automatic.

---

## 7. Costs

| Item | Cost |
|---|---|
| Starter web service (512 MB RAM, always-on) | **$7/mo** |
| 2 GB persistent disk | **$0.50/mo** |
| Outbound bandwidth (100 GB/mo included) | free |
| **Total** | **$7.50/mo** |

To shut down: Render dashboard → **corai** → **Suspend Service**. The
disk is preserved; restarting skips retraining.

---

## 8. Local development alongside Render

The same `Dockerfile` works locally:

```bash
docker compose up --build
# → http://localhost:5000
```

Without Docker:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app wsgi:app init-db
flask --app wsgi:app run
```

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/readyz` → `model: missing` | First boot, training still in progress | Wait 2–3 min, refresh |
| `/readyz` → `model: missing` after deploy | Persistent disk not mounted | Render dashboard → Disks → verify `corai-data` is attached at `/data` |
| 500 on login | `SECRET_KEY` rotated, sessions invalidated | Restart service |
| High memory / OOM killed on first request | `gunicorn -w 2` on the 512 MB Starter plan | The render.yaml uses `-w 1`; bump your Starter plan to a 1 GB+ instance if you need `-w 2` |
| Chatbot shows "needs an API key" | `GOOGLE_API_KEY` not set | Set it in Render env vars (section 4) |
| `apt-get install` fails during build | Rare transient registry error | Retry the deploy |

For anything else, check **Render → corai → Logs** — the gunicorn
output shows the full traceback.
