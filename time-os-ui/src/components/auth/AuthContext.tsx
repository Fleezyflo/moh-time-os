/* eslint-disable react-refresh/only-export-components -- Context is core functionality */
// Auth context — single-user system, always authenticated
import { createContext, useContext, type ReactNode } from 'react';

interface AuthState {
  token: string;
  role: string;
  userId: string;
  isAuthenticated: true;
}

interface AuthContextType extends AuthState {
  login: (apiKey: string) => Promise<void>;
  logout: () => void;
}

const AUTH: AuthState = {
  token: 'local',
  role: 'owner',
  userId: 'molham',
  isAuthenticated: true,
};

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const value: AuthContextType = {
    ...AUTH,
    login: async () => {
      // No-op — always authenticated
    },
    logout: () => {
      // No-op — can't log out of a single-user system
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
