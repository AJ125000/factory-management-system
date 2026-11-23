/** How entries, sizes and wage lines are written on screens and wage slips. */

import type { TFunction } from 'i18next';

import type { Machine, MachineKind, ProductionEntry, RateComponent, WageLine } from '../api/types';
import { localName } from '../i18n';
import { formatFeet, formatNumber, formatRate } from './format';
import { battiOf } from './wages';

type T = TFunction | ((key: string, options?: Record<string, unknown>) => string);

/** "Cutting", "Polish, 4 batti", ... */
export function componentLabel(t: T, component: RateComponent): string {
  const batti = battiOf(component);
  return batti ? t('components.polish', { count: batti }) : t(`components.${component}`);
}

/** "2 × 1½ ft", "22½ × 22½ in" — an entry's size. */
export function entrySize(
  e: Pick<ProductionEntry, 'length_ft' | 'width_ft' | 'size_label'>,
  t: T,
): string {
  if (e.size_label && e.length_ft === null) return `${e.size_label} ${t('units.in')}`;
  if (e.length_ft !== null && e.width_ft !== null) {
    return `${e.size_label ?? `${formatFeet(e.length_ft)} × ${formatFeet(e.width_ft)}`} ${t('units.ft')}`;
  }
  return e.size_label ?? '';
}

/** Cuts / batti, when the machine has them: "2 cuts", "4 batti". */
export function entryDetails(e: Pick<ProductionEntry, 'cuts' | 'batti'>, t: T): string {
  return [
    e.cuts ? `${e.cuts} ${String(t('production.cuts')).toLowerCase()}` : '',
    e.batti ? t('production.battiCount', { count: e.batti }) : '',
  ]
    .filter(Boolean)
    .join(' · ');
}

const unitKey = (l: Pick<WageLine, 'unit'>) => (l.unit === 'rft' ? 'units.rft' : 'units.sqft');

/** "80 running ft", "45 sq ft" — what a wage line's rate was multiplied by. */
export function lineBasis(l: WageLine, t: T): string {
  return `${formatNumber(l.basis)} ${t(unitKey(l))}`;
}

/** "₹0.22/running ft" */
export function lineRate(l: WageLine, t: T): string {
  return `${formatRate(l.rate)}/${t(unitKey(l))}`;
}

export const MACHINE_KINDS: MachineKind[] = [
  'double_edge',
  'table_polish',
  'single_cutting',
  'block_cutting',
];

/** Machines for a dropdown, grouped by type: "Table polish" → machine 1, machine 2... */
export function machineOptions(machines: Machine[], t: T, lang: string) {
  return MACHINE_KINDS.map((kind) => ({
    group: String(t(`machineKinds.${kind}`)),
    items: machines
      .filter((m) => m.kind === kind)
      .map((m) => ({ value: m.id, label: localName(m.name_en, m.name_hi, lang) })),
  })).filter((g) => g.items.length > 0);
}
