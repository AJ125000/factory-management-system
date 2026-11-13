"""Start the hub server: `python -m fms`."""

import uvicorn

from .config import Settings
from .logging_setup import configure_logging
from .main import create_app


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_dir)
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_config=None)


if __name__ == "__main__":
    main()
