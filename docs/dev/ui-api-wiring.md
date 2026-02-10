# UI-API Wiring Guide

This document describes the architecture and conventions for API integration between the React UI and FastAPI backend.

## Overview

The UI uses a typed, validated API layer with the following components:

```
src/api/
├── index.ts           # Single entrypoint - export everything
├── http.ts            # HTTP client with zod validation + request-id
├── schemas/           # Zod schemas for all API responses
├── hooks/             # TanStack Query hooks
├── queryClient.ts     # Query client configuration
├── fixtures/          # MSW handlers for testing
└── __tests__/         # Integration tests
```

## Key Principles

### 1. Single API Entrypoint

**All API access MUST go through `src/api/`.**

Direct `fetch()` or `axios` usage outside this directory is banned by ESLint:

```typescript
// ❌ BANNED - will fail lint
const data = await fetch('/api/health').then(r => r.json());

// ✅ CORRECT - use the API module
import { get, healthResponseSchema } from '../api';
const data = await get('/health', healthResponseSchema);
```

### 2. Runtime Response Validation (Zod)

Every API response is validated at runtime using zod schemas:

```typescript
// src/api/schemas/index.ts
export const healthResponseSchema = z.object({
  status: z.enum(['healthy', 'unhealthy']),
  timestamp: z.string(),
});

// src/api/http.ts
export async function get<T>(url: string, schema: z.ZodType<T>): Promise<T> {
  const response = await fetch(url);
  const json = await response.json();
  return schema.parse(json);  // Throws if invalid
}
```

Benefits:
- Catch API contract violations at runtime
- TypeScript types inferred from schemas
- Clear error messages when API changes unexpectedly

### 3. TanStack Query Integration

Data fetching uses TanStack Query for caching, retries, and state management:

```typescript
// src/api/hooks/index.ts
export function useClients() {
  return useQuery({
    queryKey: queryKeys.clients(),
    queryFn: () => get('/clients', clientListSchema),
    staleTime: 30_000,
  });
}

// Component usage
function ClientList() {
  const { data, isLoading, error } = useClients();
  // ...
}
```

Query key conventions:
- `['entity']` - list queries
- `['entity', id]` - detail queries
- `['entity', { filters }]` - filtered queries

### 4. Request-ID Propagation

Every request includes a client-generated request ID:

```typescript
// Automatically added by http.ts
headers: {
  'X-Request-ID': 'ui-1707654321000-abc123'
}
```

The API echoes this back, enabling end-to-end tracing:
- UI logs: `[API] GET /api/health [ui-1707654321000-abc123]`
- API logs: `request_id=ui-1707654321000-abc123`
- Response headers: `X-Request-ID: ui-1707654321000-abc123`

### 5. Standardized Error Handling

All API errors are wrapped in `ApiError`:

```typescript
class ApiError extends Error {
  status: number;
  statusText: string;
  code: string;
  requestId: string;
  details: unknown;
}

// Usage
try {
  await get('/api/endpoint', schema);
} catch (err) {
  if (err instanceof ApiError) {
    if (err.isUnauthorized) { /* handle 401 */ }
    if (err.isNotFound) { /* handle 404 */ }
    console.error('Request ID:', err.requestId);
  }
}
```

## Testing

### Unit Tests

Test hooks and components with MSW:

```typescript
import { server } from '../api/fixtures/server';
import { fixtures } from '../api/fixtures/handlers';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test('displays clients', async () => {
  render(<ClientList />);
  await waitFor(() => {
    expect(screen.getByText(fixtures.clients.items[0].name)).toBeInTheDocument();
  });
});
```

### Integration Tests

Run `make ui-integration` or:

```bash
cd time-os-ui && pnpm test -- integration
```

These tests verify the full flow: UI client → MSW → zod validation.

## Make Targets

| Target | Description |
|--------|-------------|
| `make ui-check` | Full UI quality suite (lint + typecheck + test + build) |
| `make ui-test` | Run Vitest unit tests |
| `make ui-contracts` | Run API contract tests |
| `make ui-fixtures` | Validate MSW fixtures against schemas |
| `make ui-integration` | Run integration tests (<30s) |
| `make dev` | Start API + UI dev servers |

## Contract Enforcement

UI-used endpoints are tracked and protected:

```typescript
// src/api/schemas/index.ts
export const UI_USED_ENDPOINTS = [
  '/api/health',
  '/api/v2/health',
  '/api/v2/proposals',
  '/api/v2/issues',
  '/api/v2/clients',
  '/api/v2/team',
  '/api/metrics',
] as const;
```

The CI enforces that these endpoints cannot loosen (remove required fields, change types).

## Adding a New Endpoint

1. Add zod schema in `src/api/schemas/index.ts`
2. Add hook in `src/api/hooks/index.ts`
3. Add MSW fixture in `src/api/fixtures/handlers.ts`
4. Add to `UI_USED_ENDPOINTS` if it's a core endpoint
5. Write tests

Example:

```typescript
// 1. Schema
export const newEndpointSchema = z.object({
  id: z.string(),
  data: z.string(),
});

// 2. Hook
export function useNewEndpoint() {
  return useQuery({
    queryKey: ['new-endpoint'],
    queryFn: () => get('/new-endpoint', newEndpointSchema),
  });
}

// 3. Fixture
export const fixtures = {
  newEndpoint: { id: 'test', data: 'test-data' },
};

http.get('*/api/v2/new-endpoint', () => HttpResponse.json(fixtures.newEndpoint));
```

## Debugging

Enable verbose logging in development:

```bash
VITE_API_BASE_URL=http://localhost:8421/api/v2 pnpm dev
```

The console will show:
```
[API] GET /api/v2/health [ui-1707654321000-abc123]
[API] ✓ /api/v2/health [ui-1707654321000-abc123]
```
