import { Alert, Button, Stack, Text } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { checkHub } from '../lib/hub';
import { reportError } from '../lib/reportError';

function isLoadError(error: Error): boolean {
  // A screen's code couldn't be downloaded (laptop off, or a newer version replaced it).
  return /dynamically imported module|Importing a module script failed|error loading dynamically/i.test(
    error.message,
  );
}

function Fallback({ error }: { error: Error }) {
  const { t } = useTranslation();
  const retry = async () => {
    // A failed screen download is remembered by the browser, so a fresh start is needed —
    // but only once the laptop can be reached, or the whole app would go blank.
    if (await checkHub()) window.location.reload();
  };
  return (
    <Alert color="orange" variant="light" icon={<IconAlertTriangle />} title={t('screen.title')}>
      <Stack gap="sm" align="flex-start">
        <Text size="sm">{isLoadError(error) ? t('screen.notSaved') : t('screen.crashed')}</Text>
        <Button size="xs" variant="light" onClick={() => void retry()}>
          {t('sync.retry')}
        </Button>
      </Stack>
    </Alert>
  );
}

/** Keeps a problem in one screen from blanking the whole app. */
export class ScreenBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Screen failed', error, info.componentStack);
    if (!isLoadError(error)) reportError(error, `screen ${location.pathname}`);
  }

  render() {
    return this.state.error ? <Fallback error={this.state.error} /> : this.props.children;
  }
}
