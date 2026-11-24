"""Excel exports of wages and production, in English or Hindi.

Numbers are written as real numbers and dates as real dates (not text), so the
owner can sort, filter and add them up in Excel.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy.orm import Session

from ..models import Worker
from ..schemas import GroupBy, Language
from ..wages import Role, Unit, batti_of
from .production import piece_of, splitting_sqft
from .reports import pays_in_period, production_summary, wages_report
from .settings import get_settings

MONEY = "#,##0.00"
AREA = "#,##0.00"
DATE = "DD/MM/YYYY"

MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "hi": [
        "जनवरी",
        "फ़रवरी",
        "मार्च",
        "अप्रैल",
        "मई",
        "जून",
        "जुलाई",
        "अगस्त",
        "सितंबर",
        "अक्टूबर",
        "नवंबर",
        "दिसंबर",
    ],
}

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "wages": "Wages",
        "entries": "Entries",
        "production": "Production",
        "period": "Period",
        "grouped": "Grouped by",
        "day": "Day",
        "month": "Month",
        "year": "Year",
        "worker": "Worker",
        "type": "Work",
        "date": "Date",
        "length": "Length (ft)",
        "width": "Width (ft)",
        "cuts": "Cuts",
        "pieces": "Pieces",
        "area": "Area (sq ft)",
        "rates": "Rate (₹)",
        "wage": "Wages (₹)",
        "missing": "Entries without a rate",
        "notes": "Notes",
        "total": "Total",
        "rate_missing": "Rate not set",
        "cutting": "Cutting",
        "loading": "Loading",
        "unloading": "Unloading",
        "polish": "Polish ({n} batti)",
        "role": "Paid as",
        "operator": "Operator",
        "loader": "Loader",
        "machine": "Machine",
        "size": "Size",
        "batti": "Batti",
        "rft": "Running ft",
        "per_sqft": "/sq ft",
        "per_rft": "/running ft",
        "no_loader": "Entries with no loader at the machine",
        "shift": "Shift",
        "shifts": "Shifts",
        "day_shift": "Day",
        "night_shift": "Night",
        "per_shift": "/shift",
        "shift_worker": "Per shift",
        "cutting_sqft": "Machine man production (sq ft)",
        "unloading_sqft": "Unloading production (sq ft)",
    },
    "hi": {
        "wages": "मज़दूरी",
        "entries": "एंट्रियाँ",
        "production": "उत्पादन",
        "period": "अवधि",
        "grouped": "समूह",
        "day": "दिन",
        "month": "महीना",
        "year": "साल",
        "worker": "मज़दूर",
        "type": "काम",
        "date": "तारीख",
        "length": "लंबाई (फुट)",
        "width": "चौड़ाई (फुट)",
        "cuts": "कट",
        "pieces": "नग",
        "area": "क्षेत्रफल (वर्ग फुट)",
        "rates": "दर (₹)",
        "wage": "मज़दूरी (₹)",
        "missing": "बिना दर वाली एंट्रियाँ",
        "notes": "टिप्पणी",
        "total": "कुल",
        "rate_missing": "दर तय नहीं",
        "cutting": "कटिंग",
        "loading": "लोडिंग",
        "unloading": "अनलोडिंग",
        "polish": "पॉलिश ({n} बत्ती)",
        "role": "किस काम का",
        "operator": "ऑपरेटर",
        "loader": "लोडर",
        "machine": "मशीन",
        "size": "साइज़",
        "batti": "बत्ती",
        "rft": "रनिंग फुट",
        "per_sqft": "/वर्ग फुट",
        "per_rft": "/रनिंग फुट",
        "no_loader": "बिना लोडर वाली एंट्रियाँ",
        "shift": "शिफ़्ट",
        "shifts": "शिफ़्टें",
        "day_shift": "दिन",
        "night_shift": "रात",
        "per_shift": "/शिफ़्ट",
        "shift_worker": "शिफ़्ट पर",
        "cutting_sqft": "मशीन मैन उत्पादन (वर्ग फुट)",
        "unloading_sqft": "अनलोडिंग उत्पादन (वर्ग फुट)",
    },
}

HEADER_FILL = PatternFill("solid", fgColor="E9ECEF")
THIN = Side(style="thin", color="ADB5BD")
HEADER_BORDER = Border(bottom=THIN)
TOTAL_BORDER = Border(top=Side(style="medium", color="000000"))


def _name(en: str, hi: str | None, lang: str) -> str:
    return hi if lang == "hi" and hi else en


def component_label(component: str, lang: str) -> str:
    batti = batti_of(component)
    t = LABELS[lang]
    return t["polish"].format(n=batti) if batti else t.get(component, component)


def _size(e, lang: str) -> str:
    """How the entry's size is written: "2 × 1½ ft", "22½ × 22½ in"."""
    if e.size_label and e.length_ft is None:
        return f"{e.size_label} in"
    if e.size_label:
        return f"{e.size_label} ft"
    if e.length_ft is not None and e.width_ft is not None:
        return f"{format(e.length_ft.normalize(), 'f')} × {format(e.width_ft.normalize(), 'f')} ft"
    return ""


