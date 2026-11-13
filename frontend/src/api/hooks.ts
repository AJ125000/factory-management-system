/** React Query hooks: one place that knows every endpoint and what to refresh after changes. */

import { useMutation, useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query';

import { api } from './client';
import type {
  AppSettings,
  CurrentRate,
  ISODate,
  PayScheme,
  ProductionEntry,
  ProductionInput,
  ProductionSummary,
  GroupBy,
  Rate,
  RateComponent,
  WagePreview,
  WagesReport,
  Worker,
  WorkerInput,
  WorkerType,
} from './types';

export const keys = {
  settings: ['settings'] as const,
  workerTypes: ['worker-types'] as const,
  workers: ['workers'] as const,
  rates: ['rates'] as const,
  production: ['production'] as const,
  reports: ['reports'] as const,
};

/** Data that depends on workers, rates or entries — refreshed after any change to them. */
const DERIVED: QueryKey[] = [keys.production, keys.reports];

function useInvalidate() {
  const qc = useQueryClient();
  return (...groups: QueryKey[]) =>
    Promise.all(groups.map((queryKey) => qc.invalidateQueries({ queryKey })));
}

// ------------------------------------------------------------------ settings
export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: () => api<AppSettings>('GET', '/settings') });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<AppSettings>) => api<AppSettings>('PATCH', '/settings', { body }),
    onSuccess: (data) => qc.setQueryData(keys.settings, data),
  });
}

// --------------------------------------------------------------- worker types
export function useWorkerTypes(includeInactive = false) {
  return useQuery({
    queryKey: [...keys.workerTypes, { includeInactive }],
    queryFn: () =>
      api<WorkerType[]>('GET', '/worker-types', { params: { include_inactive: includeInactive } }),
  });
}

export function useSaveWorkerType() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: { id?: string; name_en?: string; name_hi?: string | null; pay_scheme?: PayScheme; is_active?: boolean }) =>
      id
        ? api<WorkerType>('PATCH', `/worker-types/${id}`, { body })
        : api<WorkerType>('POST', '/worker-types', { body }),
    onSuccess: () => invalidate(keys.workerTypes, keys.workers),
  });
}

// -------------------------------------------------------------------- workers
export function useWorkers(includeArchived = false) {
  return useQuery({
    queryKey: [...keys.workers, { includeArchived }],
    queryFn: () =>
      api<Worker[]>('GET', '/workers', { params: { include_archived: includeArchived } }),
  });
}

export function useSaveWorker() {
  const invalidate = useInvalidate();
  return useMutation({
    meta: { handlesErrors: true }, // duplicate-name conflicts are handled by the form
    mutationFn: ({ id, body }: { id?: string; body: WorkerInput }) =>
      id
        ? api<Worker>('PATCH', `/workers/${id}`, { body })
        : api<Worker>('POST', '/workers', { body }),
    onSuccess: () => invalidate(keys.workers, ...DERIVED),
  });
}

export function useArchiveWorker() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, archive }: { id: string; archive: boolean }) =>
      api<Worker>('POST', `/workers/${id}/${archive ? 'archive' : 'restore'}`),
    onSuccess: () => invalidate(keys.workers, ...DERIVED),
  });
}

export function fetchDeleteImpact(id: string) {
  return api<{ worker_id: string; production_entries: number }>(
    'GET',
    `/workers/${id}/delete-impact`,
  );
}

export function useDeleteWorker() {
  const invalidate = useInvalidate();
  return useMutation({
    meta: { handlesErrors: true },
    mutationFn: ({ id, confirmEntries }: { id: string; confirmEntries: number }) =>
      api<void>('DELETE', `/workers/${id}`, { params: { confirm_entries: confirmEntries } }),
    onSuccess: () => invalidate(keys.workers, ...DERIVED),
  });
}

// ---------------------------------------------------------------------- rates
export function useRates() {
  return useQuery({ queryKey: [...keys.rates, 'all'], queryFn: () => api<Rate[]>('GET', '/rates') });
}

export function useCurrentRates(on?: ISODate) {
  return useQuery({
    queryKey: [...keys.rates, 'current', on ?? 'today'],
    queryFn: () => api<CurrentRate[]>('GET', '/rates/current', { params: { on } }),
  });
}

export interface RateInput {
  worker_type_id: string;
  component: RateComponent;
  rate_per_sqft: string;
  effective_from: ISODate;
  note?: string | null;
}

export function useSaveRate() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Partial<RateInput> }) =>
      id
        ? api<Rate>('PATCH', `/rates/${id}`, { body })
        : api<Rate>('POST', '/rates', { body }),
    onSuccess: () => invalidate(keys.rates, ...DERIVED),
  });
}

export function useDeleteRate() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api<void>('DELETE', `/rates/${id}`),
    onSuccess: () => invalidate(keys.rates, ...DERIVED),
  });
}

// ----------------------------------------------------------------- production
export interface ProductionFilters {
  start?: ISODate;
  end?: ISODate;
  worker_id?: string;
  limit?: number;
  offset?: number;
}

export function useProduction(filters: ProductionFilters) {
  return useQuery({
    queryKey: [...keys.production, filters],
    queryFn: () =>
      api<{ total: number; items: ProductionEntry[] }>('GET', '/production', {
        params: { ...filters },
      }),
    placeholderData: (previous) => previous, // keep the table steady while paging
  });
}

export function previewWage(body: Omit<ProductionInput, 'notes'>) {
  return api<WagePreview>('POST', '/production/preview', { body });
}

export function useSaveEntry() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: ProductionInput }) =>
      id
        ? api<ProductionEntry>('PATCH', `/production/${id}`, { body })
        : api<ProductionEntry>('POST', '/production', { body }),
    onSuccess: () => invalidate(...DERIVED),
  });
}

export function useDeleteEntry() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api<void>('DELETE', `/production/${id}`),
    onSuccess: () => invalidate(...DERIVED),
  });
}

// -------------------------------------------------------------------- reports
export function useWagesReport(
  start: ISODate,
  end: ISODate,
  options: { includeEntries?: boolean; workerIds?: string[] } = {},
) {
  return useQuery({
    queryKey: [...keys.reports, 'wages', start, end, options],
    queryFn: () =>
      api<WagesReport>('GET', '/reports/wages', {
        params: {
          start,
          end,
          include_entries: options.includeEntries ?? false,
          worker_id: options.workerIds,
        },
      }),
    enabled: Boolean(start && end),
  });
}

export function useProductionSummary(
  start: ISODate,
  end: ISODate,
  groupBy: GroupBy,
  workerIds?: string[],
) {
  return useQuery({
    queryKey: [...keys.reports, 'production', start, end, groupBy, workerIds],
    queryFn: () =>
      api<ProductionSummary>('GET', '/reports/production', {
        params: { start, end, group_by: groupBy, worker_id: workerIds },
      }),
    enabled: Boolean(start && end),
  });
}

/** Link that downloads an Excel export (the browser handles the file save). */
export function exportUrl(
  kind: 'wages' | 'production',
  params: Record<string, string | string[] | undefined>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, v));
    else search.append(key, value);
  }
  return `/api/exports/${kind}.xlsx?${search}`;
}
