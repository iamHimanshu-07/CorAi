# Render / Heroku-style Procfile. Only used if you set runtime=python in
# render.yaml instead of runtime=docker. Buildpack will install requirements.txt.
#
# On first boot we:
#   1. Train the model if the artifact is missing.
#   2. Run init-db.
#   3. Hand off to gunicorn on $PORT.
web: sh -c "if [ ! -f \"$MODEL_PATH\" ]; then LOKY_MAX_CPU_COUNT=2 python -m ml.train --data heart.csv --version 1.0.0; fi && flask --app wsgi:app init-db && gunicorn -w 2 -b 0.0.0.0:$PORT wsgi:app"