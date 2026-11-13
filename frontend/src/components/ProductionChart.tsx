import { BarChart } from '@mantine/charts';
import { SegmentedControl } from '@mantine/core';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';

import type { GroupBy, ProductionBucket } from '../api/types';
import { formatMoney, formatNumber } from '../lib/format';

export type Metric = 'area' | 'wages' | 'pieces';

/** Single-series bars: one validated hue (passes contrast on the light surface). */
const SERIES_COLOR = '#2a78d6';

const compact = new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 });

export function metricValue(bucket: ProductionBucket | undefined, metric: Metric): number {
  if (!bucket) return 0;
  if (metric === 'area') return Number(bucket.total_area_sqft);
  if (metric === 'wages') return Number(bucket.total_wage);
  return bucket.total_quantity;
}

export function useMetricFormatter() {
  const { t } = useTranslation();
  return (metric: Metric) => (value: number) => {
    if (metric === 'wages') return formatMoney(value);
    if (metric === 'area') return `${formatNumber(value)} ${t('units.sqft')}`;
    return formatNumber(value);
  };
}

export function MetricToggle({ value, onChange }: { value: Metric; onChange: (m: Metric) => void }) {
  const { t } = useTranslation();
  return (
    <SegmentedControl
      size="xs"
      value={value}
      onChange={(v) => onChange(v as Metric)}
      data={[
        { value: 'area', label: t('metrics.area') },
        { value: 'wages', label: t('metrics.wages') },
        { value: 'pieces', label: t('metrics.pieces') },
      ]}
    />
  );
}

/** Every period between start and end, so gaps show as zero bars instead of vanishing. */
export function periodKeys(start: string, end: string, groupBy: GroupBy): string[] {
  const unit = groupBy === 'day' ? 'day' : groupBy === 'month' ? 'month' : 'year';
  const fmt = groupBy === 'day' ? 'YYYY-MM-DD' : groupBy === 'month' ? 'YYYY-MM' : 'YYYY';
  const keys: string[] = [];
  let d = dayjs(start).startOf(unit);
  const last = dayjs(end);
  while (!d.isAfter(last) && keys.length < 400) {
    keys.push(d.format(fmt));
    d = d.add(1, unit);
  }
  return keys;
}

export function periodLabel(key: string, groupBy: GroupBy, long = false): string {
  if (groupBy === 'day') return dayjs(key).format(long ? 'D MMM YYYY' : 'D');
  if (groupBy === 'month') return dayjs(`${key}-01`).format(long ? 'MMMM YYYY' : 'MMM');
  return key;
}

export function chartData(
  buckets: ProductionBucket[],
  start: string,
  end: string,
  groupBy: GroupBy,
  metric: Metric,
) {
  const byKey = new Map(buckets.map((b) => [b.period, b]));
  return periodKeys(start, end, groupBy).map((key) => ({
    label: periodLabel(key, groupBy),
    value: metricValue(byKey.get(key), metric),
  }));
}

export function ProductionChart({
  data,
  metric,
  height = 260,
  label,
}: {
  data: { label: string; value: number }[];
  metric: Metric;
  height?: number;
  label: string;
}) {
  const { t } = useTranslation();
  const format = useMetricFormatter()(metric);
  return (
    <BarChart
      h={height}
      data={data}
      dataKey="label"
      aria-label={label}
      series={[{ name: 'value', color: SERIES_COLOR, label: t(`metrics.${metric}`) }]}
      valueFormatter={format}
      yAxisProps={{ tickFormatter: (v: number) => compact.format(v), width: 48 }}
      gridAxis="x"
      strokeDasharray="0"
      tickLine="none"
      maxBarWidth={24}
      barProps={{ radius: [4, 4, 0, 0] }}
      tooltipAnimationDuration={120}
    />
  );
}
