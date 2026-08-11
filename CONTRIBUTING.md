# Contributing

Thanks for your interest in the CorAi.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m ml.train --data heart.csv --version 1.0.0
flask --app wsgi:app init-db
flask --app wsgi:app run
```

## Code style

We use `ruff` for linting. Run `ruff check .` before committing.

## Tests

```bash
pytest -q
```

The full pipeline smoke test (`tests/test_train.py`) is marked `slow`. Run it
explicitly when changing the training pipeline:

```bash
pytest -q -m slow
```

## Submitting changes

1. Open an issue describing the change.
2. Fork, branch, commit.
3. Run lint + tests.
4. Open a pull request referencing the issue.

Please keep PRs focused. For large features, discuss in the issue first.

## Reporting issues

Use the GitHub issue tracker. Include the model version (`/readyz`), Python
version, and a minimal reproduction when reporting bugs.