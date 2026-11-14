/** Thin fetch wrapper. Backend errors look like {"error": {code, message, details}}. */

import { authToken, clearAuthToken } from '../lib/auth';
import { markReachable, markUnreachable } from '../lib/hub';

const GATEWAY_ERRORS = new Set([502, 503, 504]);

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }

  /** The `reason` the backend attached to a conflict, e.g. "duplicate_name". */
  get reason(): string | undefined {
    return typeof this.details.reason === 'string' ? this.details.reason : undefined;
  }
}

type Params = Record<string, string | number | boolean | string[] | undefined | null>;

function buildUrl(path: string, params?: Params): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, v));
    else search.append(key, String(value));
  }
  const qs = search.toString();
  return `/api${path}${qs ? `?${qs}` : ''}`;
}

async function parseError(resp: Response): Promise<ApiError> {
  try {
    const body = await resp.json();
    if (body?.error) {
      return new ApiError(resp.status, body.error.code, body.error.message, body.error.details);
    }
    // FastAPI request validation errors: {"detail": [{loc, msg}, ...]}
    if (Array.isArray(body?.detail)) {
      const first = body.detail[0];
      const field = Array.isArray(first?.loc) ? first.loc[first.loc.length - 1] : '';
      return new ApiError(resp.status, 'invalid', `${field}: ${first?.msg ?? 'Invalid value'}`);
    }
  } catch {
    /* not JSON */
  }
  return new ApiError(resp.status, 'error', `Request failed (${resp.status})`);
}

async function send(
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
  path: string,
  options: { body?: unknown; params?: Params; raw?: Blob },
): Promise<Response> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.raw) headers['Content-Type'] = 'application/octet-stream';
  const token = authToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let resp: Response;
  try {
    resp = await fetch(buildUrl(path, options.params), {
      method,
      headers,
      body: options.raw ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
      // Uploading or restoring a backup can take longer than a normal request.
      signal: AbortSignal.timeout(options.raw ? 300_000 : 20_000),
    });
  } catch {
    markUnreachable();
    throw new ApiError(0, 'offline', 'Cannot reach the FMS server. Is it running?');
  }
  // Tailscale answers 502/503/504 when the laptop is on but the FMS server isn't running.
  if (GATEWAY_ERRORS.has(resp.status)) {
    markUnreachable();
    throw new ApiError(0, 'offline', 'Cannot reach the FMS server. Is it running?');
  }
  markReachable();
  if (!resp.ok) {
    const error = await parseError(resp);
    // The hub no longer accepts this device (signed out elsewhere, or logged out):
    // forget the login so the app shows the login screen. Waiting changes are kept.
    if (resp.status === 401 && error.reason === 'login_required') clearAuthToken();
    throw error;
  }
  return resp;
}

export async function api<T>(
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
  path: string,
  options: { body?: unknown; params?: Params } = {},
): Promise<T> {
  const resp = await send(method, path, options);
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

/**
 * Download a file (e.g. an Excel export) with this device's login attached, and hand
 * it to the browser to save. A plain link can't carry the login, and putting the
 * token in the address would leave it in the server's logs.
 */
export async function downloadFile(path: string, params: Params, fallbackName: string) {
  const resp = await send('GET', path, { params });
  const disposition = resp.headers.get('Content-Disposition') ?? '';
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await resp.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** Send a file as the request body (e.g. a backup to restore). */
export async function uploadFile<T>(path: string, file: Blob): Promise<T> {
  const resp = await send('POST', path, { raw: file });
  return (await resp.json()) as T;
}
