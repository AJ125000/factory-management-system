"""Request/response shapes for the API (validated by pydantic).

Decimals are sent as JSON strings (e.g. "180.00") so no precision is lost.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .wages import PayScheme, RateComponent

Dimension = Annotated[Decimal, Field(gt=0, le=100, max_digits=7, decimal_places=3)]
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
    pay_scheme: PayScheme


class WorkerTypeUpdate(In):
    # pay_scheme is fixed once created: changing it would invalidate existing rates.
    name_en: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    name_hi: Annotated[str, Field(max_length=80)] | None = None
    is_active: bool | None = None


class WorkerTypeOut(Out):
    id: str
    code: str
    name_en: str
    name_hi: str | None
    pay_scheme: PayScheme
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------- workers
class WorkerCreate(In):
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


# ----------------------------------------------------------------------- rates
class RateCreate(In):
    worker_type_id: str
    component: RateComponent
    rate_per_sqft: RateValue
    effective_from: date
    note: Notes | None = None


class RateUpdate(In):
    rate_per_sqft: RateValue | None = None
    effective_from: date | None = None
    note: Notes | None = None


class RateOut(Out):
    id: str
    worker_type_id: str
    component: RateComponent
    rate_per_sqft: Decimal
    effective_from: date
    note: str | None
    created_at: datetime
    updated_at: datetime


class CurrentRateOut(BaseModel):
    worker_type_id: str
    component: RateComponent
    rate_per_sqft: Decimal | None
    effective_from: date | None


# ------------------------------------------------------------------ production
class ProductionCreate(In):
    worker_id: str
    entry_date: date
    length_ft: Dimension
    width_ft: Dimension
    cuts: Cuts
    quantity: Quantity
    notes: Notes | None = None


class ProductionUpdate(In):
    worker_id: str | None = None
    entry_date: date | None = None
    length_ft: Dimension | None = None
    width_ft: Dimension | None = None
    cuts: Cuts | None = None
    quantity: Quantity | None = None
    notes: Notes | None = None


class WageLineOut(BaseModel):
    component: RateComponent
    effective_area_sqft: Decimal
    rate_per_sqft: Decimal
    amount: Decimal


class ProductionOut(Out):
    id: str
    worker_id: str
    worker_type_id: str
    entry_date: date
    length_ft: Decimal
    width_ft: Decimal
    cuts: int
    quantity: int
    notes: str | None
    area_sqft: Decimal
    wage: Decimal | None = None
    wage_lines: list[WageLineOut] = []
    missing_rates: list[RateComponent] = []
    created_at: datetime
    updated_at: datetime


class ProductionPage(BaseModel):
    total: int
    items: list[ProductionOut]


class WagePreviewIn(In):
    worker_id: str
    entry_date: date
    length_ft: Dimension
    width_ft: Dimension
    cuts: Cuts
    quantity: Quantity


class WagePreviewOut(BaseModel):
    area_sqft: Decimal
    wage: Decimal | None
    wage_lines: list[WageLineOut]
    missing_rates: list[RateComponent]


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


class AppSettingsUpdate(In):
    factory_name_en: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    factory_name_hi: Annotated[str, Field(max_length=120)] | None = None
    factory_address: Annotated[str, Field(max_length=300)] | None = None
    ui_language: Language | None = None
    print_language: Language | None = None
    pay_period: PayPeriod | None = None


# --------------------------------------------------------------------- reports
class WorkerWagesOut(BaseModel):
    worker_id: str
    name_en: str
    name_hi: str | None
    worker_type_name_en: str
    worker_type_name_hi: str | None
    is_archived: bool
    entry_count: int
    total_quantity: int
    total_area_sqft: Decimal
    total_cuts: int
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


GroupBy = Literal["day", "month", "year"]


class ProductionBucketOut(BaseModel):
    period: str
    entry_count: int
    total_quantity: int
    total_area_sqft: Decimal
    total_cuts: int
    total_wage: Decimal
    missing_rate_entries: int


class ProductionSummaryOut(BaseModel):
    start: date
    end: date
    group_by: GroupBy
    buckets: list[ProductionBucketOut]
    totals: ProductionBucketOut
