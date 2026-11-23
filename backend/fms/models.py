"""Database tables.

Design notes:
* UUID string primary keys and `updated_at` everywhere, ready for phone <-> laptop sync.
* Hard deletes leave a row in `tombstones` so other devices learn about them when syncing.
* Measurements and rates are stored as exact decimal text, never floats.
* Each production entry records the worker type it was paid under, so changing a
  worker's type later never changes their past wages.
* Each production entry also keeps the sq ft / running ft of one piece as worked out
  when it was saved, so editing a machine's size table never changes past wages.
* The loader paid for an entry is the one assigned to its machine on the entry's
  date (or the one chosen on the entry when the usual loader was absent).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from .util import new_id, utcnow
from .wages import component_unit

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class DecimalText(TypeDecorator[Decimal]):
    """Stores Decimal values as exact text (SQLite would otherwise round-trip through float)."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        return format(Decimal(value).normalize(), "f")

    def process_result_value(self, value, dialect):  # type: ignore[override]
        return None if value is None else Decimal(value)


def _id_column() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class WorkerType(TimestampMixin, Base):
    __tablename__ = "worker_types"
    __table_args__ = (CheckConstraint("role IN ('operator', 'loader')", name="role"),)

    id: Mapped[str] = _id_column()
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_hi: Mapped[str | None] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)


class Machine(TimestampMixin, Base):
    """A machine on the factory floor. Its kind decides how its workers are paid."""

    __tablename__ = "machines"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('block_cutting', 'double_edge', 'table_polish', 'single_cutting')",
            name="kind",
        ),
    )

    id: Mapped[str] = _id_column()
    code: Mapped[str] = mapped_column(String(40), unique=True)
    kind: Mapped[str] = mapped_column(String(20))
    name_en: Mapped[str] = mapped_column(String(80))
    name_hi: Mapped[str | None] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


class MachineSize(TimestampMixin, Base):
    """A standard size and the running ft / sq ft paid per piece ("market standard"),
    shared by every machine of a type.

    Lengths are in feet for double edge cutting and in inches for single cutting.
    """

    __tablename__ = "machine_sizes"
    __table_args__ = (UniqueConstraint("kind", "length", "width"),)

    id: Mapped[str] = _id_column()
    kind: Mapped[str] = mapped_column(String(20))
    length: Mapped[Decimal] = mapped_column(DecimalText())
    width: Mapped[Decimal] = mapped_column(DecimalText())
    rft: Mapped[Decimal] = mapped_column(DecimalText())
    sqft: Mapped[Decimal] = mapped_column(DecimalText())


class LoaderAssignment(TimestampMixin, Base):
    """Who loads at a machine from `effective_from` onwards (no worker = no loader)."""

    __tablename__ = "loader_assignments"
    __table_args__ = (UniqueConstraint("machine_id", "effective_from"),)

    id: Mapped[str] = _id_column()
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"))
    worker_id: Mapped[str | None] = mapped_column(
        ForeignKey("workers.id", ondelete="SET NULL"), nullable=True
    )
    effective_from: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)


class Worker(TimestampMixin, Base):
    __tablename__ = "workers"

    id: Mapped[str] = _id_column()
    name_en: Mapped[str] = mapped_column(String(120), index=True)
    name_hi: Mapped[str | None] = mapped_column(String(120))
    worker_type_id: Mapped[str] = mapped_column(ForeignKey("worker_types.id", ondelete="RESTRICT"))
    phone: Mapped[str | None] = mapped_column(String(20))
    joined_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)

    worker_type: Mapped[WorkerType] = relationship(lazy="joined")

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


class Rate(TimestampMixin, Base):
    """A wage rate for one machine type and component, valid from `effective_from` onwards.
    Every machine of the type is paid at it.

    Per sq ft, except cutting on double edge / single cutting: per running foot.
    """

    __tablename__ = "rates"
    __table_args__ = (UniqueConstraint("kind", "component", "effective_from"),)

    id: Mapped[str] = _id_column()
    kind: Mapped[str] = mapped_column(String(20))
    component: Mapped[str] = mapped_column(String(20))
    rate: Mapped[Decimal] = mapped_column(DecimalText())
    effective_from: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)

    @property
    def unit(self) -> str:
        return component_unit(self.kind, self.component)


class ProductionEntry(TimestampMixin, Base):
    __tablename__ = "production_entries"
    __table_args__ = (
        CheckConstraint("cuts >= 0", name="cuts_non_negative"),
        CheckConstraint("quantity >= 1", name="quantity_positive"),
        Index("ix_production_entries_worker_date", "worker_id", "entry_date"),
    )

    id: Mapped[str] = _id_column()
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"))
    # Snapshot of the worker's type when the entry was made (see module docstring).
    worker_type_id: Mapped[str] = mapped_column(ForeignKey("worker_types.id", ondelete="RESTRICT"))
    machine_id: Mapped[str] = mapped_column(
        ForeignKey("machines.id", ondelete="RESTRICT"), index=True
    )
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    # Size in feet (not used by single cutting, which picks a size from its table).
    length_ft: Mapped[Decimal | None] = mapped_column(DecimalText(), nullable=True)
    width_ft: Mapped[Decimal | None] = mapped_column(DecimalText(), nullable=True)
    size_id: Mapped[str | None] = mapped_column(
        ForeignKey("machine_sizes.id", ondelete="SET NULL"), nullable=True
    )
    # What one piece counted for when saved (see module docstring).
    size_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    piece_sqft: Mapped[Decimal] = mapped_column(DecimalText())
    piece_rft: Mapped[Decimal | None] = mapped_column(DecimalText(), nullable=True)
    cuts: Mapped[int] = mapped_column(Integer, default=0)
    batti: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)
    # Someone filling in for the machine's usual loader on this entry only.
    loader_id: Mapped[str | None] = mapped_column(
        ForeignKey("workers.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    worker: Mapped[Worker] = relationship(lazy="joined", foreign_keys=[worker_id])
    worker_type: Mapped[WorkerType] = relationship(lazy="joined")
    machine: Mapped[Machine] = relationship(lazy="joined")

    @property
    def area_sqft(self) -> Decimal:
        return self.piece_sqft * self.quantity

    @property
    def rft_total(self) -> Decimal | None:
        return None if self.piece_rft is None else self.piece_rft * self.quantity


class Tombstone(Base):
    """Remembers hard-deleted rows so the deletion can be synced to other devices."""

    __tablename__ = "tombstones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    deleted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AuditLog(Base):
    """History of every change, with before/after snapshots (JSON)."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_entity", "entity", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    action: Mapped[str] = mapped_column(String(20))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    summary: Mapped[str] = mapped_column(Text)
    before: Mapped[str | None] = mapped_column(Text)
    after: Mapped[str | None] = mapped_column(Text)


class OwnerAccount(TimestampMixin, Base):
    """The one owner login. Only a hash of the password is stored (scrypt, salted)."""

    __tablename__ = "owner_account"

    id: Mapped[int] = mapped_column(primary_key=True)  # always 1
    password_hash: Mapped[str] = mapped_column(String(200))


class DeviceSession(Base):
    """A device (laptop, phone, PC) the owner has logged in on.

    Devices stay logged in — phones may be offline for weeks — until the owner signs
    them out (e.g. a lost phone). Only a hash of each device's token is stored.
    """

    __tablename__ = "device_sessions"

    id: Mapped[str] = _id_column()
    name: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text)  # JSON
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
