"""Command line for the hub.

python -m fms [--port 8765] [--host 127.0.0.1] [--data-dir PATH]   start the hub
python -m fms reset-password [--data-dir PATH]                      set a new owner password
"""

import argparse
import getpass
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__
from .config import Settings


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


def reset_password(argv: list[str], ask=getpass.getpass, out=print) -> int:
    """Set a new owner password from the laptop itself. Signs out every device."""
    from .db import make_engine, make_session_factory, run_migrations
    from .errors import Invalid
    from .services import auth

    parser = argparse.ArgumentParser(prog="fms reset-password")
    parser.add_argument("--data-dir", type=Path, default=Settings().data_dir)
    args = parser.parse_args(argv)
    settings = replace(Settings(), data_dir=args.data_dir)

    out("Reset the FMS owner password.")
    out("Every phone and PC will be signed out and must log in with the new password.\n")
    first = ask("New password: ")
    if first != ask("Type it again: "):
        out("The two passwords don't match. Nothing was changed.")
        return 1

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    try:
        with make_session_factory(engine)() as session:
            try:
                signed_out = auth.reset_password(session, first)
            except Invalid as exc:
                out(f"{exc.message}. Nothing was changed.")
                return 1
            session.commit()
    finally:
        engine.dispose()
    out(f"Done. The password is changed and {signed_out} device(s) were signed out.")
    return 0


def serve(argv: list[str]) -> int:
    import uvicorn

    from .logging_setup import configure_logging
    from .main import create_app

    settings = parse_settings(argv)
    configure_logging(settings.log_dir)
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_config=None)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "reset-password":
        return reset_password(argv[1:])
    return serve(argv)


if __name__ == "__main__":
    sys.exit(main())
