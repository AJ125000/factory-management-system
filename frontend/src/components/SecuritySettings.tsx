import {
  Badge,
  Button,
  Card,
  Checkbox,
  Divider,
  Group,
  PasswordInput,
  PinInput,
  Select,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { modals } from '@mantine/modals';
import { useQueryClient } from '@tanstack/react-query';
import { IconDeviceMobile, IconLock, IconLogout, IconShieldLock } from '@tabler/icons-react';
import dayjs from 'dayjs';
import { del } from 'idb-keyval';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError } from '../api/client';
import {
  requestLogout,
  useChangePassword,
  useDevices,
  useSignOutDevice,
} from '../api/hooks';
import { clearAuthToken } from '../lib/auth';
import { errorMessage } from '../lib/errors';
import { useHubState } from '../lib/hub';
import { clearOutbox, outboxItems } from '../lib/outbox';
import {
  LOCK_CHOICES,
  isValidPin,
  lockAfterMinutes,
  lockNow,
  removePin,
  setLockAfter,
  setPin,
  usePinEnabled,
} from '../lib/pin';
import { notifyError, notifySaved } from './common';

export function SecuritySettings() {
  const { t } = useTranslation();
  return (
    <Card withBorder>
      <Group gap="xs" mb="md">
        <IconShieldLock size={20} />
        <Title order={4}>{t('security.title')}</Title>
      </Group>
      <Stack gap="lg">
        <PinSection />
        <Divider />
        <DevicesSection />
        <Divider />
        <PasswordSection />
        <Divider />
        <LogoutSection />
      </Stack>
    </Card>
  );
}

