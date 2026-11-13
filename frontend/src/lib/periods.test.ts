import dayjs from 'dayjs';
import { describe, expect, it } from 'vitest';

import { formatMoney, formatNumber, parseTypedDate } from './format';
import { presetPeriod } from './periods';

describe('presetPeriod', () => {
  it('splits months into halves at the 15th', () => {
    expect(presetPeriod('this_half', dayjs('2026-11-13'))).toEqual({
      start: '2026-11-01',
      end: '2026-11-15',
    });
    expect(presetPeriod('this_half', dayjs('2026-11-16'))).toEqual({
      start: '2026-11-16',
      end: '2026-11-30',
    });
  });

  it('finds the previous half across month and year boundaries', () => {
    expect(presetPeriod('last_half', dayjs('2026-11-13'))).toEqual({
      start: '2026-10-16',
      end: '2026-10-31',
    });
    expect(presetPeriod('last_half', dayjs('2026-01-05'))).toEqual({
      start: '2025-12-16',
      end: '2025-12-31',
    });
    expect(presetPeriod('last_half', dayjs('2026-03-20'))).toEqual({
      start: '2026-03-01',
      end: '2026-03-15',
    });
  });

  it('handles February and leap years', () => {
    expect(presetPeriod('this_half', dayjs('2028-02-20')).end).toBe('2028-02-29');
    expect(presetPeriod('last_month', dayjs('2026-03-31'))).toEqual({
      start: '2026-02-01',
      end: '2026-02-28',
    });
  });

  it('covers whole years', () => {
    expect(presetPeriod('last_year', dayjs('2026-06-01'))).toEqual({
      start: '2025-01-01',
      end: '2025-12-31',
    });
  });
});

describe('parseTypedDate', () => {
  it('reads dates day-first, as written in India', () => {
    expect(parseTypedDate('05/11/2026')).toBe('2026-11-05'); // 5 November, not 11 May
    expect(parseTypedDate('5-11-26')).toBe('2026-11-05');
    expect(parseTypedDate('5.11.2026')).toBe('2026-11-05');
    expect(parseTypedDate(' 13/11/2026 ')).toBe('2026-11-13');
  });

  it('accepts month names and ISO dates', () => {
    expect(parseTypedDate('1 Nov 2026')).toBe('2026-11-01');
    expect(parseTypedDate('1 november 2026')).toBe('2026-11-01');
    expect(parseTypedDate('2026-11-01')).toBe('2026-11-01');
  });

  it('rejects impossible or unclear input', () => {
    expect(parseTypedDate('31/02/2026')).toBeNull();
    expect(parseTypedDate('13/13/2026')).toBeNull();
    expect(parseTypedDate('yesterday')).toBeNull();
    expect(parseTypedDate('')).toBeNull();
  });
});

describe('formatting', () => {
  it('uses Indian digit grouping for rupees', () => {
    expect(formatMoney('123456.5')).toBe('₹1,23,456.50');
    expect(formatMoney(null)).toBe('—');
  });

  it('trims numbers sensibly', () => {
    expect(formatNumber('45.00')).toBe('45');
    expect(formatNumber('1234567.891')).toBe('12,34,567.89');
  });
});
