# Running CorAi locally

Step-by-step to get the app running on Windows / macOS / Linux with no
errors. Assumes Python 3.11+ (project tested on 3.11 and 3.14).

---

## 1. Clone + venv

```bash
git clone https://github.com/iamHimanshu-07/CorAi.git
cd CorAi

# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

If you see `running scripts is disabled on this system`, run PowerShell as
admin once and execute `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Environment file

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

Open `.env` and fill in the values you care about. **Minimum required**:

```env
SECRET_KEY=any-random-string-here
BOOTSTRAP_DOCTOR_USERNAME=doctor
BOOTSTRAP_DOCTOR_PASSWORD=corai2026
```

## 4. Train the model (first run only)

```bash
python -m ml.train --data heart.csv --version 1.0.0
```

This writes `models/corai-1.0.0.pkl` (the inference artifact). Takes
~30 seconds. Skip on subsequent runs.

## 5. Initialize the database

```bash
flask --app app:create_app init-db
```

This creates `instance/corai.db` (SQLite) and runs lightweight additive
migrations on every request after that.

## 6. Run the dev server

```bash
flask --app app:create_app run --debug
```

Open <http://127.0.0.1:5000> and log in with:

| field    | value       |
|----------|-------------|
| username | `doctor`    |
| password | `corai2026` |

**Change the password on first login** via the admin page, or by setting
`BOOTSTRAP_DOCTOR_PASSWORD` in `.env` before the first request.

## 7. What you should see

| URL                          | What it does                                          |
|------------------------------|-------------------------------------------------------|
| `/`                          | Home / dashboard                                      |
| `/predict`                   | 11-feature manual prediction form                     |
| `/upload-report`             | PDF upload → auto-parse → predict                     |
| `/map`                       | Doctor map (Leaflet + OpenStreetMap)                  |
| `/about`                     | Static "About" page                                   |
| `/metrics`                   | Model evaluation dashboard                            |
| `/admin/audit-log`           | Per-prediction audit trail (admin only)               |
| `/v1/predict`                | JSON API: `POST` JSON in, JSON out (Pydantic v2)      |
| `/healthz`                   | Liveness check                                        |
| `/readyz`                    | Readiness check (DB + model state)                    |

## 8. Run the tests

```bash
pytest -q
```

Expected: **17 passed, 1 skipped**. The skipped test is
`test_delete_patient` — it targets a patient-CRUD endpoint that was
removed from the patients blueprint (the blueprint is now a catch-all
404). Skip with comment, no functional regression.

## Troubleshooting

### `ModuleNotFoundError: No module named 'flask'`
You forgot to activate the venv. Run step 1 again and make sure your
prompt shows `(.venv)`.

### Database errors on first run
Run `flask --app app:create_app init-db` again. If the dev DB schema is
messed up, delete `instance/corai.db` and re-run init-db.

### Port already in use
Change `PORT` in `.env` (default 5000), or pass `--port 5001` to
`flask run`.

---

## Production / Render

For Render deployment instructions, see `README.md`. The local-run path
above mirrors the dev-mode branch of the Render Blueprint.
