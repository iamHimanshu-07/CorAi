# Migrations

Database migrations are managed by Flask-Migrate / Alembic. The
`migrations/` directory will be populated by running:

```bash
flask --app wsgi:app db init
flask --app wsgi:app db migrate -m "initial schema"
flask --app wsgi:app db upgrade
```

In development, the lazy `_ensure_schema()` hook in `app/__init__.py` will
create tables on the first request, so this directory may stay empty for
local use.