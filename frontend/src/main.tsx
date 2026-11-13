import '@mantine/core/styles.css';
import '@mantine/dates/styles.css';
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
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';

import App from './App';
import i18n from './i18n';
import { theme } from './theme';

declare module '@tanstack/react-query' {
  interface Register {
    mutationMeta: { handlesErrors?: boolean };
    queryMeta: { silent?: boolean };
  }
}

function showError(error: Error) {
  notifications.show({ color: 'red', title: i18n.t('app.error'), message: error.message });
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
  defaultOptions: { queries: { retry: 1, staleTime: 10_000, refetchOnWindowFocus: true } },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={theme}>
      <QueryClientProvider client={queryClient}>
        <ModalsProvider>
          <Notifications position="top-right" />
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ModalsProvider>
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);
