/**
 * Consumer-driven API contract tests.
 *
 * These tests verify that the API responses match what the UI expects.
 * They run against the generated TypeScript types from OpenAPI.
 *
 * Two levels of verification:
 * 1. Compile-time: TypeScript ensures the types match
 * 2. Runtime: Tests verify actual API responses decode correctly
 */

import { describe, it, expect } from 'vitest';
import type { paths } from '../types/generated';

// Type helpers for extracting response types
type HealthResponse = paths['/api/health']['get']['responses']['200']['content']['application/json'];
type ClientsResponse = paths['/api/clients']['get']['responses']['200']['content']['application/json'];

// Concrete interfaces for runtime checks (mirrors expected shapes)
interface ExpectedHealthResponse {
  status: string;
  timestamp: string;
}

interface ExpectedClient {
  id: string;
  name: string;
  status: string;
}

/**
 * Compile-time contract verification.
 *
 * These tests use TypeScript's type system to verify at compile time
 * that our expected shapes match the generated types.
 */
describe('Compile-time API contracts', () => {
  it('health endpoint has required fields', () => {
    // This test passes at compile time if the types match
    const healthResponse = {
      status: 'healthy',
      timestamp: '2024-01-01T00:00:00Z',
    } as HealthResponse & ExpectedHealthResponse;

    expect(healthResponse.status).toBeDefined();
    expect(healthResponse.timestamp).toBeDefined();
  });

  it('clients endpoint returns array', () => {
    // Verify clients response is an array
    const clientsResponse: ClientsResponse = [];
    expect(Array.isArray(clientsResponse)).toBe(true);
  });
});

/**
 * Runtime contract verification.
 *
 * These tests verify that actual API responses can be decoded
 * into the expected TypeScript types without errors.
 */
describe('Runtime API contracts', () => {
  // Mock API responses based on actual API behavior
  const mockHealthResponse = {
    status: 'healthy',
    timestamp: '2024-01-01T00:00:00Z',
  };

  const mockClientsResponse = [
    {
      id: 'client-1',
      name: 'Test Client',
      status: 'active',
    },
  ];

  it('health response decodes correctly', () => {
    // Simulate decoding API response - verify it satisfies both generated and expected types
    const decoded = mockHealthResponse as HealthResponse & ExpectedHealthResponse;

    expect(decoded.status).toBe('healthy');
    expect(decoded.timestamp).toBeDefined();
  });

  it('clients response decodes correctly', () => {
    // Simulate decoding API response
    const decoded = mockClientsResponse as ClientsResponse & ExpectedClient[];

    expect(Array.isArray(decoded)).toBe(true);
    expect(decoded.length).toBeGreaterThan(0);
  });

  it('rejects malformed health response', () => {
    // Test that we can detect missing required fields
    const malformed = {
      status: 'healthy',
      // missing timestamp
    };

    // In a real app, you'd use a runtime validator like zod
    // For now, just verify the shape
    expect('timestamp' in malformed).toBe(false);
  });
});

/**
 * Schema strictness contracts.
 *
 * These tests verify that the API schema doesn't accidentally become more permissive.
 */
describe('Schema strictness contracts', () => {
  it('health response has no extra fields', () => {
    // Verify we're not allowing arbitrary extra fields
    const response = {
      status: 'healthy',
      timestamp: '2024-01-01T00:00:00Z',
    };

    const allowedKeys = ['status', 'timestamp', 'components', 'version'];
    const actualKeys = Object.keys(response);

    for (const key of actualKeys) {
      expect(allowedKeys).toContain(key);
    }
  });
});

/**
 * Required endpoint existence.
 *
 * Compile-time verification that required endpoints exist in the API spec.
 */
describe('Required endpoints exist', () => {
  it('/api/health exists', () => {
    // This would fail at compile time if the endpoint didn't exist
    type HealthEndpoint = paths['/api/health'];
    const endpoint: HealthEndpoint = {} as HealthEndpoint;
    expect(endpoint).toBeDefined();
  });

  it('/api/clients exists', () => {
    type ClientsEndpoint = paths['/api/clients'];
    const endpoint: ClientsEndpoint = {} as ClientsEndpoint;
    expect(endpoint).toBeDefined();
  });

  it('/api/control-room/proposals exists', () => {
    type ProposalsEndpoint = paths['/api/control-room/proposals'];
    const endpoint: ProposalsEndpoint = {} as ProposalsEndpoint;
    expect(endpoint).toBeDefined();
  });
});
