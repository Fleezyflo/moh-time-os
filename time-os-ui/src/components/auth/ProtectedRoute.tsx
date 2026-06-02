// Protected route — single-user guard (WS2).
// Renders children only when an API token is configured; otherwise shows a
// minimal sign-in prompt. This is the one place future auth changes, not the
// routes themselves.
import type { ReactNode } from 'react';
import { getApiToken } from '../../lib/auth';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const token = getApiToken();
  if (!token) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <h2>Authentication required</h2>
        <p>
          Set <code>VITE_API_TOKEN</code> to your API key (the value of{' '}
          <code>MOH_TIME_OS_API_KEY</code>) and reload.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}
