/** Machines & rates: each machine's name, rates, loader and size table. */

import {
  Accordion,
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { modals } from '@mantine/modals';
import { IconInfoCircle, IconPencil, IconPlus, IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  useDeleteLoaderAssignment,
  useDeleteRate,
  useDeleteSize,
  useLoaderAssignments,
  useMachines,
  useRates,
  useSaveLoaderAssignment,
  useSaveRate,
  useSaveSize,
  useSizes,
  useUpdateMachine,
  useWorkers,
} from '../api/hooks';
import type {
  LoaderAssignment,
  Machine,
  MachineSize,
  Rate,
  RateComponent,
  Role,
  Worker,
} from '../api/types';
import { DateField, PageHeader, notifySaved } from '../components/common';
import { notifyResult } from '../components/Sync';
import { localName } from '../i18n';
import { componentLabel } from '../lib/entryText';
import { formatDate, formatNumber, formatRate, todayISO } from '../lib/format';
import { useHubState } from '../lib/hub';
import {
  allowedComponents,
  battiOf,
  componentUnit,
  loaderOn,
  roleComponents,
  sizeLabel,
  usesSizeTable,
} from '../lib/wages';

/** "Cutting", "Polish, 4 batti", ... in the app's language. */
export function useComponentLabel() {
  const { t } = useTranslation();
  return (component: RateComponent) => componentLabel(t, component);
}

function currentRate(rates: Rate[], machineId: string, component: RateComponent, on: string) {
  let best: Rate | null = null;
  for (const r of rates) {
    if (r.machine_id !== machineId || r.component !== component || r.effective_from > on) continue;
    if (!best || r.effective_from > best.effective_from) best = r;
  }
  return best;
}

type Dialog =
  | { kind: 'rename'; machine: Machine }
  | { kind: 'rate'; machine: Machine; rate?: Rate; component?: RateComponent }
  | { kind: 'loader'; machine: Machine; assignment?: LoaderAssignment }
  | { kind: 'size'; machine: Machine; size?: MachineSize }
  | null;

export default function RatesPage() {
  const { t } = useTranslation();
  const machines = useMachines(true);
  const [dialog, setDialog] = useState<Dialog>(null);

  const title = (() => {
    if (!dialog) return '';
    if (dialog.kind === 'rename') return t('machines.renameTitle');
    if (dialog.kind === 'rate') return dialog.rate ? t('rates.correctTitle') : t('rates.change');
    if (dialog.kind === 'loader') {
      return t('machines.changeLoaderTitle', { machine: dialog.machine.name_en });
    }
    return dialog.size ? t('machines.editSize') : t('machines.addSize');
  })();

  return (
    <>
      <PageHeader title={t('machines.title')} />
      <Alert icon={<IconInfoCircle />} variant="light" mb="md">
        {t('machines.intro')}
      </Alert>

      <Stack gap="lg">
        {(machines.data ?? []).map((m) => (
          <MachineCard key={m.id} machine={m} open={setDialog} />
        ))}
      </Stack>

      <Modal opened={dialog !== null} onClose={() => setDialog(null)} title={title}>
        {dialog?.kind === 'rename' && (
          <RenameForm machine={dialog.machine} onDone={() => setDialog(null)} />
        )}
        {dialog?.kind === 'rate' && (
          <RateForm
            machine={dialog.machine}
            existing={dialog.rate ?? null}
            initialComponent={dialog.component}
            onDone={() => setDialog(null)}
          />
        )}
        {dialog?.kind === 'loader' && (
          <LoaderForm
            machine={dialog.machine}
            existing={dialog.assignment ?? null}
            onDone={() => setDialog(null)}
          />
        )}
        {dialog?.kind === 'size' && (
          <SizeForm machine={dialog.machine} existing={dialog.size ?? null} onDone={() => setDialog(null)} />
        )}
      </Modal>
    </>
  );
}

function MachineCard({ machine, open }: { machine: Machine; open: (d: Dialog) => void }) {
  const { t, i18n } = useTranslation();
  const label = useComponentLabel();
  const rates = useRates().data ?? [];
  const assignments = (useLoaderAssignments().data ?? []).filter((a) => a.machine_id === machine.id);
  const workers = useWorkers(true).data ?? [];
  const sizes = (useSizes().data ?? []).filter((s) => s.machine_id === machine.id);
  const removeRate = useDeleteRate();
  const removeAssignment = useDeleteLoaderAssignment();
  const removeSize = useDeleteSize();
  const { reachable } = useHubState();
  const today = todayISO();

  const name = localName(machine.name_en, machine.name_hi, i18n.language);
  const other = name === machine.name_en ? machine.name_hi : machine.name_en;
  const history = rates.filter((r) => r.machine_id === machine.id);
  const workerName = (id: string | null) => {
    const w = workers.find((x) => x.id === id);
    return w ? localName(w.name_en, w.name_hi, i18n.language) : t('machines.noLoader');
  };
  const loaderId = loaderOn(assignments, machine.id, today);
  const loader = workers.find((w) => w.id === loaderId);

  // Table polish shows the batti counts that have a rate (plus "add a batti rate").
  const shown = (role: Role) =>
    roleComponents(machine.kind, role).filter(
      (c) => battiOf(c) === null || history.some((r) => r.component === c),
    );
  const unitText = (c: RateComponent) =>
    componentUnit(machine.kind, c) === 'rft' ? t('machines.perRft') : t('machines.perSqft');

  const rateCard = (c: RateComponent) => {
    const cur = currentRate(rates, machine.id, c, today);
    return (
      <Card
        key={c}
        bg="var(--mantine-color-gray-0)"
        radius="md"
        p="sm"
        style={{ cursor: 'pointer' }}
        onClick={() => open({ kind: 'rate', machine, component: c })}
      >
        <Text size="sm" c="dimmed">
          {label(c)}
        </Text>
        {cur ? (
          <>
            <Text fz={22} fw={700} className="num" ta="left">
              {formatRate(cur.rate)}
              <Text span size="sm" c="dimmed" fw={400}>
                {' '}
                {unitText(c)}
              </Text>
            </Text>
            <Text size="xs" c="dimmed">
              {t('rates.since', { date: formatDate(cur.effective_from) })}
            </Text>
          </>
        ) : (
          <Badge color="orange" variant="light" mt={6}>
            {t('rates.notSet')}
          </Badge>
        )}
      </Card>
    );
  };

  const confirm = (title: string, body: string, onConfirm: () => void) =>
    modals.openConfirmModal({
      title,
      children: <Text size="sm">{body}</Text>,
      labels: { confirm: t('common.delete'), cancel: t('common.cancel') },
      confirmProps: { color: 'red' },
      onConfirm,
    });
  const deleted = { onSuccess: () => notifySaved(t('common.deleted')) };

  return (
    <Card withBorder opacity={machine.is_active ? 1 : 0.7}>
      <Group justify="space-between" mb="sm" wrap="wrap">
        <div>
          <Group gap="xs">
            <Title order={3}>{name}</Title>
            {!machine.is_active && <Badge color="gray">{t('machines.notInUse')}</Badge>}
          </Group>
          {other && (
            <Text size="sm" c="dimmed">
              {other}
            </Text>
          )}
        </div>
        <Group gap="xs">
          <Button variant="default" onClick={() => open({ kind: 'rename', machine })}>
            {t('machines.rename')}
          </Button>
          <Button onClick={() => open({ kind: 'rate', machine })}>{t('rates.change')}</Button>
        </Group>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
        <Stack gap="xs">
          <Text fw={600}>{t('machines.operatorRates')}</Text>
          <SimpleGrid cols={{ base: 2, xs: 2 }} spacing="xs">
            {shown('operator').map(rateCard)}
          </SimpleGrid>
          {machine.kind === 'table_polish' && (
            <Button
              variant="subtle"
              size="xs"
              leftSection={<IconPlus size={14} />}
              onClick={() => open({ kind: 'rate', machine, component: 'polish_3' })}
              style={{ alignSelf: 'flex-start' }}
            >
              {t('machines.addBatti')}
            </Button>
          )}
        </Stack>
        <Stack gap="xs">
          <Group justify="space-between">
            <Text fw={600}>{t('machines.loaderRates')}</Text>
            <Button size="xs" variant="light" onClick={() => open({ kind: 'loader', machine })}>
              {t('machines.changeLoader')}
            </Button>
          </Group>
          <Card bg="var(--mantine-color-gray-0)" radius="md" p="sm">
            <Text size="sm" c="dimmed">
              {t('machines.loaderNow')}
            </Text>
            <Text fw={700} fz="lg" c={loader ? undefined : 'orange'}>
              {workerName(loaderId)}
            </Text>
            {loader?.is_archived && (
              <Text size="xs" c="orange">
                {t('machines.archivedLoader', { name: loader.name_en })}
              </Text>
            )}
          </Card>
          <SimpleGrid cols={{ base: 2, xs: 2 }} spacing="xs">
            {shown('loader').map(rateCard)}
          </SimpleGrid>
        </Stack>
      </SimpleGrid>

      {usesSizeTable(machine.kind) && (
        <Stack gap={4} mt="lg">
          <Group justify="space-between">
            <Text fw={600}>{t('machines.sizes')}</Text>
            <Button
              size="xs"
              variant="light"
              leftSection={<IconPlus size={14} />}
              onClick={() => open({ kind: 'size', machine })}
            >
              {t('machines.addSize')}
            </Button>
          </Group>
          <Text size="xs" c="dimmed">
            {machine.kind === 'single_cutting' ? t('machines.sizesHelpSingle') : t('machines.sizesHelpDouble')}
          </Text>
          <Table.ScrollContainer minWidth={420}>
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>
                    {t('production.size')} ({machine.kind === 'single_cutting' ? t('units.in') : t('units.ft')})
                  </Table.Th>
                  <Table.Th className="num">{t('machines.rftPerPiece')}</Table.Th>
                  <Table.Th className="num">{t('machines.sqftPerPiece')}</Table.Th>
                  <Table.Th w={80} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {sizes.map((s) => (
                  <Table.Tr key={s.id}>
                    <Table.Td>{sizeLabel(s.length, s.width)}</Table.Td>
                    <Table.Td className="num">{formatNumber(s.rft)}</Table.Td>
                    <Table.Td className="num">{formatNumber(s.sqft)}</Table.Td>
                    <Table.Td>
                      <Group gap={4} wrap="nowrap">
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          aria-label={t('common.edit')}
                          disabled={!reachable}
                          title={reachable ? t('common.edit') : t('sync.needsLaptop')}
                          onClick={() => open({ kind: 'size', machine, size: s })}
                        >
                          <IconPencil size={16} />
                        </ActionIcon>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          aria-label={t('common.delete')}
                          disabled={!reachable}
                          title={reachable ? t('common.delete') : t('sync.needsLaptop')}
                          onClick={() =>
                            confirm(t('machines.deleteSizeTitle'), t('machines.deleteSizeBody'), () =>
                              removeSize.mutate(s.id, deleted),
                            )
                          }
                        >
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Stack>
      )}

      <Accordion variant="contained" mt="lg" multiple>
        <Accordion.Item value="rates">
          <Accordion.Control>{t('rates.history')}</Accordion.Control>
          <Accordion.Panel>
            {history.length === 0 ? (
              <Text size="sm" c="dimmed">
                {t('rates.noHistory')}
              </Text>
            ) : (
              <Table.ScrollContainer minWidth={480}>
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{t('machines.rateFor')}</Table.Th>
                      <Table.Th>{t('rates.effectiveFrom')}</Table.Th>
                      <Table.Th className="num">{t('rates.rate')}</Table.Th>
                      <Table.Th>{t('rates.note')}</Table.Th>
                      <Table.Th w={80} />
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {history.map((r) => (
                      <Table.Tr key={r.id}>
                        <Table.Td>{label(r.component)}</Table.Td>
                        <Table.Td>{formatDate(r.effective_from)}</Table.Td>
                        <Table.Td className="num">
                          {formatRate(r.rate)} {unitText(r.component)}
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm" c="dimmed" lineClamp={1}>
                            {r.note ?? ''}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          <Group gap={4} wrap="nowrap">
                            <ActionIcon
                              variant="subtle"
                              color="gray"
                              aria-label={t('rates.correct')}
                              disabled={!reachable}
                              title={reachable ? t('rates.correct') : t('sync.needsLaptop')}
                              onClick={() => open({ kind: 'rate', machine, rate: r })}
                            >
                              <IconPencil size={16} />
                            </ActionIcon>
                            <ActionIcon
                              variant="subtle"
                              color="red"
                              aria-label={t('common.delete')}
                              disabled={!reachable}
                              title={reachable ? t('common.delete') : t('sync.needsLaptop')}
                              onClick={() =>
                                confirm(t('rates.deleteTitle'), t('rates.deleteBody'), () =>
                                  removeRate.mutate(r.id, deleted),
                                )
                              }
                            >
                              <IconTrash size={16} />
                            </ActionIcon>
                          </Group>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            )}
          </Accordion.Panel>
        </Accordion.Item>
        <Accordion.Item value="loaders">
          <Accordion.Control>{t('machines.loaderHistory')}</Accordion.Control>
          <Accordion.Panel>
            {assignments.length === 0 ? (
              <Text size="sm" c="dimmed">
                {t('machines.noLoader')}
              </Text>
            ) : (
              <Table>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('machines.loaderFrom')}</Table.Th>
                    <Table.Th>{t('production.loader')}</Table.Th>
                    <Table.Th>{t('rates.note')}</Table.Th>
                    <Table.Th w={80} />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {assignments.map((a) => (
                    <Table.Tr key={a.id}>
                      <Table.Td>{formatDate(a.effective_from)}</Table.Td>
                      <Table.Td>{workerName(a.worker_id)}</Table.Td>
                      <Table.Td>
                        <Text size="sm" c="dimmed" lineClamp={1}>
                          {a.note ?? ''}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Group gap={4} wrap="nowrap">
                          <ActionIcon
                            variant="subtle"
                            color="gray"
                            aria-label={t('rates.correct')}
                            disabled={!reachable}
                            title={reachable ? t('rates.correct') : t('sync.needsLaptop')}
                            onClick={() => open({ kind: 'loader', machine, assignment: a })}
                          >
                            <IconPencil size={16} />
                          </ActionIcon>
                          <ActionIcon
                            variant="subtle"
                            color="red"
                            aria-label={t('common.delete')}
                            disabled={!reachable}
                            title={reachable ? t('common.delete') : t('sync.needsLaptop')}
                            onClick={() =>
                              confirm(t('machines.deleteLoaderTitle'), t('machines.deleteLoaderBody'), () =>
                                removeAssignment.mutate(a.id, deleted),
                              )
                            }
                          >
                            <IconTrash size={16} />
                          </ActionIcon>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Card>
  );
}

function FormButtons({ onDone, loading, disabled }: { onDone: () => void; loading: boolean; disabled: boolean }) {
  const { t } = useTranslation();
  return (
    <Group justify="flex-end">
      <Button variant="default" onClick={onDone}>
        {t('common.cancel')}
      </Button>
      <Button type="submit" loading={loading} disabled={disabled}>
        {t('common.save')}
      </Button>
    </Group>
  );
}

function RenameForm({ machine, onDone }: { machine: Machine; onDone: () => void }) {
  const { t } = useTranslation();
  const save = useUpdateMachine();
  const [nameEn, setNameEn] = useState(machine.name_en);
  const [nameHi, setNameHi] = useState(machine.name_hi ?? '');
  const [active, setActive] = useState(machine.is_active);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(
          { id: machine.id, name_en: nameEn.trim(), name_hi: nameHi.trim() || null, is_active: active },
          {
            onSuccess: () => {
              notifySaved(t('common.saved'));
              onDone();
            },
          },
        );
      }}
    >
      <Stack>
        <TextInput label={t('machines.nameEn')} required data-autofocus value={nameEn} onChange={(e) => setNameEn(e.currentTarget.value)} />
        <TextInput label={t('machines.nameHi')} lang="hi" value={nameHi} onChange={(e) => setNameHi(e.currentTarget.value)} />
        <Switch
          label={active ? t('machines.inUse') : t('machines.notInUse')}
          checked={active}
          onChange={(e) => setActive(e.currentTarget.checked)}
        />
        <FormButtons onDone={onDone} loading={save.isPending} disabled={!nameEn.trim()} />
      </Stack>
    </form>
  );
}

function RateForm({
  machine,
  existing,
  initialComponent,
  onDone,
}: {
  machine: Machine;
  existing: Rate | null;
  initialComponent?: RateComponent;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const label = useComponentLabel();
  const save = useSaveRate();
  const components = allowedComponents(machine.kind);
  const [component, setComponent] = useState<RateComponent>(
    existing?.component ?? initialComponent ?? components[0],
  );
  const [rate, setRate] = useState<string | number>(existing ? Number(existing.rate) : '');
  const [from, setFrom] = useState<string | null>(existing?.effective_from ?? todayISO());
  const [note, setNote] = useState(existing?.note ?? '');
  const unit = componentUnit(machine.kind, component) === 'rft' ? t('machines.perRft') : t('machines.perSqft');
  const valid = rate !== '' && Number(rate) >= 0 && from;

  const submit = () => {
    if (!valid) return;
    const common = { rate: String(rate), effective_from: from!, note: note || null };
    const text = `${machine.name_en} · ${label(component)} ₹${rate} · ${formatDate(from, 'short')}`;
    save.mutate(
      existing
        ? { id: existing.id, body: common, label: text }
        : { body: { ...common, machine_id: machine.id, component }, label: text },
      {
        onSuccess: (r) => {
          notifyResult(r, t('common.saved'));
          onDone();
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
      <Stack>
        {existing && (
          <Alert color="orange" variant="light">
            {t('rates.correctWarning')}
          </Alert>
        )}
        {!existing && (
          <Select
            label={t('machines.rateFor')}
            allowDeselect={false}
            value={component}
            onChange={(v) => v && setComponent(v)}
            data={[
              {
                group: t('machines.operatorRates'),
                items: roleComponents(machine.kind, 'operator').map((c) => ({ value: c, label: label(c) })),
              },
              {
                group: t('machines.loaderRates'),
                items: roleComponents(machine.kind, 'loader').map((c) => ({ value: c, label: label(c) })),
              },
            ]}
          />
        )}
        <NumberInput
          label={`${t('rates.rate')} ${unit}`}
          required
          data-autofocus
          min={0}
          decimalScale={4}
          prefix="₹ "
          value={rate}
          onChange={setRate}
        />
        <DateField
          label={t('rates.effectiveFrom')}
          description={existing ? undefined : t('rates.effectiveHelp')}
          required
          value={from}
          onChange={setFrom}
        />
        <TextInput
          label={`${t('rates.note')} (${t('common.optional')})`}
          value={note}
          onChange={(e) => setNote(e.currentTarget.value)}
        />
        <FormButtons onDone={onDone} loading={save.isPending} disabled={!valid} />
      </Stack>
    </form>
  );
}

function LoaderForm({
  machine,
  existing,
  onDone,
}: {
  machine: Machine;
  existing: LoaderAssignment | null;
  onDone: () => void;
}) {
  const { t, i18n } = useTranslation();
  const save = useSaveLoaderAssignment();
  const workers = useWorkers(true).data ?? [];
  const loaders = workers.filter(
    (w: Worker) => w.worker_type.role === 'loader' && (!w.is_archived || w.id === existing?.worker_id),
  );
  const NONE = '__none__';
  const [worker, setWorker] = useState<string>(existing ? (existing.worker_id ?? NONE) : '');
  const [from, setFrom] = useState<string | null>(existing?.effective_from ?? todayISO());
  const [note, setNote] = useState(existing?.note ?? '');
  const valid = Boolean(worker && from);

  const submit = () => {
    if (!valid) return;
    const body = { worker_id: worker === NONE ? null : worker, effective_from: from!, note: note || null };
    const who = workers.find((w) => w.id === body.worker_id)?.name_en ?? t('machines.noLoader');
    const text = `${machine.name_en} · ${who} · ${formatDate(from, 'short')}`;
    save.mutate(
      existing
        ? { id: existing.id, body, label: text }
        : { body: { ...body, machine_id: machine.id }, label: text },
      {
        onSuccess: (r) => {
          notifyResult(r, t('common.saved'));
          onDone();
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
      <Stack>
        {existing && (
          <Alert color="orange" variant="light">
            {t('machines.loaderCorrectWarning')}
          </Alert>
        )}
        {loaders.length === 0 && (
          <Alert color="blue" variant="light">
            {t('machines.noLoaders')}
          </Alert>
        )}
        <Select
          label={t('production.loader')}
          required
          searchable
          data-autofocus
          value={worker || null}
          onChange={(v) => setWorker(v ?? '')}
          data={[
            ...loaders.map((w) => ({ value: w.id, label: localName(w.name_en, w.name_hi, i18n.language) })),
            { value: NONE, label: t('machines.noLoader') },
          ]}
        />
        <DateField
          label={t('machines.loaderFrom')}
          description={existing ? undefined : t('machines.loaderFromHelp')}
          required
          value={from}
          onChange={setFrom}
        />
        <TextInput
          label={`${t('rates.note')} (${t('common.optional')})`}
          value={note}
          onChange={(e) => setNote(e.currentTarget.value)}
        />
        <FormButtons onDone={onDone} loading={save.isPending} disabled={!valid} />
      </Stack>
    </form>
  );
}

function SizeForm({
  machine,
  existing,
  onDone,
}: {
  machine: Machine;
  existing: MachineSize | null;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const save = useSaveSize();
  const num = (v: string | undefined) => (v === undefined ? '' : Number(v));
  const [length, setLength] = useState<string | number>(num(existing?.length));
  const [width, setWidth] = useState<string | number>(num(existing?.width));
  const [rft, setRft] = useState<string | number>(num(existing?.rft));
  const [sqft, setSqft] = useState<string | number>(num(existing?.sqft));
  const unit = machine.kind === 'single_cutting' ? t('units.in') : t('units.ft');
  const positive = (v: string | number) => v !== '' && Number(v) > 0;
  const valid = [length, width, rft, sqft].every(positive);

  const submit = () => {
    if (!valid) return;
    const body = { length: String(length), width: String(width), rft: String(rft), sqft: String(sqft) };
    const text = `${machine.name_en} · ${sizeLabel(body.length, body.width)}`;
    save.mutate(
      existing
        ? { id: existing.id, body, label: text }
        : { body: { ...body, machine_id: machine.id }, label: text },
      {
        onSuccess: (r) => {
          notifyResult(r, t('common.saved'));
          onDone();
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
      <Stack>
        {existing && (
          <Text size="sm" c="dimmed">
            {t('machines.sizeChangeNote')}
          </Text>
        )}
        <Group grow>
          <NumberInput label={`${t('machines.length')} (${unit})`} required data-autofocus min={0} decimalScale={3} value={length} onChange={setLength} />
          <NumberInput label={`${t('machines.width')} (${unit})`} required min={0} decimalScale={3} value={width} onChange={setWidth} />
        </Group>
        <Group grow>
          <NumberInput label={t('machines.rftPerPiece')} required min={0} decimalScale={3} value={rft} onChange={setRft} />
          <NumberInput label={t('machines.sqftPerPiece')} required min={0} decimalScale={3} value={sqft} onChange={setSqft} />
        </Group>
        <FormButtons onDone={onDone} loading={save.isPending} disabled={!valid} />
      </Stack>
    </form>
  );
}
