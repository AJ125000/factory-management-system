import {
  Badge,
  Button,
  Card,
  Group,
  Modal,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core';
import { IconPlus } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useSaveWorkerType, useSettings, useUpdateSettings, useWorkerTypes } from '../api/hooks';
import type { AppSettings, Language, PayPeriod, PayScheme, WorkerType } from '../api/types';
import { ConnectPhone } from '../components/ConnectPhone';
import { PageHeader, notifySaved } from '../components/common';
import { localName, setUiLanguage } from '../i18n';
import { useHubState } from '../lib/hub';

export default function SettingsPage() {
  const { t } = useTranslation();
  return (
    <>
      <PageHeader title={t('settings.title')} />
      <Stack gap="lg" maw={900}>
        <FactorySettings />
        <ConnectPhone />
        <WorkerTypes />
      </Stack>
    </>
  );
}

function FactorySettings() {
  const { t } = useTranslation();
  const settings = useSettings();
  const update = useUpdateSettings();
  const { reachable } = useHubState();
  const [values, setValues] = useState<AppSettings | null>(null);
  useEffect(() => {
    if (settings.data && !values) setValues(settings.data);
  }, [settings.data, values]);
  if (!values) return null;

  const set = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) =>
    setValues((v) => (v ? { ...v, [key]: value } : v));

  const save = () =>
    update.mutate(values, {
      onSuccess: (saved) => {
        setUiLanguage(saved.ui_language);
        notifySaved(t('common.saved'));
      },
    });

  const languages = [
    { value: 'en', label: 'English' },
    { value: 'hi', label: 'हिंदी' },
  ];

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
    >
      <Card withBorder>
        <Title order={4}>{t('settings.factory')}</Title>
        <Text size="sm" c="dimmed" mb="sm">
          {t('settings.factoryHelp')}
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 2 }} mb="sm">
          <TextInput
            label={t('settings.factoryNameEn')}
            required
            value={values.factory_name_en}
            onChange={(e) => set('factory_name_en', e.currentTarget.value)}
          />
          <TextInput
            label={t('settings.factoryNameHi')}
            lang="hi"
            value={values.factory_name_hi}
            onChange={(e) => set('factory_name_hi', e.currentTarget.value)}
          />
        </SimpleGrid>
        <Textarea
          label={t('settings.address')}
          autosize
          minRows={2}
          mb="lg"
          value={values.factory_address}
          onChange={(e) => set('factory_address', e.currentTarget.value)}
        />

        <Title order={4} mb="sm">
          {t('settings.preferences')}
        </Title>
        <SimpleGrid cols={{ base: 1, sm: 3 }} mb="md">
          <Select
            label={t('settings.uiLanguage')}
            allowDeselect={false}
            data={languages}
            value={values.ui_language}
            onChange={(v) => v && set('ui_language', v as Language)}
          />
          <Select
            label={t('settings.printLanguage')}
            allowDeselect={false}
            data={languages}
            value={values.print_language}
            onChange={(v) => v && set('print_language', v as Language)}
          />
          <Select
            label={t('settings.payPeriod')}
            allowDeselect={false}
            data={[
              { value: 'half_month', label: t('settings.halfMonth') },
              { value: 'month', label: t('settings.month') },
            ]}
            value={values.pay_period}
            onChange={(v) => v && set('pay_period', v as PayPeriod)}
          />
        </SimpleGrid>
        <Group justify="flex-end">
          {!reachable && (
            <Text size="sm" c="dimmed">
              {t('sync.needsLaptop')}
            </Text>
          )}
          <Button
            type="submit"
            loading={update.isPending}
            disabled={!values.factory_name_en.trim() || !reachable}
          >
            {t('common.save')}
          </Button>
        </Group>
      </Card>
    </form>
  );
}

