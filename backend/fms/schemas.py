"""Request/response shapes for the API (validated by pydantic).

Decimals are sent as JSON strings (e.g. "180.00") so no precision is lost.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .wages import MAX_BATTI, MachineKind, Role, Shift, Unit

Dimension = Annotated[Decimal, Field(gt=0, le=100, max_digits=7, decimal_places=3)]
SizeValue = Annotated[Decimal, Field(gt=0, le=1000, max_digits=8, decimal_places=3)]
Batti = Annotated[int, Field(ge=1, le=MAX_BATTI)]
Component = Annotated[str, Field(pattern=r"^[a-z_0-9]{1,20}$")]
RateValue = Annotated[Decimal, Field(ge=0, le=100000, max_digits=10, decimal_places=4)]
Cuts = Annotated[int, Field(ge=0, le=100)]
Quantity = Annotated[int, Field(ge=1, le=100000)]
Phone = Annotated[str, Field(pattern=r"^[0-9+\- ]{6,20}$")]
Notes = Annotated[str, Field(max_length=1000)]


class In(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- worker types
class WorkerTypeCreate(In):
    name_en: Annotated[str, Field(min_length=1, max_length=80)]
    name_hi: Annotated[str, Field(max_length=80)] | None = None
    role: Role


class WorkerTypeUpdate(In):
    # role is fixed once created: changing it would change how past entries are paid.
    name_en: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    name_hi: Annotated[str, Field(max_length=80)] | None = None
    is_active: bool | None = None


class WorkerTypeOut(Out):
    id: str
    code: str
    name_en: str
    name_hi: str | None
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime


# -------------------------------------------------------------------- machines
class MachineCreate(In):
    kind: MachineKind
    name_en: Annotated[str, Field(min_length=1, max_length=80)]
    name_hi: Annotated[str, Field(max_length=80)] | None = None


class MachineUpdate(In):
    name_en: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    name_hi: Annotated[str, Field(max_length=80)] | None = None
    is_active: bool | None = None


class MachineOut(Out):
    id: str
    code: str
    kind: MachineKind
    name_en: str
    name_hi: str | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MachineSizeCreate(In):
    id: UUID | None = None
    kind: MachineKind
    length: SizeValue
    width: SizeValue
    rft: SizeValue
    sqft: SizeValue


class MachineSizeUpdate(In):
    length: SizeValue | None = None
    width: SizeValue | None = None
    rft: SizeValue | None = None
    sqft: SizeValue | None = None


class MachineSizeOut(Out):
    id: str
    kind: MachineKind
    length: Decimal
    width: Decimal
    rft: Decimal
    sqft: Decimal
    created_at: datetime
    updated_at: datetime


class MachineDeleteImpact(BaseModel):
    machine_id: str
    production_entries: int  # a machine with entries can only be retired, not deleted


class LoaderAssignmentCreate(In):
    id: UUID | None = None
    machine_id: str
    worker_id: str | None  # None: no loader at this machine from this date
    effective_from: date
    note: Notes | None = None


class LoaderAssignmentUpdate(In):
    worker_id: str | None = None  # an explicit null means "no loader"
    effective_from: date | None = None
    note: Notes | None = None


class LoaderAssignmentOut(Out):
    id: str
    machine_id: str
    worker_id: str | None
    effective_from: date
    note: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------- workers
class WorkerCreate(In):
    # Set by the device that created the record (see services/_common.py: existing_replay).
    id: UUID | None = None
    name_en: Annotated[str, Field(min_length=1, max_length=120)]
    name_hi: Annotated[str, Field(max_length=120)] | None = None
    worker_type_id: str
    phone: Phone | None = None
    joined_on: date | None = None
    notes: Notes | None = None
    allow_duplicate_name: bool = False


class WorkerUpdate(In):
    name_en: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    name_hi: Annotated[str, Field(max_length=120)] | None = None
    worker_type_id: str | None = None
    phone: Phone | None = None
    joined_on: date | None = None
    notes: Notes | None = None
    allow_duplicate_name: bool = False


class WorkerOut(Out):
    id: str
    name_en: str
    name_hi: str | None
    worker_type_id: str
    worker_type: WorkerTypeOut
    phone: str | None
    joined_on: date | None
    notes: str | None
    archived_at: datetime | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class DeleteImpact(BaseModel):
    worker_id: str
    production_entries: int
    # Machines this worker is (or was) the loader at; those periods become "no loader".
    loader_assignments: int = 0


# ----------------------------------------------------------------------- rates
class RateCreate(In):
    # Set by the device that created the record (see services/_common.py: existing_replay).
    id: UUID | None = None
    kind: MachineKind
    component: Component
    rate: RateValue
    effective_from: date
    note: Notes | None = None


class RateUpdate(In):
    rate: RateValue | None = None
    effective_from: date | None = None
    note: Notes | None = None


class RateOut(Out):
    id: str
    kind: MachineKind
    component: str
    unit: Unit
    rate: Decimal
    effective_from: date
    note: str | None
    created_at: datetime
    updated_at: datetime


class CurrentRateOut(BaseModel):
    kind: MachineKind
    component: str
    unit: Unit
    rate: Decimal | None
    effective_from: date | None


# ------------------------------------------------------------------ production
class ProductionCreate(In):
    # Set by the device that created the record (see services/_common.py: existing_replay).
    id: UUID | None = None
    worker_id: str
    # Leaving it out means the original cutting machine (entries made before machines).
    machine_id: str | None = None
    entry_date: date
    length_ft: Dimension | None = None
    width_ft: Dimension | None = None
    size_id: str | None = None
    cuts: Cuts = 0
    batti: Batti | None = None
    # Block cutter: the shift worked. Its quantity is 1 (one shift).
    shift: Shift | None = None
    quantity: Quantity = 1
    # Someone filling in for the machine's usual loader on this entry only.
    loader_id: str | None = None
    notes: Notes | None = None


class ProductionUpdate(In):
    worker_id: str | None = None
    machine_id: str | None = None
    entry_date: date | None = None
    length_ft: Dimension | None = None
    width_ft: Dimension | None = None
    size_id: str | None = None
    cuts: Cuts | None = None
    batti: Batti | None = None
    shift: Shift | None = None
    quantity: Quantity | None = None
    loader_id: str | None = None
    notes: Notes | None = None


class WageLineOut(BaseModel):
    component: str
    basis: Decimal  # the sq ft or running ft the rate is multiplied by
    unit: Unit
    rate: Decimal
    amount: Decimal


class ProductionOut(Out):
    id: str
    worker_id: str
    worker_type_id: str
    machine_id: str
    entry_date: date
    length_ft: Decimal | None
    width_ft: Decimal | None
    size_id: str | None
    size_label: str | None
    piece_sqft: Decimal
    piece_rft: Decimal | None
    cuts: int
    batti: int | None
    shift: Shift | None = None
    quantity: int
    loader_id: str | None  # only when chosen on this entry
    notes: str | None
    area_sqft: Decimal
    rft_total: Decimal | None
    # Splitting machine: the sq ft the operator's cutting and the loader's unloading
    # are paid on (loading is paid on area_sqft).
    cutting_sqft: Decimal | None = None
    unloading_sqft: Decimal | None = None
    # The pay of `paid_worker_id` in the role `paid_as` (the operator, in entry lists).
    paid_as: Role = Role.OPERATOR
    paid_worker_id: str | None = None
    wage: Decimal | None = None
    wage_lines: list[WageLineOut] = []
    missing_rates: list[str] = []
    # The loader paid from this entry (the machine's loader on that date, or loader_id).
    loader_worker_id: str | None = None
    loader_wage: Decimal | None = None
    loader_wage_lines: list[WageLineOut] = []
    loader_missing_rates: list[str] = []
    no_loader: bool = False
    created_at: datetime
    updated_at: datetime


class ProductionPage(BaseModel):
    total: int
    items: list[ProductionOut]


class WagePreviewIn(In):
    worker_id: str
    machine_id: str | None = None
    entry_date: date
    length_ft: Dimension | None = None
    width_ft: Dimension | None = None
    size_id: str | None = None
    cuts: Cuts = 0
    batti: Batti | None = None
    shift: Shift | None = None
    quantity: Quantity = 1
    loader_id: str | None = None


class WagePreviewOut(BaseModel):
    area_sqft: Decimal
    rft_total: Decimal | None
    cutting_sqft: Decimal | None = None
    unloading_sqft: Decimal | None = None
    piece_sqft: Decimal
    piece_rft: Decimal | None
    wage: Decimal | None
    wage_lines: list[WageLineOut]
    missing_rates: list[str]
    loader_worker_id: str | None
    loader_wage: Decimal | None
    loader_wage_lines: list[WageLineOut]
    loader_missing_rates: list[str]
    no_loader: bool


# -------------------------------------------------------------------- settings
Language = Literal["en", "hi"]
PayPeriod = Literal["half_month", "month"]


class AppSettingsOut(BaseModel):
    """Owner preferences. Every key has a default, so a fresh install works immediately."""

    factory_name_en: str = "Kota Stone Factory"
    factory_name_hi: str = "कोटा स्टोन फैक्ट्री"
    factory_address: str = ""
    ui_language: Language = "en"
    print_language: Language = "hi"
    pay_period: PayPeriod = "half_month"
    phone_url: str = ""  # optional override of the detected Tailscale address
    backup_copy_dir: str = ""  # optional second folder for backups (USB drive, Drive folder)


class AppSettingsUpdate(In):
    factory_name_en: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    factory_name_hi: Annotated[str, Field(max_length=120)] | None = None
    factory_address: Annotated[str, Field(max_length=300)] | None = None
    ui_language: Language | None = None
    print_language: Language | None = None
    pay_period: PayPeriod | None = None
    phone_url: Annotated[str, Field(max_length=200, pattern=r"^(https?://\S+)?$")] | None = None
    backup_copy_dir: Annotated[str, Field(max_length=500)] | None = None


# --------------------------------------------------------------------- reports
class WorkerWagesOut(BaseModel):
    worker_id: str
    name_en: str
    name_hi: str | None
    worker_type_name_en: str
    worker_type_name_hi: str | None
    role: Role
    is_archived: bool
    entry_count: int
    total_quantity: int
    total_area_sqft: Decimal
    total_rft: Decimal
    total_cuts: int
    total_shifts: int = 0  # block cutter shifts worked
    total_wage: Decimal
    missing_rate_entries: int
    entries: list[ProductionOut] | None = None


class WagesReportOut(BaseModel):
    start: date
    end: date
    workers: list[WorkerWagesOut]
    total_wage: Decimal
    total_area_sqft: Decimal
    missing_rate_entries: int
    # Entries whose machine had no loader on that date (nobody was paid for loading).
    no_loader_entries: int = 0


GroupBy = Literal["day", "month", "year"]


class ProductionBucketOut(BaseModel):
    period: str
    entry_count: int
    total_quantity: int
    total_area_sqft: Decimal
    total_rft: Decimal
    total_cuts: int
    total_shifts: int = 0  # block cutter shifts worked
    total_wage: Decimal
    missing_rate_entries: int


class ProductionSummaryOut(BaseModel):
    start: date
    end: date
    group_by: GroupBy
    buckets: list[ProductionBucketOut]
    totals: ProductionBucketOut


# ------------------------------------------------------------------------ auth
Password = Annotated[str, Field(min_length=1, max_length=200)]
DeviceName = Annotated[str, Field(min_length=1, max_length=80)]


class SetupIn(In):
    password: Password
    device_name: DeviceName


class LoginIn(In):
    password: Password
    device_name: DeviceName


class PasswordChangeIn(In):
    current_password: Password
    new_password: Password
    sign_out_other_devices: bool = False


class DeviceOut(Out):
    id: str
    name: str
    created_at: datetime
    last_seen_at: datetime
    current: bool = False


class LoginOut(BaseModel):
    token: str
    device: DeviceOut


class AuthStatusOut(BaseModel):
    setup_required: bool
    logged_in: bool
    device: DeviceOut | None = None


# --------------------------------------------------------------------- backups
class BackupOut(BaseModel):
    name: str
    size: int
    created_at: datetime
    kind: str


class BackupStatusOut(BaseModel):
    backups: list[BackupOut]
    last_backup_at: datetime | None
    copy_dir: str
    copy_dir_ok: bool | None  # None when no extra folder is set
    last_error: str | None
