# UI-API Wiring Guide

This document describes the patterns for API integration between the React UI and FastAPI backend.

## Overview

The UI uses **two patterns** for API calls, both acceptable:

### Pattern 1: Typed Fetch Wrappers (majority)

Used by: `lib/api.ts`, `intelligence/api.ts`, most pages

```typescript
// intelligence/api.ts
interface Signal {
  signal_id: string;
  name: string;
  severity: 'critical' | 'warning' | 'watch';
  // ...
}

async function fetchJson<T>(url: string): Promise<ApiResponse<T>> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json();
}

export async function fetchSignals(): Promise<ApiResponse<Signal[]>> {
  return fetchJson(`${API_BASE}/signals`);
}
```

With hooks:

```typescript
function useData<T>(fetchFn: () => Promise<T>): { data: T | null; loading: boolean; error: Error | null } {
  // useState + useEffect pattern
}

export function useSignals() {
  return useData(() => api.fetchSignals());
}
```

### Pattern 2: TanStack Query + Zod (src/api/)

Used by: 5 core endpoints (health, clients, proposals, issues, team)

```
src/api/
├── http.ts            # HTTP client with zod validation + request-id
├── schemas/           # Zod schemas for responses
├── hooks/             # TanStack Query hooks
└── queryClient.ts     # Query client config
```

```typescript
// Using TanStack Query + zod
import { useClients } from '../api';

function ClientList() {
  const { data, isLoading, error } = useClients();
}
```

## When to Use Which

| Pattern | Use When |
|---------|----------|
| Typed fetch wrapper | New feature modules, simpler data needs |
| TanStack Query + zod | Need runtime validation, complex caching, optimistic updates |

Both patterns provide:
- TypeScript type safety
- Centralized error handling
- Testable code

The TanStack Query pattern adds:
- Runtime response validation (catches API contract violations)
- Automatic caching and refetching
- Query invalidation

## Error Handling

### Pattern 1 (fetch wrapper)
```typescript
const { data, error, refetch } = useSignals();

if (error) {
  return <ErrorState error={error} onRetry={refetch} />;
}
```

### Pattern 2 (TanStack Query)
```typescript
const { data, isLoading, error, refetch } = useClients();

// ApiError class provides rich error info
if (error instanceof ApiError) {
  if (error.isUnauthorized) { /* handle 401 */ }
}
```

## Testing

Both patterns can be tested with MSW for mocking API responses.

```typescript
import { server } from '../api/fixtures/server';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test('displays data', async () => {
  render(<Component />);
  await waitFor(() => {
    expect(screen.getByText('expected')).toBeInTheDocument();
  });
});
```

## Make Targets

| Target | Description |
|--------|-------------|
| `make ui-check` | Full UI quality suite (lint + typecheck + test + build) |
| `make ui-test` | Run Vitest unit tests |
| `make dev` | Start API + UI dev servers |

## Adding a New Endpoint

### For new feature modules (recommended: Pattern 1)

1. Create typed API file: `src/feature/api.ts`
2. Define TypeScript interfaces for responses
3. Create fetch wrapper functions
4. Create hooks using `useData` pattern

### For core endpoints (Pattern 2)

1. Add zod schema in `src/api/schemas/index.ts`
2. Add hook in `src/api/hooks/index.ts`
3. Add MSW fixture in `src/api/fixtures/handlers.ts`
