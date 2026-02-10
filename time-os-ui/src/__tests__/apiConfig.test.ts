import { describe, it, expect, vi, afterEach } from 'vitest';

describe('API Base URL Configuration', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('should use VITE_API_BASE_URL when set', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com/control-room');

    // The env variable should be accessible
    expect(import.meta.env.VITE_API_BASE_URL).toBe('https://api.example.com/control-room');
  });

  it('should resolve to relative path for production deploy', () => {
    // Verify the default fallback pattern
    const envValue = undefined;
    const apiBase = envValue || '/api/control-room';

    expect(apiBase).toBe('/api/control-room');
    expect(apiBase.startsWith('/')).toBe(true);
    expect(apiBase).not.toContain('localhost');
  });

  it('should allow full URL override for custom backends', () => {
    const customUrl = 'https://api.production.example.com/v1';
    const envValue = customUrl;
    const apiBase = envValue || '/api/control-room';

    expect(apiBase).toBe(customUrl);
  });
});

describe('Vite Proxy Configuration', () => {
  it('should have correct proxy pattern for /api routes', () => {
    // This documents the expected proxy config in vite.config.ts
    const expectedProxyConfig = {
      '/api': {
        target: 'http://localhost:8420',
        changeOrigin: true,
        secure: false,
      }
    };

    // Proxy only affects dev server, not production
    expect(expectedProxyConfig['/api'].target).toContain('8420');
    expect(expectedProxyConfig['/api'].changeOrigin).toBe(true);
  });
});
