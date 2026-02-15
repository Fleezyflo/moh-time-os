/**
 * HTTP Client with zod validation.
 *
 * One of two API patterns in this codebase:
 * - This module: zod validation + TanStack Query (used by 5 core endpoints)
 * - Typed fetch wrappers: TypeScript interfaces (used by intelligence, pages)
 *
 * Features:
 * - Runtime response validation via zod
 * - Automatic request-id generation and propagation
 * - Standardized error handling with ApiError
 * - Request/response logging in development
 */

import { z } from 'zod';
import { apiErrorSchema } from './schemas';

// ============================================================================
// Configuration
// ============================================================================

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v2';
const IS_DEV = import.meta.env.DEV;

// ============================================================================
// Request ID Generation
// ============================================================================

function generateRequestId(): string {
  return `ui-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// ============================================================================
// API Error Class
// ============================================================================

export class ApiError extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly code: string;
  readonly requestId: string;
  readonly details: unknown;
  readonly isNetworkError: boolean;

  constructor(
    status: number,
    statusText: string,
    message: string,
    options?: {
      code?: string;
      requestId?: string;
      details?: unknown;
      isNetworkError?: boolean;
    }
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.code = options?.code || 'UNKNOWN_ERROR';
    this.requestId = options?.requestId || '';
    this.details = options?.details;
    this.isNetworkError = options?.isNetworkError || false;
  }

  get isUnauthorized() {
    return this.status === 401;
  }
  get isForbidden() {
    return this.status === 403;
  }
  get isNotFound() {
    return this.status === 404;
  }
  get isServerError() {
    return this.status >= 500;
  }
  get isClientError() {
    return this.status >= 400 && this.status < 500;
  }

  toJSON() {
    return {
      name: this.name,
      message: this.message,
      status: this.status,
      statusText: this.statusText,
      code: this.code,
      requestId: this.requestId,
      details: this.details,
    };
  }
}

// ============================================================================
// Core HTTP Functions
// ============================================================================

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

/**
 * Low-level fetch wrapper with request-id propagation and error handling.
 * Use get/post/patch helpers below instead of calling directly.
 */
async function request<T>(
  url: string,
  schema: z.ZodType<T>,
  options: RequestOptions = {}
): Promise<{ data: T; requestId: string }> {
  const requestId = generateRequestId();
  const fullUrl = url.startsWith('http')
    ? url
    : `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`;

  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-Request-ID': requestId,
    ...options.headers,
  };

  if (options.body) {
    headers['Content-Type'] = 'application/json';
  }

  if (IS_DEV) {
    // eslint-disable-next-line no-console
    console.log(`[API] ${options.method || 'GET'} ${fullUrl} [${requestId}]`);
  }

  let response: Response;
  try {
    response = await fetch(fullUrl, {
      method: options.method || 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });
  } catch (err) {
    // Network error (offline, CORS, etc.)
    throw new ApiError(0, 'Network Error', 'Unable to connect to server', {
      code: 'NETWORK_ERROR',
      requestId,
      isNetworkError: true,
      details: err,
    });
  }

  // Get response request-id (server may override)
  const serverRequestId = response.headers.get('X-Request-ID') || requestId;

  if (!response.ok) {
    let errorBody: unknown = null;
    let errorMessage = response.statusText;

    try {
      errorBody = await response.json();
      const parsed = apiErrorSchema.safeParse(errorBody);
      if (parsed.success) {
        errorMessage =
          parsed.data.detail || parsed.data.error || parsed.data.message || errorMessage;
      }
    } catch {
      // Response not JSON
    }

    throw new ApiError(response.status, response.statusText, errorMessage, {
      code: `HTTP_${response.status}`,
      requestId: serverRequestId,
      details: errorBody,
    });
  }

  // Parse and validate response
  const json = await response.json();
  const parseResult = schema.safeParse(json);

  if (!parseResult.success) {
    if (IS_DEV) {
      console.error(`[API] Schema validation failed for ${fullUrl}:`, parseResult.error.issues);
    }
    throw new ApiError(0, 'Validation Error', 'Invalid response from server', {
      code: 'SCHEMA_VALIDATION_ERROR',
      requestId: serverRequestId,
      details: parseResult.error.issues,
    });
  }

  if (IS_DEV) {
    // eslint-disable-next-line no-console
    console.log(`[API] ✓ ${fullUrl} [${serverRequestId}]`);
  }

  return { data: parseResult.data, requestId: serverRequestId };
}

/**
 * GET request with schema validation.
 */
export async function get<T>(url: string, schema: z.ZodType<T>): Promise<T> {
  const { data } = await request(url, schema, { method: 'GET' });
  return data;
}

/**
 * POST request with schema validation.
 */
export async function post<T>(url: string, body: unknown, schema: z.ZodType<T>): Promise<T> {
  const { data } = await request(url, schema, { method: 'POST', body });
  return data;
}

/**
 * PATCH request with schema validation.
 */
export async function patch<T>(url: string, body: unknown, schema: z.ZodType<T>): Promise<T> {
  const { data } = await request(url, schema, { method: 'PATCH', body });
  return data;
}

/**
 * DELETE request with schema validation.
 */
export async function del<T>(url: string, schema: z.ZodType<T>): Promise<T> {
  const { data } = await request(url, schema, { method: 'DELETE' });
  return data;
}

// Re-export ApiError for use elsewhere
export { ApiError as default };
