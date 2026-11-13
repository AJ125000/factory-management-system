from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from fms.models import Base

config = context.config
target_metadata = Base.metadata


def _configure(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite needs table rebuilds for most ALTERs
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:
    # Called from fms.db.run_migrations with an open connection.
    _configure(connection)
else:
    # Called from the alembic CLI.
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with engine.begin() as conn:
        _configure(conn)
