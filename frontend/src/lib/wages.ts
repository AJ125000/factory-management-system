/**
 * Wage formulas on the device — an exact port of backend/fms/wages.py (and the piece
 * rules in services/production.py), used for the live wage preview while the laptop
 * can't be reached. The server stays the source of truth; shared/wage-cases.json is
 * checked by BOTH test suites so they never drift.
 *
 * JavaScript numbers are binary floats (0.1 + 0.2 !== 0.3), so money is computed with
 * BigInt fixed-point decimals instead.
 */

import type {
  LoaderAssignment,
  MachineKind,
  MachineSize,
  Rate,
  RateComponent,
  Role,
  Unit,
} from '../api/types';

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

function add(a: Dec, b: Dec): Dec {
  const scale = Math.max(a.scale, b.scale);
  const up = (x: Dec) => x.units * 10n ** BigInt(scale - x.scale);
  return { units: up(a) + up(b), scale };
}

function same(a: Dec, b: Dec): boolean {
  const scale = Math.max(a.scale, b.scale);
  const up = (x: Dec) => x.units * 10n ** BigInt(scale - x.scale);
  return up(a) === up(b);
}

/** Exact decimal as a plain string without trailing zeros: "30", "3.984375". */
function str(a: Dec): string {
  const negative = a.units < 0n;
  const abs = negative ? -a.units : a.units;
  const s = abs.toString().padStart(a.scale + 1, '0');
  const whole = a.scale ? s.slice(0, -a.scale) : s;
  const frac = a.scale ? s.slice(-a.scale).replace(/0+$/, '') : '';
  return `${negative ? '-' : ''}${whole}${frac ? `.${frac}` : ''}`;
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

// ------------------------------------------------------------------ components
export const MAX_BATTI = 9;
export const polishComponent = (batti: number) => `polish_${batti}`;

export function battiOf(component: string): number | null {
  const m = /^polish_([1-9])$/.exec(component);
  return m ? Number(m[1]) : null;
}

/** Every rate a machine of this kind can have (table polish: one per batti count). */
export function allowedComponents(kind: MachineKind): RateComponent[] {
  if (kind === 'block_cutting') return ['cutting', 'loading', 'unloading'];
  if (kind === 'table_polish') {
    return [...Array.from({ length: MAX_BATTI }, (_, i) => polishComponent(i + 1)), 'unloading'];
  }
  return ['cutting', 'unloading'];
}

export function componentUnit(kind: MachineKind, component: RateComponent): Unit {
  return component === 'cutting' && (kind === 'double_edge' || kind === 'single_cutting')
    ? 'rft'
    : 'sqft';
}

export const usesSizeTable = (kind: MachineKind) =>
  kind === 'double_edge' || kind === 'single_cutting';

/** Which rates pay the operator, and which the loader, on this kind of machine. */
export function roleComponents(kind: MachineKind, role: Role): RateComponent[] {
  if (role === 'loader') return kind === 'block_cutting' ? ['loading', 'unloading'] : ['unloading'];
  if (kind === 'table_polish') return allowedComponents(kind).filter((c) => battiOf(c) !== null);
  return ['cutting'];
}

// ------------------------------------------------------------------------ wages
export interface PieceInput {
  piece_sqft: string;
  piece_rft: string | null;
  cuts: number;
  quantity: number;
  batti: number | null;
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

function bases(kind: MachineKind, role: Role, p: PieceInput): [RateComponent, Dec][] {
  const sqft = dec(p.piece_sqft);
  const qty = p.quantity;
  if (kind === 'block_cutting') {
    if (role === 'operator') return [['cutting', times(times(times(sqft, 2), p.cuts), qty)]];
    return [
      ['loading', times(sqft, qty)],
      ['unloading', times(times(sqft, 1 + p.cuts), qty)],
    ];
  }
  if (role === 'loader') return [['unloading', times(sqft, qty)]];
  if (kind === 'table_polish') {
    if (p.batti == null) return [];
    return [[polishComponent(p.batti), times(sqft, qty)]];
  }
  if (p.piece_rft == null) return [];
  return [['cutting', times(dec(p.piece_rft), qty)]];
}

export function calculateWage(
  kind: MachineKind,
  role: Role,
  piece: PieceInput,
  rates: Partial<Record<RateComponent, string | null>>,
): WageResult {
  const needed = bases(kind, role, piece);
  const missing = needed.map(([c]) => c).filter((c) => rates[c] == null);
  if (missing.length) return { lines: [], total: null, missing };
  let total = 0n;
  const lines = needed.map(([component, basis]) => {
    const paise = toPaise(mul(basis, dec(rates[component]!)));
    total += paise;
    return { component, amount: paiseToString(paise) };
  });
  return { lines, total: paiseToString(total), missing: [] };
}

/** The rate in effect on a date for a machine type (same rule as the hub's RateBook). */
export function rateOn(
  rates: Rate[],
  kind: MachineKind,
  component: RateComponent,
  date: string,
): string | null {
  let best: Rate | null = null;
  for (const r of rates) {
    if (r.kind !== kind || r.component !== component) continue;
    if (r.effective_from > date) continue; // ISO dates compare correctly as strings
    if (!best || r.effective_from > best.effective_from) best = r;
  }
  return best ? best.rate : null;
}

export function ratesFor(
  rates: Rate[],
  kind: MachineKind,
  role: Role,
  date: string,
): Partial<Record<RateComponent, string | null>> {
  return Object.fromEntries(roleComponents(kind, role).map((c) => [c, rateOn(rates, kind, c, date)]));
}

/** The loader at a machine on a date (same rule as the hub's LoaderBook). */
export function loaderOn(
  assignments: LoaderAssignment[],
  machineId: string,
  date: string,
): string | null {
  let best: LoaderAssignment | null = null;
  for (const a of assignments) {
    if (a.machine_id !== machineId || a.effective_from > date) continue;
    if (!best || a.effective_from > best.effective_from) best = a;
  }
  return best ? best.worker_id : null;
}

// ----------------------------------------------------------------------- pieces
export interface Piece {
  piece_sqft: string;
  piece_rft: string | null;
  size: MachineSize | null;
}

/** The type's table size with these measurements, either way round. */
export function findSize(
  sizes: MachineSize[],
  kind: MachineKind,
  length: string,
  width: string,
): MachineSize | null {
  const l = dec(length);
  const w = dec(width);
  return (
    sizes.find(
      (s) =>
        s.kind === kind &&
        ((same(dec(s.length), l) && same(dec(s.width), w)) ||
          (same(dec(s.length), w) && same(dec(s.width), l))),
    ) ?? null
  );
}

/**
 * What one piece counts for: the size table's figures for sizes in the table ("market
 * standard"), otherwise the true area and perimeter. Null if something is missing.
 */
export function resolvePiece(
  kind: MachineKind,
  sizes: MachineSize[],
  input: { length_ft: string | null; width_ft: string | null; size_id: string | null },
): Piece | null {
  if (kind === 'single_cutting') {
    const size = sizes.find((s) => s.id === input.size_id && s.kind === kind);
    return size ? { piece_sqft: size.sqft, piece_rft: size.rft, size } : null;
  }
  if (!input.length_ft || !input.width_ft) return null;
  const l = dec(input.length_ft);
  const w = dec(input.width_ft);
  if (kind === 'double_edge') {
    const size = findSize(sizes, kind, input.length_ft, input.width_ft);
    if (size) return { piece_sqft: size.sqft, piece_rft: size.rft, size };
    return { piece_sqft: str(mul(l, w)), piece_rft: str(times(add(l, w), 2)), size: null };
  }
  return { piece_sqft: str(mul(l, w)), piece_rft: null, size: null };
}

/** "2" -> "2", "1.5" -> "1½", "22.5" -> "22½" (same as the hub's size labels). */
export function fraction(value: string): string {
  const s = str(dec(value));
  if (s.endsWith('.5')) {
    const whole = s.slice(0, -2);
    return `${whole === '0' ? '' : whole}½`;
  }
  return s;
}

export const sizeLabel = (length: string, width: string) =>
  `${fraction(length)} × ${fraction(width)}`;

/** Total sq ft or running ft as a plain string, e.g. "30" or "3.984375". */
export function totalOf(perPiece: string, quantity: number): string {
  return str(times(dec(perPiece), quantity));
}
