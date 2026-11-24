/**
 * Production entries as this device works them out, for changes that haven't reached the
 * laptop yet. Same formulas as the hub (lib/wages.ts); the hub's figures replace these
 * as soon as the change is sent.
 */

import type {
  LoaderAssignment,
  Machine,
  MachineSize,
  ProductionEntry,
  ProductionInput,
  Rate,
  Role,
  WageLine,
  Worker,
  WorkerWages,
} from '../api/types';
import type { OutboxItem } from './outbox';
import {
  calculateWage,
  isShiftPaid,
  loaderOn,
  paiseToString,
  ratesFor,
  resolvePiece,
  sizeLabel,
  splittingSqft,
  totalOf,
  type WageResult,
} from './wages';

export interface LocalData {
  machines: Machine[];
  sizes: MachineSize[];
  rates: Rate[];
  assignments: LoaderAssignment[];
}

/** An entry made on this device and not yet on the laptop: shown with a "Not sent yet" tag. */
export type LocalEntry = ProductionEntry & { pending: true };

const lines = (r: WageResult): WageLine[] =>
  r.lines.map((l) => ({
    component: l.component,
    basis: l.basis,
    unit: l.unit,
    rate: l.rate,
    amount: l.amount,
  }));

/** The entry the hub would save for this input, with its wages; null if it's incomplete. */
export function localEntry(
  id: string,
  input: ProductionInput,
  workerTypeId: string,
  data: LocalData,
): LocalEntry | null {
  const machine = data.machines.find((m) => m.id === input.machine_id);
  if (!machine) return null;
  const shiftPaid = isShiftPaid(machine.kind);
  if (shiftPaid && !input.shift) return null;
  const piece = shiftPaid
    ? { piece_sqft: '0', piece_rft: null, size: null }
    : resolvePiece(machine.kind, data.sizes, input);
  if (!piece) return null;
  const quantity = shiftPaid ? 1 : input.quantity;
  const cuts = machine.kind === 'block_cutting' ? input.cuts : 0;
  const batti = machine.kind === 'table_polish' ? input.batti : null;
  const p = { ...piece, cuts, quantity, batti };
  const date = input.entry_date;
  const op = calculateWage(machine.kind, 'operator', p, ratesFor(data.rates, machine.kind, 'operator', date));
  const ld = shiftPaid
    ? null
    : calculateWage(machine.kind, 'loader', p, ratesFor(data.rates, machine.kind, 'loader', date));
  const loaderId = shiftPaid ? null : (input.loader_id ?? loaderOn(data.assignments, machine.id, date));
  const split = splittingSqft(machine.kind, p);
  const size = piece.size;
  const dims = shiftPaid || machine.kind === 'single_cutting';
  return {
    pending: true,
    id,
    worker_id: input.worker_id,
    worker_type_id: workerTypeId,
    machine_id: machine.id,
    entry_date: date,
    length_ft: dims ? null : size ? size.length : input.length_ft,
    width_ft: dims ? null : size ? size.width : input.width_ft,
    size_id: size?.id ?? null,
    size_label: size
      ? sizeLabel(size.length, size.width)
      : machine.kind === 'double_edge' && input.length_ft && input.width_ft
        ? sizeLabel(input.length_ft, input.width_ft)
        : null,
    piece_sqft: piece.piece_sqft,
    piece_rft: piece.piece_rft,
    cuts,
    batti,
    shift: shiftPaid ? input.shift : null,
    quantity,
    loader_id: shiftPaid ? null : input.loader_id,
    notes: input.notes ?? null,
    area_sqft: totalOf(piece.piece_sqft, quantity),
    rft_total: piece.piece_rft === null ? null : totalOf(piece.piece_rft, quantity),
    cutting_sqft: split?.cutting ?? null,
    unloading_sqft: split?.unloading ?? null,
    paid_as: 'operator',
    paid_worker_id: input.worker_id,
    wage: op.total,
    wage_lines: lines(op),
    missing_rates: op.missing,
    loader_worker_id: loaderId,
    loader_wage: ld ? ld.total : null,
    loader_wage_lines: ld ? lines(ld) : [],
    loader_missing_rates: ld ? ld.missing : [],
    no_loader: !shiftPaid && loaderId === null,
  };
}

/** What the waiting changes do to the production list. */
export interface PendingProduction {
  created: LocalEntry[]; // new entries not on the laptop yet
  edited: Map<string, LocalEntry>; // hub entries with an edit waiting
  deleted: Set<string>; // hub entries with a delete waiting
}

export function pendingProduction(
  outbox: OutboxItem[],
  workers: Worker[],
  data: LocalData,
  server: ProductionEntry[] = [],
): PendingProduction {
  const typeOf = (workerId: string) =>
    workers.find((w) => w.id === workerId)?.worker_type_id ?? '';
  const out: PendingProduction = { created: [], edited: new Map(), deleted: new Set() };
  for (const item of outbox) {
    if (item.entity !== 'production') continue;
    if (item.action === 'delete') {
      out.deleted.add(item.entityId);
      out.edited.delete(item.entityId);
      continue;
    }
    const body = item.body as Partial<ProductionInput> | undefined;
    if (!body) continue;
    const base = server.find((e) => e.id === item.entityId);
    const input: ProductionInput = base
      ? {
          worker_id: base.worker_id,
          machine_id: base.machine_id,
          entry_date: base.entry_date,
          length_ft: base.length_ft,
          width_ft: base.width_ft,
          size_id: base.size_id,
          cuts: base.cuts,
          batti: base.batti,
          shift: base.shift,
          quantity: base.quantity,
          loader_id: base.loader_id,
          notes: base.notes,
          ...body,
        }
      : (body as ProductionInput);
    const entry = localEntry(item.entityId, input, typeOf(input.worker_id), data);
    if (!entry) continue;
    if (item.action === 'create') {
      const i = out.created.findIndex((e) => e.id === entry.id);
      if (i >= 0) out.created[i] = entry;
      else out.created.push(entry);
    } else {
      out.edited.set(item.entityId, entry);
    }
  }
  return out;
}

