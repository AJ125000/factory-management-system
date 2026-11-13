import '@mantine/core/styles.css';
import '@mantine/dates/styles.css';
import '@mantine/charts/styles.css';
import '@mantine/notifications/styles.css';
import '@fontsource/noto-sans/400.css';
import '@fontsource/noto-sans/600.css';
import '@fontsource/noto-sans/700.css';
import '@fontsource/noto-sans-devanagari/400.css';
import '@fontsource/noto-sans-devanagari/600.css';
import '@fontsource/noto-sans-devanagari/700.css';
import './styles.css';
import './i18n';

import { MantineProvider } from '@mantine/core';
import { ModalsProvider } from '@mantine/modals';
import { Notifications, notifications } from '@mantine/notifications';
import { createAsyncStoragePersister } from '@tanstack/query-async-storage-persister';
import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { del, get, set } from 'idb-keyval';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';

import App from './App';
import { ApiError } from './api/client';
import { prefetchEssentials } from './api/hooks';
import i18n from './i18n';
import { KEEP_DATA_MS } from './lib/cacheTime';
import { errorMessage } from './lib/errors';
import { startHubWatch } from './lib/hub';
import { flush, loadOutbox, setOnApplied } from './lib/outbox';
import { registerServiceWorker } from './lib/serviceWorker';
import { theme } from './theme';

declare module '@tanstack/react-query' {
  interface Register {
    mutationMeta: { handlesErrors?: boolean };
    queryMeta: { silent?: boolean };
  }
}

function showError(error: Error) {
  // "Laptop not reachable" is shown once in the header, not as a pop-up per request.
  if (error instanceof ApiError && error.code === 'offline') return;
  notifications.show({ color: 'red', title: i18n.t('app.error'), message: errorMessage(error) });
}



const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (!query.meta?.silent) showError(error);
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _vars, _ctx, mutation) => {
      if (!mutation.meta?.handlesErrors) showError(error);
    },
  }),
  defaultOptions: {
    // Keep data around long enough to be saved on the device and read offline.
    queries: { retry: 1, staleTime: 10_000, gcTime: KEEP_DATA_MS, refetchOnWindowFocus: true },
    // Changes always run: they go into the offline queue, which decides when to send.
    mutations: { networkMode: 'always' },
  },
});

/** Saves fetched data in IndexedDB so screens still show it when the laptop is off. */
const persister = createAsyncStoragePersister({
  storage: {
    getItem: async (key) => (await get<string>(key)) ?? null,
    setItem: (key, value) => set(key, value),
    removeItem: (key) => del(key),
  },
  key: 'fms.queryCache.v1',
  throttleTime: 2000,
});

// Diagnostics for support: localStorage.setItem('fms.debug', '1') exposes the data store.
try {
  if (localStorage.getItem('fms.debug') === '1') {
    (window as unknown as { __fms: unknown }).__fms = { queryClient };
  }
} catch {
  /* storage unavailable */
}

// When changes reach the laptop (or it comes back), refresh what every screen shows.
const refreshAll = () => void queryClient.invalidateQueries();
// Workers, rates, etc. are fetched up front so entry works offline even for screens
// the owner hasn't opened yet.
setOnApplied(refreshAll);
void loadOutbox().then(() => flush());
prefetchEssentials(queryClient);
startHubWatch(() => {
  void flush();
  refreshAll();
  prefetchEssentials(queryClient);
});
registerServiceWorker();

// Ask the browser not to clear our stored data under storage pressure (matters on phones).
void navigator.storage?.persist?.();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={theme}>
      <PersistQueryClientProvider
        client={queryClient}
        persistOptions={{
          persister,
          maxAge: KEEP_DATA_MS,
          buster: __APP_VERSION__, // a new app version starts with fresh saved data
          dehydrateOptions: {
            // Keep anything that has data — including data whose last refresh failed
            // because the laptop was away (it's still the latest the device has).
            shouldDehydrateQuery: (q) => q.state.data !== undefined && q.queryKey[0] !== 'preview',
          },
        }}
      >
        <ModalsProvider>
          <Notifications position="top-right" />
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ModalsProvider>
      </PersistQueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);
