// Single source of truth for the API credential (WS2).
// The backend enforces a shared-secret Bearer token (MOH_TIME_OS_API_KEY).
// The client reads it from VITE_API_TOKEN at build time; setApiToken allows a
// runtime override (e.g. a future sign-in form) without touching call sites.

let apiToken: string = import.meta.env.VITE_API_TOKEN || '';

export function getApiToken(): string {
  return apiToken;
}

export function setApiToken(token: string): void {
  apiToken = token;
}

/** Authorization header object, or {} when no token is configured. */
export function authHeader(): Record<string, string> {
  return apiToken ? { Authorization: `Bearer ${apiToken}` } : {};
}
