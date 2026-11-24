import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Checkbox,
  Chip,
  Group,
  Modal,
  NumberInput,
  Pagination,
  SegmentedControl,
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
  useLoaderAssignments,
  useMachines,
  useProduction,
  useRates,
  useSaveEntry,
  useSettings,
  useSizes,
} from '../api/hooks';
import { usePendingProduction, useWorkersWithPending } from '../api/pending';
import type {
  LoaderAssignment,
  Machine,
  MachineSize,
  ProductionEntry,
  ProductionInput,
  Rate,
  RateComponent,
  Shift,
  WagePreview,
  Worker,
} from '../api/types';
import { PendingForEntity, notifyResult } from '../components/Sync';
import {
  DateField,
  PageHeader,
  PeriodPicker,
  WorkerName,
  periodFromPreset,
  workerOptions,
  type PeriodValue,
} from '../components/common';
import { localName } from '../i18n';
import { formatDate, formatMoney, formatNumber, todayISO } from '../lib/format';
import { useHubState } from '../lib/hub';
import { defaultPreset } from '../lib/periods';
import {
  battiOf,
  calculateWage,
  isShiftPaid,
  loaderOn,
  ratesFor,
  resolvePiece,
  sizeLabel,
  splittingSqft,
  totalOf,
} from '../lib/wages';
import { useComponentLabel } from './RatesPage';
import { entryDetails, entrySize, machineOptions } from '../lib/entryText';

const LAST_MACHINE = 'fms.lastMachine';

function rememberedMachine(): string | null {
  try {
    return localStorage.getItem(LAST_MACHINE);
  } catch {
    return null;
  }
}

function rememberMachine(id: string) {
  try {
    localStorage.setItem(LAST_MACHINE, id);
  } catch {
    /* storage unavailable */
  }
}

/** How a change is described in the "waiting to sync" list. */
function entryLabel(
  e: Pick<ProductionInput, 'entry_date' | 'quantity'> & { size: string; shift?: Shift | null },
  w: Worker | undefined,
  m: Machine | undefined,
): string {
  const what = e.shift ? `${e.shift} shift` : `${e.size} × ${e.quantity}`;
  return `${w?.name_en ?? '?'} · ${formatDate(e.entry_date, 'short')} · ${m?.name_en ?? ''} · ${what}`;
}

/** The wage preview worked out on this device (same formulas as the hub, tested to match). */
function localPreview(
  input: ProductionInput,
  machine: Machine,
  sizes: MachineSize[],
  rates: Rate[],
  assignments: LoaderAssignment[],
): WagePreview | null {
  const date = input.entry_date;
  if (isShiftPaid(machine.kind)) {
    const p = { piece_sqft: '0', piece_rft: null, cuts: 0, quantity: 1, batti: null };
    const op = calculateWage(machine.kind, 'operator', p, ratesFor(rates, machine.kind, 'operator', date));
    return {
      area_sqft: '0',
      rft_total: null,
      cutting_sqft: null,
      unloading_sqft: null,
      piece_sqft: '0',
      piece_rft: null,
      wage: op.total,
      wage_lines: [],
      missing_rates: op.missing,
      loader_worker_id: null,
      loader_wage: null,
      loader_wage_lines: [],
      loader_missing_rates: [],
      no_loader: false,
    };
  }
  const piece = resolvePiece(machine.kind, sizes, input);
  if (!piece) return null;
  const p = { ...piece, cuts: input.cuts, quantity: input.quantity, batti: input.batti };
  const op = calculateWage(machine.kind, 'operator', p, ratesFor(rates, machine.kind, 'operator', date));
  const ld = calculateWage(machine.kind, 'loader', p, ratesFor(rates, machine.kind, 'loader', date));
  const loader = input.loader_id ?? loaderOn(assignments, machine.id, date);
  const split = splittingSqft(machine.kind, p);
  return {
    area_sqft: totalOf(piece.piece_sqft, input.quantity),
    rft_total: piece.piece_rft === null ? null : totalOf(piece.piece_rft, input.quantity),
    cutting_sqft: split?.cutting ?? null,
    unloading_sqft: split?.unloading ?? null,
    piece_sqft: piece.piece_sqft,
    piece_rft: piece.piece_rft,
    wage: op.total,
    wage_lines: [],
    missing_rates: op.missing,
    loader_worker_id: loader,
    loader_wage: ld.total,
    loader_wage_lines: [],
    loader_missing_rates: ld.missing,
    no_loader: loader === null,
  };
}

