"""Database tables.

Design notes:
* UUID string primary keys and `updated_at` everywhere, ready for phone <-> laptop sync.
* Hard deletes leave a row in `tombstones` so other devices learn about them when syncing.
* Measurements and rates are stored as exact decimal text, never floats.
* Each production entry records the worker type it was paid under, so changing a
  worker's type later never changes their past wages.
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
    __table_args__ = (CheckConstraint("pay_scheme IN ('cutting', 'loading')", name="pay_scheme"),)

    id: Mapped[str] = _id_column()
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_hi: Mapped[str | None] = mapped_column(String(80))
    pay_scheme: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)


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
    """A wage rate for one worker type and component, valid from `effective_from` onwards."""

    __tablename__ = "rates"
    __table_args__ = (
        UniqueConstraint("worker_type_id", "component", "effective_from"),
        CheckConstraint("component IN ('cutting', 'loading', 'unloading')", name="component"),
    )

    id: Mapped[str] = _id_column()
    worker_type_id: Mapped[str] = mapped_column(ForeignKey("worker_types.id", ondelete="RESTRICT"))
    component: Mapped[str] = mapped_column(String(20))
    rate_per_sqft: Mapped[Decimal] = mapped_column(DecimalText())
    effective_from: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)

    worker_type: Mapped[WorkerType] = relationship(lazy="joined")


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
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    length_ft: Mapped[Decimal] = mapped_column(DecimalText())
    width_ft: Mapped[Decimal] = mapped_column(DecimalText())
    cuts: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    worker: Mapped[Worker] = relationship(lazy="joined")
    worker_type: Mapped[WorkerType] = relationship(lazy="joined")

    @property
    def area_sqft(self) -> Decimal:
        return self.length_ft * self.width_ft * self.quantity


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
