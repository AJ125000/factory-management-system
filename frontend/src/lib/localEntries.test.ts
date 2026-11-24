import { describe, expect, it } from 'vitest';

import type { Machine, ProductionEntry, ProductionInput, Rate, Worker, WorkerWages } from '../api/types';
import { localEntry, pendingProduction, withPendingWages, type LocalData } from './localEntries';
import type { OutboxItem } from './outbox';

const machine = (id: string, kind: Machine['kind']): Machine => ({
  id,
  code: id,
  kind,
  name_en: id,
  name_hi: null,
  sort_order: 0,
  is_active: true,
});
const rate = (kind: Machine['kind'], component: string, value: string): Rate => ({
  id: `${kind}-${component}`,
  kind,
  component,
  unit: component === 'shift' ? 'shift' : 'sqft',
  rate: value,
  effective_from: '2026-01-01',
  note: null,
});
const worker = (id: string, role: 'operator' | 'loader'): Worker => ({
  id,
  name_en: id,
  name_hi: null,
  worker_type_id: role,
  worker_type: { id: role, code: role, name_en: role, name_hi: null, role, is_active: true },
  phone: null,
  joined_on: null,
  notes: null,
  archived_at: null,
  is_archived: false,
});

const data: LocalData = {
  machines: [machine('split', 'block_cutting'), machine('bc', 'block_cutter')],
  sizes: [],
  rates: [
    rate('block_cutting', 'cutting', '1.5'),
    rate('block_cutting', 'loading', '0.5'),
    rate('block_cutting', 'unloading', '0.25'),
    rate('block_cutter', 'shift', '450'),
  ],
  assignments: [
    { id: 'a', machine_id: 'split', worker_id: 'raju', effective_from: '2026-01-01', note: null },
  ],
};
const people = [worker('ramesh', 'operator'), worker('raju', 'loader')];

const splitInput: ProductionInput = {
  worker_id: 'ramesh',
  machine_id: 'split',
  entry_date: '2026-03-02',
  length_ft: '2',
  width_ft: '3',
  size_id: null,
  cuts: 2,
  batti: null,
  shift: null,
  quantity: 5,
  loader_id: null,
};
const shiftInput: ProductionInput = {
  ...splitInput,
  machine_id: 'bc',
  length_ft: null,
  width_ft: null,
  cuts: 0,
  shift: 'night',
  quantity: 1,
};

const item = (entityId: string, action: OutboxItem['action'], body?: object): OutboxItem => ({
  id: `o-${entityId}-${action}`,
  createdAt: 0,
  entity: 'production',
  action,
  entityId,
  method: action === 'create' ? 'POST' : action === 'delete' ? 'DELETE' : 'PATCH',
  path: '/production',
  body: body as Record<string, unknown>,
  label: '',
  status: 'pending',
});

describe('entries worked out on the device', () => {
  it('matches the hub for a splitting machine entry', () => {
    const e = localEntry('e1', splitInput, 'operator', data)!;
    expect(e.wage).toBe('180.00'); // 2 x 6 x 2 x 5 x 1.5
    expect(e.loader_worker_id).toBe('raju');
    expect(e.loader_wage).toBe('37.50'); // 30 x 0.5 + 90 x 0.25
    expect([e.area_sqft, e.cutting_sqft, e.unloading_sqft]).toEqual(['30', '120', '90']);
    expect(e.wage_lines[0]).toMatchObject({ basis: '120', unit: 'sqft', rate: '1.5' });
  });

  it('pays a block cutter shift with no loader', () => {
    const e = localEntry('e2', shiftInput, 'operator', data)!;
    expect(e.wage).toBe('450.00');
    expect(e.shift).toBe('night');
    expect(e.loader_worker_id).toBeNull();
    expect(e.no_loader).toBe(false);
    expect(e.cutting_sqft).toBeNull();
    expect(localEntry('e3', { ...shiftInput, shift: null }, 'operator', data)).toBeNull();
  });
});

describe('waiting changes in the lists', () => {
  const server = localEntry('s1', splitInput, 'operator', data)! as ProductionEntry;

  it('collects new, edited and deleted entries', () => {
    const p = pendingProduction(
      [
        item('n1', 'create', { ...shiftInput, id: 'n1' }),
        item('s1', 'update', { ...splitInput, quantity: 10 }),
      ],
      people,
      data,
      [server],
    );
    expect(p.created.map((e) => e.wage)).toEqual(['450.00']);
    expect(p.edited.get('s1')?.wage).toBe('360.00');
    const gone = pendingProduction([item('s1', 'delete')], people, data, [server]);
    expect(gone.deleted.has('s1')).toBe(true);
  });

  it('adds waiting entries to the wages report', () => {
    const report: WorkerWages[] = [
      {
        worker_id: 'ramesh',
        name_en: 'ramesh',
        name_hi: null,
        worker_type_name_en: 'operator',
        worker_type_name_hi: null,
        role: 'operator',
        is_archived: false,
        entry_count: 1,
        total_quantity: 5,
        total_area_sqft: '30.00',
        total_rft: '0.00',
        total_cuts: 10,
        total_shifts: 0,
        total_wage: '180.00',
        missing_rate_entries: 0,
        entries: [server],
      },
    ];
    const p = pendingProduction(
      [item('n1', 'create', shiftInput), item('n2', 'create', { ...splitInput, entry_date: '2026-05-01' })],
      people,
      data,
    );
    const rows = withPendingWages(report, p, '2026-03-01', '2026-03-31', people);
    expect(rows).toHaveLength(1); // the May entry is outside the period; the shift pays no loader
    expect(rows[0]).toMatchObject({ total_wage: '630.00', total_shifts: 1, entry_count: 2, pending: true });

    const deleted = pendingProduction([item('s1', 'delete')], people, data, [server]);
    expect(withPendingWages(report, deleted, '2026-03-01', '2026-03-31', people)).toEqual([]);

    const loaderToo = pendingProduction([item('n3', 'create', splitInput)], people, data);
    const withLoader = withPendingWages([], loaderToo, '2026-03-01', '2026-03-31', people);
    expect(withLoader.map((r) => [r.worker_id, r.total_wage])).toEqual([
      ['raju', '37.50'],
      ['ramesh', '180.00'],
    ]);
  });
});
