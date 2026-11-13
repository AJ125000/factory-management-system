import dayjs, { type Dayjs } from 'dayjs';

import type { PayPeriod } from '../api/types';

export type PeriodPreset =
  | 'this_half'
  | 'last_half'
  | 'this_month'
  | 'last_month'
  | 'this_year'
  | 'last_year';

export interface Period {
  start: string; // YYYY-MM-DD
  end: string;
}

const iso = (d: Dayjs) => d.format('YYYY-MM-DD');

/** Half-months run 1st–15th and 16th–last day of the month. */
function halfContaining(d: Dayjs): Period {
  return d.date() <= 15
    ? { start: iso(d.startOf('month')), end: iso(d.date(15)) }
    : { start: iso(d.date(16)), end: iso(d.endOf('month')) };
}

export function presetPeriod(preset: PeriodPreset, today: Dayjs = dayjs()): Period {
  switch (preset) {
    case 'this_half':
      return halfContaining(today);
    case 'last_half': {
      const thisStart = dayjs(halfContaining(today).start);
      return halfContaining(thisStart.subtract(1, 'day'));
    }
    case 'this_month':
      return { start: iso(today.startOf('month')), end: iso(today.endOf('month')) };
    case 'last_month': {
      const m = today.subtract(1, 'month');
      return { start: iso(m.startOf('month')), end: iso(m.endOf('month')) };
    }
    case 'this_year':
      return { start: iso(today.startOf('year')), end: iso(today.endOf('year')) };
    case 'last_year': {
      const y = today.subtract(1, 'year');
      return { start: iso(y.startOf('year')), end: iso(y.endOf('year')) };
    }
  }
}

/** The owner's normal pay period (from settings) decides the default view. */
export function defaultPreset(payPeriod: PayPeriod): PeriodPreset {
  return payPeriod === 'month' ? 'this_month' : 'this_half';
}

export const PRESETS: PeriodPreset[] = [
  'this_half',
  'last_half',
  'this_month',
  'last_month',
  'this_year',
  'last_year',
];
