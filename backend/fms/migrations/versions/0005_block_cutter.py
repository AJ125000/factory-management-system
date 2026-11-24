"""block cutter machines, paid per shift

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-24

A new machine type: the block cutter. Its workers are paid a fixed amount per shift
(day or night) instead of by the piece, and it has no loader. Each production entry on
it is one shift of one worker, so entries get a `shift` column. One block cutter machine
is added; the owner adds more and sets the per-shift rate in the app.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fms.util import utcnow

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BLOCK_CUTTER_ID = "00000000-0000-4000-8000-000000000105"
OLD_KINDS = "kind IN ('block_cutting', 'double_edge', 'table_polish', 'single_cutting')"
NEW_KINDS = (
    "kind IN ('block_cutting', 'double_edge', 'table_polish', 'single_cutting', 'block_cutter')"
)


def upgrade() -> None:
    with op.batch_alter_table("machines") as batch_op:
        batch_op.drop_constraint(op.f("ck_machines_kind"), type_="check")
        batch_op.create_check_constraint(op.f("ck_machines_kind"), NEW_KINDS)

    with op.batch_alter_table("production_entries") as batch_op:
        batch_op.add_column(sa.Column("shift", sa.String(length=10), nullable=True))
        batch_op.create_check_constraint(
            op.f("ck_production_entries_shift"), "shift IS NULL OR shift IN ('day', 'night')"
        )

    now = utcnow()
    machines = sa.table(
        "machines",
        *(sa.column(c) for c in (
            "id", "code", "kind", "name_en", "name_hi", "sort_order", "is_active",
            "created_at", "updated_at",
        )),
    )
    order = op.get_bind().scalar(sa.text("SELECT COALESCE(MAX(sort_order), 0) FROM machines"))
    op.bulk_insert(machines, [{
        "id": BLOCK_CUTTER_ID, "code": "block_cutter", "kind": "block_cutter",
        "name_en": "Block cutter 1", "name_hi": "ब्लॉक कटर 1", "sort_order": order + 1,
        "is_active": True, "created_at": now, "updated_at": now,
    }])


def downgrade() -> None:
    raise NotImplementedError("Restore a backup made before the upgrade instead.")
