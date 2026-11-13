import { ApiError } from '../api/client';
import i18n from '../i18n';

/**
 * A message for the owner in the app's current language.
 * The server sends a `reason` (or `code`) with each error; known ones are translated,
 * anything else falls back to the server's English message.
 */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    for (const key of [error.reason, error.code]) {
      if (key && i18n.exists(`errors.${key}`)) return i18n.t(`errors.${key}`);
    }
    return error.message;
  }
  return error instanceof Error ? error.message : String(error);
}
