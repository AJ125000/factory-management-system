/** Show changes that haven't reached the hub yet alongside the hub's data. */

import { useMemo } from 'react';

import { pendingProduction, type PendingProduction } from '../lib/localEntries';
import { useOutbox } from '../lib/outbox';
import {
  useLoaderAssignments,
  useMachines,
  useRates,
  useSizes,
  useWorkers,
  useWorkerTypes,
} from './hooks';
import type { ProductionEntry, Worker } from './types';

/**
 * Workers from the hub plus workers added on this device that haven't been sent yet,
 * so production can be entered for a new worker even with the laptop off.
 */
export function useWorkersWithPending(includeArchived = false) {
  const query = useWorkers(includeArchived);
  const types = useWorkerTypes(true).data ?? [];
  const outbox = useOutbox();

  const data = useMemo(() => {
    const server = query.data ?? [];
    const known = new Set(server.map((w) => w.id));
    const pending: Worker[] = [];
    for (const item of outbox) {
      if (item.entity !== 'worker' || item.action !== 'create' || known.has(item.entityId)) continue;
      const body = item.body as Partial<Worker>;
      const type = types.find((t) => t.id === body.worker_type_id);
      if (!type) continue;
      pending.push({
        id: item.entityId,
        name_en: body.name_en ?? '',
        name_hi: body.name_hi ?? null,
        worker_type_id: type.id,
        worker_type: type,
        phone: body.phone ?? null,
        joined_on: body.joined_on ?? null,
        notes: body.notes ?? null,
        archived_at: null,
        is_archived: false,
      });
    }
    return [...server, ...pending].sort((a, b) =>
      a.name_en.localeCompare(b.name_en, undefined, { sensitivity: 'base' }),
    );
  }, [query.data, types, outbox]);

  const pendingIds = useMemo(
    () =>
      new Set(
        outbox
          .filter((i) => i.entity === 'worker' && i.action === 'create')
          .map((i) => i.entityId),
      ),
    [outbox],
  );

  return { ...query, data, pendingIds };
}

/**
 * Production changes waiting on this device, worked out with the same formulas as the
 * laptop, so a phone shows its own entries (and their pay) before they're sent.
 */
export function usePendingProduction(server: ProductionEntry[] = []): PendingProduction {
  const outbox = useOutbox();
  const workers = useWorkersWithPending(true).data;
  const machines = useMachines(true).data;
  const sizes = useSizes().data;
  const rates = useRates().data;
  const assignments = useLoaderAssignments().data;
  return useMemo(
    () =>
      pendingProduction(
        outbox,
        workers ?? [],
        {
          machines: machines ?? [],
          sizes: sizes ?? [],
          rates: rates ?? [],
          assignments: assignments ?? [],
        },
        server,
      ),
    [outbox, workers, machines, sizes, rates, assignments, server],
  );
}