def _unit(unit: Unit, t: dict[str, str]) -> str:
    return {Unit.RFT: t["per_rft"], Unit.SHIFT: t["per_shift"]}.get(unit, t["per_sqft"])


def _fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _period_label(key: str, group_by: GroupBy, lang: str) -> str:
    if group_by == "day":
        return _fmt_date(date.fromisoformat(key))
    if group_by == "month":
        year, month = key.split("-")
        return f"{MONTHS[lang][int(month) - 1]} {year}"
    return key


def _title(ws: Worksheet, lines: list[str]) -> int:
    """Write the heading lines; return the row where the table starts."""
    for i, text in enumerate(lines, start=1):
        ws.cell(row=i, column=1, value=text).font = Font(bold=i == 1, size=14 if i == 1 else 11)
    return len(lines) + 2


def _text_safe(cell):
    """Typed text such as a name "=HYPERLINK(...)" must stay text, never become a formula."""
    if isinstance(cell.value, str) and cell.value.startswith("="):
        cell.data_type = "s"
    return cell


def _table(
    ws: Worksheet,
    start_row: int,
    headers: list[str],
    rows: list[list[Any]],
    formats: dict[int, str],
    total: list[Any] | None = None,
) -> None:
    for col, text in enumerate(headers, start=1):
        cell = _text_safe(ws.cell(row=start_row, column=col, value=text))
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.border = HEADER_BORDER
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for r, values in enumerate(rows, start=start_row + 1):
        for col, value in enumerate(values, start=1):
            cell = _text_safe(ws.cell(row=r, column=col, value=value))
            if col in formats:
                cell.number_format = formats[col]
    if total:
        r = start_row + len(rows) + 1
        for col, value in enumerate(total, start=1):
            cell = _text_safe(ws.cell(row=r, column=col, value=value))
            cell.font = Font(bold=True)
            cell.border = TOTAL_BORDER
            if col in formats:
                cell.number_format = formats[col]
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    # Size columns to their content (Excel has no auto-fit in the file format).
    for col in range(1, len(headers) + 1):
        letter = get_column_letter(col)
        longest = max(
            (len(str(c.value)) for c in ws[letter][start_row - 1 :] if c.value is not None),
            default=8,
        )
        ws.column_dimensions[letter].width = min(max(10, longest + 2), 45)


