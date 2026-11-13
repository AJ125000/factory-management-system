import { describe, expect, it } from 'vitest';

import { ApiError } from '../api/client';
import { chartData, periodKeys } from '../components/ProductionChart';
import i18n from '../i18n';
import { errorMessage } from './errors';

const bucket = (period: string, area: string) => ({
  period,
  entry_count: 1,
  total_quantity: 5,
  total_area_sqft: area,
  total_cuts: 2,
  total_wage: '100.00',
  missing_rate_entries: 0,
});

describe('chart periods', () => {
  it('lists every period so empty ones show as zero', () => {
    expect(periodKeys('2026-01-01', '2026-12-31', 'month')).toHaveLength(12);
    expect(periodKeys('2026-11-01', '2026-11-30', 'day')).toHaveLength(30);
    expect(periodKeys('2024-03-15', '2026-02-01', 'year')).toEqual(['2024', '2025', '2026']);
  });

  it('fills gaps with zero and keeps values in order', () => {
    const data = chartData(
      [bucket('2026-03', '45.5')],
      '2026-01-01',
      '2026-04-30',
      'month',
      'area',
    );
    expect(data.map((d) => d.value)).toEqual([0, 0, 45.5, 0]);
  });
});

describe('errorMessage', () => {
  it('translates known server reasons', async () => {
    const err = new ApiError(409, 'conflict', 'English message', { reason: 'worker_archived' });
    await i18n.changeLanguage('hi');
    expect(errorMessage(err)).toContain('निष्क्रिय');
    await i18n.changeLanguage('en');
    expect(errorMessage(err)).toBe(
      'This worker is archived. Restore them before adding production.',
    );
  });

  it('falls back to the code, then to the server message', () => {
    expect(errorMessage(new ApiError(0, 'offline', 'x'))).toContain('Is the laptop on?');
    expect(errorMessage(new ApiError(400, 'mystery', 'Server says no'))).toBe('Server says no');
  });
});

describe('device data lifetime', () => {
  it('stays below the browser timer limit (longer delays fire immediately)', async () => {
    const { KEEP_DATA_MS, MAX_TIMER_MS } = await import('./cacheTime');
    expect(KEEP_DATA_MS).toBeLessThan(MAX_TIMER_MS);
    expect(KEEP_DATA_MS).toBeGreaterThanOrEqual(14 * 24 * 60 * 60 * 1000); // at least two weeks
  });
});
