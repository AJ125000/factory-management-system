"""rates and size tables belong to the machine type

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-23

The owner runs several machines of each type (e.g. 3 splitting, 3 table polish) and
adds or retires machines over time. Every machine of a type is paid the same rates and
uses the same size table, so those now belong to the type; loaders stay per machine.

Until now there was exactly one machine per type, so each rate and size simply takes
that machine's type. The four machines keep their names, except that defaults the owner
hasn't changed get a number ("Table polish machine 1"), and the original cutting
machine becomes "Splitting machine 1".
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RENAMES = [
    # (old English, old Hindi) -> (new English, new Hindi), only if still unchanged
    ("Cutting machine", "कटिंग मशीन", "Splitting machine 1", "स्प्लिटिंग मशीन 1"),
    ("Double edge cutting machine", "डबल एज कटिंग मशीन",
     "Double edge cutting machine 1", "डबल एज कटिंग मशीन 1"),
    ("Table polish machine", "टेबल पॉलिश मशीन", "Table polish machine 1", "टेबल पॉलिश मशीन 1"),
    ("Single cutting machine", "सिंगल कटिंग मशीन",
     "Single cutting machine 1", "सिंगल कटिंग मशीन 1"),
]


def upgrade() -> None:
    conn = op.get_bind()

    for table, unique_old, unique_new, cols in (
        ("rates", "uq_rates_machine_id_component_effective_from",
         "uq_rates_kind_component_effective_from", ["kind", "component", "effective_from"]),
        ("machine_sizes", "uq_machine_sizes_machine_id_length_width",
         "uq_machine_sizes_kind_length_width", ["kind", "length", "width"]),
    ):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("kind", sa.String(length=20), nullable=True))
        conn.execute(sa.text(
            f"UPDATE {table} SET kind = "
            f"(SELECT machines.kind FROM machines WHERE machines.id = {table}.machine_id)"
        ))
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(op.f(unique_old), type_="unique")
            batch_op.drop_constraint(op.f(f"fk_{table}_machine_id_machines"), type_="foreignkey")
            batch_op.drop_column("machine_id")
            batch_op.alter_column("kind", existing_type=sa.String(length=20), nullable=False)
            batch_op.create_unique_constraint(op.f(unique_new), cols)

    for old_en, old_hi, new_en, new_hi in RENAMES:
        conn.execute(
            sa.text("UPDATE machines SET name_en = :new_en, name_hi = :new_hi "
                    "WHERE name_en = :old_en AND name_hi = :old_hi"),
            {"old_en": old_en, "old_hi": old_hi, "new_en": new_en, "new_hi": new_hi},
        )


def downgrade() -> None:
    raise NotImplementedError("Restore a backup made before the upgrade instead.")
