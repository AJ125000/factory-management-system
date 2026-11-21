/** React Query hooks: one place that knows every endpoint and what to refresh after changes. */

import {
  queryOptions,
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryKey,
} from '@tanstack/react-query';

import { newId, submit } from '../lib/outbox';
import { api, uploadFile } from './client';
import type {
  AppSettings,
  AuthStatus,
  BackupInfo,
  BackupStatus,
  DeviceInfo,
  ConnectInfo,
  CurrentRate,
  ISODate,
  LoaderAssignment,
  Machine,
  MachineSize,
  ProductionEntry,
  ProductionInput,
  ProductionSummary,
  GroupBy,
  Rate,
  RateComponent,
  Role,
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
  machines: ['machines'] as const,
  sizes: ['machine-sizes'] as const,
  loaders: ['loader-assignments'] as const,
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

// ----------------------------------------------------------- essential data
// Each kind of data is fetched ONE way (everything, filtered on the device), so there's
// a single saved copy that every screen can read while the laptop is off.

export const settingsQuery = queryOptions({
  queryKey: keys.settings,
  queryFn: () => api<AppSettings>('GET', '/settings'),
});

export const workerTypesQuery = queryOptions({
  queryKey: keys.workerTypes,
  queryFn: () => api<WorkerType[]>('GET', '/worker-types', { params: { include_inactive: true } }),
});

export const workersQuery = queryOptions({
  queryKey: keys.workers,
  queryFn: () => api<Worker[]>('GET', '/workers', { params: { include_archived: true } }),
});

export const ratesQuery = queryOptions({
  queryKey: [...keys.rates, 'all'],
  queryFn: () => api<Rate[]>('GET', '/rates'),
});

export const machinesQuery = queryOptions({
  queryKey: keys.machines,
  queryFn: () => api<Machine[]>('GET', '/machines'),
});

export const sizesQuery = queryOptions({
  queryKey: keys.sizes,
  queryFn: () => api<MachineSize[]>('GET', '/machine-sizes'),
});

export const loadersQuery = queryOptions({
  queryKey: keys.loaders,
  queryFn: () => api<LoaderAssignment[]>('GET', '/loader-assignments'),
});

/** Fetched at start-up (and when the laptop is back) so data entry works offline. */
export function prefetchEssentials(client: QueryClient) {
  for (const query of [
    settingsQuery,
    workerTypesQuery,
    workersQuery,
    machinesQuery,
    sizesQuery,
    loadersQuery,
    ratesQuery,
  ]) {
    void client.prefetchQuery(query as typeof settingsQuery);
  }
}

const activeTypes = (types: WorkerType[]) => types.filter((t) => t.is_active);
const currentWorkers = (workers: Worker[]) => workers.filter((w) => !w.is_archived);

// ------------------------------------------------------------------ settings
export function useSettings() {
  return useQuery(settingsQuery);
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
  return useQuery({ ...workerTypesQuery, select: includeInactive ? undefined : activeTypes });
}

export function useSaveWorkerType() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: { id?: string; name_en?: string; name_hi?: string | null; role?: Role; is_active?: boolean }) =>
      id
        ? api<WorkerType>('PATCH', `/worker-types/${id}`, { body })
        : api<WorkerType>('POST', '/worker-types', { body }),
    onSuccess: () => invalidate(keys.workerTypes, keys.workers),
  });
}

// -------------------------------------------------------------------- workers
export function useWorkers(includeArchived = false) {
  return useQuery({ ...workersQuery, select: includeArchived ? undefined : currentWorkers });
}

export function useSaveWorker() {
  const invalidate = useInvalidate();
  return useMutation({
    meta: { handlesErrors: true }, // duplicate-name conflicts are handled by the form
    mutationFn: ({ id, body, label }: { id?: string; body: WorkerInput; label: string }) => {
      if (id) {
        return submit<Worker>({
          entity: 'worker', action: 'update', entityId: id, label,
          method: 'PATCH', path: `/workers/${id}`, body: { ...body },
        });
      }
      const entityId = newId();
      return submit<Worker>({
        entity: 'worker', action: 'create', entityId, label,
        method: 'POST', path: '/workers', body: { ...body, id: entityId },
      });
    },
    onSuccess: () => invalidate(keys.workers, ...DERIVED),
  });
}

