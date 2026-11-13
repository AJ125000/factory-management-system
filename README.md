# Factory Management System (FMS)

Wage and production management for a Kota stone factory. The owner records each
worker's production; the FMS works out wages at the correct rate for each date,
shows production reports, and prints wage slips in Hindi or English.

## How it runs

The owner's **laptop is the hub**: it runs the FMS server and keeps the master
database. The app opens in a browser window on the laptop (phone access and
offline sync arrive in phase 4).

| Folder | What it is |
|---|---|
| `backend/` | Hub server — Python 3.12, FastAPI, SQLite ([details](backend/README.md)) |
| `frontend/` | The app — React, TypeScript, Mantine; English/Hindi |
| `legacy/` | The original Tkinter prototype, kept for reference |
| `assets/` | Icons |

## Development

Everything installs inside the project (`backend/.venv`, `frontend/node_modules`).

```bash
# 1. Hub server (API on http://127.0.0.1:8765)
cd backend && uv sync && uv run python -m fms

# 2. In a second terminal: the app with live reload on http://localhost:5173
cd frontend && npm install && npm run dev
```

To try the finished app the way the owner will see it, build it once and open
http://127.0.0.1:8765 (the hub serves the built app):

```bash
cd frontend && npm run build
```

## Checks (also run by CI on Windows and Linux)

```bash
cd backend && uv run ruff check . && uv run pytest
cd frontend && npm run typecheck && npm test && npm run build
```