const PAGE_SIZE = 50;
const NO_ENTRIES: ProductionEntry[] = [];

export default function ProductionPage() {
  const { t, i18n } = useTranslation();
  const settings = useSettings().data;
  const allWorkers = useWorkersWithPending(true);
  const machines = useMachines(true).data ?? [];
  const byId = useMemo(
    () => new Map((allWorkers.data ?? []).map((w) => [w.id, w])),
    [allWorkers.data],
  );
  const machineById = useMemo(() => new Map(machines.map((m) => [m.id, m])), [machines]);

  const [period, setPeriod] = useState<PeriodValue | null>(null);
  const activePeriod = period ?? periodFromPreset(defaultPreset(settings?.pay_period ?? 'half_month'));
  const [workerFilter, setWorkerFilter] = useState<string | null>(null);
  const [machineFilter, setMachineFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<ProductionEntry | null>(null);

  const entries = useProduction({
    start: activePeriod.start,
    end: activePeriod.end,
    worker_id: workerFilter ?? undefined,
    machine_id: machineFilter ?? undefined,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });
  const remove = useDeleteEntry();
  const { reachable } = useHubState();
  const name = (w: Worker | undefined) => (w ? localName(w.name_en, w.name_hi, i18n.language) : '');

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
      onConfirm: () =>
        remove.mutate(
          {
            id: e.id,
            label: entryLabel({ ...e, size: entrySize(e, t) }, w, machineById.get(e.machine_id)),
          },
          { onSuccess: (r) => notifyResult(r, t('common.deleted')) },
        ),
    });
  };

  // Entries made on this device that haven't reached the laptop yet are shown too.
  const serverItems = entries.data?.items ?? NO_ENTRIES;
  const pending = usePendingProduction(serverItems);
  const matches = (e: ProductionEntry) =>
    e.entry_date >= activePeriod.start &&
    e.entry_date <= activePeriod.end &&
    (!workerFilter || e.worker_id === workerFilter || e.loader_worker_id === workerFilter) &&
    (!machineFilter || e.machine_id === machineFilter);
  const notSent =
    page === 1
      ? pending.created
          .filter((e) => matches(e) && !serverItems.some((x) => x.id === e.id))
          .sort((a, b) => b.entry_date.localeCompare(a.entry_date))
      : [];
  const removed = serverItems.filter((e) => pending.deleted.has(e.id)).length;
  const rows: (ProductionEntry & { pending?: boolean })[] = [
    ...notSent,
    ...serverItems.filter((e) => !pending.deleted.has(e.id)).map((e) => pending.edited.get(e.id) ?? e),
  ];
  const total = (entries.data?.total ?? 0) + notSent.length - removed;
  const active = (allWorkers.data ?? []).filter((w) => !w.is_archived);
  const operators = active.filter((w) => w.worker_type.role === 'operator');

  return (
    <>
      <PageHeader title={t('production.title')} />

      <Card withBorder mb="lg">
        <Title order={4} mb={2}>
          {t('production.newEntry')}
        </Title>
        <Text size="sm" c="dimmed" mb="sm">
          {t('production.onlyOperators')}
        </Text>
        <EntryForm workers={operators} shiftWorkers={active} />
      </Card>

      <PendingForEntity entity="production" />

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
              w={220}
              data={workerOptions(allWorkers.data ?? [], i18n.language)}
              value={workerFilter}
              onChange={(v) => {
                setWorkerFilter(v);
                setPage(1);
              }}
            />
            <Select
              label={t('production.machine')}
              placeholder={t('production.filterMachine')}
              clearable
              w={220}
              data={machineOptions(machines, t, i18n.language)}
              value={machineFilter}
              onChange={(v) => {
                setMachineFilter(v);
                setPage(1);
              }}
            />
          </Group>
          {(entries.data || notSent.length > 0) && (
            <Text size="sm" c="dimmed">
              {t('production.count', { count: total })}
            </Text>
          )}
        </Group>

        {!entries.data && !reachable && notSent.length === 0 ? (
          // The laptop is away and this list was never saved on this device.
          <Text c="dimmed" ta="center" py="xl">
            {t('sync.notOnDevice')}
          </Text>
        ) : (entries.isSuccess || !reachable) && total === 0 ? (
          <Text c="dimmed" ta="center" py="xl">
            {t('production.noEntries')}
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={1100}>
            <Table highlightOnHover striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('common.date')}</Table.Th>
                  <Table.Th>{t('production.worker')}</Table.Th>
                  <Table.Th>{t('production.machine')}</Table.Th>
                  <Table.Th>{t('production.size')}</Table.Th>
                  <Table.Th className="num">{t('production.quantity')}</Table.Th>
                  <Table.Th className="num">
                    {t('production.area')} ({t('units.sqft')})
                  </Table.Th>
                  <Table.Th className="num">{t('production.cuttingSqft')}</Table.Th>
                  <Table.Th className="num">{t('production.unloadingSqft')}</Table.Th>
                  <Table.Th className="num">{t('production.wage')}</Table.Th>
                  <Table.Th>{t('production.loader')}</Table.Th>
                  <Table.Th w={80} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {rows.map((e) => {
                  const w = byId.get(e.worker_id);
                  const m = machineById.get(e.machine_id);
                  const loader = e.loader_worker_id ? byId.get(e.loader_worker_id) : undefined;
                  const details = entryDetails(e, t);
                  return (
                    <Table.Tr key={e.id}>
                      <Table.Td style={{ whiteSpace: 'nowrap' }}>
                        {formatDate(e.entry_date)}
                        {e.pending && (
                          <Badge display="block" mt={2} size="xs" color="gray" variant="light">
                            {t('sync.pending')}
                          </Badge>
                        )}
                      </Table.Td>
                      <Table.Td>{w && <WorkerName nameEn={w.name_en} nameHi={w.name_hi} />}</Table.Td>
                      <Table.Td>
                        <Text size="sm">{m ? localName(m.name_en, m.name_hi, i18n.language) : ''}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" style={{ whiteSpace: 'nowrap' }}>
                          {entrySize(e, t)}
                        </Text>
                        {details && (
                          <Text size="xs" c="dimmed">
                            {details}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td className="num">{e.shift ? '—' : e.quantity}</Table.Td>
                      <Table.Td className="num">{e.shift ? '—' : formatNumber(e.area_sqft)}</Table.Td>
                      <Table.Td className="num">
                        {e.cutting_sqft !== null ? formatNumber(e.cutting_sqft) : '—'}
                      </Table.Td>
                      <Table.Td className="num">
                        {e.unloading_sqft !== null ? formatNumber(e.unloading_sqft) : '—'}
                      </Table.Td>
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
                        {e.paid_as === 'loader' || e.shift ? null : e.no_loader ? (
                          <Badge color="orange" variant="light">
                            {t('machines.noLoader')}
                          </Badge>
                        ) : (
                          <Stack gap={0}>
                            <Text size="sm">{name(loader)}</Text>
                            {e.loader_id && (
                              <Text size="xs" c="orange">
                                {t('production.loaderAbsent')}
                              </Text>
                            )}
                            <Text size="xs" c="dimmed">
                              {e.loader_wage !== null ? formatMoney(e.loader_wage) : t('slip.rateMissing')}
                            </Text>
                          </Stack>
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
              (w) => (!w.is_archived && w.worker_type.role === 'operator') || w.id === editing.worker_id,
            )}
            shiftWorkers={(allWorkers.data ?? []).filter(
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
  machine_id: string | null;
  entry_date: string | null;
  length: number | string;
  width: number | string;
  size_id: string | null;
  cuts: number | string;
  batti: number | null;
  shift: Shift | null;
  quantity: number | string;
  fill_in: boolean;
  loader_id: string | null;
  notes: string;
}

function toInput(v: FormState, machine: Machine | undefined): ProductionInput | null {
  const n = (x: number | string) => (x === '' ? NaN : Number(x));
  if (!v.worker_id || !v.entry_date || !machine) return null;
  if (isShiftPaid(machine.kind)) {
    if (!v.shift) return null;
    return {
      worker_id: v.worker_id,
      machine_id: machine.id,
      entry_date: v.entry_date,
      length_ft: null,
      width_ft: null,
      size_id: null,
      cuts: 0,
      batti: null,
      shift: v.shift,
      quantity: 1,
      loader_id: null,
      notes: v.notes.trim() || null,
    };
  }
  if (!(n(v.quantity) >= 1)) return null;
  if (v.fill_in && !v.loader_id) return null;
  const base = {
    worker_id: v.worker_id,
    machine_id: machine.id,
    entry_date: v.entry_date,
    length_ft: null as string | null,
    width_ft: null as string | null,
    size_id: null as string | null,
    cuts: 0,
    batti: null as number | null,
    shift: null,
    quantity: Math.trunc(n(v.quantity)),
    loader_id: v.fill_in ? v.loader_id : null,
    notes: v.notes.trim() || null,
  };
  if (machine.kind === 'single_cutting') {
    return v.size_id ? { ...base, size_id: v.size_id } : null;
  }
  if (!(n(v.length) > 0) || !(n(v.width) > 0)) return null;
  const sized = { ...base, length_ft: String(v.length), width_ft: String(v.width) };
  if (machine.kind === 'block_cutting') {
    return n(v.cuts) >= 0 ? { ...sized, cuts: Math.trunc(n(v.cuts)) } : null;
  }
  if (machine.kind === 'table_polish') return v.batti ? { ...sized, batti: v.batti } : null;
  return sized;
}

function EntryForm({
  workers: operators,
  shiftWorkers,
  entry,
  onDone,
}: {
  workers: Worker[];
  /** Anyone can work a block cutter shift, loaders included. */
  shiftWorkers: Worker[];
  entry?: ProductionEntry;
  onDone?: () => void;
}) {
  const { t, i18n } = useTranslation();
  const label = useComponentLabel();
  const save = useSaveEntry();
  const quantityRef = useRef<HTMLInputElement>(null);
  const machines = useMachines(true).data ?? [];
  const usable = machines.filter((m) => m.is_active || m.id === entry?.machine_id);
  const sizes = useSizes().data ?? [];
  const rates = useRates().data;
  const assignments = useLoaderAssignments().data ?? [];
  const allWorkers = useWorkersWithPending(true).data ?? [];
  const remembered = rememberedMachine();
  const [values, setValues] = useState<FormState>({
    worker_id: entry?.worker_id ?? null,
    machine_id:
      entry?.machine_id ?? (usable.some((m) => m.id === remembered) ? remembered : null),
    entry_date: entry?.entry_date ?? todayISO(),
    length: entry?.length_ft ? Number(entry.length_ft) : '',
    width: entry?.width_ft ? Number(entry.width_ft) : '',
    size_id: entry?.size_id ?? null,
    cuts: entry ? entry.cuts : '',
    batti: entry?.batti ?? null,
    shift: entry?.shift ?? null,
    quantity: entry?.shift ? '' : (entry?.quantity ?? ''),
    fill_in: Boolean(entry?.loader_id),
    loader_id: entry?.loader_id ?? null,
    notes: entry?.notes ?? '',
  });
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setValues((v) => ({ ...v, [key]: value }));

  const machine = machines.find((m) => m.id === values.machine_id);
  const shiftPaid = machine ? isShiftPaid(machine.kind) : false;
  const workers = shiftPaid ? shiftWorkers : operators;
  const machineSizes = sizes.filter((s) => s.kind === machine?.kind);
  const name = (id: string | null) => {
    const w = allWorkers.find((x) => x.id === id);
    return w ? localName(w.name_en, w.name_hi, i18n.language) : '';
  };

  const { reachable } = useHubState();
  const input = toInput(values, machine);
  const [debounced] = useDebouncedValue(input, 250);
  const preview = useQuery({
    queryKey: ['preview', debounced],
    queryFn: () => {
      const { notes: _notes, ...body } = debounced!;
      return previewWage(body);
    },
    enabled: debounced !== null && reachable,
    meta: { silent: true },
    staleTime: 0,
  });
  const devicePreview = useMemo(
    () => (!reachable && input && machine && rates ? localPreview(input, machine, sizes, rates, assignments) : null),
    [reachable, input, machine, sizes, rates, assignments],
  );
  const shown = reachable ? (input && debounced && preview.data ? preview.data : null) : devicePreview;

  // The size as the owner typed it maps to a standard size (double edge) or not.
  const piece =
    machine && input ? resolvePiece(machine.kind, sizes, input) : null;
  const usualLoader =
    machine && values.entry_date ? loaderOn(assignments, machine.id, values.entry_date) : null;
  const loaders = allWorkers.filter((w) => w.worker_type.role === 'loader' && !w.is_archived);
  const battiChoices = (() => {
    const withRates = new Set(
      (rates ?? [])
        .filter((r) => r.kind === machine?.kind)
        .map((r) => battiOf(r.component))
        .filter((b): b is number => b !== null),
    );
    if (values.batti) withRates.add(values.batti);
    return [...(withRates.size ? withRates : new Set([1, 2, 4, 5]))].sort((a, b) => a - b);
  })();

  const submit = () => {
    if (!input) return;
    const w = workers.find((x) => x.id === input.worker_id);
    const size = machine && !shiftPaid ? entrySize({ ...input, size_label: piece?.size ? sizeLabel(piece.size.length, piece.size.width) : null }, t) : '';
    rememberMachine(input.machine_id);
    save.mutate(
      { id: entry?.id, body: input, label: entryLabel({ ...input, size }, w, machine) },
      {
        onSuccess: (result) => {
          notifyResult(
            result,
            t('production.savedFor', {
              name: w?.name_en ?? '',
              wage: formatMoney(result.data?.wage ?? null),
            }),
          );
          if (onDone) onDone();
          else if (shiftPaid) {
            // Next worker on the same shift.
            setValues((v) => ({ ...v, worker_id: null, notes: '' }));
          } else {
            // Keep worker, machine, date and size for fast repeat entries.
            setValues((v) => ({ ...v, quantity: '', notes: '', fill_in: false, loader_id: null }));
            quantityRef.current?.focus();
          }
        },
      },
    );
  };

  const quantityField = (
    <NumberInput
      label={t('production.quantity')}
      required
      min={1}
      allowDecimal={false}
      ref={quantityRef}
      value={values.quantity}
      onChange={(v) => set('quantity', v)}
    />
  );
  const sizeFields = (
    <>
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
    </>
  );
  const missing = [...(shown?.missing_rates ?? []), ...(shown?.loader_missing_rates ?? [])];

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <Stack gap="sm">
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
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
          <Select
            label={t('production.machine')}
            placeholder={t('production.selectMachine')}
            required
            allowDeselect={false}
            data={machineOptions(usable, t, i18n.language)}
            value={values.machine_id}
            onChange={(v) =>
              setValues((s) => {
                // Machines of the same type share sizes and batti rates: keep them.
                const next = machines.find((m) => m.id === v);
                const sameKind = next?.kind === machine?.kind;
                // Only operators work piece-rate machines; anyone can work a shift.
                const allowed = next && isShiftPaid(next.kind) ? shiftWorkers : operators;
                const keepWorker = allowed.some((w) => w.id === s.worker_id);
                return {
                  ...s,
                  machine_id: v,
                  size_id: sameKind ? s.size_id : null,
                  worker_id: keepWorker ? s.worker_id : null,
                };
              })
            }
          />
          <DateField
            label={t('production.entryDate')}
            required
            maxDate={todayISO()}
            value={values.entry_date}
            onChange={(v) => set('entry_date', v)}
          />
        </SimpleGrid>

        {machine?.kind === 'double_edge' && machineSizes.length > 0 && (
          <Chip.Group
            value={piece?.size ? piece.size.id : ''}
            onChange={(id) => {
              const s = machineSizes.find((x) => x.id === id);
              if (s) setValues((v) => ({ ...v, length: Number(s.length), width: Number(s.width) }));
            }}
          >
            <Group gap="xs">
              {machineSizes.map((s) => (
                <Chip key={s.id} value={s.id}>
                  {sizeLabel(s.length, s.width)} {t('units.ft')}
                </Chip>
              ))}
            </Group>
          </Chip.Group>
        )}

        {machine?.kind === 'table_polish' && (
          <Stack gap={4}>
            <Text size="sm" fw={500}>
              {t('production.batti')} <Text span c="red">*</Text>
            </Text>
            <SegmentedControl
              value={values.batti ? String(values.batti) : ''}
              onChange={(v) => set('batti', Number(v))}
              data={battiChoices.map((b) => ({ value: String(b), label: label(`polish_${b}`) }))}
              style={{ alignSelf: 'flex-start' }}
            />
          </Stack>
        )}

        {shiftPaid && (
          <Stack gap={4}>
            <Text size="sm" fw={500}>
              {t('production.shift')} <Text span c="red">*</Text>
            </Text>
            <SegmentedControl
              value={values.shift ?? ''}
              onChange={(v) => set('shift', v as Shift)}
              data={[
                { value: 'day', label: t('shifts.day') },
                { value: 'night', label: t('shifts.night') },
              ]}
              style={{ alignSelf: 'flex-start' }}
            />
            <Text size="xs" c="dimmed">
              {t('production.shiftHelp')}
            </Text>
          </Stack>
        )}

        {machine && !shiftPaid && (
          <SimpleGrid cols={{ base: 2, sm: 4 }}>
            {machine.kind === 'single_cutting' ? (
              <Select
                label={t('production.sizeIn')}
                placeholder={t('production.pickSize')}
                required
                searchable
                description={t('production.addSizeHint')}
                data={machineSizes.map((s) => ({ value: s.id, label: sizeLabel(s.length, s.width) }))}
                value={values.size_id}
                onChange={(v) => set('size_id', v)}
                style={{ gridColumn: 'span 2' }}
              />
            ) : (
              sizeFields
            )}
            {machine.kind === 'block_cutting' && (
              <NumberInput
                label={t('production.cuts')}
                required
                min={0}
                allowDecimal={false}
                value={values.cuts}
                onChange={(v) => set('cuts', v)}
              />
            )}
            {quantityField}
          </SimpleGrid>
        )}

        {piece && machine?.kind === 'double_edge' && piece.piece_rft && (
          <Text size="xs" c="dimmed">
            {t(piece.size ? 'production.tableSize' : 'production.trueSize', {
              rft: formatNumber(piece.piece_rft),
              sqft: formatNumber(piece.piece_sqft),
            })}
          </Text>
        )}

        {machine && !shiftPaid && (
          <Group gap="md" align="flex-end" wrap="wrap">
            {values.fill_in ? (
              <Select
                label={t('production.whoLoaded')}
                description={t('production.fillInHelp')}
                required
                searchable
                w={260}
                data={loaders.map((w) => ({ value: w.id, label: localName(w.name_en, w.name_hi, i18n.language) }))}
                value={values.loader_id}
                onChange={(v) => set('loader_id', v)}
              />
            ) : usualLoader ? (
              <Text size="sm">{t('production.usualLoader', { name: name(usualLoader) })}</Text>
            ) : (
              <Alert color="orange" variant="light" p="xs" icon={<IconAlertTriangle size={16} />}>
                <Text size="sm">{t('production.noLoader')}</Text>
              </Alert>
            )}
            <Checkbox
              label={t('production.fillIn')}
              checked={values.fill_in}
              onChange={(e) => {
                const checked = e.currentTarget.checked;
                setValues((v) => ({ ...v, fill_in: checked, loader_id: checked ? v.loader_id : null }));
              }}
            />
          </Group>
        )}

        <TextInput
          label={`${t('common.notes')} (${t('common.optional')})`}
          value={values.notes}
          onChange={(e) => set('notes', e.currentTarget.value)}
        />

        {missing.length > 0 && <MissingRateAlert components={missing} />}

        <Group justify="space-between" align="center" wrap="wrap">
          <div>
            {shown && (
              <Group gap="lg" align="baseline" wrap="wrap">
                {!shiftPaid && (
                  <Text size="sm" c="dimmed">
                    {t('production.previewArea', { area: formatNumber(shown.area_sqft) })}
                    {shown.rft_total && ` · ${t('production.previewRft', { rft: formatNumber(shown.rft_total) })}`}
                    {shown.cutting_sqft &&
                      ` · ${t('production.cuttingSqft')}: ${formatNumber(shown.cutting_sqft)}` +
                        ` · ${t('production.unloadingSqft')}: ${formatNumber(shown.unloading_sqft)}`}
                  </Text>
                )}
                {shown.wage !== null && (
                  <Text size="lg" fw={700}>
                    {t(shiftPaid ? 'production.shiftWage' : 'production.operatorWage')}:{' '}
                    {formatMoney(shown.wage)}
                  </Text>
                )}
                {shown.loader_wage !== null && !shown.no_loader && (
                  <Text size="md" fw={600}>
                    {t('production.loaderWage')}: {formatMoney(shown.loader_wage)}
                  </Text>
                )}
                {!reachable && (
                  <Text span size="xs" c="dimmed">
                    ({t('sync.deviceCalc')})
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
  const label = useComponentLabel();
  return (
    <Alert color="orange" variant="light" icon={<IconAlertTriangle />}>
      {t('production.missingRate', { components: [...new Set(components)].map(label).join(', ') })}{' '}
      <Anchor component={Link} to="/rates" size="sm">
        {t('production.setRates')}
      </Anchor>
    </Alert>
  );
}
