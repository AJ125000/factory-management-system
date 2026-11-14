/**
 * Send unexpected app errors to the laptop's log, so problems on any device (including
 * phones) can be looked at in one place. Best effort only: never throws, never shows
 * anything, and only while logged in (the hub refuses reports otherwise).
 */

import { authToken } from './auth';

let sentThisSession = 0;

export function reportError(error: unknown, where?: string) {
  if (!authToken() || sentThisSession >= 20) return;
  sentThisSession++;
  const err = error instanceof Error ? error : new Error(String(error));
  void fetch('/api/client-errors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken()}` },
    body: JSON.stringify({
      message: err.message.slice(0, 2000),
      stack: err.stack?.slice(0, 8000) ?? null,
      url: location.pathname,
      app_version: __APP_VERSION__,
      where: where ?? null,
    }),
  }).catch(() => {});
}

export function startErrorReporting() {
  window.addEventListener('error', (e) => reportError(e.error ?? e.message, 'window'));
  window.addEventListener('unhandledrejection', (e) => reportError(e.reason, 'promise'));
}
