/**
 * API Module - TanStack Query + Zod Pattern
 *
 * Used by core endpoints (health, clients, proposals, issues, team).
 * Other modules (intelligence, pages) use typed fetch wrappers directly.
 */

// HTTP Client
export { get, post, patch, del, ApiError } from './http';

// Zod Schemas
export * from './schemas';

// TanStack Query Hooks
export * from './hooks';

// Query Client
export { queryClient } from './queryClient';
