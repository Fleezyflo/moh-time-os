/**
 * Domain Model Layer
 *
 * Maps API DTOs to UI-safe view models.
 * All components consume domain models only.
 *
 * Invariants:
 * - No nulls in view models (defaults applied)
 * - All dates normalized to ISO strings
 * - All IDs are non-empty strings
 */

export * from './client';
export * from './proposal';
export * from './issue';
export * from './types';
