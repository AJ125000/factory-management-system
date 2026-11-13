from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from fms.db import make_engine, run_migrations
from fms.models import Base


def test_models_match_migrations(tmp_path):
    """Fails if someone changes models.py without adding a migration."""
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    run_migrations(url)
    engine = make_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def test_migrations_are_idempotent(tmp_path):
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    run_migrations(url)
    run_migrations(url)  # second start must be a no-op, not re-seed
    engine = make_engine(url)
    with engine.connect() as conn:
        count = conn.exec_driver_sql("SELECT COUNT(*) FROM worker_types").scalar()
    engine.dispose()
    assert count == 2
