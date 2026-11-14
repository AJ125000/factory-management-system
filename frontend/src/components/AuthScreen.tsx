import {
  Alert,
  Button,
  Center,
  Group,
  Loader,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { IconCloudOff, IconLock } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { requestLogin, useAuthStatus } from '../api/hooks';
import { guessDeviceName, setAuthToken } from '../lib/auth';
import { errorMessage } from '../lib/errors';
import { LanguageToggle } from './AppLayout';

/** First-run password setup, or logging this device in. */
export default function AuthScreen() {
  const { t } = useTranslation();
  const status = useAuthStatus();
  const setup = status.data?.setup_required ?? false;

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [deviceName, setDeviceName] = useState(guessDeviceName);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const mismatch = setup && confirm.length > 0 && password !== confirm;
  const canSubmit =
    password.length > 0 && deviceName.trim().length > 0 && (!setup || password === confirm);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const { token } = await requestLogin(setup ? 'setup' : 'login', password, deviceName.trim());
      setAuthToken(token);
    } catch (e) {
      setError(errorMessage(e));
      setPassword('');
      setConfirm('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Center mih="100vh" p="md" bg="var(--mantine-color-gray-0)">
      <Paper withBorder shadow="sm" radius="md" p="xl" w="100%" maw={420}>
        <Group justify="space-between" mb="lg">
          <Group gap="sm">
            <img src="/icon.png" alt="" width={36} height={36} />
            <Title order={3}>{setup ? t('auth.setupTitle') : t('auth.loginTitle')}</Title>
          </Group>
          <LanguageToggle />
        </Group>

        {status.isLoading ? (
          <Center py="xl">
            <Loader />
          </Center>
        ) : status.isError ? (
          <Stack>
            <Alert color="orange" icon={<IconCloudOff />}>
              {t('auth.needsLaptop')}
            </Alert>
            <Button onClick={() => void status.refetch()}>{t('auth.retry')}</Button>
          </Stack>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (canSubmit) void submit();
            }}
          >
            <Stack>
              <Text size="sm" c="dimmed">
                {setup ? t('auth.setupIntro') : t('auth.loginIntro')}
              </Text>
              <PasswordInput
                label={t('auth.password')}
                description={setup ? t('auth.passwordHelp') : undefined}
                leftSection={<IconLock size={16} />}
                autoComplete={setup ? 'new-password' : 'current-password'}
                required
                data-autofocus
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
              />
              {setup && (
                <PasswordInput
                  label={t('auth.confirmPassword')}
                  autoComplete="new-password"
                  required
                  error={mismatch ? t('auth.mismatch') : undefined}
                  value={confirm}
                  onChange={(e) => setConfirm(e.currentTarget.value)}
                />
              )}
              <TextInput
                label={t('auth.deviceName')}
                description={t('auth.deviceNameHelp')}
                required
                maxLength={80}
                value={deviceName}
                onChange={(e) => setDeviceName(e.currentTarget.value)}
              />
              {error && <Alert color="red">{error}</Alert>}
              <Button type="submit" size="md" loading={busy} disabled={!canSubmit}>
                {setup ? t('auth.start') : t('auth.login')}
              </Button>
              {!setup && (
                <Text size="xs" c="dimmed">
                  {t('auth.forgot')}
                </Text>
              )}
            </Stack>
          </form>
        )}
      </Paper>
    </Center>
  );
}
