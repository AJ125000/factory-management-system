/** Machines & rates: each machine type's rates and size table, and its machines with their loaders. */

import {
  Accordion,
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Menu,
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
import {
  IconDots,
  IconInfoCircle,
  IconPencil,
  IconPlus,
  IconTrash,
  IconUserCog,
} from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  fetchMachineDeleteImpact,
  useCreateMachine,
  useDeleteLoaderAssignment,
  useDeleteMachine,
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
  MachineKind,
  MachineSize,
  Rate,
  RateComponent,
  Role,
  Worker,
} from '../api/types';
import { DateField, PageHeader, notifyError, notifySaved } from '../components/common';
import { notifyResult } from '../components/Sync';
import { localName } from '../i18n';
import { MACHINE_KINDS, componentLabel } from '../lib/entryText';
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

function currentRate(rates: Rate[], kind: MachineKind, component: RateComponent, on: string) {
  let best: Rate | null = null;
  for (const r of rates) {
    if (r.kind !== kind || r.component !== component || r.effective_from > on) continue;
    if (!best || r.effective_from > best.effective_from) best = r;
  }
  return best;
}

type Dialog =
  | { kind: 'machine'; machineKind: MachineKind; machine: Machine | null }
  | { kind: 'rate'; machineKind: MachineKind; rate?: Rate; component?: RateComponent }
  | { kind: 'loader'; machine: Machine; assignment?: LoaderAssignment }
  | { kind: 'size'; machineKind: MachineKind; size?: MachineSize }
  | null;

export default function RatesPage() {
  const { t, i18n } = useTranslation();
  const machines = useMachines(true).data ?? [];
  const [dialog, setDialog] = useState<Dialog>(null);

  const title = (() => {
    if (!dialog) return '';
    if (dialog.kind === 'machine') {
      return dialog.machine
        ? t('machines.renameTitle')
        : t('machines.addMachineTitle', { type: t(`machineKinds.${dialog.machineKind}`) });
    }
    if (dialog.kind === 'rate') return dialog.rate ? t('rates.correctTitle') : t('rates.change');
    if (dialog.kind === 'loader') {
      return t('machines.changeLoaderTitle', {
        machine: localName(dialog.machine.name_en, dialog.machine.name_hi, i18n.language),
      });
    }
    return dialog.size ? t('machines.editSize') : t('machines.addSize');
  })();

  // "Table polish machine 3" for the next machine of a type.
  const suggestedName = (kind: MachineKind) => {
    const n = machines.filter((m) => m.kind === kind).length + 1;
    const base = machines.find((m) => m.kind === kind);
    const strip = (name: string | null | undefined) => (name ?? '').replace(/\s*\d+$/, '');
    return {
      en: `${strip(base?.name_en) || t(`machineKinds.${kind}`)} ${n}`,
      hi: base?.name_hi ? `${strip(base.name_hi)} ${n}` : '',
    };
  };

  return (
    <>
      <PageHeader title={t('machines.title')} />
      <Alert icon={<IconInfoCircle />} variant="light" mb="md">
        {t('machines.intro')}
      </Alert>

      <Stack gap="lg">
        {MACHINE_KINDS.map((kind) => (
          <TypeCard
            key={kind}
            kind={kind}
            machines={machines.filter((m) => m.kind === kind)}
            open={setDialog}
          />
        ))}
      </Stack>

      <Modal opened={dialog !== null} onClose={() => setDialog(null)} title={title}>
        {dialog?.kind === 'machine' && (
          <MachineForm
            machine={dialog.machine}
            kind={dialog.machineKind}
            suggestedName={suggestedName(dialog.machineKind)}
            onDone={() => setDialog(null)}
          />
        )}
        {dialog?.kind === 'rate' && (
          <RateForm
            kind={dialog.machineKind}
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
          <SizeForm kind={dialog.machineKind} existing={dialog.size ?? null} onDone={() => setDialog(null)} />
        )}
      </Modal>
    </>
  );
}

