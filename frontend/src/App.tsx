import { Center, Loader } from '@mantine/core';
import { DatesProvider } from '@mantine/dates';
import { Suspense, lazy, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Route, Routes } from 'react-router';

import { useSettings } from './api/hooks';
import AppLayout from './components/AppLayout';
import { setUiLanguage } from './i18n';

// Each screen loads on first visit, so the app starts fast and the chart
// library is only downloaded when a screen with charts is opened.
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ProductionPage = lazy(() => import('./pages/ProductionPage'));
const WagesPage = lazy(() => import('./pages/WagesPage'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));
const WorkersPage = lazy(() => import('./pages/WorkersPage'));
const RatesPage = lazy(() => import('./pages/RatesPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const PrintSlipsPage = lazy(() => import('./pages/PrintSlipsPage'));
const PrintReportPage = lazy(() => import('./pages/PrintReportPage'));

function PageLoader() {
  return (
    <Center py="xl">
      <Loader />
    </Center>
  );
}

export default function App() {
  const { i18n } = useTranslation();
  const settings = useSettings();

  // The hub's saved language wins on start-up (so every device follows the owner's choice).
  const hubLanguage = settings.data?.ui_language;
  useEffect(() => {
    if (hubLanguage && hubLanguage !== i18n.language) setUiLanguage(hubLanguage);
    // Only react to the hub value changing, not to local toggles.
  }, [hubLanguage]);

  return (
    <DatesProvider settings={{ locale: i18n.language, firstDayOfWeek: 1 }}>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/print/wages" element={<PrintSlipsPage />} />
          <Route path="/print/production" element={<PrintReportPage />} />
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/production" element={<ProductionPage />} />
            <Route path="/wages" element={<WagesPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/workers" element={<WorkersPage />} />
            <Route path="/rates" element={<RatesPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </DatesProvider>
  );
}
