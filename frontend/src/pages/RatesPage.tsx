import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { modals } from '@mantine/modals';
import { IconInfoCircle, IconPencil, IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useCurrentRates, useDeleteRate, useRates, useSaveRate, useWorkerTypes } from '../api/hooks';
import type { Rate, RateComponent, WorkerType } from '../api/types';
import { DateField, PageHeader, notifySaved } from '../components/common';
import { localName } from '../i18n';
import { formatDate, formatRate, todayISO } from '../lib/format';

export const SCHEME_COMPONENTS: Record<WorkerType['pay_scheme'], RateComponent[]> = {
  cutting: ['cutting'],
  loading: ['loading', 'unloading'],
};

type Dialog =
  | { kind: 'change'; type: WorkerType }
  | { kind: 'correct'; type: WorkerType; rate: Rate }
  | null;

export default function RatesPage() {
  const { t, i18n } = useTranslation();
  const types = useWorkerTypes();
  const rates = useRates();
  const current = useCurrentRates();
  const remove = useDeleteRate();
  const [dialog, setDialog] = useState<Dialog>(null);

  const confirmDelete = (rate: Rate) =>
    modals.openConfirmModal({
      title: t('rates.deleteTitle'),
      children: <Text size="sm">{t('rates.deleteBody')}</Text>,
      labels: { confirm: t('common.delete'), cancel: t('common.cancel') },
      confirmProps: { color: 'red' },
      onConfirm: () => remove.mutate(rate.id, { onSuccess: () => notifySaved(t('common.deleted')) }),
    });

  return (
    <>
      <PageHeader title={t('rates.title')} />
      <Alert icon={<IconInfoCircle />} variant="light" mb="md">
        {t('rates.intro')}
      </Alert>

      <Stack gap="lg">
        {(types.data ?? []).map((wt) => {
          const typeName = localName(wt.name_en, wt.name_hi, i18n.language);
          const history = (rates.data ?? []).filter((r) => r.worker_type_id === wt.id);
          return (
            <Card withBorder key={wt.id}>
              <Group justify="space-between" mb="sm">
                <Title order={3}>{typeName}</Title>
                <Button onClick={() => setDialog({ kind: 'change', type: wt })}>
                  {t('rates.change')}
                </Button>
              </Group>

              <SimpleGrid cols={{ base: 1, xs: SCHEME_COMPONENTS[wt.pay_scheme].length }} mb="md">
                {SCHEME_COMPONENTS[wt.pay_scheme].map((c) => {
                  const cur = current.data?.find(
                    (r) => r.worker_type_id === wt.id && r.component === c,
                  );
                  return (
                    <Card key={c} bg="var(--mantine-color-gray-0)" radius="md" p="md">
                      <Text size="sm" c="dimmed">
                        {t(`components.${c}`)} · {t('rates.current')}
                      </Text>
                      {cur?.rate_per_sqft ? (
                        <>
                          <Text fz={28} fw={700} className="num" ta="left">
                            {formatRate(cur.rate_per_sqft)}
                            <Text span size="sm" c="dimmed" fw={400}>
                              {' '}
                              / {t('units.sqft')}
                            </Text>
                          </Text>
                          <Text size="xs" c="dimmed">
                            {t('rates.since', { date: formatDate(cur.effective_from) })}
                          </Text>
                        </>
                      ) : (
                        <Badge color="orange" variant="light" mt={6}>
                          {t('rates.notSet')}
                        </Badge>
                      )}
                    </Card>
                  );
                })}
              </SimpleGrid>

              <Text fw={600} size="sm" mb={4}>
                {t('rates.history')}
              </Text>
              {history.length === 0 ? (
                <Text size="sm" c="dimmed">
                  {t('rates.noHistory')}
                </Text>
              ) : (
                <Table.ScrollContainer minWidth={480}>
                  <Table>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>{t('rates.component')}</Table.Th>
                        <Table.Th>{t('rates.effectiveFrom')}</Table.Th>
                        <Table.Th className="num">{t('rates.rate')}</Table.Th>
                        <Table.Th>{t('rates.note')}</Table.Th>
                        <Table.Th w={80} />
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {history.map((r) => (
                        <Table.Tr key={r.id}>
                          <Table.Td>{t(`components.${r.component}`)}</Table.Td>
                          <Table.Td>{formatDate(r.effective_from)}</Table.Td>
                          <Table.Td className="num">{formatRate(r.rate_per_sqft)}</Table.Td>
                          <Table.Td>
                            <Text size="sm" c="dimmed" lineClamp={1}>
                              {r.note ?? ''}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Group gap={4} wrap="nowrap">
                              <ActionIcon
                                variant="subtle"
                                color="gray"
                                aria-label={t('rates.correct')}
                                onClick={() => setDialog({ kind: 'correct', type: wt, rate: r })}
                              >
                                <IconPencil size={16} />
                              </ActionIcon>
                              <ActionIcon
                                variant="subtle"
                                color="red"
                                aria-label={t('common.delete')}
                                onClick={() => confirmDelete(r)}
                              >
                                <IconTrash size={16} />
                              </ActionIcon>
                            </Group>
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Table.ScrollContainer>
              )}
            </Card>
          );
        })}
      </Stack>

      <Modal
        opened={dialog !== null}
        onClose={() => setDialog(null)}
        title={
          dialog?.kind === 'correct'
            ? t('rates.correctTitle')
            : dialog
              ? t('rates.changeTitle', {
                  type: localName(dialog.type.name_en, dialog.type.name_hi, i18n.language),
                })
              : ''
        }
      >
        {dialog && <RateForm dialog={dialog} onDone={() => setDialog(null)} />}
      </Modal>
    </>
  );
}

function RateForm({ dialog, onDone }: { dialog: NonNullable<Dialog>; onDone: () => void }) {
  const { t } = useTranslation();
  const save = useSaveRate();
  const components = SCHEME_COMPONENTS[dialog.type.pay_scheme];
  const existing = dialog.kind === 'correct' ? dialog.rate : null;
  const [component, setComponent] = useState<RateComponent>(existing?.component ?? components[0]);
  const [rate, setRate] = useState<string | number>(existing ? Number(existing.rate_per_sqft) : '');
  const [from, setFrom] = useState<string | null>(existing?.effective_from ?? todayISO());
  const [note, setNote] = useState(existing?.note ?? '');

  const valid = rate !== '' && Number(rate) >= 0 && from;

  const submit = () => {
    if (!valid) return;
    const common = { rate_per_sqft: String(rate), effective_from: from!, note: note || null };
    save.mutate(
      existing
        ? { id: existing.id, body: common }
        : { body: { ...common, worker_type_id: dialog.type.id, component } },
      {
        onSuccess: () => {
          notifySaved(t('common.saved'));
          onDone();
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
        {existing && (
          <Alert color="orange" variant="light">
            {t('rates.correctWarning')}
          </Alert>
        )}
        {components.length > 1 && !existing && (
          <Select
            label={t('rates.component')}
            allowDeselect={false}
            value={component}
            onChange={(v) => v && setComponent(v as RateComponent)}
            data={components.map((c) => ({ value: c, label: t(`components.${c}`) }))}
          />
        )}
        <NumberInput
          label={t('rates.rate')}
          required
          data-autofocus
          min={0}
          decimalScale={4}
          prefix="₹ "
          value={rate}
          onChange={setRate}
        />
        <DateField
          label={t('rates.effectiveFrom')}
          description={existing ? undefined : t('rates.effectiveHelp')}
          required
          value={from}
          onChange={setFrom}
        />
        <TextInput
          label={`${t('rates.note')} (${t('common.optional')})`}
          value={note}
          onChange={(e) => setNote(e.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onDone}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" loading={save.isPending} disabled={!valid}>
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
