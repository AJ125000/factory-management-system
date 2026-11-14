/**
 * PIN lock for this device.
 *
 * Locks FMS when the app starts and after it has been idle for a while. The PIN is
 * checked on the device (so it works with the laptop off): only a salted PBKDF2 hash is
 * stored. It stops someone who picks up an unlocked phone; it is not meant to resist a
 * determined attacker with developer tools, which is why the real secret (the login) is
 * the owner password and can be revoked from the laptop.
 */

import { useSyncExternalStore } from 'react';

interface PinConfig {
  salt: string; // base64
  hash: string; // base64
  iterations: number;
  length: number; // digits, so the lock screen shows the right number of boxes
  lockAfterMinutes: number;
}

interface Attempts {
  failures: number;
  waitUntil: number; // ms timestamp
}

const PIN_KEY = 'fms.pin';
const ATTEMPTS_KEY = 'fms.pin.attempts';
const ITERATIONS = 150_000;
const FREE_TRIES = 5;
export const LOCK_CHOICES = [1, 2, 5, 10, 30];

function load<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function save(key: string, value: unknown) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable */
  }
}

const toB64 = (b: ArrayBuffer | Uint8Array) =>
  btoa(String.fromCharCode(...new Uint8Array(b instanceof Uint8Array ? b : new Uint8Array(b))));
const fromB64 = (s: string) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

async function derive(
  pin: string,
  salt: Uint8Array<ArrayBuffer>,
  iterations: number,
): Promise<string> {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(pin), 'PBKDF2', false, [
    'deriveBits',
  ]);
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', hash: 'SHA-256', salt, iterations },
    key,
    256,
  );
  return toB64(bits);
}

// ---------------------------------------------------------------- state
let config: PinConfig | null = load<PinConfig>(PIN_KEY);
let locked = config !== null; // locked whenever the app starts
let lastActive = Date.now();
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

export function isValidPin(pin: string): boolean {
  return /^\d{4,6}$/.test(pin);
}

export function pinEnabled(): boolean {
  return config !== null;
}

export function pinLength(): number {
  return config?.length ?? 4;
}

export function lockAfterMinutes(): number {
  return config?.lockAfterMinutes ?? 5;
}

export async function setPin(pin: string, minutes: number): Promise<void> {
  if (!isValidPin(pin)) throw new Error('PIN must be 4 to 6 digits');
  const salt = crypto.getRandomValues(new Uint8Array(16));
  config = {
    salt: toB64(salt),
    hash: await derive(pin, salt, ITERATIONS),
    iterations: ITERATIONS,
    length: pin.length,
    lockAfterMinutes: minutes,
  };
  save(PIN_KEY, config);
  save(ATTEMPTS_KEY, null);
  emit();
}

export function setLockAfter(minutes: number) {
  if (!config) return;
  config = { ...config, lockAfterMinutes: minutes };
  save(PIN_KEY, config);
  emit();
}

export function removePin() {
  config = null;
  locked = false;
  save(PIN_KEY, null);
  save(ATTEMPTS_KEY, null);
  emit();
}

export function lockNow() {
  if (!config) return;
  locked = true;
  emit();
}

/** Seconds to wait before another try (0 = may try now). Survives reloads. */
export function waitSeconds(now = Date.now()): number {
  const a = load<Attempts>(ATTEMPTS_KEY);
  return a && a.waitUntil > now ? Math.ceil((a.waitUntil - now) / 1000) : 0;
}

export type UnlockResult = 'ok' | 'wrong' | 'wait';

export async function unlock(pin: string): Promise<UnlockResult> {
  if (!config) {
    locked = false;
    emit();
    return 'ok';
  }
  if (waitSeconds() > 0) return 'wait';
  const hash = await derive(pin, fromB64(config.salt), config.iterations);
  if (hash === config.hash) {
    save(ATTEMPTS_KEY, null);
    locked = false;
    lastActive = Date.now();
    emit();
    return 'ok';
  }
  // After 5 wrong tries: wait 30 s, then 60 s, 120 s… (at most 15 minutes).
  const previous = load<Attempts>(ATTEMPTS_KEY)?.failures ?? 0;
  const failures = previous + 1;
  const over = failures - FREE_TRIES;
  const wait = over >= 0 ? Math.min(30_000 * 2 ** over, 15 * 60_000) : 0;
  save(ATTEMPTS_KEY, { failures, waitUntil: Date.now() + wait });
  return wait ? 'wait' : 'wrong';
}

// ---------------------------------------------------------------- idle lock
function idleTooLong(now = Date.now()) {
  return config !== null && now - lastActive > config.lockAfterMinutes * 60_000;
}

export function startIdleLock() {
  const activity = () => {
    if (!locked) lastActive = Date.now();
  };
  for (const event of ['pointerdown', 'keydown', 'touchstart', 'wheel']) {
    window.addEventListener(event, activity, { passive: true });
  }
  document.addEventListener('visibilitychange', () => {
    // Coming back to the app after a while (e.g. the phone was in a pocket) locks it.
    if (document.visibilityState === 'visible' && idleTooLong()) lockNow();
    else if (document.visibilityState === 'visible') activity();
  });
  setInterval(() => {
    if (!locked && idleTooLong()) lockNow();
  }, 15_000);
}

export function useLocked(): boolean {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => locked,
  );
}

export function usePinEnabled(): boolean {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => config !== null,
  );
}
