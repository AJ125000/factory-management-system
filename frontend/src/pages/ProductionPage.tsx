import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  NumberInput,
  Pagination,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { modals } from '@mantine/modals';
import { IconAlertTriangle, IconPencil, IconTrash } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import {
  previewWage,
  useDeleteEntry,
  useProduction,
  useSaveEntry,
  useSettings,
  useWorkers,
} from '../api/hooks';
import type { ProductionEntry, ProductionInput, RateComponent, Worker } from '../api/types';
import {
  DateField,
  PageHeader,
  PeriodPicker,
  WorkerName,
  notifySaved,
  periodFromPreset,
  workerOptions,
  type PeriodValue,
} from '../components/common';
import { formatDate, formatFeet, formatMoney, formatNumber, todayISO } from '../lib/format';
import { defaultPreset } from '../lib/periods';

const PAGE_SIZE = 50;

export default function ProductionPage() {
  const { t, i18n } = useTranslation();
  const settings = useSettings().data;
  const allWorkers = useWorkers(true);
  const byId = useMemo(
    () => new Map((allWorkers.data ?? []).map((w) => [w.id, w])),
    [allWorkers.data],
  );

  const [period, setPeriod] = useState<PeriodValue | null>(null);
  const activePeriod = period ?? periodFromPreset(defaultPreset(settings?.pay_period ?? 'half_month'));
  const [workerFilter, setWorkerFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<ProductionEntry | null>(null);

  const entries = useProduction({
    start: activePeriod.start,
    end: activePeriod.end,
    worker_id: workerFilter ?? undefined,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });
  const remove = useDeleteEntry();

  const confirmDelete = (e: ProductionEntry) => {
    const w = byId.get(e.worker_id);
    modals.openConfirmModal({
      title: t('production.deleteTitle'),
      children: (
        <Text size="sm">
          {t('production.deleteBody', {
            name: w?.name_en ?? '',
            date: formatDate(e.entry_date),
            wage: formatMoney(e.wage),
          })}
        </Text>
      ),
      labels: { confirm: t('common.delete'), cancel: t('common.cancel') },
      confirmProps: { color: 'red' },
      onConfirm: () => remove.mutate(e.id, { onSuccess: () => notifySaved(t('common.deleted')) }),
    });
  };

  const total = entries.data?.total ?? 0;

  return (
    <>
      <PageHeader title={t('production.title')} />

      <Card withBorder mb="lg">
        <Title order={4} mb="sm">
          {t('production.newEntry')}
        </Title>
        <EntryForm workers={(allWorkers.data ?? []).filter((w) => !w.is_archived)} />
      </Card>

      <Card withBorder>
        <Group justify="space-between" align="flex-end" mb="md" wrap="wrap">
          <Group align="flex-end" wrap="wrap">
            <PeriodPicker
              value={activePeriod}
              onChange={(p) => {
                setPeriod(p);
                setPage(1);
              }}
            />
            <Select
              label={t('production.worker')}
              placeholder={t('production.filterWorker')}
              clearable
              searchable
              w={240}
              data={workerOptions(allWorkers.data ?? [], i18n.language)}
              value={workerFilter}
              onChange={(v) => {
                setWorkerFilter(v);
                setPage(1);
              }}
            />
          </Group>
          <Text size="sm" c="dimmed">
            {t('production.count', { count: total })}
          </Text>
        </Group>

        {entries.isSuccess && total === 0 ? (
          <Text c="dimmed" ta="center" py="xl">
            {t('production.noEntries')}
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={760}>
            <Table highlightOnHover striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('common.date')}</Table.Th>
                  <Table.Th>{t('production.worker')}</Table.Th>
                  <Table.Th className="num">{t('production.size')}</Table.Th>
                  <Table.Th className="num">{t('production.cuts')}</Table.Th>
                  <Table.Th className="num">{t('production.quantity')}</Table.Th>
                  <Table.Th className="num">
                    {t('production.area')} ({t('units.sqft')})
                  </Table.Th>
                  <Table.Th className="num">{t('production.wage')}</Table.Th>
                  <Table.Th w={80} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {(entries.data?.items ?? []).map((e) => {
                  const w = byId.get(e.worker_id);
                  return (
                    <Table.Tr key={e.id}>
                      <Table.Td style={{ whiteSpace: 'nowrap' }}>{formatDate(e.entry_date)}</Table.Td>
                      <Table.Td>{w && <WorkerName nameEn={w.name_en} nameHi={w.name_hi} />}</Table.Td>
                      <Table.Td className="num">
                        {formatFeet(e.length_ft)} × {formatFeet(e.width_ft)}
                      </Table.Td>
                      <Table.Td className="num">{e.cuts}</Table.Td>
                      <Table.Td className="num">{e.quantity}</Table.Td>
                      <Table.Td className="num">{formatNumber(e.area_sqft)}</Table.Td>
                      <Table.Td className="num">
                        {e.wage !== null ? (
                          <Text fw={600} size="sm">
                            {formatMoney(e.wage)}
                          </Text>
                        ) : (
                          <Badge color="orange" variant="light">
                            {t('slip.rateMissing')}
                          </Badge>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Group gap={4} wrap="nowrap">
                          <ActionIcon
                            variant="subtle"
                            color="gray"
                            aria-label={t('common.edit')}
                            onClick={() => setEditing(e)}
                          >
                            <IconPencil size={16} />
                          </ActionIcon>
                          <ActionIcon
                            variant="subtle"
                            color="red"
                            aria-label={t('common.delete')}
                            onClick={() => confirmDelete(e)}
                          >
                            <IconTrash size={16} />
                          </ActionIcon>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
        {total > PAGE_SIZE && (
          <Group justify="center" mt="md">
            <Pagination total={Math.ceil(total / PAGE_SIZE)} value={page} onChange={setPage} />
          </Group>
        )}
      </Card>

      <Modal opened={editing !== null} onClose={() => setEditing(null)} title={t('production.editEntry')} size="lg">
        {editing && (
          <EntryForm
            entry={editing}
            workers={(allWorkers.data ?? []).filter(
              (w) => !w.is_archived || w.id === editing.worker_id,
            )}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>
    </>
  );
}

interface FormState {
  worker_id: string | null;
  entry_date: string | null;
  length: number | string;
  width: number | string;
  cuts: number | string;
  quantity: number | string;
  notes: string;
}

function toInput(v: FormState): ProductionInput | null {
  const n = (x: number | string) => (x === '' ? NaN : Number(x));
  if (!v.worker_id || !v.entry_date) return null;
  if (!(n(v.length) > 0) || !(n(v.width) > 0) || !(n(v.cuts) >= 0) || !(n(v.quantity) >= 1)) {
    return null;
  }
  return {
    worker_id: v.worker_id,
    entry_date: v.entry_date,
    length_ft: String(v.length),
    width_ft: String(v.width),
    cuts: Math.trunc(n(v.cuts)),
    quantity: Math.trunc(n(v.quantity)),
    notes: v.notes.trim() || null,
  };
}

function EntryForm({
  workers,
  entry,
  onDone,
}: {
  workers: Worker[];
  entry?: ProductionEntry;
  onDone?: () => void;
}) {
  const { t, i18n } = useTranslation();
  const save = useSaveEntry();
  const quantityRef = useRef<HTMLInputElement>(null);
  const [values, setValues] = useState<FormState>({
    worker_id: entry?.worker_id ?? null,
    entry_date: entry?.entry_date ?? todayISO(),
    length: entry ? Number(entry.length_ft) : '',
    width: entry ? Number(entry.width_ft) : '',
    cuts: entry?.cuts ?? '',
    quantity: entry?.quantity ?? '',
    notes: entry?.notes ?? '',
  });
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setValues((v) => ({ ...v, [key]: value }));

  const input = toInput(values);
  const [debounced] = useDebouncedValue(input, 250);
  const preview = useQuery({
    queryKey: ['preview', debounced],
    queryFn: () => {
      const { notes: _notes, ...body } = debounced!;
      return previewWage(body);
    },
    enabled: debounced !== null,
    meta: { silent: true },
    staleTime: 0,
  });
  const shownPreview = input && debounced && preview.data ? preview.data : null;

  const submit = () => {
    if (!input) return;
    const workerName = workers.find((w) => w.id === input.worker_id)?.name_en ?? '';
    save.mutate(
      { id: entry?.id, body: input },
      {
        onSuccess: (saved) => {
          notifySaved(
            t('production.savedFor', { name: workerName, wage: formatMoney(saved.wage) }),
          );
          if (onDone) onDone();
          else {
            // Keep worker, date and size for fast repeat entries; clear what changes most.
            setValues((v) => ({ ...v, quantity: '', notes: '' }));
            quantityRef.current?.focus();
          }
        },
      },
    );
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <Stack gap="sm">
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Select
            label={t('production.worker')}
            placeholder={workers.length ? t('production.selectWorker') : t('production.noWorkersYet')}
            required
            searchable
            data={workerOptions(workers, i18n.language)}
            value={values.worker_id}
            onChange={(v) => set('worker_id', v)}
            nothingFoundMessage={t('workers.noMatch')}
          />
          <DateField
            label={t('production.entryDate')}
            required
            maxDate={todayISO()}
            value={values.entry_date}
            onChange={(v) => set('entry_date', v)}
          />
        </SimpleGrid>
        <SimpleGrid cols={{ base: 2, sm: 4 }}>
          <NumberInput
            label={t('production.length')}
            required
            min={0}
            decimalScale={3}
            value={values.length}
            onChange={(v) => set('length', v)}
          />
          <NumberInput
            label={t('production.width')}
            required
            min={0}
            decimalScale={3}
            value={values.width}
            onChange={(v) => set('width', v)}
          />
          <NumberInput
            label={t('production.cuts')}
            required
            min={0}
            allowDecimal={false}
            value={values.cuts}
            onChange={(v) => set('cuts', v)}
          />
          <NumberInput
            label={t('production.quantity')}
            required
            min={1}
            allowDecimal={false}
            ref={quantityRef}
            value={values.quantity}
            onChange={(v) => set('quantity', v)}
          />
        </SimpleGrid>
        <TextInput
          label={`${t('common.notes')} (${t('common.optional')})`}
          value={values.notes}
          onChange={(e) => set('notes', e.currentTarget.value)}
        />

        {shownPreview && shownPreview.missing_rates.length > 0 && (
          <MissingRateAlert components={shownPreview.missing_rates} />
        )}

        <Group justify="space-between" align="center" wrap="wrap">
          <div>
            {shownPreview && (
              <Group gap="lg">
                <Text size="sm" c="dimmed">
                  {t('production.previewArea', { area: formatNumber(shownPreview.area_sqft) })}
                </Text>
                {shownPreview.wage !== null && (
                  <Text size="lg" fw={700}>
                    {t('production.wage')}: {formatMoney(shownPreview.wage)}
                  </Text>
                )}
              </Group>
            )}
          </div>
          <Group gap="sm">
            {onDone && (
              <Button variant="default" onClick={onDone}>
                {t('common.cancel')}
              </Button>
            )}
            <Button type="submit" size="md" loading={save.isPending} disabled={!input}>
              {entry ? t('common.save') : t('production.saveEntry')}
            </Button>
          </Group>
        </Group>
      </Stack>
    </form>
  );
}

function MissingRateAlert({ components }: { components: RateComponent[] }) {
  const { t } = useTranslation();
  return (
    <Alert color="orange" variant="light" icon={<IconAlertTriangle />}>
      {t('production.missingRate', {
        components: components.map((c) => t(`components.${c}`)).join(', '),
      })}{' '}
      <Anchor component={Link} to="/rates" size="sm">
        {t('production.setRates')}
      </Anchor>
    </Alert>
  );
}
