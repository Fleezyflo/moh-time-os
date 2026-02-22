import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from '@tanstack/react-router';
import { router } from './router';
import { AuthProvider } from './components/auth';
import { ErrorBoundary, ToastProvider } from './components';
import { EventStreamSetup } from './components/EventStreamSetup';
import './index.css';

// Register service worker for PWA
if ('serviceWorker' in navigator) {
  navigator.serviceWorker
    .getRegistrations()
    .then((registrations) => {
      for (const registration of registrations) {
        registration.unregister();
        console.warn('Old service worker unregistered');
      }
    })
    .then(() => {
      // Register the new service worker from VitePWA
      return navigator.serviceWorker.register('/sw.js', { scope: '/' });
    })
    .then((registration) => {
      console.warn('Service worker registered:', registration);
    })
    .catch((error) => {
      console.error('Service worker registration failed:', error);
    });
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <ErrorBoundary>
        <ToastProvider>
          <EventStreamSetup>
            <RouterProvider router={router} />
          </EventStreamSetup>
        </ToastProvider>
      </ErrorBoundary>
    </AuthProvider>
  </StrictMode>
);