/** A pending entry seen by one worker: the operator's pay or the loader's. */
function payOf(e: LocalEntry, role: Role): LocalEntry {
  if (role === 'operator') return e;
  return {
    ...e,
    paid_as: 'loader',
    paid_worker_id: e.loader_worker_id,
    wage: e.loader_wage,
    wage_lines: e.loader_wage_lines,
    missing_rates: e.loader_missing_rates,
  };
}

function addPaise(a: string, b: string | null): string {
  if (b === null) return a;
  const p = (x: string) => BigInt(x.replace('.', ''));
  return paiseToString(p(a) + p(b));
}

/**
 * The wages report with this device's waiting changes added: new entries are added to
 * the worker's totals, deleted ones taken out, edited ones swapped for the new figures.
 * Rows and entries that changed carry `pending` so the screen can say so.
 */
export function withPendingWages(
  workers: (WorkerWages & { pending?: boolean })[],
  pending: PendingProduction,
  start: string,
  end: string,
  people: Worker[],
): (WorkerWages & { pending?: boolean })[] {
  const inPeriod = (e: ProductionEntry) => e.entry_date >= start && e.entry_date <= end;
  const rows = new Map(
    workers.map((w) => [w.worker_id, { ...w, entries: [...(w.entries ?? [])] }]),
  );
  const changed = new Set<string>();

  const drop = (entryId: string) => {
    for (const row of rows.values()) {
      const kept = row.entries.filter((e) => {
        if (e.id !== entryId) return true;
        row.entry_count -= 1;
        if (e.shift) row.total_shifts -= 1;
        else row.total_quantity -= e.quantity;
        row.total_area_sqft = minus(row.total_area_sqft, e.area_sqft);
        if (e.paid_as === 'operator' && e.rft_total) row.total_rft = minus(row.total_rft, e.rft_total);
        row.total_cuts -= e.cuts * e.quantity;
        if (e.wage === null) row.missing_rate_entries -= 1;
        else row.total_wage = addPaise(row.total_wage, `-${e.wage}`);
        changed.add(row.worker_id);
        return false;
      });
      row.entries = kept;
    }
  };
  const add = (e: LocalEntry, role: Role) => {
    const workerId = role === 'operator' ? e.worker_id : e.loader_worker_id;
    if (!workerId) return;
    let row = rows.get(workerId);
    if (!row) {
      const w = people.find((x) => x.id === workerId);
      if (!w) return;
      row = {
        worker_id: w.id,
        name_en: w.name_en,
        name_hi: w.name_hi,
        worker_type_name_en: w.worker_type.name_en,
        worker_type_name_hi: w.worker_type.name_hi,
        role: w.worker_type.role,
        is_archived: w.is_archived,
        entry_count: 0,
        total_quantity: 0,
        total_area_sqft: '0',
        total_rft: '0',
        total_cuts: 0,
        total_shifts: 0,
        total_wage: '0.00',
        missing_rate_entries: 0,
        entries: [],
      };
      rows.set(workerId, row);
    }
    const paid = payOf(e, role);
    row.entries.push(paid);
    row.entry_count += 1;
    if (e.shift) row.total_shifts += 1;
    else row.total_quantity += e.quantity;
    row.total_area_sqft = plus(row.total_area_sqft, e.area_sqft);
    if (role === 'operator' && e.rft_total) row.total_rft = plus(row.total_rft, e.rft_total);
    row.total_cuts += e.cuts * e.quantity;
    if (paid.wage === null) row.missing_rate_entries += 1;
    else row.total_wage = addPaise(row.total_wage, paid.wage);
    changed.add(workerId);
  };

  for (const id of pending.deleted) drop(id);
  for (const [id, e] of pending.edited) {
    drop(id);
    if (inPeriod(e)) {
      add(e, 'operator');
      add(e, 'loader');
    }
  }
  for (const e of pending.created) {
    if (!inPeriod(e)) continue;
    add(e, 'operator');
    add(e, 'loader');
  }

  return [...rows.values()]
    .filter((r) => r.entry_count > 0)
    .map((r) => {
      r.entries.sort((a, b) => a.entry_date.localeCompare(b.entry_date));
      return changed.has(r.worker_id) ? { ...r, pending: true } : r;
    })
    .sort((a, b) => a.name_en.toLowerCase().localeCompare(b.name_en.toLowerCase()));
}

// Areas are exact decimals; keep them as strings without float error.
function plus(a: string, b: string): string {
  return totalPlus(a, b, 1);
}
function minus(a: string, b: string): string {
  return totalPlus(a, b, -1);
}
function totalPlus(a: string, b: string, sign: 1 | -1): string {
  const scale = Math.max(frac(a), frac(b));
  const up = (x: string) => {
    const [w, f = ''] = x.replace('-', '').split('.');
    const v = BigInt(w + f.padEnd(scale, '0'));
    return x.startsWith('-') ? -v : v;
  };
  const v = up(a) + BigInt(sign) * up(b);
  const neg = v < 0n;
  const s = (neg ? -v : v).toString().padStart(scale + 1, '0');
  const whole = scale ? s.slice(0, -scale) : s;
  const f = scale ? s.slice(-scale).replace(/0+$/, '') : '';
  return `${neg ? '-' : ''}${whole}${f ? `.${f}` : ''}`;
}
function frac(x: string): number {
  return x.includes('.') ? x.split('.')[1].length : 0;
}
