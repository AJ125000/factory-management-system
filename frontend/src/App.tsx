import { DatesProvider } from '@mantine/dates';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Route, Routes } from 'react-router';

import { useSettings } from './api/hooks';
import AppLayout from './components/AppLayout';
import { setUiLanguage } from './i18n';
import PrintSlipsPage from './pages/PrintSlipsPage';
import ProductionPage from './pages/ProductionPage';
import RatesPage from './pages/RatesPage';
import SettingsPage from './pages/SettingsPage';
import WagesPage from './pages/WagesPage';
import WorkersPage from './pages/WorkersPage';

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
      <Routes>
        <Route path="/print/wages" element={<PrintSlipsPage />} />
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/production" replace />} />
          <Route path="/production" element={<ProductionPage />} />
          <Route path="/wages" element={<WagesPage />} />
          <Route path="/workers" element={<WorkersPage />} />
          <Route path="/rates" element={<RatesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/production" replace />} />
        </Route>
      </Routes>
    </DatesProvider>
  );
}
