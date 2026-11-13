import { beforeEach, describe, expect, it, vi } from 'vitest';

// In-memory stand-ins for IndexedDB and the hub.
const store = new Map<string, unknown>();
vi.mock('idb-keyval', () => ({
  get: async (k: string) => store.get(k),
  set: async (k: string, v: unknown) => void store.set(k, structuredClone(v)),
}));

const hub = { up: true, received: [] as { method: string; path: string; body?: unknown }[] };
const refusals = new Map<string, { status: number; reason: string }>();

vi.mock('../api/client', async () => {
  class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string,
      public details: Record<string, unknown> = {},
    ) {
      super(message);
    }
    get reason() {
      return this.details.reason as string | undefined;
    }
  }
  return {
    ApiError,
    api: async (method: string, path: string, opts: { body?: unknown } = {}) => {
      if (!hub.up) throw new ApiError(0, 'offline', 'hub is off');
      const refusal = refusals.get(path);
      if (refusal) throw new ApiError(refusal.status, 'conflict', 'refused', { reason: refusal.reason });
      hub.received.push({ method, path, body: opts.body });
      return { ok: true, path };
    },
  };
});

vi.mock('./hub', () => ({
  hubState: () => ({ reachable: hub.up, lastContact: null }),
  checkHub: async () => hub.up,
}));

async function freshOutbox() {
  vi.resetModules();
  return import('./outbox');
}

const create = (entityId: string, body: Record<string, unknown> = {}) => ({
  entity: 'production' as const,
  action: 'create' as const,
  entityId,
  method: 'POST' as const,
  path: '/production',
  body: { id: entityId, quantity: 5, ...body },
  label: `entry ${entityId}`,
});

beforeEach(() => {
  store.clear();
  refusals.clear();
  hub.up = true;
  hub.received = [];
});

describe('outbox', () => {
  it('sends straight away when the hub is reachable', async () => {
    const outbox = await freshOutbox();
    const result = await outbox.submit(create('a'));
    expect(result.queued).toBe(false);
    expect(hub.received).toHaveLength(1);
    expect(outbox.outboxItems()).toHaveLength(0);
  });

  it('keeps changes while the hub is away and sends them in order when it is back', async () => {
    const outbox = await freshOutbox();
    hub.up = false;
    expect((await outbox.submit(create('a'))).queued).toBe(true);
    expect((await outbox.submit(create('b'))).queued).toBe(true);
    expect(outbox.outboxItems()).toHaveLength(2);
    expect(hub.received).toHaveLength(0);

    hub.up = true;
    await outbox.flush();
    expect(hub.received.map((r) => (r.body as { id: string }).id)).toEqual(['a', 'b']);
    expect(outbox.outboxItems()).toHaveLength(0);
  });

  it('survives the app being closed (queue is stored on the device)', async () => {
    hub.up = false;
    const first = await freshOutbox();
    await first.submit(create('a'));

    const reopened = await freshOutbox(); // a new app session: memory is empty
    await reopened.loadOutbox();
    expect(reopened.outboxItems().map((i) => i.entityId)).toEqual(['a']);
    hub.up = true;
    await reopened.flush();
    expect(hub.received).toHaveLength(1);
  });

  it('folds edits of a not-yet-sent entry into its create', async () => {
    const outbox = await freshOutbox();
    hub.up = false;
    await outbox.submit(create('a'));
    await outbox.submit({ ...create('a'), action: 'update', method: 'PATCH', path: '/production/a', body: { quantity: 9 } });
    expect(outbox.outboxItems()).toHaveLength(1);
    hub.up = true;
    await outbox.flush();
    expect(hub.received).toEqual([
      { method: 'POST', path: '/production', body: { id: 'a', quantity: 9 } },
    ]);
  });

  it('deleting a not-yet-sent entry means the hub never hears of it', async () => {
    const outbox = await freshOutbox();
    hub.up = false;
    await outbox.submit(create('a'));
    await outbox.submit({ ...create('a'), action: 'delete', method: 'DELETE', path: '/production/a', body: undefined });
    hub.up = true;
    await outbox.flush();
    expect(hub.received).toHaveLength(0);
    expect(outbox.outboxItems()).toHaveLength(0);
  });

  it('keeps refused changes for review and carries on with the rest', async () => {
    const outbox = await freshOutbox();
    hub.up = false;
    await outbox.submit({ ...create('a'), path: '/production-refused' });
    await outbox.submit(create('b'));
    refusals.set('/production-refused', { status: 409, reason: 'worker_archived' });
    hub.up = true;
    await outbox.flush();

    const [failed] = outbox.outboxItems();
    expect(failed.status).toBe('failed');
    expect(failed.error?.reason).toBe('worker_archived');
    expect(hub.received.map((r) => (r.body as { id: string }).id)).toEqual(['b']);

    refusals.clear();
    await outbox.retry(failed.id);
    expect(outbox.outboxItems()).toHaveLength(0);
  });

  it('tells the form when the hub refuses a change', async () => {
    const outbox = await freshOutbox();
    refusals.set('/workers', { status: 409, reason: 'duplicate_name' });
    await expect(
      outbox.submit({ ...create('w'), entity: 'worker', path: '/workers' }),
    ).rejects.toMatchObject({ reason: 'duplicate_name' });
  });

  it('a delete of something already gone counts as done', async () => {
    const outbox = await freshOutbox();
    refusals.set('/production/x', { status: 404, reason: 'not_found' });
    const result = await outbox.submit({ ...create('x'), action: 'delete', method: 'DELETE', path: '/production/x' });
    expect(result.queued).toBe(false);
    expect(outbox.outboxItems()).toHaveLength(0);
  });
});
