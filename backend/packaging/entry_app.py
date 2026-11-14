"""PyInstaller entry point for FMS.exe (tray app, no console window)."""

import sys

from fms.launcher import main

sys.exit(main())
