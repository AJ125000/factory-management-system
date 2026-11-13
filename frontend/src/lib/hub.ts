/**
 * Is the hub (the laptop) reachable right now?
 *
 * `navigator.onLine` only says the phone has *some* network; the laptop may still be
 * off. So we ask the hub itself (/api/health) and tell React Query, which then pauses
 * data loading while the hub is away and resumes automatically when it's back.
 */

import { onlineManager } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';

export interface HubState {
  reachable: boolean;
  lastContact: number | null; // ms timestamp of the last successful reply
}

const LAST_CONTACT_KEY = 'fms.lastContact';
const listeners = new Set<() => void>();

function storedLastContact(): number | null {
  try {
    const v = Number(localStorage.getItem(LAST_CONTACT_KEY));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

let state: HubState = { reachable: true, lastContact: storedLastContact() };

function set(next: Partial<HubState>) {
  const merged = { ...state, ...next };
  if (merged.reachable === state.reachable && merged.lastContact === state.lastContact) return;
  state = merged;
  onlineManager.setOnline(state.reachable);
  listeners.forEach((l) => l());
}

export function markReachable() {
  const now = Date.now();
  try {
    localStorage.setItem(LAST_CONTACT_KEY, String(now));
  } catch {
    /* fine */
  }
  // Only re-render for the reachable flip, not for every successful request.
  if (!state.reachable || !state.lastContact || now - state.lastContact > 60_000) {
    set({ reachable: true, lastContact: now });
  }
}

export function markUnreachable() {
  set({ reachable: false });
}

export function hubState(): HubState {
  return state;
}

export async function checkHub(): Promise<boolean> {
  try {
    const resp = await fetch('/api/health', { cache: 'no-store', signal: AbortSignal.timeout(4000) });
    if (resp.ok) {
      markReachable();
      return true;
    }
  } catch {
    /* unreachable */
  }
  markUnreachable();
  return false;
}

let timer: ReturnType<typeof setTimeout> | undefined;

/** Keep checking: often while the hub is away, rarely while it's fine. */
export function startHubWatch(onBack: () => void) {
  const loop = async () => {
    const wasReachable = state.reachable;
    const ok = await checkHub();
    if (ok && !wasReachable) onBack();
    timer = setTimeout(loop, ok ? 60_000 : 10_000);
  };
  const recheckNow = () => {
    clearTimeout(timer);
    void loop();
  };
  window.addEventListener('online', recheckNow);
  window.addEventListener('focus', recheckNow);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') recheckNow();
  });
  void loop();
}

export function useHubState(): HubState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
  );
}
