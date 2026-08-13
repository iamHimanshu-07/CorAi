# Deploying CorAi to Hugging Face Spaces (free)

This is the recommended **free** deployment path for CorAi. HF Spaces (Docker
SDK) gives you **2 vCPU + 16 GB RAM** on the free tier — plenty of room to
build and run the full ML/RAG stack, which Render's free plan (512 MB) cannot
do. Total cost: **$0/month**.

---

## 1. Prerequisites

- A free Hugging Face account — <https://huggingface.co/join>.
- A GitHub account that owns [`iamHimanshu-07/CorAi`](https://github.com/iamHimanshu-07/CorAi).
- (Optional) A **Google AI Studio** key if you want the HeartAI Copilot
  chatbot to answer. **The app boots and serves predictions without it.**

---

## 2. Create the Space (one-time)

1. Go to <https://huggingface.co/new-space>.
2. Fill in:
   - **Owner:** your HF username
   - **Space name:** `CorAi`
   - **License:** MIT
   - **SDK:** **Docker**  ← important, not Gradio / Streamlit
   - **Space hardware:** CPU basic (free)
   - **Visibility:** Public (or Private if you have a Pro plan)
3. Click **Create Space**. HF initialises a git repo at
   `https://huggingface.co/spaces/<you>/CorAi`.

---

## 3. Push the CorAi code

The repo already contains an HF Spaces–ready `Dockerfile` and a `README.md`
with the `sdk: docker` frontmatter. From your local clone:

```bash
# Add the HF Space as a remote (one-time)
git remote add hf https://huggingface.co/spaces/<you>/CorAi

# Push. HF Spaces watches the default branch (main).
git push hf main
```

HF will start building the Docker image. The first build takes **5–10 minutes**
(mostly `pip install` of scikit-learn, shap, langchain, faiss-cpu,
sentence-transformers). You can watch the build log in the Space's
**Logs** tab.

---

## 4. Set environment variables

HF Spaces does **not** read `.env` files. Configure variables in the Space's
**Settings → Variables and secrets**:

| Variable | Required? | Value / how to generate |
|---|---|---|
| `SECRET_KEY` | ✅ | Click the 🔑 "Generate" button — HF stores it encrypted. |
| `BOOTSTRAP_DOCTOR_PASSWORD` | ✅ | Set your own (the default in `render.yaml` is a placeholder). |
| `BOOTSTRAP_DOCTOR_USERNAME` | optional | `doctor` (default). |
| `BOOTSTRAP_DOCTOR_EMAIL` | optional | `doctor@corai.local` (default). |
| `GOOGLE_API_KEY` | optional | A key from <https://aistudio.google.com/app/apikey>. Enables the HeartAI Copilot. |
| `DATABASE_URL` | optional | Leave unset — see "Persistence" below. |
| `MODEL_PATH` | optional | Leave unset — see "Persistence" below. |

Click **Save** → HF triggers a rebuild with the new env vars.

---

## 5. Get the bootstrap admin password

You set `BOOTSTRAP_DOCTOR_PASSWORD` in step 4 — that's the password. On the
Space's login page, sign in as `doctor` and rotate the password from the
admin profile page (or via the user settings).

> **Default demo password in `render.yaml` is `change-me-after-first-login`.**
> Override it in the Space's variables before the first login, or rotate
> immediately after.

---

## 6. (Optional) Enable the HeartAI Copilot chatbot

If you set `GOOGLE_API_KEY` in step 4, the floating chatbot widget will
answer questions on the first request. The RAG index is built lazily and
cached in `/data/.rag_cache` (or in the image, if no Storage Bucket — see
below).

If you don't set the key, the rest of the app works normally and the chat
widget will show a friendly "needs an API key" message.

---

## 7. Verify the deployment

After the first build finishes:

```bash
# Health check
curl https://<you>-corai.hf.space/healthz
# → {"status":"ok"}

# Readiness check (DB + model)
curl https://<you>-corai.hf.space/readyz
# → {"status":"ok","checks":{"db":"ok","model":"ok"}}
```

Open `https://<you>-corai.hf.space`, sign in with the bootstrap credentials,
and run a prediction.

---

## 8. Persistence (important)

Free HF Docker Spaces have **no persistent disk by default** — every cold
start wipes `/data`, so the entrypoint retrains the model from `heart.csv`
and re-seeds the SQLite DB. This is fine for a demo; first cold start is
**~3–5 minutes** (mostly the model retrain), subsequent warm restarts are
fast because the Docker image layer is cached.

If you need persistence (so the trained model and DB survive restarts):

1. Subscribe to a paid HF plan and attach a **Storage Bucket** to the Space,
   mounted at `/data`. Set the four env vars:
   ```
   DATABASE_URL=sqlite:////data/corai.db
   MODEL_PATH=/data/models/corai-1.0.0.pkl
   CorAi_RAG_INDEX=/data/.rag_cache/corai_index
   CorAi_HF_CACHE=/data/.hf_cache
   ```
2. Or: pre-train the model locally, push the `.pkl` artifact to an HF
   Dataset, and download it on first boot. (Not implemented by default; ask
   if you want this added.)

---

## 9. Cold-start behavior

Free Docker Spaces **sleep after 48 hours of idle**. When a request comes
in, the container restarts in a few seconds. The first request after a
cold start incurs the retrain cost (~3–5 min) **only if `/data` is not
persisted** — otherwise the existing model and DB are reused.

---

## 10. Auto-rebuild on GitHub push (optional)

To rebuild the Space every time you push to `main`:

1. In the Space's **Settings → Source**, click **Connect to a GitHub repo**.
2. Choose `iamHimanshu-07/CorAi`, branch `main`.
3. HF adds a webhook to your repo. Each push triggers a Space rebuild.

> This auto-deploys to your public Space. If you prefer manual rebuilds,
> skip this step and use the **Factory → Restart** / `git push hf main`
> flow instead.

---

## 11. Custom domain (optional)

HF Spaces are reachable at `https://<you>-corai.hf.space`. To use a custom
domain, you need an HF Pro plan — see
<https://huggingface.co/docs/hub/spaces-domains>.

---

## 12. Costs

| Item | Cost |
|---|---|
| CPU basic Space (2 vCPU, 16 GB RAM, Docker) | **$0/mo** |
| Storage (in-image, no bucket) | **$0/mo** |
| Outbound bandwidth (HF provides ample) | **$0/mo** |
| **Total** | **$0/mo** |

To shut down: Space → **Settings → Delete this Space**.

---

## 13. Local development alongside the Space

The same `Dockerfile` works locally:

```bash
docker build -t corai-local .
docker run --rm -p 7860:7860 -e SECRET_KEY=test corai-local
# → http://localhost:7860
```

Without Docker:

```bash
python -m venv .venv && source .venv/bin/activate  # or: .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
flask --app wsgi:app init-db
flask --app wsgi:app run --port 7860
```

---

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Build fails with `Killed` / exit 137 | Out of memory during `pip install` (rare on free tier; usually safe) | Retry; if persistent, switch to CPU upgrade hardware. |
| `gunicorn: error: unrecognized arguments` | Old entrypoint in the image | Force rebuild: Space → Settings → Factory → **Reboot / Clear build cache**. |
| `/readyz` → `model: missing` (and stays missing) | First boot, training still in progress | Wait 2–3 min, refresh. |
| App returns 502 on first request after idle | Cold start in progress (free Spaces sleep after 48 h) | Refresh after ~30 s. |
| Chatbot shows "needs an API key" | `GOOGLE_API_KEY` not set | Set it in Space → Settings → Variables and secrets. |
| Session cookie / login breaks after redeploy | `SECRET_KEY` rotated | Set a stable `SECRET_KEY` in Space variables. |
| `Permission denied` writing to `/data` | Image was built with the old `corai` user | Pull latest `main` and rebuild the Space. |

For anything else, check **Space → Logs** — gunicorn output shows the
full traceback.
