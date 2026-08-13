"""WSGI entrypoint for production servers (gunicorn).

Usage:
    gunicorn -w 2 -b 0.0.0.0:$PORT wsgi:app

The default ``$PORT`` is ``7860`` to match Hugging Face Spaces. Render and
Railway set ``$PORT`` to their own value at runtime, so they override this
default. Local dev can still pin ``PORT=5000`` via ``.env``.
"""

import os

from app import create_app

app = create_app(os.getenv("FLASK_CONFIG", "config.Config"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "7860")), debug=False)
