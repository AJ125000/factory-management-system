"""Start the hub server: `python -m fms [--port 8765] [--host 127.0.0.1] [--data-dir PATH]`."""

import argparse
from dataclasses import replace
from pathlib import Path

import uvicorn

from . import __version__
from .config import Settings
from .logging_setup import configure_logging
from .main import create_app


def parse_settings(argv: list[str] | None = None) -> Settings:
    defaults = Settings()
    parser = argparse.ArgumentParser(prog="fms", description="Factory Management System hub")
    parser.add_argument("--port", type=int, default=defaults.port, help="default %(default)s")
    parser.add_argument("--host", default=defaults.host, help="default %(default)s")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=defaults.data_dir,
        help="where the database and logs live (default %(default)s)",
    )
    parser.add_argument("--version", action="version", version=f"FMS {__version__}")
    args = parser.parse_args(argv)  # unknown options are an error, never silently ignored
    return replace(defaults, port=args.port, host=args.host, data_dir=args.data_dir)


def main() -> None:
    settings = parse_settings()
    configure_logging(settings.log_dir)
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_config=None)


if __name__ == "__main__":
    main()