export function useArchiveWorker() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, archive, label }: { id: string; archive: boolean; label: string }) =>
      submit<Worker>({
        entity: 'worker', action: archive ? 'archive' : 'restore', entityId: id, label,
        method: 'POST', path: `/workers/${id}/${archive ? 'archive' : 'restore'}`,
      }),
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

// ------------------------------------------------------------------- machines
const activeMachines = (machines: Machine[]) => machines.filter((m) => m.is_active);

export function useMachines(includeInactive = false) {
  return useQuery({ ...machinesQuery, select: includeInactive ? undefined : activeMachines });
}

export function useUpdateMachine() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; name_en?: string; name_hi?: string | null; is_active?: boolean }) =>
      api<Machine>('PATCH', `/machines/${id}`, { body }),
    onSuccess: () => invalidate(keys.machines, ...DERIVED),
  });
}

export function useSizes() {
  return useQuery(sizesQuery);
}

export interface SizeInput {
  machine_id: string;
  length: string;
  width: string;
  rft: string;
  sqft: string;
}

export function useSaveSize() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({ id, body, label }: { id?: string; body: Partial<SizeInput>; label: string }) => {
      if (id) {
        return { queued: false as const, data: await api<MachineSize>('PATCH', `/machine-sizes/${id}`, { body }) };
      }
      const entityId = newId();
      return submit<MachineSize>({
        entity: 'size', action: 'create', entityId, label,
        method: 'POST', path: '/machine-sizes', body: { ...body, id: entityId },
      });
    },
    onSuccess: () => invalidate(keys.sizes),
  });
}

export function useDeleteSize() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api<void>('DELETE', `/machine-sizes/${id}`),
    onSuccess: () => invalidate(keys.sizes),
  });
}

export function useLoaderAssignments() {
  return useQuery(loadersQuery);
}

export interface LoaderAssignmentInput {
  machine_id: string;
  worker_id: string | null;
  effective_from: ISODate;
  note?: string | null;
}

export function useSaveLoaderAssignment() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({
      id,
      body,
      label,
    }: {
      id?: string;
      body: Partial<LoaderAssignmentInput>;
      label: string;
    }) => {
      if (id) {
        // Correcting a past assignment moves loader pay: only with the laptop reachable.
        return {
          queued: false as const,
          data: await api<LoaderAssignment>('PATCH', `/loader-assignments/${id}`, { body }),
        };
      }
      const entityId = newId();
      return submit<LoaderAssignment>({
        entity: 'loader_assignment', action: 'create', entityId, label,
        method: 'POST', path: '/loader-assignments', body: { ...body, id: entityId },
      });
    },
    onSuccess: () => invalidate(keys.loaders, ...DERIVED),
  });
}

export function useDeleteLoaderAssignment() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api<void>('DELETE', `/loader-assignments/${id}`),
    onSuccess: () => invalidate(keys.loaders, ...DERIVED),
  });
}

// ---------------------------------------------------------------------- rates
export function useRates() {
  return useQuery(ratesQuery);
}

export function useCurrentRates(on?: ISODate) {
  return useQuery({
    queryKey: [...keys.rates, 'current', on ?? 'today'],
    queryFn: () => api<CurrentRate[]>('GET', '/rates/current', { params: { on } }),
  });
}

export interface RateInput {
  machine_id: string;
  component: RateComponent;
  rate: string;
  effective_from: ISODate;
  note?: string | null;
}

