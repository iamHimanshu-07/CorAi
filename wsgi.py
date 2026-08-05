"""WSGI entrypoint for production servers (gunicorn).

Usage:
    gunicorn -w 2 -b 0.0.0.0:5000 wsgi:app
"""

import os

from app import create_app

app = create_app(os.getenv("FLASK_CONFIG", "config.Config"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
