import { AppShell, Burger, Group, NavLink, SegmentedControl, Text, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconCoinRupee,
  IconPercentage,
  IconSettings,
  IconStack2,
  IconUsers,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { NavLink as RouterLink, Outlet, useLocation } from 'react-router';

import { useSettings, useUpdateSettings } from '../api/hooks';
import type { Language } from '../api/types';
import { localName, setUiLanguage } from '../i18n';

const LINKS = [
  { to: '/production', key: 'nav.production', icon: IconStack2 },
  { to: '/wages', key: 'nav.wages', icon: IconCoinRupee },
  { to: '/workers', key: 'nav.workers', icon: IconUsers },
  { to: '/rates', key: 'nav.rates', icon: IconPercentage },
  { to: '/settings', key: 'nav.settings', icon: IconSettings },
] as const;

export function LanguageToggle() {
  const { i18n } = useTranslation();
  const update = useUpdateSettings();
  return (
    <SegmentedControl
      size="xs"
      value={i18n.language}
      onChange={(value) => {
        const lang = value as Language;
        setUiLanguage(lang);
        update.mutate({ ui_language: lang });
      }}
      data={[
        { value: 'en', label: 'EN' },
        { value: 'hi', label: 'हिं' },
      ]}
      aria-label="Language"
    />
  );
}

export default function AppLayout() {
  const { t, i18n } = useTranslation();
  const [opened, { toggle, close }] = useDisclosure();
  const { pathname } = useLocation();
  const settings = useSettings().data;
  const factory = settings
    ? localName(settings.factory_name_en, settings.factory_name_hi, i18n.language)
    : '';

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <img src="/icon.png" alt="" width={28} height={28} />
            <div>
              <Title order={4} lh={1.1}>
                {t('app.short')}
              </Title>
              <Text size="xs" c="dimmed" lh={1.1} truncate maw={220}>
                {factory}
              </Text>
            </div>
          </Group>
          <LanguageToggle />
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        {LINKS.map(({ to, key, icon: Icon }) => (
          <NavLink
            key={to}
            component={RouterLink}
            to={to}
            label={t(key)}
            leftSection={<Icon size={20} stroke={1.6} />}
            active={pathname.startsWith(to)}
            onClick={close}
            styles={{ label: { fontSize: 'var(--mantine-font-size-md)' } }}
          />
        ))}
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
