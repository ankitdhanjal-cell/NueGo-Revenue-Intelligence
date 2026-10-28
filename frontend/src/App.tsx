import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { ToastProvider } from './components/Toast';
import { UserProvider } from './lib/user';
import DeskPage from './pages/DeskPage';
import FarePredictorPage from './pages/FarePredictorPage';
import SettingsPage from './pages/SettingsPage';
import TotalsPage from './pages/TotalsPage';
import WarningsPage from './pages/WarningsPage';

const ServicePage = lazy(() => import('./pages/ServicePage'));

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <UserProvider>
        <ToastProvider>
          <Suspense fallback={<p className="p-6">Loading…</p>}>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<DeskPage />} />
                <Route path="services/:id" element={<ServicePage />} />
                <Route path="warnings" element={<WarningsPage />} />
                <Route path="totals" element={<TotalsPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="fare-predictor" element={<FarePredictorPage />} />
                <Route path="*" element={<p>Page not found.</p>} />
              </Route>
            </Routes>
          </Suspense>
        </ToastProvider>
      </UserProvider>
    </QueryClientProvider>
  );
}
