/** Registers the service worker (see sw/sw-template.js) and offers updates politely. */

import { useSyncExternalStore } from 'react';

let waiting: ServiceWorker | null = null;
const listeners = new Set<() => void>();

function setWaiting(worker: ServiceWorker | null) {
  waiting = worker;
  listeners.forEach((l) => l());
}

export function registerServiceWorker() {
  // Only in the built app, and only where the browser allows it (https or localhost).
  if (!import.meta.env.PROD || !('serviceWorker' in navigator) || !window.isSecureContext) return;

  window.addEventListener('load', async () => {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js');
      const check = () => {
        // A waiting worker while one is already in control = a new version is ready.
        if (registration.waiting && navigator.serviceWorker.controller) {
          setWaiting(registration.waiting);
        }
      };
      check();
      registration.addEventListener('updatefound', () => {
        registration.installing?.addEventListener('statechange', check);
      });
      // Look for a new version every hour while the app stays open.
      setInterval(() => void registration.update().catch(() => {}), 60 * 60 * 1000);
    } catch {
      /* the app still works online without it */
    }
  });

  // Reload only when a NEW version takes over — not when the first one starts (first visit).
  const hadController = Boolean(navigator.serviceWorker.controller);
  let reloading = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloading || !hadController) return;
    reloading = true;
    window.location.reload();
  });
}

/** Switch to the new version now (the page reloads once it has taken over). */
export function applyUpdate() {
  waiting?.postMessage('SKIP_WAITING');
}

export function useUpdateReady(): boolean {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => waiting !== null,
  );
}
