/**
 * How long data stays on the device (in memory and in IndexedDB) after it was last used.
 *
 * Must stay BELOW 2^31 - 1 ms (~24.8 days): browsers store timer delays as 32-bit
 * numbers, and a longer delay overflows and fires almost immediately — which made
 * React Query throw away every unused query (e.g. rates) seconds after loading it.
 * 20 days still lets the phone go weeks without seeing the laptop.
 */
export const KEEP_DATA_MS = 20 * 24 * 60 * 60 * 1000;

export const MAX_TIMER_MS = 2 ** 31 - 1;
