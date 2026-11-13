import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Drawer,
  Group,
  Stack,
  Text,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { modals } from '@mantine/modals';
import {
  IconAlertTriangle,
  IconCloudCheck,
  IconCloudOff,
  IconCloudUpload,
  IconRefresh,
  IconTrash,
} from '@tabler/icons-react';
import dayjs from 'dayjs';
import type { ReactElement, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError } from '../api/client';
import i18n from '../i18n';
import { errorMessage } from '../lib/errors';
import { useHubState } from '../lib/hub';
import { discard, flush, retry, useOutbox, type Entity, type OutboxItem } from '../lib/outbox';
import { applyUpdate, useUpdateReady } from '../lib/serviceWorker';
import { notifySaved } from './common';

/** "Saved" — or, if the laptop is away, "kept on this device". */
export function notifyResult(result: { queued: boolean }, savedMessage: string) {
  notifySaved(result.queued ? i18n.t('sync.queuedSaved') : savedMessage);
}

/** Disables controls that need the laptop, with a tooltip saying why. */
export function NeedsHub({ children }: { children: (disabled: boolean) => ReactElement }) {
  const { t } = useTranslation();
  const { reachable } = useHubState();
  if (reachable) return children(false);
  return (
    <Tooltip label={t('sync.needsLaptop')} withArrow>
      <span>{children(true)}</span>
    </Tooltip>
  );
}

function useSyncSummary() {
  const items = useOutbox();
  const failed = items.filter((i) => i.status === 'failed');
  const waiting = items.filter((i) => i.status === 'pending');
  return { items, failed, waiting };
}

/** The status in the header: all saved / saving / offline with N waiting / N not saved. */
export function SyncStatus() {
  const { t } = useTranslation();
  const { reachable } = useHubState();
  const { failed, waiting } = useSyncSummary();
  const [opened, { open, close }] = useDisclosure(false);

  let color = 'teal';
  let icon: ReactNode = <IconCloudCheck size={16} />;
  let label = t('sync.synced');
  if (failed.length) {
    color = 'red';
    icon = <IconAlertTriangle size={16} />;
    label = t('sync.failed', { count: failed.length });
  } else if (!reachable) {
    color = 'orange';
    icon = <IconCloudOff size={16} />;
    label = waiting.length ? t('sync.waiting', { count: waiting.length }) : t('sync.offline');
  } else if (waiting.length) {
    color = 'blue';
    icon = <IconCloudUpload size={16} />;
    label = t('sync.syncing');
  }

  return (
    <>
      <UnstyledButton onClick={open} aria-label={label}>
        <Badge
          color={color}
          variant="light"
          size="lg"
          leftSection={icon}
          style={{ textTransform: 'none', cursor: 'pointer' }}
        >
          <Text span size="xs" fw={600} visibleFrom="xs">
            {label}
          </Text>
        </Badge>
      </UnstyledButton>
      <Drawer opened={opened} onClose={close} position="right" title={t('sync.panelTitle')} size="md">
        <SyncPanel />
      </Drawer>
    </>
  );
}

function SyncPanel() {
  const { t } = useTranslation();
  const { reachable } = useHubState();
  const { items, failed, waiting } = useSyncSummary();
  if (!items.length) {
    return <Text c="dimmed">{t('sync.nothing')}</Text>;
  }
  return (
    <Stack>
      {failed.length > 0 && <PendingList title={t('sync.failedTitle')} items={failed} />}
      {waiting.length > 0 && (
        <PendingList
          title={t('sync.waitingTitle')}
          items={waiting}
          action={
            reachable && (
              <Button size="xs" variant="light" leftSection={<IconRefresh size={14} />} onClick={() => void flush()}>
                {t('sync.sendNow')}
              </Button>
            )
          }
        />
      )}
    </Stack>
  );
}

