/**
 * Wage formulas on the device — an exact port of backend/fms/wages.py, used for the
 * live wage preview while the laptop can't be reached. The server stays the source
 * of truth; shared/wage-cases.json is checked by BOTH test suites so they never drift.
 *
 * JavaScript numbers are binary floats (0.1 + 0.2 !== 0.3), so money is computed with
 * BigInt fixed-point decimals instead.
 */

import type { PayScheme, Rate, RateComponent } from '../api/types';

/** An exact decimal: value = units / 10^scale. */
interface Dec {
  units: bigint;
  scale: number;
}

function dec(text: string | number): Dec {
  const s = String(text).trim();
  if (!/^-?\d+(\.\d+)?$/.test(s)) throw new Error(`Not a decimal number: ${s}`);
  const [whole, frac = ''] = s.split('.');
  return { units: BigInt(whole + frac), scale: frac.length };
}

function mul(a: Dec, b: Dec): Dec {
  return { units: a.units * b.units, scale: a.scale + b.scale };
}

function times(a: Dec, n: number): Dec {
  return { units: a.units * BigInt(n), scale: a.scale };
}

/** Round to the paisa, half away from zero (matches Python's ROUND_HALF_UP). */
function toPaise(a: Dec): bigint {
  if (a.scale <= 2) return a.units * 10n ** BigInt(2 - a.scale);
  const divisor = 10n ** BigInt(a.scale - 2);
  const negative = a.units < 0n;
  const abs = negative ? -a.units : a.units;
  let q = abs / divisor;
  if ((abs % divisor) * 2n >= divisor) q += 1n;
  return negative ? -q : q;
}

/** 18000n paise -> "180.00" */
export function paiseToString(paise: bigint): string {
  const negative = paise < 0n;
  const abs = negative ? -paise : paise;
  const rupees = abs / 100n;
  const rest = (abs % 100n).toString().padStart(2, '0');
  return `${negative ? '-' : ''}${rupees}.${rest}`;
}

export const SCHEME_COMPONENTS: Record<PayScheme, RateComponent[]> = {
  cutting: ['cutting'],
  loading: ['loading', 'unloading'],
};

export interface StoneInput {
  length_ft: string;
  width_ft: string;
  cuts: number;
  quantity: number;
}

export interface WageLineResult {
  component: RateComponent;
  amount: string; // "180.00"
}

export interface WageResult {
  lines: WageLineResult[];
  total: string | null;
  missing: RateComponent[];
}

function effectiveAreas(scheme: PayScheme, s: StoneInput): [RateComponent, Dec][] {
  const area = mul(dec(s.length_ft), dec(s.width_ft));
  if (scheme === 'cutting') {
    return [['cutting', times(times(times(area, 2), s.cuts), s.quantity)]];
  }
  return [
    ['loading', times(area, s.quantity)],
    ['unloading', times(times(area, 1 + s.cuts), s.quantity)],
  ];
}

export function calculateWage(
  scheme: PayScheme,
  stone: StoneInput,
  rates: Partial<Record<RateComponent, string | null>>,
): WageResult {
  const areas = effectiveAreas(scheme, stone);
  const missing = areas.map(([c]) => c).filter((c) => rates[c] == null);
  if (missing.length) return { lines: [], total: null, missing };
  let total = 0n;
  const lines = areas.map(([component, area]) => {
    const paise = toPaise(mul(area, dec(rates[component]!)));
    total += paise;
    return { component, amount: paiseToString(paise) };
  });
  return { lines, total: paiseToString(total), missing: [] };
}

/** The rate in effect on a date for a worker type (same rule as the hub's RateBook). */
export function rateOn(
  rates: Rate[],
  workerTypeId: string,
  component: RateComponent,
  date: string,
): string | null {
  let best: Rate | null = null;
  for (const r of rates) {
    if (r.worker_type_id !== workerTypeId || r.component !== component) continue;
    if (r.effective_from > date) continue; // ISO dates compare correctly as strings
    if (!best || r.effective_from > best.effective_from) best = r;
  }
  return best ? best.rate_per_sqft : null;
}

export function ratesFor(
  rates: Rate[],
  workerTypeId: string,
  scheme: PayScheme,
  date: string,
): Partial<Record<RateComponent, string | null>> {
  return Object.fromEntries(
    SCHEME_COMPONENTS[scheme].map((c) => [c, rateOn(rates, workerTypeId, c, date)]),
  );
}

/** Area in sq ft as a plain string, e.g. "30" or "3.984375". */
export function totalArea(stone: StoneInput): string {
  const a = times(mul(dec(stone.length_ft), dec(stone.width_ft)), stone.quantity);
  const s = a.units.toString().padStart(a.scale + 1, '0');
  const whole = a.scale ? s.slice(0, -a.scale) : s;
  const frac = a.scale ? s.slice(-a.scale).replace(/0+$/, '') : '';
  return frac ? `${whole}.${frac}` : whole;
}
