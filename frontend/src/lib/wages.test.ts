import { describe, expect, it } from 'vitest';

import cases from '../../../shared/wage-cases.json';
import type { PayScheme, Rate, RateComponent } from '../api/types';
import { calculateWage, rateOn, totalArea } from './wages';

describe('shared wage cases (must match the hub exactly)', () => {
  for (const c of cases) {
    it(c.name, () => {
      const result = calculateWage(
        c.scheme as PayScheme,
        { length_ft: c.length_ft, width_ft: c.width_ft, cuts: c.cuts, quantity: c.quantity },
        c.rates as Partial<Record<RateComponent, string | null>>,
      );
      expect(result.total).toBe(c.expected.total);
      expect(result.missing).toEqual(c.expected.missing);
      expect(result.lines.map((l) => l.amount)).toEqual(c.expected.lines.map((l) => l.amount));
    });
  }
});

describe('rateOn', () => {
  const rate = (component: RateComponent, value: string, from: string): Rate => ({
    id: from,
    worker_type_id: 'op',
    component,
    rate_per_sqft: value,
    effective_from: from,
    note: null,
  });
  const rates = [rate('cutting', '2', '2026-07-01'), rate('cutting', '1.5', '2026-01-01')];

  it('uses the rate in effect on the date', () => {
    expect(rateOn(rates, 'op', 'cutting', '2025-12-31')).toBeNull();
    expect(rateOn(rates, 'op', 'cutting', '2026-06-30')).toBe('1.5');
    expect(rateOn(rates, 'op', 'cutting', '2026-07-01')).toBe('2');
    expect(rateOn(rates, 'other', 'cutting', '2026-07-01')).toBeNull();
  });
});

describe('totalArea', () => {
  it('is exact', () => {
    expect(totalArea({ length_ft: '2', width_ft: '3', cuts: 0, quantity: 5 })).toBe('30');
    expect(totalArea({ length_ft: '0.1', width_ft: '0.2', cuts: 0, quantity: 3 })).toBe('0.06');
  });
});