/** A list of changes that are still on this device, optionally for one kind of record. */
export function PendingList({
  title,
  items,
  action,
}: {
  title: string;
  items: OutboxItem[];
  action?: ReactNode;
}) {
  const { t } = useTranslation();
  const anyFailed = items.some((i) => i.status === 'failed');

  const confirmDiscard = (item: OutboxItem) =>
    modals.openConfirmModal({
      title: t('sync.discardTitle'),
      children: <Text size="sm">{t('sync.discardBody', { label: item.label })}</Text>,
      labels: { confirm: t('sync.discard'), cancel: t('common.cancel') },
      confirmProps: { color: 'red' },
      onConfirm: () => void discard(item.id),
    });

  return (
    <Card withBorder padding="sm">
      <Group justify="space-between" mb={6}>
        <Title order={5}>{title}</Title>
        {action}
      </Group>
      {anyFailed && (
        <Text size="xs" c="dimmed" mb="xs">
          {t('sync.failedHelp')}
        </Text>
      )}
      <Stack gap={6}>
        {items.map((item) => (
          <Group key={item.id} justify="space-between" wrap="nowrap" gap="xs" align="flex-start">
            <div style={{ minWidth: 0 }}>
              <Text size="sm" fw={500} truncate>
                <Badge size="xs" variant="outline" color="gray" mr={6}>
                  {t(`sync.actions.${item.action}`)}
                </Badge>
                {item.label}
              </Text>
              <Text size="xs" c={item.status === 'failed' ? 'red' : 'dimmed'}>
                {item.status === 'failed' && item.error
                  ? errorMessage(new ApiError(400, item.error.code, item.error.message, { reason: item.error.reason }))
                  : `${t('sync.pending')} · ${dayjs(item.createdAt).format('D MMM, HH:mm')}`}
              </Text>
            </div>
            {item.status === 'failed' && (
              <Group gap={4} wrap="nowrap">
                <ActionIcon variant="subtle" aria-label={t('sync.retry')} onClick={() => void retry(item.id)}>
                  <IconRefresh size={16} />
                </ActionIcon>
                <ActionIcon
                  variant="subtle"
                  color="red"
                  aria-label={t('sync.discard')}
                  onClick={() => confirmDiscard(item)}
                >
                  <IconTrash size={16} />
                </ActionIcon>
              </Group>
            )}
          </Group>
        ))}
      </Stack>
    </Card>
  );
}

/** Changes of one kind still on this device (e.g. production entries on the Production screen). */
export function PendingForEntity({ entity }: { entity: Entity }) {
  const { t } = useTranslation();
  const items = useOutbox().filter((i) => i.entity === entity);
  if (!items.length) return null;
  const failed = items.filter((i) => i.status === 'failed');
  const waiting = items.filter((i) => i.status === 'pending');
  return (
    <Stack mb="md" gap="sm">
      {failed.length > 0 && <PendingList title={t('sync.failedTitle')} items={failed} />}
      {waiting.length > 0 && <PendingList title={t('sync.waitingTitle')} items={waiting} />}
    </Stack>
  );
}

/** "A new version is ready" — the owner chooses when to switch, so nothing reloads mid-entry. */
export function UpdateBanner() {
  const { t } = useTranslation();
  const ready = useUpdateReady();
  if (!ready) return null;
  return (
    <Alert color="blue" variant="light" mb="md">
      <Group justify="space-between" gap="sm">
        <Text size="sm">{t('sync.updateReady')}</Text>
        <Button size="xs" onClick={applyUpdate}>
          {t('sync.updateNow')}
        </Button>
      </Group>
    </Alert>
  );
}

/** Shown under the header while the laptop is away. */
export function OfflineBanner() {
  const { t } = useTranslation();
  const { reachable, lastContact } = useHubState();
  if (reachable) return null;
  return (
    <Alert color="orange" variant="light" icon={<IconCloudOff />} mb="md">
      {t('sync.offlineBanner')}{' '}
      {lastContact && t('sync.dataFrom', { time: dayjs(lastContact).format('D MMM, HH:mm') })}
    </Alert>
  );
}
