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

/** Cuts / batti / shift, when the machine has them: "2 cuts", "4 batti", "Night shift". */
export function entryDetails(
  e: Pick<ProductionEntry, 'cuts' | 'batti'> & { shift?: ProductionEntry['shift'] },
  t: T,
): string {
  if (e.shift) return t(`shifts.${e.shift}`);
  return [
    e.cuts ? `${e.cuts} ${String(t('production.cuts')).toLowerCase()}` : '',
    e.batti ? t('production.battiCount', { count: e.batti }) : '',
  ]
    .filter(Boolean)
    .join(' · ');
}

/** Splitting machine: "Machine man prod. (sq ft): 120 · Unloading prod. (sq ft): 90". */
export function splittingText(
  e: Pick<ProductionEntry, 'cutting_sqft' | 'unloading_sqft'>,
  t: T,
): string {
  if (e.cutting_sqft === null || e.unloading_sqft === null) return '';
  return `${t('production.cuttingSqft')}: ${formatNumber(e.cutting_sqft)} · ${t('production.unloadingSqft')}: ${formatNumber(e.unloading_sqft)}`;
}

const unitKey = (l: Pick<WageLine, 'unit'>) =>
  l.unit === 'rft' ? 'units.rft' : l.unit === 'shift' ? 'units.shift' : 'units.sqft';

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
  'block_cutter',
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
