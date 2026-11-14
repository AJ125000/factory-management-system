import { Card, Code, Group, Stack, Text, Title } from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { useSystemInfo } from '../api/hooks';

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Group justify="space-between" wrap="wrap" gap="xs">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      {children}
    </Group>
  );
}

/** Versions and file locations — what someone helping the owner needs to know. */
export function AboutCard() {
  const { t } = useTranslation();
  const info = useSystemInfo().data;
  return (
    <Card withBorder>
      <Group gap="xs" mb="sm">
        <IconInfoCircle size={20} />
        <Title order={4}>{t('about.title')}</Title>
      </Group>
      <Stack gap={6}>
        <Row label={t('about.appVersion')}>
          <Text size="sm">{__APP_VERSION__}</Text>
        </Row>
        <Row label={t('about.hubVersion')}>
          <Text size="sm">{info?.version ?? '—'}</Text>
        </Row>
        <Row label={t('about.databaseSize')}>
          <Text size="sm">
            {info ? `${(info.database_size / 1024 / 1024).toFixed(1)} MB` : '—'}
          </Text>
        </Row>
        <Row label={t('about.dataFolder')}>
          <Code>{info?.data_dir ?? '—'}</Code>
        </Row>
        <Row label={t('about.logFile')}>
          <Code>{info?.log_file ?? '—'}</Code>
        </Row>
      </Stack>
    </Card>
  );
}
