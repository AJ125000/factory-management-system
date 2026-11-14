# PyInstaller build for the FMS hub. Run from backend/ after building the frontend:
#
#     uv sync --extra desktop --group build
#     uv run pyinstaller packaging/fms.spec --noconfirm
#
# Produces dist/FMS/ with FMS.exe (tray app) and fms-admin.exe (console tools).

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent  # backend/
FMS = ROOT / "fms"

if not (FMS / "static" / "index.html").is_file():
    raise SystemExit("Build the frontend first: cd frontend && npm run build")

# The app (built frontend) and the database migrations are read from disk at runtime.
datas = [
    (str(FMS / "static"), "fms/static"),
    (str(FMS / "migrations"), "fms/migrations"),
]
hiddenimports = [
    *collect_submodules("uvicorn"),  # uvicorn picks its loop/protocol modules at runtime
    *collect_submodules("fms"),  # migration scripts import fms.models by name
    "sqlalchemy.dialects.sqlite",
]
excludes = ["tkinter", "pytest", "ruff"]

app = Analysis(
    [str(ROOT / "packaging" / "entry_app.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports + ["pystray", "PIL"],
    excludes=excludes,
)
admin = Analysis(
    [str(ROOT / "packaging" / "entry_admin.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
)

icon = str(ROOT.parent / "assets" / "output_icon.ico")

app_exe = EXE(
    PYZ(app.pure),
    app.scripts,
    [],
    exclude_binaries=True,
    name="FMS",
    console=False,  # a tray app: no black console window
    icon=icon,
)
admin_exe = EXE(
    PYZ(admin.pure),
    admin.scripts,
    [],
    exclude_binaries=True,
    name="fms-admin",
    console=True,  # asks for the new password in a console
    icon=icon,
)

COLLECT(
    app_exe,
    app.binaries,
    app.datas,
    admin_exe,
    admin.binaries,
    admin.datas,
    name="FMS",
)
