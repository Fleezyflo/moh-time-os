// Login screen with API key input
import { useState } from 'react';
import { useAuth } from './AuthContext';

export function LoginScreen() {
  const { login } = useAuth();
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login(apiKey);
      setApiKey('');
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Login failed');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--black)] px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-[var(--white)] mb-2">Time OS</h1>
          <p className="text-[var(--grey)]">Enter your API key to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="apikey" className="block text-sm font-medium text-[var(--white)] mb-2">
              API Key
            </label>
            <input
              id="apikey"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your API key"
              disabled={loading}
              className="w-full px-4 py-3 rounded-lg bg-[var(--grey-dim)] text-[var(--white)] placeholder-[var(--grey)] border border-[var(--grey)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 outline-none transition-colors disabled:opacity-50"
            />
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-[var(--danger)]/10 border border-[var(--danger)]/50 text-[var(--danger)] text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !apiKey.trim()}
            className="w-full py-3 rounded-lg bg-[var(--accent)] text-white font-medium hover:bg-[var(--accent)]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[44px]"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <p className="text-center text-[var(--grey)] text-sm mt-6">
          Your API key is stored securely in memory and will not be sent elsewhere.
        </p>
      </div>
    </div>
  );
}
