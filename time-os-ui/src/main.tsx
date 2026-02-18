import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from '@tanstack/react-router';
import { router } from './router';
import { ErrorBoundary, ToastProvider, DegradedModeBanner } from './components';
import { initOfflineListeners } from './lib/offline';
import './index.css';

// Force unregister any cached service workers
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then((registrations) => {
    for (const registration of registrations) {
      registration.unregister();
      // eslint-disable-next-line no-console
      console.log('Service worker unregistered');
    }
  });
}

// Initialize offline/degraded mode detection
initOfflineListeners();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <ToastProvider>
        <DegradedModeBanner />
        <RouterProvider router={router} />
      </ToastProvider>
    </ErrorBoundary>
  </StrictMode>
);