function PinSection() {
  const { t } = useTranslation();
  const enabled = usePinEnabled();
  const [editing, setEditing] = useState(false);
  const [pin, setPinValue] = useState('');
  const [confirm, setConfirm] = useState('');
  const [minutes, setMinutes] = useState(String(lockAfterMinutes()));

  const minuteOptions = LOCK_CHOICES.map((m) => ({
    value: String(m),
    label: t('security.minutes', { count: m }),
  }));
  const mismatch = confirm.length === pin.length && pin.length > 0 && confirm !== pin;

  const save = async () => {
    try {
      await setPin(pin, Number(minutes));
      notifySaved(t('security.pinSaved'));
      setEditing(false);
      setPinValue('');
      setConfirm('');
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <Stack gap="xs">
      <Group justify="space-between">
        <Text fw={600}>{t('security.pin')}</Text>
        <Badge color={enabled ? 'teal' : 'gray'} variant="light">
          {enabled ? t('security.pinOn') : t('security.pinOff')}
        </Badge>
      </Group>
      <Text size="sm" c="dimmed">
        {t('security.pinIntro')}
      </Text>

      {editing ? (
        <Stack gap="sm" maw={360}>
          <Text size="sm">{t('security.newPin')}</Text>
          <PinInput
            type="number"
            mask
            length={6}
            value={pin}
            onChange={setPinValue}
            oneTimeCode={false}
            ariaLabel={t('security.newPin')}
          />
          <Text size="sm">{t('security.confirmPin')}</Text>
          <PinInput
            type="number"
            mask
            length={6}
            value={confirm}
            onChange={setConfirm}
            oneTimeCode={false}
            error={mismatch}
            ariaLabel={t('security.confirmPin')}
          />
          {mismatch && (
            <Text size="sm" c="red">
              {t('security.pinMismatch')}
            </Text>
          )}
          <Select
            label={t('security.lockAfter')}
            data={minuteOptions}
            value={minutes}
            onChange={(v) => v && setMinutes(v)}
            allowDeselect={false}
            w={180}
          />
          <Group>
            <Button variant="default" onClick={() => setEditing(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={() => void save()} disabled={!isValidPin(pin) || pin !== confirm}>
              {t('common.save')}
            </Button>
          </Group>
        </Stack>
      ) : (
        <Group gap="sm">
          <Button variant="light" leftSection={<IconLock size={16} />} onClick={() => setEditing(true)}>
            {enabled ? t('security.changePin') : t('security.setPin')}
          </Button>
          {enabled && (
            <>
              <Select
                aria-label={t('security.lockAfter')}
                data={minuteOptions}
                value={String(lockAfterMinutes())}
                onChange={(v) => {
                  if (!v) return;
                  setMinutes(v);
                  setLockAfter(Number(v));
                }}
                allowDeselect={false}
                w={160}
              />
              <Button variant="default" onClick={lockNow}>
                {t('security.lockNow')}
              </Button>
              <Button
                variant="subtle"
                color="red"
                onClick={() => {
                  removePin();
                  notifySaved(t('security.pinRemoved'));
                }}
              >
                {t('security.removePin')}
              </Button>
            </>
          )}
        </Group>
      )}
    </Stack>
  );
}

function DevicesSection() {
  const { t } = useTranslation();
  const devices = useDevices();
  const signOut = useSignOutDevice();
  const { reachable } = useHubState();

  const confirmSignOut = (id: string, name: string) =>
    modals.openConfirmModal({
      title: t('security.signOutTitle', { name }),
      children: <Text size="sm">{t('security.signOutBody')}</Text>,
      labels: { confirm: t('security.signOut'), cancel: t('common.cancel') },
      confirmProps: { color: 'red' },
      onConfirm: () =>
        signOut.mutate(id, { onSuccess: () => notifySaved(t('security.signedOut', { name })) }),
    });

  return (
    <Stack gap="xs">
      <Text fw={600}>{t('security.devices')}</Text>
      <Text size="sm" c="dimmed">
        {t('security.devicesHelp')}
      </Text>
      {(devices.data ?? []).map((d) => (
        <Group key={d.id} justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <IconDeviceMobile size={18} />
            <div>
              <Text size="sm" fw={500}>
                {d.name}{' '}
                {d.current && (
                  <Badge size="xs" variant="light" ml={4}>
                    {t('security.thisDevice')}
                  </Badge>
                )}
              </Text>
              <Text size="xs" c="dimmed">
                {t('security.lastUsed', { time: dayjs(d.last_seen_at + 'Z').format('D MMM YYYY, HH:mm') })}
              </Text>
            </div>
          </Group>
          {!d.current && (
            <Button
              size="xs"
              variant="subtle"
              color="red"
              disabled={!reachable}
              onClick={() => confirmSignOut(d.id, d.name)}
            >
              {t('security.signOut')}
            </Button>
          )}
        </Group>
      ))}
    </Stack>
  );
}

function PasswordSection() {
  const { t } = useTranslation();
  const change = useChangePassword();
  const { reachable } = useHubState();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [signOutOthers, setSignOutOthers] = useState(false);
  const mismatch = confirm.length > 0 && confirm !== next;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        change.mutate(
          { current_password: current, new_password: next, sign_out_other_devices: signOutOthers },
          {
            onSuccess: () => {
              notifySaved(t('security.passwordChanged'));
              setCurrent('');
              setNext('');
              setConfirm('');
            },
            onError: (err) => notifyError(errorMessage(err)),
          },
        );
      }}
    >
      <Stack gap="sm" maw={360}>
        <Text fw={600}>{t('security.changePassword')}</Text>
        <PasswordInput
          label={t('security.currentPassword')}
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.currentTarget.value)}
        />
        <PasswordInput
          label={t('security.newPassword')}
          description={t('auth.passwordHelp')}
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.currentTarget.value)}
        />
        <PasswordInput
          label={t('auth.confirmPassword')}
          autoComplete="new-password"
          error={mismatch ? t('auth.mismatch') : undefined}
          value={confirm}
          onChange={(e) => setConfirm(e.currentTarget.value)}
        />
        <Checkbox
          label={t('security.signOutOthers')}
          checked={signOutOthers}
          onChange={(e) => setSignOutOthers(e.currentTarget.checked)}
        />
        <Group>
          <Button
            type="submit"
            loading={change.isPending}
            disabled={!reachable || !current || next.length < 6 || next !== confirm}
          >
            {t('security.changePassword')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

function LogoutSection() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const logout = () => {
    const pending = outboxItems().length;
    modals.openConfirmModal({
      title: t('security.logoutTitle'),
      children: (
        <Stack gap="xs">
          <Text size="sm">{t('security.logoutBody')}</Text>
          {pending > 0 && (
            <Text size="sm" c="red" fw={500}>
              {t('security.logoutPending', { count: pending })}
            </Text>
          )}
        </Stack>
      ),
      labels: { confirm: t('security.logout'), cancel: t('common.cancel') },
      confirmProps: { color: 'red' },
      onConfirm: async () => {
        try {
          await requestLogout();
        } catch (e) {
          // Already signed out, or the laptop is away: still forget the login here.
          if (!(e instanceof ApiError)) notifyError(e);
        }
        removePin();
        await clearOutbox();
        qc.clear();
        await del('fms.queryCache.v1');
        clearAuthToken();
      },
    });
  };

  return (
    <Group>
      <Button variant="light" color="red" leftSection={<IconLogout size={16} />} onClick={logout}>
        {t('security.logout')}
      </Button>
    </Group>
  );
}
