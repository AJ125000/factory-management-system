# FMS backend (hub server)

Runs on the owner's laptop. It holds the master SQLite database and serves the
API that the FMS app on the laptop, the other PC and the phone talk to.

## Development

```bash
cd backend
uv sync                 # creates .venv with Python 3.12 + all dependencies
uv run pytest           # run the test suite
uv run ruff check .     # lint
uv run python -m fms    # start the server on http://127.0.0.1:8765 (API docs at /docs)
```

Server options (unknown options are rejected, never silently ignored):

```bash
uv run python -m fms --port 8766 --data-dir /path/to/test-data   # a separate test hub
uv run python -m fms --help
```

Data is stored in the platform's app-data folder (on Windows,
`%LOCALAPPDATA%\FMS\fms.db`). Set `FMS_DATA_DIR` to use a different folder.

## Layout

| Path | What it holds |
|---|---|
| `fms/wages.py` | Pure wage formulas (no database) |
| `fms/models.py` | Database tables |
| `fms/services/` | Business rules: workers, rates, production, reports, Excel exports |
| `fms/api/` | HTTP endpoints (thin layer over services) |
| `fms/migrations/` | Alembic schema migrations, applied automatically on start |
| `tests/` | Automated tests |

## Database changes

After changing `fms/models.py`, generate a migration and review it:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

`tests/test_migrations.py` fails if the models and migrations drift apart.
