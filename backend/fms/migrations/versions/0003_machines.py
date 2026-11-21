"""machines, size tables and automatic loader pay

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21

* Adds the four machines from the owner's rate sheet, with the sheet's size tables
  and rates (from 01/01/2026, so they cover every entry).
* Rates now belong to a machine instead of a worker type. Existing rates (all for the
  original cutting machine) move to that machine.
* Worker types now say whether a worker is an operator or a loader.
* Production entries record their machine, and what one piece counted for (sq ft,
  running ft) as worked out when saved. Existing entries are on the original machine.
* Loaders are assigned to machines (with a start date) and paid automatically from
  the operators' entries. No loader is assigned here: the owner does that.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

import fms.models
from fms.util import utcnow

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BLOCK_CUTTING_ID = "00000000-0000-4000-8000-000000000101"
DOUBLE_EDGE_ID = "00000000-0000-4000-8000-000000000102"
TABLE_POLISH_ID = "00000000-0000-4000-8000-000000000103"
SINGLE_CUTTING_ID = "00000000-0000-4000-8000-000000000104"

MACHINES = [
    # id, code, kind, English, Hindi, order
    (DOUBLE_EDGE_ID, "double_edge", "double_edge", "Double edge cutting machine",
     "डबल एज कटिंग मशीन", 1),
    (TABLE_POLISH_ID, "table_polish", "table_polish", "Table polish machine",
     "टेबल पॉलिश मशीन", 2),
    (SINGLE_CUTTING_ID, "single_cutting", "single_cutting", "Single cutting machine",
     "सिंगल कटिंग मशीन", 3),
    # The original machine; its real name is still to be confirmed by the owner.
    (BLOCK_CUTTING_ID, "block_cutting", "block_cutting", "Cutting machine",
     "कटिंग मशीन", 4),
]

# (length, width, running ft per piece, sq ft per piece) from the owner's sheet.
DOUBLE_EDGE_SIZES = [("2", "2", "8", "4"), ("2", "1.5", "7", "3"), ("2", "1", "6", "2")]  # feet
SINGLE_CUTTING_SIZES = [  # inches; "market standard" figures, not the exact area
    ("9", "9", "4", "1"),
    ("10", "10", "4", "1"),
    ("11", "11", "4", "1"),
    ("14", "14", "6", "2"),
    ("15", "15", "6", "2"),
    ("16", "16", "6", "2"),
    ("22.5", "22.5", "8", "4"),
    ("22", "22", "8", "4"),
    ("21", "21", "8", "4"),
    ("16", "22", "7", "3"),
    ("15", "22", "7", "3"),
    ("14", "22", "7", "3"),
    ("11", "22", "6", "2"),
]

SHEET_DATE = date(2026, 1, 1)
SHEET_RATES = [  # machine, component, rate
    (DOUBLE_EDGE_ID, "cutting", "0.22"),  # per running ft
    (DOUBLE_EDGE_ID, "unloading", "0.15"),
    (TABLE_POLISH_ID, "polish_1", "0.45"),
    (TABLE_POLISH_ID, "polish_2", "0.90"),
    (TABLE_POLISH_ID, "polish_4", "1.10"),
    (TABLE_POLISH_ID, "polish_5", "1.25"),
    (TABLE_POLISH_ID, "unloading", "0.15"),
    (SINGLE_CUTTING_ID, "cutting", "0.28"),  # per running ft
    (SINGLE_CUTTING_ID, "unloading", "0.15"),
]


def _seed_id(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def upgrade() -> None:
    now = utcnow()
    conn = op.get_bind()

    # ---------------------------------------------------------------- machines
    op.create_table(
        "machines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name_en", sa.String(length=80), nullable=False),
        sa.Column("name_hi", sa.String(length=80), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('block_cutting', 'double_edge', 'table_polish', 'single_cutting')",
            name=op.f("ck_machines_kind"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_machines")),
        sa.UniqueConstraint("code", name=op.f("uq_machines_code")),
    )
    machines = sa.table(
        "machines",
        *(sa.column(c) for c in (
            "id", "code", "kind", "name_en", "name_hi", "sort_order", "is_active",
            "created_at", "updated_at",
        )),
    )
    op.bulk_insert(machines, [
        {"id": i, "code": code, "kind": kind, "name_en": en, "name_hi": hi, "sort_order": order,
         "is_active": True, "created_at": now, "updated_at": now}
        for i, code, kind, en, hi, order in MACHINES
    ])

    op.create_table(
        "machine_sizes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("machine_id", sa.String(length=36), nullable=False),
        sa.Column("length", fms.models.DecimalText(length=32), nullable=False),
        sa.Column("width", fms.models.DecimalText(length=32), nullable=False),
        sa.Column("rft", fms.models.DecimalText(length=32), nullable=False),
        sa.Column("sqft", fms.models.DecimalText(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"],
                                name=op.f("fk_machine_sizes_machine_id_machines"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_machine_sizes")),
        sa.UniqueConstraint("machine_id", "length", "width",
                            name=op.f("uq_machine_sizes_machine_id_length_width")),
    )
    sizes = sa.table("machine_sizes", *(sa.column(c) for c in (
        "id", "machine_id", "length", "width", "rft", "sqft", "created_at", "updated_at")))
    rows, n = [], 200
    for machine_id, table in ((DOUBLE_EDGE_ID, DOUBLE_EDGE_SIZES),
                              (SINGLE_CUTTING_ID, SINGLE_CUTTING_SIZES)):
        for length, width, rft, sqft in table:
            n += 1
            rows.append({"id": _seed_id(n), "machine_id": machine_id, "length": length,
                         "width": width, "rft": rft, "sqft": sqft,
                         "created_at": now, "updated_at": now})
    op.bulk_insert(sizes, rows)

    # ------------------------------------------------------------ worker types
    with op.batch_alter_table("worker_types") as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(length=20), nullable=True))
    conn.execute(sa.text(
        "UPDATE worker_types SET role = CASE pay_scheme WHEN 'loading' THEN 'loader' "
        "ELSE 'operator' END"
    ))
    with op.batch_alter_table("worker_types") as batch_op:
        batch_op.drop_constraint(op.f("ck_worker_types_pay_scheme"), type_="check")
        batch_op.drop_column("pay_scheme")
        batch_op.alter_column("role", existing_type=sa.String(length=20), nullable=False)
        batch_op.create_check_constraint("role", "role IN ('operator', 'loader')")

    # ------------------------------------------------------------------- rates
    # Every existing rate was for the original machine (worker types were its two
    # jobs). Should a custom worker type have duplicated a rate on the same date, the
    # first one entered is kept.
    conn.execute(sa.text(
        "DELETE FROM rates WHERE EXISTS (SELECT 1 FROM rates AS older "
        "WHERE older.component = rates.component "
        "AND older.effective_from = rates.effective_from "
        "AND (older.created_at < rates.created_at "
        "     OR (older.created_at = rates.created_at AND older.id < rates.id)))"
    ))
    with op.batch_alter_table("rates") as batch_op:
        batch_op.add_column(sa.Column("machine_id", sa.String(length=36), nullable=True))
        batch_op.alter_column("rate_per_sqft", new_column_name="rate",
                              existing_type=sa.String(length=32))
    conn.execute(sa.text("UPDATE rates SET machine_id = :m"), {"m": BLOCK_CUTTING_ID})
    with op.batch_alter_table("rates") as batch_op:
        batch_op.drop_constraint(op.f("uq_rates_worker_type_id_component_effective_from"),
                                 type_="unique")
        batch_op.drop_constraint(op.f("ck_rates_component"), type_="check")
        batch_op.drop_constraint(op.f("fk_rates_worker_type_id_worker_types"), type_="foreignkey")
        batch_op.drop_column("worker_type_id")
        batch_op.alter_column("machine_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_foreign_key(op.f("fk_rates_machine_id_machines"), "machines",
                                    ["machine_id"], ["id"], ondelete="RESTRICT")
        batch_op.create_unique_constraint(
            op.f("uq_rates_machine_id_component_effective_from"),
            ["machine_id", "component", "effective_from"],
        )
    rates = sa.table("rates", *(sa.column(c) for c in (
        "id", "machine_id", "component", "rate", "effective_from", "note",
        "created_at", "updated_at")))
    op.bulk_insert(rates, [
        {"id": _seed_id(300 + i), "machine_id": m, "component": c, "rate": r,
         "effective_from": SHEET_DATE, "note": "Owner's rate sheet",
         "created_at": now, "updated_at": now}
        for i, (m, c, r) in enumerate(SHEET_RATES, start=1)
    ])

    # ------------------------------------------------------- loader assignments
    op.create_table(
        "loader_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("machine_id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"],
                                name=op.f("fk_loader_assignments_machine_id_machines"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"],
                                name=op.f("fk_loader_assignments_worker_id_workers"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_loader_assignments")),
        sa.UniqueConstraint("machine_id", "effective_from",
                            name=op.f("uq_loader_assignments_machine_id_effective_from")),
    )

    # ------------------------------------------------------- production entries
    with op.batch_alter_table("production_entries") as batch_op:
        batch_op.add_column(sa.Column("machine_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("size_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("size_label", sa.String(length=40), nullable=True))
        batch_op.add_column(
            sa.Column("piece_sqft", fms.models.DecimalText(length=32), nullable=True))
        batch_op.add_column(
            sa.Column("piece_rft", fms.models.DecimalText(length=32), nullable=True))
        batch_op.add_column(sa.Column("batti", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("loader_id", sa.String(length=36), nullable=True))
    for entry_id, length, width in conn.execute(
        sa.text("SELECT id, length_ft, width_ft FROM production_entries")
    ):
        sqft = format((Decimal(length) * Decimal(width)).normalize(), "f")
        conn.execute(
            sa.text("UPDATE production_entries SET machine_id = :m, piece_sqft = :s "
                    "WHERE id = :id"),
            {"m": BLOCK_CUTTING_ID, "s": sqft, "id": entry_id},
        )
    with op.batch_alter_table("production_entries") as batch_op:
        batch_op.alter_column("machine_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column("piece_sqft", existing_type=sa.String(length=32),
                              nullable=False)
        batch_op.alter_column("length_ft", existing_type=sa.String(length=32),
                              nullable=True)
        batch_op.alter_column("width_ft", existing_type=sa.String(length=32),
                              nullable=True)
        batch_op.create_foreign_key(op.f("fk_production_entries_machine_id_machines"), "machines",
                                    ["machine_id"], ["id"], ondelete="RESTRICT")
        batch_op.create_foreign_key(op.f("fk_production_entries_size_id_machine_sizes"),
                                    "machine_sizes", ["size_id"], ["id"], ondelete="SET NULL")
        batch_op.create_foreign_key(op.f("fk_production_entries_loader_id_workers"), "workers",
                                    ["loader_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index(op.f("ix_production_entries_machine_id"), ["machine_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("Restore a backup made before the upgrade instead.")
