import './print.css';

import { Alert, Button, Group, Loader, SegmentedControl, Text } from '@mantine/core';
import { IconAlertTriangle, IconArrowLeft, IconPrinter } from '@tabler/icons-react';
import type { TFunction } from 'i18next';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router';

import { useMachines, useSettings, useWagesReport, useWorkers } from '../api/hooks';
import type { AppSettings, Language, Machine, Worker, WorkerWages } from '../api/types';
import { localName } from '../i18n';
import { componentLabel, entryDetails, entrySize, lineBasis, lineRate } from '../lib/entryText';
import { formatAmount, formatDate, formatMoney, formatNumber, todayISO } from '../lib/format';

export default function PrintSlipsPage() {
  const { t: uiT, i18n } = useTranslation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const start = params.get('start') ?? '';
  const end = params.get('end') ?? '';
  const lang: Language = params.get('lang') === 'en' ? 'en' : 'hi';
  const layout = params.get('layout') === 'compact' ? 'compact' : 'one-per-page';
  const workerIds = params.get('workers')?.split(',').filter(Boolean);

  const settings = useSettings().data;
  const machines = useMachines(true).data ?? [];
  const workers = useWorkers(true).data ?? [];
  const report = useWagesReport(start, end, { includeEntries: true, workerIds });
  const t = i18n.getFixedT(lang); // the slip's language, independent of the app's

  const setParam = (key: string, value: string) =>
    setParams(
      (p) => {
        p.set(key, value);
        return p;
      },
      { replace: true },
    );

  useEffect(() => {
    document.title = `${t('slip.title')} ${formatDate(start, 'short')} – ${formatDate(end, 'short')}`;
  }, [t, start, end]);

  const rows = report.data?.workers ?? [];
  const incomplete = rows.some((r) => r.missing_rate_entries > 0);

  return (
    <div className={`slip-page ${layout}`} lang={lang}>
      <div className="slip-toolbar no-print">
        <Group justify="space-between" wrap="wrap" gap="sm">
          <Button variant="default" leftSection={<IconArrowLeft size={18} />} onClick={() => navigate(-1)}>
            {uiT('common.back')}
          </Button>
          <Group gap="sm" wrap="wrap">
            <SegmentedControl
              value={lang}
              onChange={(v) => setParam('lang', v)}
              data={[
                { value: 'hi', label: 'हिंदी' },
                { value: 'en', label: 'English' },
              ]}
            />
            <SegmentedControl
              value={layout}
              onChange={(v) => setParam('layout', v)}
              data={[
                { value: 'one-per-page', label: uiT('slip.onePerPage') },
                { value: 'compact', label: uiT('slip.compact') },
              ]}
            />
            <Button
              leftSection={<IconPrinter size={18} />}
              onClick={() => window.print()}
              disabled={!rows.length}
            >
              {uiT('common.print')}
            </Button>
          </Group>
        </Group>
        {incomplete && (
          <Alert color="orange" icon={<IconAlertTriangle />} mt="sm">
            {uiT('slip.incomplete')}
          </Alert>
        )}
      </div>

      {report.isLoading || !settings ? (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      ) : rows.length === 0 ? (
        <Text ta="center" py="xl" className="no-print">
          {uiT('slip.nothing')}
        </Text>
      ) : (
        rows.map((row) => (
          <Slip key={row.worker_id} row={row} t={t} lang={lang} settings={settings} start={start} end={end} machines={machines} workers={workers} />
        ))
      )}
    </div>
  );
}

function Slip({
  row,
  t,
  lang,
  settings,
  start,
  end,
  machines,
  workers,
}: {
  row: WorkerWages;
  t: TFunction;
  lang: Language;
  settings: AppSettings;
  start: string;
  end: string;
  machines: Machine[];
  workers: Worker[];
}) {
  const entries = row.entries ?? [];
  const machineName = (id: string) => {
    const m = machines.find((x) => x.id === id);
    return m ? localName(m.name_en, m.name_hi, lang) : '';
  };
  const workerName = (id: string) => {
    const w = workers.find((x) => x.id === id);
    return w ? localName(w.name_en, w.name_hi, lang) : '';
  };
  return (
    <section className="slip">
      <header className="slip-header">
        <div>
          <div className="slip-factory">
            {localName(settings.factory_name_en, settings.factory_name_hi, lang)}
          </div>
          {settings.factory_address && <div className="sub">{settings.factory_address}</div>}
        </div>
        <div className="slip-title">{t('slip.title')}</div>
      </header>

      <dl className="slip-info">
        <dt>{t('slip.worker')}:</dt>
        <dd>{localName(row.name_en, row.name_hi, lang)}</dd>
        <dt>{t('slip.period')}:</dt>
        <dd>
          {formatDate(start, 'short')} – {formatDate(end, 'short')}
        </dd>
        <dt>{t('slip.type')}:</dt>
        <dd>{localName(row.worker_type_name_en, row.worker_type_name_hi, lang)}</dd>
        <dt>{t('slip.entries')}:</dt>
        <dd>{row.entry_count}</dd>
      </dl>

      <table>
        <thead>
          <tr>
            <th>{t('slip.date')}</th>
            <th>{t('slip.machine')}</th>
            <th>{t('slip.size')}</th>
            <th className="num">{t('slip.qty')}</th>
            <th className="num">{t('slip.basis')}</th>
            <th className="num">{t('slip.rate')}</th>
            <th className="num">{t('slip.amount')}</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => {
            const details = entryDetails(e, t);
            const many = e.wage_lines.length > 1;
            return (
              <tr key={`${e.id}-${e.paid_as}`}>
                <td>{formatDate(e.entry_date, 'short')}</td>
                <td>
                  {machineName(e.machine_id)}
                  {e.paid_as === 'loader' && (
                    <div className="sub">
                      {t('slip.operator')}: {workerName(e.worker_id)}
                    </div>
                  )}
                </td>
                <td>
                  {entrySize(e, t)}
                  {details && <div className="sub">{details}</div>}
                </td>
                <td className="num">{e.quantity}</td>
                <td className="num">
                  {e.wage_lines.map((l) => (
                    <div key={l.component} className={many ? 'sub' : undefined}>
                      {many && `${componentLabel(t, l.component)} `}
                      {lineBasis(l, t)}
                    </div>
                  ))}
                </td>
                <td className="num">
                  {e.wage_lines.length === 0
                    ? t('slip.rateMissing')
                    : e.wage_lines.map((l) => (
                        <div key={l.component} className={many ? 'sub' : undefined}>
                          {lineRate(l, t).replace('₹', '')}
                        </div>
                      ))}
                </td>
                <td className="num">
                  {e.wage === null ? '—' : formatAmount(e.wage)}
                  {many && (
                    <div className="sub">{e.wage_lines.map((l) => formatAmount(l.amount)).join(' + ')}</div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={3}>{t('common.total')}</td>
            <td className="num">{row.total_quantity}</td>
            <td className="num">
              {formatNumber(row.total_area_sqft)} {t('units.sqft')}
              {Number(row.total_rft) > 0 && (
                <div className="sub">
                  {formatNumber(row.total_rft)} {t('units.rft')}
                </div>
              )}
            </td>
            <td className="num slip-total">{t('slip.totalWage')}</td>
            <td className="num slip-total">{formatMoney(row.total_wage)}</td>
          </tr>
        </tfoot>
      </table>

      <div className="slip-signatures">
        <div>{t('slip.workerSign')}</div>
        <div>{t('slip.ownerSign')}</div>
      </div>
      <div className="slip-printed">{t('slip.printedOn', { date: formatDate(todayISO(), 'short') })}</div>
    </section>
  );
}
