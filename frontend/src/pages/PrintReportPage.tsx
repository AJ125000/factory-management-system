import './print.css';

import { Alert, Button, Group, Loader, SegmentedControl, Text } from '@mantine/core';
import { IconArrowLeft, IconInfoCircle, IconPrinter } from '@tabler/icons-react';
import dayjs from 'dayjs';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router';

import { useMachines, useProductionSummary, useSettings, useWorkers } from '../api/hooks';
import type { GroupBy, Language } from '../api/types';
import { localName } from '../i18n';
import { formatDate, formatMoney, formatNumber, todayISO } from '../lib/format';

/** Month and day names in the report's language, independent of the app's. */
function label(key: string, groupBy: GroupBy, lang: Language): string {
  if (groupBy === 'day') return dayjs(key).format('DD/MM/YYYY');
  if (groupBy === 'month') return dayjs(`${key}-01`).locale(lang).format('MMMM YYYY');
  return key;
}

export default function PrintReportPage() {
  const { t: uiT, i18n } = useTranslation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const start = params.get('start') ?? '';
  const end = params.get('end') ?? '';
  const groupBy = (['day', 'month', 'year'].includes(params.get('group_by') ?? '')
    ? params.get('group_by')
    : 'month') as GroupBy;
  const lang: Language = params.get('lang') === 'hi' ? 'hi' : 'en';
  const workerId = params.get('worker');
  const t = i18n.getFixedT(lang);

  const settings = useSettings().data;
  const machineId = params.get('machine');
  const summary = useProductionSummary(
    start,
    end,
    groupBy,
    workerId ? [workerId] : undefined,
    machineId ?? undefined,
  );
  const machine = useMachines(true).data?.find((m) => m.id === machineId);
  const worker = useWorkers(true).data?.find((w) => w.id === workerId);

  useEffect(() => {
    document.title = `${t('reports.printTitle')} ${formatDate(start, 'short')} – ${formatDate(end, 'short')}`;
  }, [t, start, end]);

  const totals = summary.data?.totals;

  return (
    <div className="slip-page" lang={lang}>
      <div className="slip-toolbar no-print">
        <Group justify="space-between" wrap="wrap" gap="sm">
          <Button variant="default" leftSection={<IconArrowLeft size={18} />} onClick={() => navigate(-1)}>
            {uiT('common.back')}
          </Button>
          <Group gap="sm">
            <SegmentedControl
              value={lang}
              onChange={(v) =>
                setParams(
                  (p) => {
                    p.set('lang', v);
                    return p;
                  },
                  { replace: true },
                )
              }
              data={[
                { value: 'hi', label: 'हिंदी' },
                { value: 'en', label: 'English' },
              ]}
            />
            <Button leftSection={<IconPrinter size={18} />} onClick={() => window.print()}>
              {uiT('common.print')}
            </Button>
          </Group>
        </Group>
        <Alert icon={<IconInfoCircle />} variant="light" mt="sm">
          {uiT('reports.pdfHint')}
        </Alert>
      </div>

      {!summary.data || !settings ? (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      ) : summary.data.buckets.length === 0 ? (
        <Text ta="center" py="xl">
          {uiT('reports.noData')}
        </Text>
      ) : (
        <section className="slip">
          <header className="slip-header">
            <div>
              <div className="slip-factory">
                {localName(settings.factory_name_en, settings.factory_name_hi, lang)}
              </div>
              {settings.factory_address && <div className="sub">{settings.factory_address}</div>}
            </div>
            <div className="slip-title">{t('reports.printTitle')}</div>
          </header>

          <dl className="slip-info">
            <dt>{t('reports.period')}:</dt>
            <dd>
              {formatDate(start, 'short')} – {formatDate(end, 'short')}
            </dd>
            <dt>{t('reports.groupedBy')}:</dt>
            <dd>{t(`reports.${groupBy}`)}</dd>
            <dt>{t('production.worker')}:</dt>
            <dd>{worker ? localName(worker.name_en, worker.name_hi, lang) : t('reports.allWorkers')}</dd>
            {machine && (
              <>
                <dt>{t('production.machine')}:</dt>
                <dd>{localName(machine.name_en, machine.name_hi, lang)}</dd>
              </>
            )}
          </dl>

          <table>
            <thead>
              <tr>
                <th>{t(`reports.${groupBy}`)}</th>
                <th className="num">{t('wages.entries')}</th>
                <th className="num">{t('metrics.pieces')}</th>
                <th className="num">{t('metrics.area')}</th>
                <th className="num">{t('wages.rft')}</th>
                <th className="num">{t('metrics.wages')}</th>
              </tr>
            </thead>
            <tbody>
              {summary.data.buckets.map((b) => (
                <tr key={b.period}>
                  <td>{label(b.period, groupBy, lang)}</td>
                  <td className="num">{formatNumber(b.entry_count)}</td>
                  <td className="num">{formatNumber(b.total_quantity)}</td>
                  <td className="num">{formatNumber(b.total_area_sqft)}</td>
                  <td className="num">{formatNumber(b.total_rft)}</td>
                  <td className="num">{formatMoney(b.total_wage)}</td>
                </tr>
              ))}
            </tbody>
            {totals && (
              <tfoot>
                <tr>
                  <td>{t('common.total')}</td>
                  <td className="num">{formatNumber(totals.entry_count)}</td>
                  <td className="num">{formatNumber(totals.total_quantity)}</td>
                  <td className="num">{formatNumber(totals.total_area_sqft)}</td>
                  <td className="num">{formatNumber(totals.total_rft)}</td>
                  <td className="num slip-total">{formatMoney(totals.total_wage)}</td>
                </tr>
              </tfoot>
            )}
          </table>
          <div className="slip-printed">{t('slip.printedOn', { date: formatDate(todayISO(), 'short') })}</div>
        </section>
      )}
    </div>
  );
}
