import { describe, expect, it } from 'vitest';

import cases from '../../../shared/wage-cases.json';
import type { LoaderAssignment, MachineKind, MachineSize, Rate, Role } from '../api/types';
import {
  calculateWage,
  componentUnit,
  fraction,
  loaderOn,
  rateOn,
  resolvePiece,
  roleComponents,
  sizeLabel,
  totalOf,
} from './wages';

describe('shared wage cases (must match the hub exactly)', () => {
  for (const c of cases) {
    it(c.name, () => {
      const result = calculateWage(
        c.kind as MachineKind,
        c.role as Role,
        {
          piece_sqft: c.piece_sqft,
          piece_rft: c.piece_rft,
          cuts: c.cuts,
          quantity: c.quantity,
          batti: c.batti,
        },
        c.rates as unknown as Record<string, string | null>,
      );
      expect(result.total).toBe(c.expected.total);
      expect(result.missing).toEqual(c.expected.missing);
      expect(result.lines.map((l) => l.amount)).toEqual(c.expected.lines.map((l) => l.amount));
    });
  }
});

describe('rateOn', () => {
  const rate = (component: string, value: string, from: string): Rate => ({
    id: from,
    machine_id: 'm',
    component,
    unit: 'sqft',
    rate: value,
    effective_from: from,
    note: null,
  });
  const rates = [rate('cutting', '2', '2026-07-01'), rate('cutting', '1.5', '2026-01-01')];

  it('uses the rate in effect on the date', () => {
    expect(rateOn(rates, 'm', 'cutting', '2025-12-31')).toBeNull();
    expect(rateOn(rates, 'm', 'cutting', '2026-06-30')).toBe('1.5');
    expect(rateOn(rates, 'm', 'cutting', '2026-07-01')).toBe('2');
    expect(rateOn(rates, 'other', 'cutting', '2026-07-01')).toBeNull();
  });
});

describe('loaderOn', () => {
  const a = (worker: string | null, from: string): LoaderAssignment => ({
    id: from,
    machine_id: 'm',
    worker_id: worker,
    effective_from: from,
    note: null,
  });
  const book = [a('raju', '2026-03-01'), a('shyam', '2026-03-10'), a(null, '2026-04-01')];

  it('follows swaps and gaps by date', () => {
    expect(loaderOn(book, 'm', '2026-02-28')).toBeNull();
    expect(loaderOn(book, 'm', '2026-03-09')).toBe('raju');
    expect(loaderOn(book, 'm', '2026-03-10')).toBe('shyam');
    expect(loaderOn(book, 'm', '2026-04-02')).toBeNull();
  });
});

describe('resolvePiece', () => {
  const size = (id: string, machine: string, l: string, w: string, rft: string, sqft: string): MachineSize => ({
    id,
    machine_id: machine,
    length: l,
    width: w,
    rft,
    sqft,
  });
  const sizes = [size('de', 'DE', '2', '1.5', '7', '3'), size('sc', 'SC', '22.5', '22.5', '8', '4')];

  it('uses the size table on double edge, either way round', () => {
    const p = resolvePiece('double_edge', 'DE', sizes, { length_ft: '1.50', width_ft: '2', size_id: null });
    expect(p).toMatchObject({ piece_rft: '7', piece_sqft: '3' });
    expect(p?.size?.id).toBe('de');
  });

  it('uses true perimeter and area for other double edge sizes', () => {
    const p = resolvePiece('double_edge', 'DE', sizes, { length_ft: '1.25', width_ft: '0.75', size_id: null });
    expect(p).toEqual({ piece_rft: '4', piece_sqft: '0.9375', size: null });
  });

  it('needs a table size on single cutting', () => {
    expect(resolvePiece('single_cutting', 'SC', sizes, { length_ft: null, width_ft: null, size_id: null })).toBeNull();
    expect(resolvePiece('single_cutting', 'SC', sizes, { length_ft: null, width_ft: null, size_id: 'de' })).toBeNull();
    expect(
      resolvePiece('single_cutting', 'SC', sizes, { length_ft: null, width_ft: null, size_id: 'sc' }),
    ).toMatchObject({ piece_rft: '8', piece_sqft: '4' });
  });

  it('uses the plain area on polish and block cutting', () => {
    expect(resolvePiece('table_polish', 'P', sizes, { length_ft: '2', width_ft: '1.5', size_id: null })).toEqual({
      piece_sqft: '3',
      piece_rft: null,
      size: null,
    });
  });
});

describe('helpers', () => {
  it('labels sizes like the hub', () => {
    expect(fraction('22.5')).toBe('22½');
    expect(fraction('0.5')).toBe('½');
    expect(fraction('2.00')).toBe('2');
    expect(sizeLabel('2', '1.5')).toBe('2 × 1½');
  });

  it('knows units and who is paid what', () => {
    expect(componentUnit('double_edge', 'cutting')).toBe('rft');
    expect(componentUnit('block_cutting', 'cutting')).toBe('sqft');
    expect(roleComponents('block_cutting', 'loader')).toEqual(['loading', 'unloading']);
    expect(roleComponents('table_polish', 'loader')).toEqual(['unloading']);
    expect(roleComponents('table_polish', 'operator')).toContain('polish_4');
  });

  it('totals exactly', () => {
    expect(totalOf('6', 5)).toBe('30');
    expect(totalOf('0.02', 3)).toBe('0.06');
  });
});
