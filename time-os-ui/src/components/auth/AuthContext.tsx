/* eslint-disable react-refresh/only-export-components -- Context is core functionality */
// Authentication context for token, role, and user info
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

interface AuthState {
  token: string | null;
  role: string | null;
  userId: string | null;
  isAuthenticated: boolean;
}

interface AuthContextType extends AuthState {
  login: (apiKey: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authState, setAuthState] = useState<AuthState>({
    token: localStorage.getItem('auth_token'),
    role: localStorage.getItem('auth_role'),
    userId: localStorage.getItem('auth_user_id'),
    isAuthenticated: !!localStorage.getItem('auth_token'),
  });

  const login = useCallback(async (apiKey: string) => {
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v2';

    try {
      const response = await fetch(`${apiBase}/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey }),
      });

      if (!response.ok) {
        throw new Error('Invalid API key');
      }

      const data = await response.json();
      const token = data.token || apiKey;
      const role = data.role || 'user';
      const userId = data.user_id || 'unknown';

      // Store in localStorage and state
      localStorage.setItem('auth_token', token);
      localStorage.setItem('auth_role', role);
      localStorage.setItem('auth_user_id', userId);

      setAuthState({
        token,
        role,
        userId,
        isAuthenticated: true,
      });
    } catch (error) {
      // Log the error but don't silence it
      if (error instanceof Error) {
        throw new Error(`Login failed: ${error.message}`);
      }
      throw new Error('Login failed: Unknown error');
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_role');
    localStorage.removeItem('auth_user_id');
    setAuthState({
      token: null,
      role: null,
      userId: null,
      isAuthenticated: false,
    });
  }, []);

  const value: AuthContextType = {
    ...authState,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
