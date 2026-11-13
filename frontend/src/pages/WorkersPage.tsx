import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Menu,
  Modal,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Textarea,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { modals } from '@mantine/modals';
import {
  IconArchive,
  IconArrowBackUp,
  IconDots,
  IconPencil,
  IconPlus,
  IconSearch,
  IconTrash,
} from '@tabler/icons-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError } from '../api/client';
import {
  fetchDeleteImpact,
  useArchiveWorker,
  useDeleteWorker,
  useSaveWorker,
  useWorkerTypes,
} from '../api/hooks';
import { useWorkersWithPending } from '../api/pending';
import type { Worker, WorkerInput } from '../api/types';
import { notifyResult } from '../components/Sync';
import { DateField, PageHeader, WorkerName, notifyError, notifySaved } from '../components/common';
import { localName } from '../i18n';
import { useHubState } from '../lib/hub';
import { todayISO } from '../lib/format';

export default function WorkersPage() {
  const { t, i18n } = useTranslation();
  const [showArchived, setShowArchived] = useState(false);
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Worker | null>(null);
  const [formOpen, form] = useDisclosure(false);
  const workers = useWorkersWithPending(showArchived);
  const pendingIds = workers.pendingIds;
  const archive = useArchiveWorker();
  const { reachable } = useHubState();

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = workers.data ?? [];
    if (!q) return list;
    return list.filter(
      (w) => w.name_en.toLowerCase().includes(q) || (w.name_hi ?? '').includes(search.trim()),
    );
  }, [workers.data, search]);

  const openForm = (worker: Worker | null) => {
    setEditing(worker);
    form.open();
  };

  const toggleArchive = (w: Worker) =>
    archive.mutate(
      { id: w.id, archive: !w.is_archived, label: w.name_en },
      {
        onSuccess: (r) =>
          notifyResult(
            r,
            t(w.is_archived ? 'workers.restoredDone' : 'workers.archivedDone', { name: w.name_en }),
          ),
      },
    );

  const deleteWorker = useDeleteWorker();
  const confirmDelete = async (w: Worker) => {
    let count: number;
    try {
      count = (await fetchDeleteImpact(w.id)).production_entries;
    } catch (e) {
      notifyError(e);
      return;
    }
    modals.openConfirmModal({
      title: t('workers.deleteTitle', { name: w.name_en }),
      children: (
        <Stack gap="sm">
          <Text size="sm">{t('workers.deleteBody', { name: w.name_en, count })}</Text>
          {!w.is_archived && (
            <Alert color="blue" variant="light">
              <Stack gap="xs" align="flex-start">
                <Text size="sm">{t('workers.deleteHint')}</Text>
                <Button
                  size="xs"
                  variant="light"
                  leftSection={<IconArchive size={14} />}
                  onClick={() => {
                    modals.closeAll();
                    toggleArchive(w);
                  }}
                >
                  {t('workers.archiveInstead')}
                </Button>
              </Stack>
            </Alert>
          )}
        </Stack>
      ),
      labels: { confirm: t('workers.deletePermanently'), cancel: t('common.cancel') },
      confirmProps: { color: 'red' },
      onConfirm: () =>
        deleteWorker.mutate(
          { id: w.id, confirmEntries: count },
          {
            onSuccess: () => notifySaved(t('common.deleted')),
            onError: (e) => {
              if (e instanceof ApiError && e.reason === 'confirmation_mismatch') {
                notifyError(t('workers.deleteChanged'));
                void confirmDelete(w);
              } else notifyError(e);
            },
          },
        ),
    });
  };

  return (
    <>
      <PageHeader
        title={t('workers.title')}
        actions={
          <Button leftSection={<IconPlus size={18} />} onClick={() => openForm(null)}>
            {t('workers.add')}
          </Button>
        }
      />

      <Card withBorder>
        <Group mb="md" justify="space-between" wrap="wrap">
          <TextInput
            placeholder={t('common.search')}
            leftSection={<IconSearch size={16} />}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
            w={280}
          />
          <Switch
            label={t('workers.showArchived')}
            checked={showArchived}
            onChange={(e) => setShowArchived(e.currentTarget.checked)}
          />
        </Group>

        {workers.isSuccess && visible.length === 0 ? (
          <Text c="dimmed" ta="center" py="xl">
            {search ? t('workers.noMatch') : t('workers.noWorkers')}
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={600}>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('production.worker')}</Table.Th>
                  <Table.Th>{t('workers.type')}</Table.Th>
                  <Table.Th>{t('workers.phone')}</Table.Th>
                  <Table.Th>{t('workers.status')}</Table.Th>
                  <Table.Th w={60} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {visible.map((w) => (
                  <Table.Tr key={w.id} opacity={w.is_archived ? 0.6 : 1}>
                    <Table.Td>
                      <WorkerName nameEn={w.name_en} nameHi={w.name_hi} />
                    </Table.Td>
                    <Table.Td>
                      {localName(w.worker_type.name_en, w.worker_type.name_hi, i18n.language)}
                    </Table.Td>
                    <Table.Td>{w.phone ?? '—'}</Table.Td>
                    <Table.Td>
                      {pendingIds.has(w.id) ? (
                        <Badge color="orange" variant="light">
                          {t('sync.pending')}
                        </Badge>
                      ) : (
                        <Badge color={w.is_archived ? 'gray' : 'teal'} variant="light">
                          {w.is_archived ? t('workers.archived') : t('workers.active')}
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Menu position="bottom-end" withinPortal>
                        <Menu.Target>
                          <ActionIcon variant="subtle" color="gray" aria-label={t('common.actions')}>
                            <IconDots size={18} />
                          </ActionIcon>
                        </Menu.Target>
                        <Menu.Dropdown>
                          <Menu.Item
                            leftSection={<IconPencil size={16} />}
                            onClick={() => openForm(w)}
                          >
                            {t('common.edit')}
                          </Menu.Item>
                          {/* A worker not yet sent to the laptop can only be edited. */}
                          {!pendingIds.has(w.id) && (
                            <>
                              <Menu.Item
                                leftSection={
                                  w.is_archived ? (
                                    <IconArrowBackUp size={16} />
                                  ) : (
                                    <IconArchive size={16} />
                                  )
                                }
                                onClick={() => toggleArchive(w)}
                              >
                                {w.is_archived ? t('workers.restore') : t('workers.archive')}
                              </Menu.Item>
                              <Menu.Divider />
                              <Menu.Item
                                color="red"
                                leftSection={<IconTrash size={16} />}
                                disabled={!reachable}
                                title={reachable ? undefined : t('sync.needsLaptop')}
                                onClick={() => void confirmDelete(w)}
                              >
                                {t('common.delete')}
                                {!reachable && (
                                  <Text size="xs" c="dimmed">
                                    {t('sync.needsLaptop')}
                                  </Text>
                                )}
                              </Menu.Item>
                            </>
                          )}
                        </Menu.Dropdown>
                      </Menu>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Card>

      <Modal
        opened={formOpen}
        onClose={form.close}
        title={editing ? t('workers.edit') : t('workers.add')}
      >
        {formOpen && <WorkerForm worker={editing} onDone={form.close} />}
      </Modal>
    </>
  );
}

function WorkerForm({ worker, onDone }: { worker: Worker | null; onDone: () => void }) {
  const { t, i18n } = useTranslation();
  const types = useWorkerTypes();
  const save = useSaveWorker();
  const [values, setValues] = useState<WorkerInput>({
    name_en: worker?.name_en ?? '',
    name_hi: worker?.name_hi ?? '',
    worker_type_id: worker?.worker_type_id ?? '',
    phone: worker?.phone ?? '',
    joined_on: worker?.joined_on ?? null,
    notes: worker?.notes ?? '',
  });
  const set = <K extends keyof WorkerInput>(key: K, value: WorkerInput[K]) =>
    setValues((v) => ({ ...v, [key]: value }));

  const typeOptions = (types.data ?? []).map((wt) => ({
    value: wt.id,
    label: localName(wt.name_en, wt.name_hi, i18n.language),
  }));
  // Keep showing the worker's current type even if it has been taken out of use.
  if (worker && !typeOptions.some((o) => o.value === worker.worker_type_id)) {
    typeOptions.push({
      value: worker.worker_type_id,
      label: localName(worker.worker_type.name_en, worker.worker_type.name_hi, i18n.language),
    });
  }

  const submit = (allowDuplicate = false) => {
    const body: WorkerInput = {
      ...values,
      name_hi: values.name_hi || null,
      phone: values.phone || null,
      notes: values.notes || null,
      allow_duplicate_name: allowDuplicate,
    };
    save.mutate(
      { id: worker?.id, body, label: values.name_en },
      {
        onSuccess: (r) => {
          notifyResult(r, t('common.saved'));
          onDone();
        },
        onError: (e) => {
          if (e instanceof ApiError && e.reason === 'duplicate_name') {
            modals.openConfirmModal({
              title: t('workers.duplicateTitle'),
              children: <Text size="sm">{t('workers.duplicateBody', { name: values.name_en })}</Text>,
              labels: { confirm: t('workers.addAnyway'), cancel: t('common.cancel') },
              onConfirm: () => submit(true),
            });
          } else notifyError(e);
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
        <TextInput
          label={t('workers.nameEn')}
          required
          data-autofocus
          value={values.name_en}
          onChange={(e) => set('name_en', e.currentTarget.value)}
        />
        <TextInput
          label={t('workers.nameHi')}
          description={t('workers.nameHiHelp')}
          lang="hi"
          value={values.name_hi ?? ''}
          onChange={(e) => set('name_hi', e.currentTarget.value)}
        />
        <Select
          label={t('workers.type')}
          required
          data={typeOptions}
          value={values.worker_type_id || null}
          onChange={(v) => set('worker_type_id', v ?? '')}
          allowDeselect={false}
        />
        <Group grow>
          <TextInput
            label={t('workers.phone')}
            type="tel"
            value={values.phone ?? ''}
            onChange={(e) => set('phone', e.currentTarget.value)}
          />
          <DateField
            label={t('workers.joinedOn')}
            clearable
            maxDate={todayISO()}
            value={values.joined_on ?? null}
            onChange={(v) => set('joined_on', v)}
          />
        </Group>
        <Textarea
          label={t('common.notes')}
          autosize
          minRows={2}
          value={values.notes ?? ''}
          onChange={(e) => set('notes', e.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onDone}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" loading={save.isPending} disabled={!values.name_en || !values.worker_type_id}>
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
