import { Anchor, Center, Paper, PinInput, Stack, Text, Title } from '@mantine/core';
import { modals } from '@mantine/modals';
import { IconLock } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { clearAuthToken } from '../lib/auth';
import { pinLength, removePin, unlock, useLocked, waitSeconds } from '../lib/pin';

/** Covers the whole app while the PIN lock is on. */
export default function LockScreen() {
  const { t } = useTranslation();
  const locked = useLocked();
  const [value, setValue] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [wait, setWait] = useState(waitSeconds());

  // Count down the "too many tries" wait.
  useEffect(() => {
    if (!locked || wait <= 0) return;
    const timer = setInterval(() => setWait(waitSeconds()), 1000);
    return () => clearInterval(timer);
  }, [locked, wait]);

  if (!locked) return null;

  const tryPin = async (pin: string) => {
    const result = await unlock(pin);
    setValue('');
    if (result === 'ok') {
      setMessage(null);
      return;
    }
    const seconds = waitSeconds();
    setWait(seconds);
    setMessage(result === 'wait' ? null : t('lock.wrong'));
  };

  const forgot = () =>
    modals.openConfirmModal({
      title: t('lock.forgotTitle'),
      children: <Text size="sm">{t('lock.forgotBody')}</Text>,
      labels: { confirm: t('auth.login'), cancel: t('common.cancel') },
      onConfirm: () => {
        removePin();
        clearAuthToken();
      },
    });

  return (
    <Center
      pos="fixed"
      inset={0}
      bg="var(--mantine-color-body)"
      style={{ zIndex: 1000 }}
      p="md"
      role="dialog"
      aria-modal="true"
      aria-label={t('lock.title')}
    >
      <Paper withBorder shadow="sm" radius="md" p="xl" w="100%" maw={360}>
        <Stack align="center" gap="md">
          <IconLock size={40} stroke={1.5} />
          <Title order={3}>{t('lock.title')}</Title>
          <Text size="sm" c="dimmed">
            {t('lock.enterPin')}
          </Text>
          <PinInput
            type="number"
            mask
            oneTimeCode={false}
            length={pinLength()}
            size="lg"
            autoFocus
            disabled={wait > 0}
            value={value}
            onChange={setValue}
            onComplete={(pin) => void tryPin(pin)}
            ariaLabel={t('lock.enterPin')}
          />
          {wait > 0 ? (
            <Text c="orange" size="sm">
              {t('lock.wait', { seconds: wait })}
            </Text>
          ) : (
            message && (
              <Text c="red" size="sm">
                {message}
              </Text>
            )
          )}
          <Anchor component="button" type="button" size="sm" onClick={forgot}>
            {t('lock.forgot')}
          </Anchor>
        </Stack>
      </Paper>
    </Center>
  );
}
