FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash corai && chown -R corai:corai /app
USER corai

EXPOSE 5000

# Train model on first run if missing (inference artifact generated)
CMD ["sh", "-c", "[ -f models/corai-1.0.0.pkl ] || python -m ml.train --data heart.csv --version 1.0.0; gunicorn -w 2 -b 0.0.0.0:5000 wsgi:app"]