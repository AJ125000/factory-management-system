import dayjs from 'dayjs';

const rupees = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const plain = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 });

const rateFormat = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

/** Rates can have up to 4 decimals (₹1.125/sq ft) — never round them to paise for display. */
export function formatRate(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return rateFormat.format(Number(value));
}

/** "123456.5" -> "₹1,23,456.50" (Indian digit grouping). Works on decimal strings. */
export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return rupees.format(Number(value));
}

const amount = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Money without the ₹ sign, for table columns whose heading already says ₹. */
export function formatAmount(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return amount.format(Number(value));
}

/** "45.00" -> "45", "12.345" -> "12.35" */
export function formatNumber(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return plain.format(Number(value));
}

/** Show a stored measurement without trailing zeros: "2.500" -> "2.5" */
export function formatFeet(value: string): string {
  return String(Number(value));
}

export function formatDate(iso: string | null | undefined, style: 'short' | 'long' = 'long'): string {
  if (!iso) return '—';
  return dayjs(iso).format(style === 'short' ? 'DD/MM/YYYY' : 'D MMM YYYY');
}

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

function isoIfValid(year: number, month: number, day: number): string | null {
  const d = dayjs(new Date(year, month - 1, day));
  // Reject impossible dates like 31/02 (JS would silently roll them into March).
  if (d.year() !== year || d.month() !== month - 1 || d.date() !== day) return null;
  return d.format('YYYY-MM-DD');
}

/**
 * Parse a typed date the way people in India write it: DAY first.
 * Accepts 5/11/2026, 05-11-26, 5.11.2026, "5 Nov 2026", and 2026-11-05.
 * (The browser's default parser would read 05/11/2026 as 11 May.)
 */
export function parseTypedDate(input: string): string | null {
  const s = input.trim().toLowerCase();
  let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) return isoIfValid(+m[1], +m[2], +m[3]);
  m = s.match(/^(\d{1,2})[/.\-\s](\d{1,2})[/.\-\s](\d{2}|\d{4})$/);
  if (m) return isoIfValid(m[3].length === 2 ? 2000 + +m[3] : +m[3], +m[2], +m[1]);
  m = s.match(/^(\d{1,2})\s+([a-z]{3,})\.?,?\s+(\d{4})$/);
  if (m) {
    const month = MONTHS.indexOf(m[2].slice(0, 3)) + 1;
    return month ? isoIfValid(+m[3], month, +m[1]) : null;
  }
  return null;
}

/** Format used in every date input box (matches what parseTypedDate reads). */
export const DATE_INPUT_FORMAT = 'DD/MM/YYYY';

export function todayISO(): string {
  return dayjs().format('YYYY-MM-DD');
}
