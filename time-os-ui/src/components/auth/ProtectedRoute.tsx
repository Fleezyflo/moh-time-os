// Protected route wrapper that redirects to login if not authenticated
import type { ReactNode } from 'react';
import { useAuth } from './AuthContext';
import { LoginScreen } from './LoginScreen';

interface ProtectedRouteProps {
  children: ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  return <>{children}</>;
}