def _save(wb: Workbook) -> bytes:
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def wages_workbook(
    session: Session,
    start: date,
    end: date,
    lang: Language = "en",
    worker_ids: Sequence[str] | None = None,
    machine_id: str | None = None,
) -> bytes:
    """Sheet 1: wages per worker. Sheet 2: every wage earned, entry by entry."""
    t = LABELS[lang]
    settings = get_settings(session)
    factory = _name(settings.factory_name_en, settings.factory_name_hi, lang)
    period = f"{t['period']}: {_fmt_date(start)} – {_fmt_date(end)}"
    report = wages_report(session, start, end, worker_ids, machine_id=machine_id)

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = t["wages"]
    row = _title(ws, [factory, f"{t['wages']} · {period}"])
    _table(
        ws,
        row,
        [
            t["worker"],
            t["type"],
            t["entries"],
            t["pieces"],
            t["area"],
            t["rft"],
            t["cuts"],
            t["shifts"],
            t["wage"],
            t["missing"],
        ],
        [
            [
                _name(w.name_en, w.name_hi, lang),
                _name(w.worker_type_name_en, w.worker_type_name_hi, lang),
                w.entry_count,
                w.total_quantity,
                w.total_area_sqft,
                w.total_rft or None,
                w.total_cuts or None,
                w.total_shifts or None,
                w.total_wage,
                w.missing_rate_entries or None,
            ]
            for w in report.workers
        ],
        {5: AREA, 6: AREA, 9: MONEY},
        total=[
            t["total"],
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            report.total_wage,
            report.missing_rate_entries or None,
        ],
    )
    if report.no_loader_entries:
        r = ws.max_row + 2
        ws.cell(row=r, column=1, value=t["no_loader"])
        ws.cell(row=r, column=3, value=report.no_loader_entries)

    ws2 = wb.create_sheet(t["entries"])
    row = _title(ws2, [factory, f"{t['entries']} · {period}"])
    rows = []
    for e, pays, _ in pays_in_period(session, start, end, worker_ids, machine_id):
        for pay in pays:
            worker = (
                e.worker if pay.worker_id == e.worker_id else session.get(Worker, pay.worker_id)
            )
            rates = (
                "; ".join(
                    f"{component_label(line.component, lang)} {line.rate}{_unit(line.unit, t)}"
                    for line in pay.result.lines
                )
                if pay.result
                else t["rate_missing"]
            )
            cutting_sqft, unloading_sqft = splitting_sqft(e.machine.kind, piece_of(e))
            on_shift = e.shift is not None
            role = (
                t["shift_worker"]
                if on_shift
                else t["loader"]
                if pay.role is Role.LOADER
                else t["operator"]
            )
            rows.append(
                [
                    e.entry_date,
                    _name(worker.name_en, worker.name_hi, lang) if worker else "",
                    role,
                    _name(e.machine.name_en, e.machine.name_hi, lang),
                    _size(e, lang),
                    t[f"{e.shift}_shift"] if on_shift else None,
                    e.cuts or None,
                    e.batti,
                    None if on_shift else e.quantity,
                    None if on_shift else e.area_sqft,
                    cutting_sqft,
                    unloading_sqft,
                    e.rft_total,
                    rates,
                    pay.total,
                    e.notes,
                ]
            )
    _table(
        ws2,
        row,
        [
            t["date"],
            t["worker"],
            t["role"],
            t["machine"],
            t["size"],
            t["shift"],
            t["cuts"],
            t["batti"],
            t["pieces"],
            t["area"],
            t["cutting_sqft"],
            t["unloading_sqft"],
            t["rft"],
            t["rates"],
            t["wage"],
            t["notes"],
        ],
        rows,
        {1: DATE, 10: AREA, 11: AREA, 12: AREA, 13: AREA, 15: MONEY},
    )
    return _save(wb)


def production_workbook(
    session: Session,
    start: date,
    end: date,
    group_by: GroupBy = "month",
    lang: Language = "en",
    worker_ids: Sequence[str] | None = None,
    machine_id: str | None = None,
) -> bytes:
    """Production (and wages) per day, month or year."""
    t = LABELS[lang]
    settings = get_settings(session)
    factory = _name(settings.factory_name_en, settings.factory_name_hi, lang)
    summary = production_summary(session, start, end, group_by, worker_ids, machine_id)

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = t["production"]
    row = _title(
        ws,
        [
            factory,
            f"{t['production']} · {t['period']}: {_fmt_date(start)} – {_fmt_date(end)}",
            f"{t['grouped']}: {t[group_by]}",
        ],
    )
    total = summary.totals
    _table(
        ws,
        row,
        [
            t[group_by],
            t["entries"],
            t["pieces"],
            t["area"],
            t["rft"],
            t["cuts"],
            t["shifts"],
            t["wage"],
        ],
        [
            [
                _period_label(b.period, group_by, lang),
                b.entry_count,
                b.total_quantity,
                b.total_area_sqft,
                b.total_rft,
                b.total_cuts,
                b.total_shifts or None,
                b.total_wage,
            ]
            for b in summary.buckets
        ],
        {4: AREA, 5: AREA, 8: MONEY},
        total=[
            t["total"],
            total.entry_count,
            total.total_quantity,
            total.total_area_sqft,
            total.total_rft,
            total.total_cuts,
            total.total_shifts or None,
            total.total_wage,
        ],
    )
    return _save(wb)