function WorkerTypes() {
  const { t, i18n } = useTranslation();
  const types = useWorkerTypes(true);
  const save = useSaveWorkerType();
  const { reachable } = useHubState();
  const [editing, setEditing] = useState<WorkerType | 'new' | null>(null);

  const schemeLabel = (s: PayScheme) =>
    s === 'cutting' ? t('settings.schemeCutting') : t('settings.schemeLoading');

  return (
    <Card withBorder>
      <Group justify="space-between" mb={4}>
        <Title order={4}>{t('settings.workerTypes')}</Title>
        <Button
          variant="light"
          leftSection={<IconPlus size={16} />}
          disabled={!reachable}
          title={reachable ? undefined : t('sync.needsLaptop')}
          onClick={() => setEditing('new')}
        >
          {t('settings.addType')}
        </Button>
      </Group>
      <Text size="sm" c="dimmed" mb="sm">
        {t('settings.workerTypesHelp')}
      </Text>
      <Table.ScrollContainer minWidth={520}>
        <Table>
          <Table.Tbody>
            {(types.data ?? []).map((wt) => (
              <Table.Tr key={wt.id} opacity={wt.is_active ? 1 : 0.6}>
                <Table.Td fw={500}>{localName(wt.name_en, wt.name_hi, i18n.language)}</Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {schemeLabel(wt.pay_scheme)}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" color={wt.is_active ? 'teal' : 'gray'}>
                    {wt.is_active ? t('settings.inUse') : t('settings.notInUse')}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs" justify="flex-end" wrap="nowrap">
                    <Button size="xs" variant="subtle" disabled={!reachable} onClick={() => setEditing(wt)}>
                      {t('common.edit')}
                    </Button>
                    <Button
                      size="xs"
                      variant="subtle"
                      color={wt.is_active ? 'gray' : 'teal'}
                      disabled={!reachable}
                      onClick={() =>
                        save.mutate(
                          { id: wt.id, is_active: !wt.is_active },
                          { onSuccess: () => notifySaved(t('common.saved')) },
                        )
                      }
                    >
                      {wt.is_active ? t('settings.stopUsing') : t('settings.useAgain')}
                    </Button>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      <Modal
        opened={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? t('settings.addType') : t('common.edit')}
      >
        {editing && (
          <WorkerTypeForm
            type={editing === 'new' ? null : editing}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>
    </Card>
  );
}

function WorkerTypeForm({ type, onDone }: { type: WorkerType | null; onDone: () => void }) {
  const { t } = useTranslation();
  const save = useSaveWorkerType();
  const [nameEn, setNameEn] = useState(type?.name_en ?? '');
  const [nameHi, setNameHi] = useState(type?.name_hi ?? '');
  const [scheme, setScheme] = useState<PayScheme>(type?.pay_scheme ?? 'cutting');

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(
          type
            ? { id: type.id, name_en: nameEn, name_hi: nameHi || null }
            : { name_en: nameEn, name_hi: nameHi || null, pay_scheme: scheme },
          {
            onSuccess: () => {
              notifySaved(t('common.saved'));
              onDone();
            },
          },
        );
      }}
    >
      <Stack>
        <TextInput
          label={t('settings.typeNameEn')}
          required
          data-autofocus
          value={nameEn}
          onChange={(e) => setNameEn(e.currentTarget.value)}
        />
        <TextInput
          label={t('settings.typeNameHi')}
          lang="hi"
          value={nameHi}
          onChange={(e) => setNameHi(e.currentTarget.value)}
        />
        <Select
          label={t('settings.payScheme')}
          allowDeselect={false}
          disabled={type !== null} // fixed once created: existing rates depend on it
          data={[
            { value: 'cutting', label: t('settings.schemeCutting') },
            { value: 'loading', label: t('settings.schemeLoading') },
          ]}
          value={scheme}
          onChange={(v) => v && setScheme(v as PayScheme)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onDone}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" loading={save.isPending} disabled={!nameEn.trim()}>
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
