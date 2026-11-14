import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  FileButton,
  Group,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { modals } from '@mantine/modals';
import {
  IconAlertTriangle,
  IconDatabaseExport,
  IconDownload,
  IconRestore,
  IconUpload,
} from '@tabler/icons-react';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { downloadFile } from '../api/client';
import {
  useBackUpNow,
  useBackups,
  useRestoreBackup,
  useSettings,
  useUpdateSettings,
} from '../api/hooks';
import type { BackupInfo } from '../api/types';
import { errorMessage } from '../lib/errors';
import { useHubState } from '../lib/hub';
import { notifyError, notifySaved } from './common';

const SHOWN = 5;

function sizeLabel(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const when = (iso: string) => dayjs(iso).format('D MMM YYYY, HH:mm');

export function BackupSettings() {
  const { t } = useTranslation();
  const { reachable } = useHubState();
  const status = useBackups();
  const backUp = useBackUpNow();
  const restore = useRestoreBackup();
  const [showAll, setShowAll] = useState(false);
  const data = status.data;
  const list = data?.backups ?? [];
  const shown = showAll ? list : list.slice(0, SHOWN);

  const onRestored = () => notifySaved(t('backups.restored'));
  const onRestoreError = (e: unknown) => notifyError(errorMessage(e));

  const confirmRestore = (b: BackupInfo) =>
    modals.openConfirmModal({
      title: t('backups.restoreTitle'),
      children: <Text size="sm">{t('backups.restoreBody', { time: when(b.created_at) })}</Text>,
      labels: { confirm: t('backups.restore'), cancel: t('common.cancel') },
      confirmProps: { color: 'orange' },
      onConfirm: () =>
        restore.mutate({ name: b.name }, { onSuccess: onRestored, onError: onRestoreError }),
    });

  const confirmRestoreFile = (file: File | null) => {
    if (!file) return;
    modals.openConfirmModal({
      title: t('backups.restoreFileTitle'),
      children: <Text size="sm">{t('backups.restoreFileBody', { name: file.name })}</Text>,
      labels: { confirm: t('backups.restore'), cancel: t('common.cancel') },
      confirmProps: { color: 'orange' },
      onConfirm: () => restore.mutate({ file }, { onSuccess: onRestored, onError: onRestoreError }),
    });
  };

  return (
    <Card withBorder>
      <Group gap="xs" mb={4}>
        <IconDatabaseExport size={20} />
        <Title order={4}>{t('backups.title')}</Title>
      </Group>
      <Text size="sm" c="dimmed" mb="md">
        {t('backups.intro')}
      </Text>

      {data?.last_error && (
        <Alert color="red" icon={<IconAlertTriangle />} mb="md">
          {t('backups.lastError', { error: data.last_error })}
        </Alert>
      )}

      <Group justify="space-between" mb="md" wrap="wrap">
        <Text fw={500}>
          {data?.last_backup_at
            ? t('backups.last', { time: when(data.last_backup_at) })
            : t('backups.never')}
        </Text>
        <Group gap="sm">
          <FileButton onChange={confirmRestoreFile} accept=".db,application/octet-stream">
            {(props) => (
              <Button
                {...props}
                variant="default"
                leftSection={<IconUpload size={16} />}
                disabled={!reachable}
                loading={restore.isPending}
              >
                {t('backups.restoreFile')}
              </Button>
            )}
          </FileButton>
          <Button
            leftSection={<IconDatabaseExport size={16} />}
            loading={backUp.isPending}
            disabled={!reachable}
            onClick={() => backUp.mutate(undefined, { onSuccess: () => notifySaved(t('backups.done')) })}
          >
            {t('backups.backupNow')}
          </Button>
        </Group>
      </Group>

      {list.length > 0 && (
        <>
          <Text size="sm" fw={600} mb={4}>
            {t('backups.list')}
          </Text>
          <Table.ScrollContainer minWidth={480}>
            <Table>
              <Table.Tbody>
                {shown.map((b) => (
                  <Table.Tr key={b.name}>
                    <Table.Td>{when(b.created_at)}</Table.Td>
                    <Table.Td>
                      <Badge variant="light" color={b.kind === 'auto' ? 'gray' : 'blue'}>
                        {t(`backups.kinds.${b.kind}`)}
                      </Badge>
                    </Table.Td>
                    <Table.Td className="num">{sizeLabel(b.size)}</Table.Td>
                    <Table.Td>
                      <Group gap={4} justify="flex-end" wrap="nowrap">
                        <Button
                          size="xs"
                          variant="subtle"
                          leftSection={<IconDownload size={14} />}
                          disabled={!reachable}
                          onClick={() =>
                            downloadFile(
                              `/backups/${encodeURIComponent(b.name)}/download`,
                              {},
                              b.name,
                            ).catch(notifyError)
                          }
                        >
                          {t('backups.download')}
                        </Button>
                        <Button
                          size="xs"
                          variant="subtle"
                          color="orange"
                          leftSection={<IconRestore size={14} />}
                          disabled={!reachable}
                          onClick={() => confirmRestore(b)}
                        >
                          {t('backups.restore')}
                        </Button>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          {list.length > SHOWN && !showAll && (
            <Anchor component="button" size="sm" onClick={() => setShowAll(true)}>
              {t('backups.showAll', { count: list.length })}
            </Anchor>
          )}
        </>
      )}

      <CopyFolder copyDirOk={data?.copy_dir_ok ?? null} />
    </Card>
  );
}

function CopyFolder({ copyDirOk }: { copyDirOk: boolean | null }) {
  const { t } = useTranslation();
  const settings = useSettings().data;
  const update = useUpdateSettings();
  const { reachable } = useHubState();
  const [value, setValue] = useState<string | null>(null);
  const current = value ?? settings?.backup_copy_dir ?? '';

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        update.mutate(
          { backup_copy_dir: current.trim() },
          {
            onSuccess: () => notifySaved(t('common.saved')),
            onError: (err) => notifyError(errorMessage(err)),
          },
        );
      }}
    >
      <Group align="flex-end" gap="sm" mt="lg">
        <TextInput
          label={t('backups.copyDir')}
          description={t('backups.copyDirHelp')}
          placeholder="E:\FMS backups"
          value={current}
          onChange={(e) => setValue(e.currentTarget.value)}
          error={copyDirOk === false && value === null ? t('backups.copyDirMissing') : undefined}
          style={{ flex: 1, minWidth: 260 }}
        />
        <Button type="submit" variant="default" loading={update.isPending} disabled={!reachable}>
          {t('common.save')}
        </Button>
      </Group>
    </form>
  );
}
