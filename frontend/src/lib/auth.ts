/**
 * This device's login.
 *
 * After the owner logs in, the hub gives this device a long random token. It is kept
 * in localStorage so the app opens (and works offline) without logging in again; it
 * stops working only if the owner signs this device out or logs out here.
 */

import { useSyncExternalStore } from 'react';

const TOKEN_KEY = 'fms.token';
const listeners = new Set<() => void>();

function read(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

let token: string | null = read();

function emit() {
  listeners.forEach((l) => l());
}

export function authToken(): string | null {
  return token;
}

export function setAuthToken(value: string) {
  token = value;
  try {
    localStorage.setItem(TOKEN_KEY, value);
  } catch {
    /* private mode: logged in for this session only */
  }
  emit();
}

/** Forget this device's login (logged out, or signed out from another device). */
export function clearAuthToken() {
  if (token === null) return;
  token = null;
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* fine */
  }
  emit();
}

export function useAuthToken(): string | null {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => token,
  );
}

/** A sensible default name for this device, shown in Settings → Devices. */
export function guessDeviceName(): string {
  const ua = navigator.userAgent;
  if (/iPhone/i.test(ua)) return 'iPhone';
  if (/iPad/i.test(ua)) return 'iPad';
  if (/Android/i.test(ua)) return /Mobile/i.test(ua) ? 'Android phone' : 'Android tablet';
  if (/Windows/i.test(ua)) return 'Windows PC';
  if (/Macintosh/i.test(ua)) return 'Mac';
  return 'Device';
}

/** Run `callback` whenever this device logs in or out. Returns an unsubscribe function. */
export function subscribeAuth(callback: () => void): () => void {
  listeners.add(callback);
  return () => listeners.delete(callback);
}
