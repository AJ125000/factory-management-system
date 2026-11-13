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
const screens = {
  dashboard: () => import('./pages/DashboardPage'),
  production: () => import('./pages/ProductionPage'),
  wages: () => import('./pages/WagesPage'),
  reports: () => import('./pages/ReportsPage'),
  workers: () => import('./pages/WorkersPage'),
  rates: () => import('./pages/RatesPage'),
  settings: () => import('./pages/SettingsPage'),
  printSlips: () => import('./pages/PrintSlipsPage'),
  printReport: () => import('./pages/PrintReportPage'),
};
const DashboardPage = lazy(screens.dashboard);
const ProductionPage = lazy(screens.production);
const WagesPage = lazy(screens.wages);
const ReportsPage = lazy(screens.reports);
const WorkersPage = lazy(screens.workers);
const RatesPage = lazy(screens.rates);
const SettingsPage = lazy(screens.settings);
const PrintSlipsPage = lazy(screens.printSlips);
const PrintReportPage = lazy(screens.printReport);

/**
 * Shortly after start-up, load the code of every screen in the background. Once loaded
 * it stays in memory, so the owner can switch screens even if the laptop then goes off
 * (the service worker also keeps it for the next start).
 */
function preloadScreens() {
  setTimeout(() => {
    for (const load of Object.values(screens)) load().catch(() => {});
  }, 1500);
}
preloadScreens();

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