export function useSaveRate() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({ id, body, label }: { id?: string; body: Partial<RateInput>; label: string }) => {
      if (id) {
        // Correcting a past rate recalculates wages: only with the laptop reachable.
        return { queued: false as const, data: await api<Rate>('PATCH', `/rates/${id}`, { body }) };
      }
      const entityId = newId();
      return submit<Rate>({
        entity: 'rate', action: 'create', entityId, label,
        method: 'POST', path: '/rates', body: { ...body, id: entityId },
      });
    },
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
  machine_id?: string;
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
    mutationFn: ({ id, body, label }: { id?: string; body: ProductionInput; label: string }) => {
      if (id) {
        return submit<ProductionEntry>({
          entity: 'production', action: 'update', entityId: id, label,
          method: 'PATCH', path: `/production/${id}`, body: { ...body },
        });
      }
      const entityId = newId();
      return submit<ProductionEntry>({
        entity: 'production', action: 'create', entityId, label,
        method: 'POST', path: '/production', body: { ...body, id: entityId },
      });
    },
    onSuccess: () => invalidate(...DERIVED),
  });
}

export function useDeleteEntry() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, label }: { id: string; label: string }) =>
      submit<void>({
        entity: 'production', action: 'delete', entityId: id, label,
        method: 'DELETE', path: `/production/${id}`,
      }),
    onSuccess: () => invalidate(...DERIVED),
  });
}

// -------------------------------------------------------------------- reports
export function useWagesReport(
  start: ISODate,
  end: ISODate,
  options: { includeEntries?: boolean; workerIds?: string[]; machineId?: string } = {},
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
          machine_id: options.machineId,
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
  machineId?: string,
) {
  return useQuery({
    queryKey: [...keys.reports, 'production', start, end, groupBy, workerIds, machineId],
    queryFn: () =>
      api<ProductionSummary>('GET', '/reports/production', {
        params: { start, end, group_by: groupBy, worker_id: workerIds, machine_id: machineId },
      }),
    enabled: Boolean(start && end),
  });
}


export function useConnectInfo() {
  return useQuery({
    queryKey: [...keys.settings, 'connect'],
    queryFn: () => api<ConnectInfo>('GET', '/connect-info'),
  });
}

// ----------------------------------------------------------------------- auth
export function useAuthStatus() {
  return useQuery({
    queryKey: ['auth', 'status'],
    queryFn: () => api<AuthStatus>('GET', '/auth/status'),
    networkMode: 'always', // try even while the laptop seems away: this is how we find out
    retry: 0,
    meta: { silent: true },
  });
}

/** First-time setup or a normal login; returns this device's new login token. */
export function requestLogin(kind: 'setup' | 'login', password: string, deviceName: string) {
  return api<{ token: string; device: DeviceInfo }>('POST', `/auth/${kind}`, {
    body: { password, device_name: deviceName },
  });
}

export function useDevices() {
  return useQuery({
    queryKey: ['auth', 'devices'],
    queryFn: () => api<DeviceInfo[]>('GET', '/auth/devices'),
  });
}

export function useSignOutDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>('DELETE', `/auth/devices/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auth', 'devices'] }),
  });
}

export function useChangePassword() {
  const qc = useQueryClient();
  return useMutation({
    meta: { handlesErrors: true },
    mutationFn: (body: {
      current_password: string;
      new_password: string;
      sign_out_other_devices: boolean;
    }) => api<{ signed_out_devices: number }>('POST', '/auth/password', { body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auth', 'devices'] }),
  });
}

export function requestLogout() {
  return api<void>('POST', '/auth/logout');
}

// -------------------------------------------------------------------- backups
export function useBackups() {
  return useQuery({
    queryKey: ['backups'],
    queryFn: () => api<BackupStatus>('GET', '/backups'),
  });
}

export function useBackUpNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<BackupInfo>('POST', '/backups'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backups'] }),
  });
}

/** Restore a backup kept on the laptop, or a file from this device. */
export function useRestoreBackup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (source: { name: string } | { file: File }) =>
      'name' in source
        ? api<BackupInfo>('POST', `/backups/${encodeURIComponent(source.name)}/restore`)
        : uploadFile<BackupInfo>('/backups/restore-upload', source.file),
    // Everything may have changed: reload every screen's data.
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useSystemInfo() {
  return useQuery({
    queryKey: ['system-info'],
    queryFn: () =>
      api<{ version: string; data_dir: string; log_file: string; database_size: number }>(
        'GET',
        '/system-info',
      ),
  });
}
