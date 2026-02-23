// Protected route — passthrough for single-user system
import type { ReactNode } from 'react';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
