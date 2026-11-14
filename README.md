# Factory Management System (FMS)

Wage and production management for a Kota stone factory. The owner records each
worker's production; the FMS works out wages at the correct rate for each date,
shows production reports, and prints wage slips in Hindi or English.

## How it runs

The owner's **laptop is the hub**: it runs the FMS server and keeps the master
database. The app opens in a browser on the laptop, and phones (or another PC)
install it from the laptop's private Tailscale address.

### Phones and offline use

- The app installs to the phone's home screen and **opens without the laptop**
  (a service worker keeps it on the device — `frontend/sw/sw-template.js`).
- Every change goes into an **offline queue** on the device (`src/lib/outbox.ts`,
  stored in IndexedDB) and is sent to the laptop in order as soon as it can be
  reached. New records get their id on the device and the hub treats a repeated
  create as already done, so retries can never duplicate anything.
- Workers, rates and recent data are **kept on the device** (React Query, saved
  to IndexedDB) so screens still show them offline, with the time they're from.
- While offline, the wage preview is **calculated on the device** with a port of
  the hub's formulas; `shared/wage-cases.json` is checked by both test suites so
  they always agree to the paisa.
- Needs the laptop: permanently deleting a worker, correcting/deleting a rate,
  worker types and settings.

**Connecting a phone:** Settings → *Connect a phone* shows a QR code and steps.
On the laptop, Tailscale must be installed and the hub published once with
`tailscale serve --bg 8765` (HTTPS is required for installing the app).

| Folder | What it is |
|---|---|
| `backend/` | Hub server — Python 3.12, FastAPI, SQLite ([details](backend/README.md)) |
| `frontend/` | The app — React, TypeScript, Mantine; English/Hindi |
| `shared/` | Wage test cases both the hub and the app must pass |
| `docs/` | [Setup guide](docs/SETUP_GUIDE.md) (installing on the laptop and phones) and [user guide](docs/USER_GUIDE.md) (English/Hindi) |
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

## Windows installer

CI builds `FMS-Setup-<version>.exe` on every push (download it from the run's
artifacts); pushing a version tag such as `v0.5.0` also attaches it to a GitHub
release. It installs FMS for the current user, runs it in the system tray, starts it
at login and keeps the data in `%LOCALAPPDATA%\FMS`. See the
[setup guide](docs/SETUP_GUIDE.md).

To build the packaged program locally (any OS; the `.exe` itself needs Windows):

```bash
cd frontend && npm run build
cd ../backend && uv sync --extra desktop --group build
uv run pyinstaller packaging/fms.spec --noconfirm   # -> backend/dist/FMS/
```

The installer is not code-signed, so Windows shows "Windows protected your PC" the
first time (More info → Run anyway). A code-signing certificate removes this.
