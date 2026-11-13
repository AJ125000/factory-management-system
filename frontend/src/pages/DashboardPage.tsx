import { Alert, Anchor, Button, Card, Group, Select, SimpleGrid, Table, Text, Title } from '@mantine/core';
import { IconAlertTriangle, IconPlus } from '@tabler/icons-react';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { useProductionSummary, useSettings, useWagesReport, useWorkers } from '../api/hooks';
import { PageHeader, WorkerName, periodFromPreset } from '../components/common';
import {
  MetricToggle,
  ProductionChart,
  chartData,
  type Metric,
} from '../components/ProductionChart';
import { formatMoney, formatNumber } from '../lib/format';
import { defaultPreset, presetPeriod } from '../lib/periods';

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card withBorder padding="md">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text fz={28} fw={700} lh={1.2} className="num" ta="left">
        {value}
      </Text>
      {sub && (
        <Text size="xs" c="dimmed">
          {sub}
        </Text>
      )}
    </Card>
  );
}

export default function DashboardPage() {
  const { t } = useTranslation();
  const settings = useSettings().data;
  const payPeriod = periodFromPreset(defaultPreset(settings?.pay_period ?? 'half_month'));
  const month = presetPeriod('this_month');
  const thisYear = dayjs().year();
  const [year, setYear] = useState(thisYear);
  const [metric, setMetric] = useState<Metric>('area');

  const wagesNow = useWagesReport(payPeriod.start, payPeriod.end);
  const monthWages = useWagesReport(month.start, month.end);
  const yearNow = useProductionSummary(`${thisYear}-01-01`, `${thisYear}-12-31`, 'year');
  const byMonth = useProductionSummary(`${year}-01-01`, `${year}-12-31`, 'month');
  const byDay = useProductionSummary(month.start, month.end, 'day');
  const workers = useWorkers(false);

  const monthTotals = monthWages.data;
  const top = [...(monthWages.data?.workers ?? [])]
    .sort((a, b) => Number(b.total_wage) - Number(a.total_wage))
    .slice(0, 5);
  const missing = monthWages.data?.missing_rate_entries ?? 0;

  return (
    <>
      <PageHeader
        title={t('dashboard.title')}
        actions={
          <Button component={Link} to="/production" leftSection={<IconPlus size={18} />}>
            {t('dashboard.addProduction')}
          </Button>
        }
      />

      <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} mb="md">
        <StatTile
          label={t('dashboard.wagesThisPeriod')}
          value={formatMoney(wagesNow.data?.total_wage ?? 0)}
          sub={t(`periods.${payPeriod.preset}`)}
        />
        <StatTile
          label={t('dashboard.productionThisMonth')}
          value={`${formatNumber(monthTotals?.total_area_sqft ?? 0)} ${t('units.sqft')}`}
          sub={dayjs().format('MMMM YYYY')}
        />
        <StatTile
          label={t('dashboard.productionThisYear')}
          value={`${formatNumber(yearNow.data?.totals.total_area_sqft ?? 0)} ${t('units.sqft')}`}
          sub={String(thisYear)}
        />
        <StatTile label={t('dashboard.activeWorkers')} value={String(workers.data?.length ?? 0)} />
      </SimpleGrid>

      {missing > 0 && (
        <Alert color="orange" variant="light" icon={<IconAlertTriangle />} mb="md">
          {t('wages.missingAlert', { count: missing })}{' '}
          <Anchor component={Link} to="/rates" size="sm">
            {t('production.setRates')}
          </Anchor>
        </Alert>
      )}

      <Card withBorder mb="md">
        <Group justify="space-between" mb="sm" wrap="wrap">
          <Title order={4}>{t('dashboard.byMonth', { year })}</Title>
          <Group gap="sm" wrap="wrap">
            <MetricToggle value={metric} onChange={setMetric} />
            <Select
              size="xs"
              w={100}
              aria-label={t('dashboard.year')}
              allowDeselect={false}
              value={String(year)}
              onChange={(v) => v && setYear(Number(v))}
              data={[0, 1, 2, 3, 4].map((i) => String(thisYear - i))}
            />
          </Group>
        </Group>
        <ProductionChart
          label={t('dashboard.byMonth', { year })}
          metric={metric}
          data={chartData(byMonth.data?.buckets ?? [], `${year}-01-01`, `${year}-12-31`, 'month', metric)}
        />
      </Card>

      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        <Card withBorder>
          <Title order={4} mb="sm">
            {t('dashboard.byDay', { month: dayjs().format('MMMM YYYY') })}
          </Title>
          <ProductionChart
            label={t('dashboard.byDay', { month: dayjs().format('MMMM YYYY') })}
            metric={metric}
            height={220}
            data={chartData(byDay.data?.buckets ?? [], month.start, month.end, 'day', metric)}
          />
        </Card>

        <Card withBorder>
          <Group justify="space-between" mb="sm">
            <Title order={4}>{t('dashboard.topWorkers')}</Title>
            <Anchor component={Link} to="/reports" size="sm">
              {t('dashboard.viewReports')}
            </Anchor>
          </Group>
          {top.length === 0 ? (
            <Text c="dimmed" size="sm" py="lg" ta="center">
              {t('dashboard.noProduction')}
            </Text>
          ) : (
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('production.worker')}</Table.Th>
                  <Table.Th className="num">{t('metrics.area')}</Table.Th>
                  <Table.Th className="num">{t('wages.wage')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {top.map((w) => (
                  <Table.Tr key={w.worker_id}>
                    <Table.Td>
                      <WorkerName nameEn={w.name_en} nameHi={w.name_hi} />
                    </Table.Td>
                    <Table.Td className="num">{formatNumber(w.total_area_sqft)}</Table.Td>
                    <Table.Td className="num" fw={600}>
                      {formatMoney(w.total_wage)}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Card>
      </SimpleGrid>
    </>
  );
}
