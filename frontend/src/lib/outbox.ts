/**
 * The offline change queue.
 *
 * Every change the owner makes is written here first (in IndexedDB, so it survives the
 * app being closed), then sent to the hub in order. If the hub is reachable this takes
 * milliseconds and feels instant; if not, changes wait and are sent automatically when
 * it's back. New records get their id on the device, and the hub treats a repeated
 * create as already done, so a change can never be applied twice.
 */

import { get, set } from 'idb-keyval';
import { useSyncExternalStore } from 'react';

import { ApiError, api } from '../api/client';
import { checkHub, hubState } from './hub';

export type Entity = 'production' | 'worker' | 'rate';
export type Action = 'create' | 'update' | 'delete' | 'archive' | 'restore';

export interface OutboxItem {
  id: string;
  createdAt: number;
  entity: Entity;
  action: Action;
  entityId: string;
  method: 'POST' | 'PATCH' | 'DELETE';
  path: string;
  body?: Record<string, unknown>;
  label: string; // shown to the owner, e.g. "Ramesh · 05/11/2026 · 2 × 3 ft × 5"
  status: 'pending' | 'failed';
  error?: { message: string; reason?: string; code: string };
}

export type SubmitResult<T> = { queued: false; data: T } | { queued: true; data: null };

const STORAGE_KEY = 'fms.outbox.v1';

let items: OutboxItem[] = [];
let loaded: Promise<void> | null = null;
const listeners = new Set<() => void>();
const waiters = new Map<
  string,
  { resolve: (r: SubmitResult<unknown>) => void; reject: (e: unknown) => void }
>();
let onApplied: () => void = () => {};

export function newId(): string {
  // randomUUID only exists in secure contexts (https or localhost).
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  // Fallback for non-secure contexts (e.g. plain http on a LAN): RFC 4122 v4 from getRandomValues.
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

function emit() {
  items = [...items]; // new identity so React re-renders
  listeners.forEach((l) => l());
}

async function persist() {
  try {
    await set(STORAGE_KEY, items);
  } catch {
    /* storage unavailable (private mode): the queue still works for this session */
  }
}

export function loadOutbox(): Promise<void> {
  loaded ??= (async () => {
    try {
      const stored = await get<OutboxItem[]>(STORAGE_KEY);
      if (stored?.length) {
        items = [...stored, ...items];
        emit();
      }
    } catch {
      /* fine */
    }
  })();
  return loaded;
}

/** Called after changes reach the hub, to refresh what the screens show. */
export function setOnApplied(callback: () => void) {
  onApplied = callback;
}

type NewItem = Omit<OutboxItem, 'id' | 'createdAt' | 'status' | 'error'>;

/**
 * Queue a change and try to send it straight away.
 * Resolves with the hub's reply, or `{queued: true}` if the hub can't be reached;
 * rejects if the hub refused the change (e.g. a duplicate name) so the form can say why.
 */
export async function submit<T>(change: NewItem): Promise<SubmitResult<T>> {
  await loadOutbox();

  // Changing something that hasn't reached the hub yet: fold it into the waiting create.
  // (Not if it's being sent right now — then the edit goes as its own update afterwards.)
  const pendingCreate = items.find(
    (i) =>
      i.entity === change.entity &&
      i.entityId === change.entityId &&
      i.action === 'create' &&
      i.status === 'pending' &&
      i.id !== sendingId,
  );
  if (pendingCreate && change.action === 'update') {
    pendingCreate.body = { ...pendingCreate.body, ...change.body };
    pendingCreate.label = change.label;
    emit();
    await persist();
    return flushAndWait<T>(pendingCreate.id);
  }
  if (pendingCreate && change.action === 'delete') {
    items = items.filter((i) => !(i.entity === change.entity && i.entityId === change.entityId));
    emit();
    await persist();
    return { queued: true, data: null };
  }

  const item: OutboxItem = { ...change, id: newId(), createdAt: Date.now(), status: 'pending' };
  items.push(item);
  emit();
  await persist();
  return flushAndWait<T>(item.id);
}

function flushAndWait<T>(itemId: string): Promise<SubmitResult<T>> {
  if (!hubState().reachable) {
    void flush(); // cheap: stops at the first failed connection
    return Promise.resolve({ queued: true, data: null });
  }
  const result = new Promise<SubmitResult<T>>((resolve, reject) => {
    waiters.set(itemId, { resolve: resolve as (r: SubmitResult<unknown>) => void, reject });
  });
  void flush();
  return result;
}

let flushing: Promise<void> | null = null;
let rerun = false;
let sendingId: string | null = null;

/**
 * Send waiting changes to the hub, oldest first. Safe to call any time.
 * A call that arrives while a flush is running makes it go round once more (the hub
 * may have just come back), and the returned promise covers that extra pass.
 */
export function flush(): Promise<void> {
  if (flushing) {
    rerun = true;
    return flushing;
  }
  flushing = (async () => {
    try {
      do {
        rerun = false;
        await flushOnce();
      } while (rerun);
    } finally {
      flushing = null;
    }
  })();
  return flushing;
}

async function flushOnce(): Promise<void> {
  await loadOutbox();
  let applied = 0;
  const tried = new Set<string>();
  try {
    // Re-read the live queue each time, so changes made during a flush are sent in it.
    for (;;) {
      const item = items.find((i) => i.status === 'pending' && !tried.has(i.id));
      if (!item) break;
      tried.add(item.id);
      sendingId = item.id;
      try {
        const data = await api(item.method, item.path, { body: item.body });
        remove(item.id);
        applied++;
        waiters.get(item.id)?.resolve({ queued: false, data });
      } catch (error) {
        if (error instanceof ApiError && error.code === 'offline') {
          // The hub went away: keep this and everything after it for later.
          for (const id of waiters.keys()) waiters.get(id)?.resolve({ queued: true, data: null });
          waiters.clear();
          break;
        }
        if (error instanceof ApiError && error.status === 404 && item.method === 'DELETE') {
          remove(item.id); // already gone: that's what we wanted
          applied++;
          waiters.get(item.id)?.resolve({ queued: false, data: null });
        } else {
          // The hub refused it (e.g. worker archived). Keep it for the owner to review.
          item.status = 'failed';
          item.error =
            error instanceof ApiError
              ? { message: error.message, reason: error.reason, code: error.code }
              : { message: String(error), code: 'error' };
          emit();
          waiters.get(item.id)?.reject(error);
        }
      }
      waiters.delete(item.id);
    }
  } finally {
    sendingId = null;
    await persist();
    if (applied) onApplied();
  }
}

function remove(itemId: string) {
  items = items.filter((i) => i.id !== itemId);
  emit();
}

export async function retry(itemId: string) {
  const item = items.find((i) => i.id === itemId);
  if (!item) return;
  item.status = 'pending';
  item.error = undefined;
  emit();
  await persist();
  if (await checkHub()) await flush();
}

export async function discard(itemId: string) {
  remove(itemId);
  await persist();
}

export function outboxItems(): OutboxItem[] {
  return items;
}

export function useOutbox(): OutboxItem[] {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => items,
  );
}
