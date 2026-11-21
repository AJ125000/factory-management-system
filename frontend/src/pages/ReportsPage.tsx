import { Button, Card, Group, SegmentedControl, Select, Stack, Table, Text, Title } from '@mantine/core';
import { IconPrinter } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { useMachines, useProductionSummary, useWorkers } from '../api/hooks';
import { localName } from '../i18n';
import type { GroupBy } from '../api/types';
import { ExportMenu } from '../components/ExportMenu';
import {
  PageHeader,
  PeriodPicker,
  periodFromPreset,
  workerOptions,
  type PeriodValue,
} from '../components/common';
import {
  MetricToggle,
  ProductionChart,
  chartData,
  periodLabel,
  type Metric,
} from '../components/ProductionChart';
import { formatMoney, formatNumber } from '../lib/format';

export default function ReportsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [period, setPeriod] = useState<PeriodValue>(periodFromPreset('this_year'));
  const [groupBy, setGroupBy] = useState<GroupBy>('month');
  const [workerId, setWorkerId] = useState<string | null>(null);
  const [machineId, setMachineId] = useState<string | null>(null);
  const machines = useMachines(true).data ?? [];
  const [metric, setMetric] = useState<Metric>('area');
  const workers = useWorkers(true);
  const workerIds = workerId ? [workerId] : undefined;
  const summary = useProductionSummary(period.start, period.end, groupBy, workerIds, machineId ?? undefined);

  const buckets = summary.data?.buckets ?? [];
  const totals = summary.data?.totals;
  const params = {
    start: period.start,
    end: period.end,
    group_by: groupBy,
    worker_id: workerIds,
    machine_id: machineId ?? undefined,
  };

  const print = () => {
    const search = new URLSearchParams({
      start: period.start,
      end: period.end,
      group_by: groupBy,
      lang: i18n.language,
    });
    if (workerId) search.set('worker', workerId);
    if (machineId) search.set('machine', machineId);
    navigate(`/print/production?${search}`);
  };

  return (
    <>
      <PageHeader
        title={t('reports.title')}
        actions={
          <>
            <ExportMenu kind="production" params={params} disabled={!buckets.length} />
            <Button leftSection={<IconPrinter size={18} />} onClick={print} disabled={!buckets.length}>
              {t('reports.printPdf')}
            </Button>
          </>
        }
      />

      <Card withBorder mb="md">
        <Group align="flex-end" wrap="wrap">
          <PeriodPicker value={period} onChange={setPeriod} />
          <Stack gap={4}>
            <Text size="sm" fw={500}>
              {t('reports.groupBy')}
            </Text>
            <SegmentedControl
              value={groupBy}
              onChange={(v) => setGroupBy(v as GroupBy)}
              data={[
                { value: 'day', label: t('reports.day') },
                { value: 'month', label: t('reports.month') },
                { value: 'year', label: t('reports.year') },
              ]}
            />
          </Stack>
          <Select
            label={t('production.worker')}
            placeholder={t('reports.allWorkers')}
            clearable
            searchable
            w={240}
            data={workerOptions(workers.data ?? [], i18n.language)}
            value={workerId}
            onChange={setWorkerId}
          />
          <Select
            label={t('production.machine')}
            placeholder={t('production.filterMachine')}
            clearable
            w={220}
            data={machines.map((m) => ({ value: m.id, label: localName(m.name_en, m.name_hi, i18n.language) }))}
            value={machineId}
            onChange={setMachineId}
          />
        </Group>
      </Card>

      {summary.isSuccess && buckets.length === 0 ? (
        <Card withBorder>
          <Text c="dimmed" ta="center" py="xl">
            {t('reports.noData')}
          </Text>
        </Card>
      ) : (
        <>
          <Card withBorder mb="md">
            <Group justify="space-between" mb="sm" wrap="wrap">
              <Title order={4}>
                {t(`reports.chart_${groupBy}`)}
              </Title>
              <MetricToggle value={metric} onChange={setMetric} />
            </Group>
            <ProductionChart
              label={t(`reports.chart_${groupBy}`)}
              metric={metric}
              data={chartData(buckets, period.start, period.end, groupBy, metric)}
            />
          </Card>

          <Card withBorder>
            <Table.ScrollContainer minWidth={600}>
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t(`reports.${groupBy}`)}</Table.Th>
                    <Table.Th className="num">{t('wages.entries')}</Table.Th>
                    <Table.Th className="num">{t('metrics.pieces')}</Table.Th>
                    <Table.Th className="num">{t('metrics.area')}</Table.Th>
                    <Table.Th className="num">{t('wages.rft')}</Table.Th>
                    <Table.Th className="num">{t('metrics.wages')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {buckets.map((b) => (
                    <Table.Tr key={b.period}>
                      <Table.Td>{periodLabel(b.period, groupBy, true)}</Table.Td>
                      <Table.Td className="num">{formatNumber(b.entry_count)}</Table.Td>
                      <Table.Td className="num">{formatNumber(b.total_quantity)}</Table.Td>
                      <Table.Td className="num">{formatNumber(b.total_area_sqft)}</Table.Td>
                      <Table.Td className="num">{formatNumber(b.total_rft)}</Table.Td>
                      <Table.Td className="num">{formatMoney(b.total_wage)}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
                {totals && (
                  <Table.Tfoot>
                    <Table.Tr fw={700}>
                      <Table.Td>{t('common.total')}</Table.Td>
                      <Table.Td className="num">{formatNumber(totals.entry_count)}</Table.Td>
                      <Table.Td className="num">{formatNumber(totals.total_quantity)}</Table.Td>
                      <Table.Td className="num">{formatNumber(totals.total_area_sqft)}</Table.Td>
                      <Table.Td className="num">{formatNumber(totals.total_rft)}</Table.Td>
                      <Table.Td className="num">{formatMoney(totals.total_wage)}</Table.Td>
                    </Table.Tr>
                  </Table.Tfoot>
                )}
              </Table>
            </Table.ScrollContainer>
          </Card>
        </>
      )}
    </>
  );
}