function TypeCard({
  kind,
  machines,
  open,
}: {
  kind: MachineKind;
  machines: Machine[];
  open: (d: Dialog) => void;
}) {
  const { t, i18n } = useTranslation();
  const label = useComponentLabel();
  const rates = useRates().data ?? [];
  const allAssignments = useLoaderAssignments().data ?? [];
  const workers = useWorkers(true).data ?? [];
  const sizes = (useSizes().data ?? []).filter((s) => s.kind === kind);
  const removeRate = useDeleteRate();
  const removeAssignment = useDeleteLoaderAssignment();
  const removeSize = useDeleteSize();
  const removeMachine = useDeleteMachine();
  const { reachable } = useHubState();
  const today = todayISO();

  const ids = new Set(machines.map((m) => m.id));
  const assignments = allAssignments.filter((a) => ids.has(a.machine_id));
  const history = rates.filter((r) => r.kind === kind);
  const local = (x: { name_en: string; name_hi: string | null } | undefined) =>
    x ? localName(x.name_en, x.name_hi, i18n.language) : '';
  const workerName = (id: string | null) =>
    local(workers.find((x) => x.id === id)) || t('machines.noLoader');

  // Table polish shows the batti counts that have a rate (plus "add a batti rate").
  const shown = (role: Role) =>
    roleComponents(kind, role).filter((c) => battiOf(c) === null || history.some((r) => r.component === c));
  const unitText = (c: RateComponent) =>
    componentUnit(kind, c) === 'rft' ? t('machines.perRft') : t('machines.perSqft');

  const rateCard = (c: RateComponent) => {
    const cur = currentRate(rates, kind, c, today);
    return (
      <Card
        key={c}
        bg="var(--mantine-color-gray-0)"
        radius="md"
        p="sm"
        style={{ cursor: 'pointer' }}
        onClick={() => open({ kind: 'rate', machineKind: kind, component: c })}
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

  const deleteMachine = async (m: Machine) => {
    let entries: number;
    try {
      entries = (await fetchMachineDeleteImpact(m.id)).production_entries;
    } catch (e) {
      notifyError(e);
      return;
    }
    if (entries > 0) {
      modals.open({
        title: t('machines.cantDeleteTitle', { name: local(m) }),
        children: <Text size="sm">{t('machines.cantDeleteBody', { count: entries })}</Text>,
      });
      return;
    }
    confirm(t('machines.deleteMachineTitle', { name: local(m) }), t('machines.deleteMachineBody'), () =>
      removeMachine.mutate(m.id, deleted),
    );
  };

  const actionProps = (titleKey: string) => ({
    disabled: !reachable,
    title: reachable ? t(titleKey) : t('sync.needsLaptop'),
  });

  return (
    <Card withBorder>
      <Group justify="space-between" mb="sm" wrap="wrap">
        <Title order={3}>{t(`machineKinds.${kind}`)}</Title>
        <Button onClick={() => open({ kind: 'rate', machineKind: kind })}>{t('rates.change')}</Button>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
        <Stack gap="xs">
          <Text fw={600}>{t('machines.operatorRates')}</Text>
          <SimpleGrid cols={2} spacing="xs">
            {shown('operator').map(rateCard)}
          </SimpleGrid>
          {kind === 'table_polish' && (
            <Button
              variant="subtle"
              size="xs"
              leftSection={<IconPlus size={14} />}
              onClick={() => open({ kind: 'rate', machineKind: kind, component: 'polish_3' })}
              style={{ alignSelf: 'flex-start' }}
            >
              {t('machines.addBatti')}
            </Button>
          )}
        </Stack>
        <Stack gap="xs">
          <Text fw={600}>{t('machines.loaderRates')}</Text>
          <SimpleGrid cols={2} spacing="xs">
            {shown('loader').map(rateCard)}
          </SimpleGrid>
        </Stack>
      </SimpleGrid>

      <Stack gap={4} mt="lg">
        <Group justify="space-between">
          <Text fw={600}>{t('machines.machinesOfType', { count: machines.filter((m) => m.is_active).length })}</Text>
          <Button
            size="xs"
            variant="light"
            leftSection={<IconPlus size={14} />}
            {...actionProps('machines.addMachine')}
            onClick={() => open({ kind: 'machine', machineKind: kind, machine: null })}
          >
            {t('machines.addMachine')}
          </Button>
        </Group>
        <Table.ScrollContainer minWidth={420}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('production.machine')}</Table.Th>
                <Table.Th>{t('machines.loaderNow')}</Table.Th>
                <Table.Th w={110} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {machines.map((m) => {
                const loaderId = loaderOn(allAssignments, m.id, today);
                const loader = workers.find((w) => w.id === loaderId);
                const other = local(m) === m.name_en ? m.name_hi : m.name_en;
                return (
                  <Table.Tr key={m.id} opacity={m.is_active ? 1 : 0.6}>
                    <Table.Td>
                      <Group gap={6}>
                        <Text size="sm" fw={500}>
                          {local(m)}
                        </Text>
                        {!m.is_active && (
                          <Badge size="xs" color="gray">
                            {t('machines.notInUse')}
                          </Badge>
                        )}
                      </Group>
                      {other && (
                        <Text size="xs" c="dimmed">
                          {other}
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c={loader ? undefined : 'orange'}>
                        {workerName(loaderId)}
                      </Text>
                      {loader?.is_archived && (
                        <Text size="xs" c="orange">
                          {t('machines.archivedLoader', { name: loader.name_en })}
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4} justify="flex-end" wrap="nowrap">
                        <Button
                          size="compact-xs"
                          variant="light"
                          leftSection={<IconUserCog size={14} />}
                          onClick={() => open({ kind: 'loader', machine: m })}
                        >
                          {t('machines.changeLoader')}
                        </Button>
                        <Menu position="bottom-end" withinPortal>
                          <Menu.Target>
                            <ActionIcon variant="subtle" color="gray" aria-label={t('common.actions')}>
                              <IconDots size={16} />
                            </ActionIcon>
                          </Menu.Target>
                          <Menu.Dropdown>
                            <Menu.Item
                              leftSection={<IconPencil size={14} />}
                              {...actionProps('machines.rename')}
                              onClick={() => open({ kind: 'machine', machineKind: kind, machine: m })}
                            >
                              {t('machines.rename')}
                            </Menu.Item>
                            <Menu.Item
                              color="red"
                              leftSection={<IconTrash size={14} />}
                              {...actionProps('common.delete')}
                              onClick={() => void deleteMachine(m)}
                            >
                              {t('common.delete')}
                            </Menu.Item>
                          </Menu.Dropdown>
                        </Menu>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Stack>

      {usesSizeTable(kind) && (
        <Stack gap={4} mt="lg">
          <Group justify="space-between">
            <Text fw={600}>{t('machines.sizes')}</Text>
            <Button
              size="xs"
              variant="light"
              leftSection={<IconPlus size={14} />}
              onClick={() => open({ kind: 'size', machineKind: kind })}
            >
              {t('machines.addSize')}
            </Button>
          </Group>
          <Text size="xs" c="dimmed">
            {kind === 'single_cutting' ? t('machines.sizesHelpSingle') : t('machines.sizesHelpDouble')}
          </Text>
          <Table.ScrollContainer minWidth={420}>
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>
                    {t('production.size')} ({kind === 'single_cutting' ? t('units.in') : t('units.ft')})
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
                          {...actionProps('common.edit')}
                          onClick={() => open({ kind: 'size', machineKind: kind, size: s })}
                        >
                          <IconPencil size={16} />
                        </ActionIcon>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          aria-label={t('common.delete')}
                          {...actionProps('common.delete')}
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
                              {...actionProps('rates.correct')}
                              onClick={() => open({ kind: 'rate', machineKind: kind, rate: r })}
                            >
                              <IconPencil size={16} />
                            </ActionIcon>
                            <ActionIcon
                              variant="subtle"
                              color="red"
                              aria-label={t('common.delete')}
                              {...actionProps('common.delete')}
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
              <Table.ScrollContainer minWidth={480}>
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{t('production.machine')}</Table.Th>
                      <Table.Th>{t('machines.loaderFrom')}</Table.Th>
                      <Table.Th>{t('production.loader')}</Table.Th>
                      <Table.Th>{t('rates.note')}</Table.Th>
                      <Table.Th w={80} />
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {assignments.map((a) => {
                      const m = machines.find((x) => x.id === a.machine_id)!;
                      return (
                        <Table.Tr key={a.id}>
                          <Table.Td>{local(m)}</Table.Td>
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
                                {...actionProps('rates.correct')}
                                onClick={() => open({ kind: 'loader', machine: m, assignment: a })}
                              >
                                <IconPencil size={16} />
                              </ActionIcon>
                              <ActionIcon
                                variant="subtle"
                                color="red"
                                aria-label={t('common.delete')}
                                {...actionProps('common.delete')}
                                onClick={() =>
                                  confirm(
                                    t('machines.deleteLoaderTitle'),
                                    t('machines.deleteLoaderBody'),
                                    () => removeAssignment.mutate(a.id, deleted),
                                  )
                                }
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

/** Add a machine of a type, or rename / stop using one. */
function MachineForm({
  machine,
  kind,
  suggestedName,
  onDone,
}: {
  machine: Machine | null;
  kind: MachineKind;
  suggestedName: { en: string; hi: string };
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const update = useUpdateMachine();
  const create = useCreateMachine();
  const [nameEn, setNameEn] = useState(machine?.name_en ?? suggestedName.en);
  const [nameHi, setNameHi] = useState(machine?.name_hi ?? suggestedName.hi);
  const [active, setActive] = useState(machine?.is_active ?? true);
  const done = {
    onSuccess: () => {
      notifySaved(t('common.saved'));
      onDone();
    },
  };
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const names = { name_en: nameEn.trim(), name_hi: nameHi.trim() || null };
        if (machine) update.mutate({ id: machine.id, ...names, is_active: active }, done);
        else create.mutate({ kind, ...names }, done);
      }}
    >
      <Stack>
        <TextInput label={t('machines.nameEn')} required data-autofocus value={nameEn} onChange={(e) => setNameEn(e.currentTarget.value)} />
        <TextInput label={t('machines.nameHi')} lang="hi" value={nameHi} onChange={(e) => setNameHi(e.currentTarget.value)} />
        {machine && (
          <Switch
            label={active ? t('machines.inUse') : t('machines.notInUse')}
            description={t('machines.retireHelp')}
            checked={active}
            onChange={(e) => setActive(e.currentTarget.checked)}
          />
        )}
        <FormButtons
          onDone={onDone}
          loading={update.isPending || create.isPending}
          disabled={!nameEn.trim()}
        />
      </Stack>
    </form>
  );
}

function RateForm({
  kind,
  existing,
  initialComponent,
  onDone,
}: {
  kind: MachineKind;
  existing: Rate | null;
  initialComponent?: RateComponent;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const label = useComponentLabel();
  const save = useSaveRate();
  const components = allowedComponents(kind);
  const [component, setComponent] = useState<RateComponent>(
    existing?.component ?? initialComponent ?? components[0],
  );
  const [rate, setRate] = useState<string | number>(existing ? Number(existing.rate) : '');
  const [from, setFrom] = useState<string | null>(existing?.effective_from ?? todayISO());
  const [note, setNote] = useState(existing?.note ?? '');
  const unit = componentUnit(kind, component) === 'rft' ? t('machines.perRft') : t('machines.perSqft');
  const valid = rate !== '' && Number(rate) >= 0 && from;

  const submit = () => {
    if (!valid) return;
    const common = { rate: String(rate), effective_from: from!, note: note || null };
    const text = `${t(`machineKinds.${kind}`)} · ${label(component)} ₹${rate} · ${formatDate(from, 'short')}`;
    save.mutate(
      existing
        ? { id: existing.id, body: common, label: text }
        : { body: { ...common, kind, component }, label: text },
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
                items: roleComponents(kind, 'operator').map((c) => ({ value: c, label: label(c) })),
              },
              {
                group: t('machines.loaderRates'),
                items: roleComponents(kind, 'loader').map((c) => ({ value: c, label: label(c) })),
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
  kind,
  existing,
  onDone,
}: {
  kind: MachineKind;
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
  const unit = kind === 'single_cutting' ? t('units.in') : t('units.ft');
  const positive = (v: string | number) => v !== '' && Number(v) > 0;
  const valid = [length, width, rft, sqft].every(positive);

  const submit = () => {
    if (!valid) return;
    const body = { length: String(length), width: String(width), rft: String(rft), sqft: String(sqft) };
    const text = `${t(`machineKinds.${kind}`)} · ${sizeLabel(body.length, body.width)}`;
    save.mutate(
      existing
        ? { id: existing.id, body, label: text }
        : { body: { ...body, kind }, label: text },
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
