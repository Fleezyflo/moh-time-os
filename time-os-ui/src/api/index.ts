/**
 * API Module - Single Entrypoint
 * 
 * ALL API access MUST go through this module.
 * Direct fetch/axios usage outside this module is BANNED.
 */

// HTTP Client
export { get, post, patch, del, ApiError } from './http';

// Zod Schemas
export * from './schemas';

// TanStack Query Hooks
export * from './hooks';

// Query Client
export { queryClient } from './queryClient';
