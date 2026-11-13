import {
  Alert,
  Button,
  Card,
  Code,
  CopyButton,
  Group,
  Image,
  List,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { IconCheck, IconCopy, IconDeviceMobile } from '@tabler/icons-react';
import QRCode from 'qrcode';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useConnectInfo, useSettings, useUpdateSettings } from '../api/hooks';
import { useHubState } from '../lib/hub';
import { notifySaved } from './common';

/** Settings card: the laptop's private address as a QR code, plus how to install on a phone. */
export function ConnectPhone() {
  const { t } = useTranslation();
  const info = useConnectInfo().data;
  const settings = useSettings().data;
  const update = useUpdateSettings();
  const { reachable } = useHubState();
  const [qr, setQr] = useState<string | null>(null);
  const [override, setOverride] = useState<string | null>(null);
  const url = info?.phone_url ?? null;

  useEffect(() => {
    if (!url) return setQr(null);
    let cancelled = false;
    QRCode.toDataURL(url, { width: 220, margin: 1 })
      .then((data) => !cancelled && setQr(data))
      .catch(() => setQr(null));
    return () => {
      cancelled = true;
    };
  }, [url]);

  const value = override ?? settings?.phone_url ?? '';

  return (
    <Card withBorder>
      <Group gap="xs" mb={4}>
        <IconDeviceMobile size={20} />
        <Title order={4}>{t('connect.title')}</Title>
      </Group>
      <Text size="sm" c="dimmed" mb="md">
        {t('connect.intro')}
      </Text>

      {url ? (
        <Group align="flex-start" gap="lg" wrap="wrap" mb="md">
          {qr && <Image src={qr} alt={url} w={180} h={180} radius="sm" />}
          <Stack gap="xs" style={{ flex: 1, minWidth: 240 }}>
            <Text size="sm">{t('connect.scan')}</Text>
            <Group gap="xs" wrap="nowrap">
              <Code fz="sm" style={{ wordBreak: 'break-all' }}>
                {url}
              </Code>
              <CopyButton value={url}>
                {({ copied, copy }) => (
                  <Button
                    size="xs"
                    variant="light"
                    onClick={copy}
                    leftSection={copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                  >
                    {copied ? t('connect.copied') : t('connect.copy')}
                  </Button>
                )}
              </CopyButton>
            </Group>
            <Text size="sm" fw={600} mt="xs">
              {t('connect.steps')}
            </Text>
            <List size="sm" type="ordered" spacing={4}>
              <List.Item>{t('connect.step1')}</List.Item>
              <List.Item>{t('connect.step2')}</List.Item>
              <List.Item>
                {t('connect.step3Android')}
                <br />
                {t('connect.step3Iphone')}
              </List.Item>
              <List.Item>{t('connect.step4')}</List.Item>
            </List>
          </Stack>
        </Group>
      ) : (
        info && (
          <Alert color="orange" variant="light" mb="md">
            <Text size="sm" mb="xs">
              {info.tailscale_installed ? t('connect.notDetected') : t('connect.notInstalled')}{' '}
              {t('connect.setupLaptop')}
            </Text>
            <Code block>{`tailscale serve --bg ${info.hub_port}`}</Code>
          </Alert>
        )
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate(
            { phone_url: value.trim() },
            { onSuccess: () => notifySaved(t('common.saved')) },
          );
        }}
      >
        <Group align="flex-end" gap="sm">
          <TextInput
            label={t('connect.override')}
            description={t('connect.overrideHelp')}
            placeholder="https://laptop-name.tailnet-name.ts.net/"
            value={value}
            onChange={(e) => setOverride(e.currentTarget.value)}
            style={{ flex: 1, minWidth: 240 }}
          />
          <Button type="submit" variant="default" loading={update.isPending} disabled={!reachable}>
            {t('common.save')}
          </Button>
        </Group>
      </form>
    </Card>
  );
}
