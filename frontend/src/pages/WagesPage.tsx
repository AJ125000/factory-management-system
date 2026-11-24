import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Text,
} from '@mantine/core';
import { IconAlertTriangle, IconChevronDown, IconChevronRight, IconPrinter } from '@tabler/icons-react';
import { Fragment, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { useMachines, useSettings, useWagesReport } from '../api/hooks';
import { usePendingProduction, useWorkersWithPending } from '../api/pending';
import { ExportMenu } from '../components/ExportMenu';
import type { Language, WorkerWages } from '../api/types';
import {
  PageHeader,
  PeriodPicker,
  WorkerName,
  periodFromPreset,
  type PeriodValue,
} from '../components/common';
import { localName } from '../i18n';
import {
  componentLabel,
  entryDetails,
  entrySize,
  lineBasis,
  lineRate,
  splittingText,
} from '../lib/entryText';
import { withPendingWages } from '../lib/localEntries';
import { formatDate, formatMoney, formatNumber } from '../lib/format';
import { defaultPreset } from '../lib/periods';

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card withBorder padding="md">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text fz={26} fw={700} className="num" ta="left">
        {value}
      </Text>
    </Card>
  );
}

export default function WagesPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const settings = useSettings().data;
  const [period, setPeriod] = useState<PeriodValue | null>(null);
  const active = period ?? periodFromPreset(defaultPreset(settings?.pay_period ?? 'half_month'));
  const report = useWagesReport(active.start, active.end, { includeEntries: true });
  const [expanded, setExpanded] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [slipLang, setSlipLang] = useState<Language | null>(null);
  const lang = slipLang ?? settings?.print_language ?? 'hi';

  // Add this device's entries that haven't reached the laptop yet.
  const pending = usePendingProduction();
  const people = useWorkersWithPending(true).data;
  const hasPending = pending.created.length + pending.edited.size + pending.deleted.size > 0;
  const rows = useMemo(
    () =>
      hasPending
        ? withPendingWages(report.data?.workers ?? [], pending, active.start, active.end, people ?? [])
        : (report.data?.workers ?? []),
    [hasPending, report.data, pending, active.start, active.end, people],
  );
  const pendingRows = rows.filter(isPending).length;
  const totalWage = hasPending ? sumMoney(rows.map((r) => r.total_wage)) : report.data?.total_wage;
  const missingEntries = rows.reduce((n, r) => n + r.missing_rate_entries, 0);
  const allSelected = rows.length > 0 && selected.length === rows.length;

  const print = () => {
    const params = new URLSearchParams({ start: active.start, end: active.end, lang });
    if (selected.length && !allSelected) params.set('workers', selected.join(','));
    navigate(`/print/wages?${params}`);
  };

  return (
    <>
      <PageHeader title={t('wages.title')} />

      <Card withBorder mb="md">
        <Group justify="space-between" align="flex-end" wrap="wrap">
          <PeriodPicker
            value={active}
            onChange={(p) => {
              setPeriod(p);
              setSelected([]);
            }}
          />
          <Group align="flex-end" wrap="wrap">
            <Stack gap={4}>
              <Text size="sm" fw={500}>
                {t('wages.slipLanguage')}
              </Text>
              <SegmentedControl
                value={lang}
                onChange={(v) => setSlipLang(v as Language)}
                data={[
                  { value: 'hi', label: 'हिंदी' },
                  { value: 'en', label: 'English' },
                ]}
              />
            </Stack>
            <ExportMenu
              kind="wages"
              params={{
                start: active.start,
                end: active.end,
                worker_id: selected.length && !allSelected ? selected : undefined,
              }}
              disabled={rows.length === 0}
            />
            <Button leftSection={<IconPrinter size={18} />} onClick={print} disabled={rows.length === 0}>
              {selected.length && !allSelected
                ? t('wages.printSelected', { count: selected.length })
                : t('wages.printSlips')}
            </Button>
          </Group>
        </Group>
      </Card>

      {(report.data || hasPending) && (
        <SimpleGrid cols={{ base: 1, xs: 3 }} mb="md">
          <Stat label={t('wages.totalWages')} value={formatMoney(totalWage ?? '0')} />
          <Stat label={t('wages.workersPaid')} value={String(rows.length)} />
          <Stat
            label={t('wages.totalArea')}
            value={`${formatNumber(report.data?.total_area_sqft ?? '0')} ${t('units.sqft')}`}
          />
        </SimpleGrid>
      )}

      {pendingRows > 0 && (
        <Alert color={report.data ? 'gray' : 'orange'} variant="light" mb="md">
          {t(report.data ? 'wages.pendingNote' : 'wages.onlyPending')}
        </Alert>
      )}

      {missingEntries > 0 && (
        <Alert color="orange" variant="light" icon={<IconAlertTriangle />} mb="md">
          {t('wages.missingAlert', { count: missingEntries })}{' '}
          <Anchor component={Link} to="/rates" size="sm">
            {t('production.setRates')}
          </Anchor>
        </Alert>
      )}

      {(report.data?.no_loader_entries ?? 0) > 0 && (
        <Alert color="orange" variant="light" icon={<IconAlertTriangle />} mb="md">
          {t('wages.noLoaderAlert', { count: report.data!.no_loader_entries })}{' '}
          <Anchor component={Link} to="/rates" size="sm">
            {t('machines.changeLoader')}
          </Anchor>
        </Alert>
      )}

      <Card withBorder>
        {(report.isSuccess || hasPending) && rows.length === 0 ? (
          <Text c="dimmed" ta="center" py="xl">
            {t('wages.noData')}
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={720}>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={40}>
                    <Checkbox
                      aria-label={t('common.all')}
                      checked={allSelected}
                      indeterminate={selected.length > 0 && !allSelected}
                      onChange={() => setSelected(allSelected ? [] : rows.map((r) => r.worker_id))}
                    />
                  </Table.Th>
                  <Table.Th>{t('production.worker')}</Table.Th>
                  <Table.Th>{t('workers.type')}</Table.Th>
                  <Table.Th className="num">{t('wages.entries')}</Table.Th>
                  <Table.Th className="num">{t('wages.quantity')}</Table.Th>
                  <Table.Th className="num">
                    {t('production.area')} ({t('units.sqft')})
                  </Table.Th>
                  <Table.Th className="num">
                    {t('wages.rft')}
                  </Table.Th>
                  <Table.Th className="num">{t('wages.shifts')}</Table.Th>
                  <Table.Th className="num">{t('wages.wage')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {rows.map((r) => (
                  <Fragment key={r.worker_id}>
                    <Table.Tr
                      className="clickable-row"
                      onClick={() => setExpanded(expanded === r.worker_id ? null : r.worker_id)}
                    >
                      <Table.Td onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          aria-label={r.name_en}
                          checked={selected.includes(r.worker_id)}
                          onChange={(e) =>
                            setSelected((s) =>
                              e.currentTarget.checked
                                ? [...s, r.worker_id]
                                : s.filter((id) => id !== r.worker_id),
                            )
                          }
                        />
                      </Table.Td>
                      <Table.Td>
                        <Group gap={6} wrap="nowrap">
                          {expanded === r.worker_id ? (
                            <IconChevronDown size={16} />
                          ) : (
                            <IconChevronRight size={16} />
                          )}
                          <WorkerName nameEn={r.name_en} nameHi={r.name_hi} />
                          {isPending(r) && (
                            <Badge size="xs" color="gray" variant="light">
                              {t('sync.pending')}
                            </Badge>
                          )}
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        {localName(r.worker_type_name_en, r.worker_type_name_hi, i18n.language)}
                      </Table.Td>
                      <Table.Td className="num">{r.entry_count}</Table.Td>
                      <Table.Td className="num">{r.total_quantity || '—'}</Table.Td>
                      <Table.Td className="num">{formatNumber(r.total_area_sqft)}</Table.Td>
                      <Table.Td className="num">
                        {Number(r.total_rft) > 0 ? formatNumber(r.total_rft) : '—'}
                      </Table.Td>
                      <Table.Td className="num">{r.total_shifts || '—'}</Table.Td>
                      <Table.Td className="num">
                        <Text fw={700}>{formatMoney(r.total_wage)}</Text>
                        {r.missing_rate_entries > 0 && (
                          <Text size="xs" c="orange">
                            +{r.missing_rate_entries} {t('slip.rateMissing')}
                          </Text>
                        )}
                      </Table.Td>
                    </Table.Tr>
                    {expanded === r.worker_id && (
                      <Table.Tr>
                        <Table.Td colSpan={9} bg="var(--mantine-color-gray-0)">
                          <WorkerEntries row={r} />
                        </Table.Td>
                      </Table.Tr>
                    )}
                  </Fragment>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Card>
    </>
  );
}

function WorkerEntries({ row }: { row: WorkerWages }) {
  const { t, i18n } = useTranslation();
  const machines = useMachines(true).data ?? [];
  const workers = useWorkersWithPending(true).data ?? [];
  const local = (x: { name_en: string; name_hi: string | null } | undefined) =>
    x ? localName(x.name_en, x.name_hi, i18n.language) : '';
  return (
    <Table withRowBorders={false} fz="sm">
      <Table.Thead>
        <Table.Tr>
          <Table.Th>{t('common.date')}</Table.Th>
          <Table.Th>{t('production.machine')}</Table.Th>
          <Table.Th>{t('production.size')}</Table.Th>
          <Table.Th className="num">{t('production.quantity')}</Table.Th>
          <Table.Th className="num">{t('slip.basis')}</Table.Th>
          <Table.Th>{t('rates.rate')}</Table.Th>
          <Table.Th className="num">{t('production.wage')}</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {(row.entries ?? []).map((e) => {
          const details = entryDetails(e, t);
          const split = splittingText(e, t);
          return (
            <Table.Tr key={`${e.id}-${e.paid_as}`}>
              <Table.Td style={{ whiteSpace: 'nowrap' }}>
                {formatDate(e.entry_date)}
                {isPending(e) && (
                  <Badge display="block" mt={2} size="xs" color="gray" variant="light">
                    {t('sync.pending')}
                  </Badge>
                )}
              </Table.Td>
              <Table.Td>
                {local(machines.find((m) => m.id === e.machine_id))}
                {e.paid_as === 'loader' && (
                  <Text size="xs" c="dimmed">
                    {t('slip.operator')}: {local(workers.find((w) => w.id === e.worker_id))}
                  </Text>
                )}
              </Table.Td>
              <Table.Td>
                {entrySize(e, t)}
                {details && (
                  <Text size="xs" c="dimmed">
                    {details}
                  </Text>
                )}
                {split && (
                  <Text size="xs" c="dimmed">
                    {split}
                  </Text>
                )}
              </Table.Td>
              <Table.Td className="num">{e.shift ? '—' : e.quantity}</Table.Td>
              <Table.Td className="num">
                {e.wage_lines.map((l) => (
                  <div key={l.component}>{lineBasis(l, t)}</div>
                ))}
              </Table.Td>
              <Table.Td>
                {e.wage_lines.length
                  ? e.wage_lines.map((l) => (
                      <div key={l.component}>
                        {componentLabel(t, l.component)} {lineRate(l, t)}
                      </div>
                    ))
                  : t('slip.rateMissing')}
              </Table.Td>
              <Table.Td className="num">{formatMoney(e.wage)}</Table.Td>
            </Table.Tr>
          );
        })}
      </Table.Tbody>
    </Table>
  );
}

function sumMoney(values: string[]): string {
  const paise = values.reduce((n, v) => n + BigInt(v.replace('.', '')), 0n);
  const neg = paise < 0n;
  const abs = neg ? -paise : paise;
  return `${neg ? '-' : ''}${abs / 100n}.${(abs % 100n).toString().padStart(2, '0')}`;
}

const isPending = (x: object) => (x as { pending?: boolean }).pending === true;
