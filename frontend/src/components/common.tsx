import { Group, Select, Stack, Text, Title } from '@mantine/core';
import { DateInput, DatePickerInput, type DateInputProps } from '@mantine/dates';
import { notifications } from '@mantine/notifications';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import type { Worker } from '../api/types';
import { localName } from '../i18n';
import { errorMessage } from '../lib/errors';
import { DATE_INPUT_FORMAT, parseTypedDate } from '../lib/format';
import { PRESETS, presetPeriod, type Period, type PeriodPreset } from '../lib/periods';

/** A date box that types and shows dates day-first (DD/MM/YYYY). Use instead of DateInput. */
export function DateField(props: DateInputProps) {
  return (
    <DateInput valueFormat={DATE_INPUT_FORMAT} dateParser={parseTypedDate} placeholder="DD/MM/YYYY" {...props} />
  );
}

export function PageHeader({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <Group justify="space-between" mb="md" wrap="wrap" gap="sm">
      <Title order={2}>{title}</Title>
      {actions && <Group gap="sm">{actions}</Group>}
    </Group>
  );
}

export function notifySaved(message: string) {
  notifications.show({ color: 'teal', message, autoClose: 2500 });
}

export function notifyError(error: unknown) {
  notifications.show({
    color: 'red',
    message: typeof error === 'string' ? error : errorMessage(error),
  });
}

/** A worker's name with their Hindi name underneath (or the other way round in Hindi). */
export function WorkerName({ nameEn, nameHi }: { nameEn: string; nameHi: string | null }) {
  const { i18n } = useTranslation();
  const primary = localName(nameEn, nameHi, i18n.language);
  const secondary = primary === nameEn ? nameHi : nameEn;
  return (
    <Stack gap={0}>
      <Text size="sm" fw={500}>
        {primary}
      </Text>
      {secondary && (
        <Text size="xs" c="dimmed">
          {secondary}
        </Text>
      )}
    </Stack>
  );
}

export function workerOptions(workers: Worker[], lang: string) {
  return workers.map((w) => ({
    value: w.id,
    label: `${localName(w.name_en, w.name_hi, lang)}${
      lang === 'hi' || !w.name_hi ? '' : ` (${w.name_hi})`
    } · ${localName(w.worker_type.name_en, w.worker_type.name_hi, lang)}`,
  }));
}

export interface PeriodValue extends Period {
  preset: PeriodPreset | 'custom';
}

export function periodFromPreset(preset: PeriodPreset): PeriodValue {
  return { preset, ...presetPeriod(preset) };
}

/** Quick pay-period choices, plus a custom date range. */
export function PeriodPicker({
  value,
  onChange,
}: {
  value: PeriodValue;
  onChange: (value: PeriodValue) => void;
}) {
  const { t } = useTranslation();
  return (
    <Group gap="sm" align="flex-end" wrap="wrap">
      <Select
        label={t('periods.range')}
        w={190}
        allowDeselect={false}
        value={value.preset}
        data={[
          ...PRESETS.map((p) => ({ value: p, label: t(`periods.${p}`) })),
          { value: 'custom', label: t('periods.custom') },
        ]}
        onChange={(preset) => {
          if (!preset || preset === 'custom') onChange({ ...value, preset: 'custom' });
          else onChange(periodFromPreset(preset as PeriodPreset));
        }}
      />
      <DatePickerInput
        type="range"
        w={260}
        valueFormat="D MMM YYYY"
        value={[value.start, value.end]}
        allowSingleDateInRange
        onChange={([start, end]) => {
          if (start && end) onChange({ preset: 'custom', start, end });
        }}
      />
    </Group>
  );
}
