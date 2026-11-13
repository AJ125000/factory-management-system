/** Thin fetch wrapper. Backend errors look like {"error": {code, message, details}}. */

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

export async function api<T>(
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
  path: string,
  options: { body?: unknown; params?: Params } = {},
): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(buildUrl(path, options.params), {
      method,
      headers: options.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'offline', 'Cannot reach the FMS server. Is it running?');
  }
  if (!resp.ok) throw await parseError(resp);
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}
