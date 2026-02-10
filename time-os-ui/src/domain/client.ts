/**
 * Client Domain Mapper
 *
 * Maps API Client DTO to ClientViewModel.
 */

import type { ClientViewModel } from './types';

// API DTO type (from zod schema or generated)
interface ClientDTO {
  id?: string | null;
  name?: string | null;
  status?: string | null;
  tier?: string | null;
  health_score?: number | null;
  last_activity?: string | null;
}

// ============================================================================
// Mapping Functions
// ============================================================================

export function mapClient(dto: ClientDTO): ClientViewModel {
  const healthScore = dto.health_score ?? 50;
  const status = normalizeStatus(dto.status);

  return {
    id: dto.id ?? 'unknown',
    name: dto.name ?? 'Unknown Client',
    status,
    tier: normalizeTier(dto.tier),
    healthScore,
    healthLabel: getHealthLabel(healthScore),
    healthColor: getHealthColor(healthScore),
    lastActivityDate: dto.last_activity ?? new Date().toISOString(),
    lastActivityRelative: formatRelativeDate(dto.last_activity),
  };
}

export function mapClients(dtos: ClientDTO[]): ClientViewModel[] {
  return dtos.map(mapClient);
}

// ============================================================================
// Helpers
// ============================================================================

function normalizeStatus(
  status: string | null | undefined
): ClientViewModel['status'] {
  switch (status?.toLowerCase()) {
    case 'active':
      return 'active';
    case 'inactive':
      return 'inactive';
    case 'at-risk':
    case 'at_risk':
      return 'at-risk';
    case 'churned':
      return 'churned';
    default:
      return 'inactive';
  }
}

function normalizeTier(
  tier: string | null | undefined
): ClientViewModel['tier'] {
  switch (tier?.toUpperCase()) {
    case 'A':
      return 'A';
    case 'B':
      return 'B';
    case 'C':
      return 'C';
    case 'D':
      return 'D';
    default:
      return 'C';
  }
}

function getHealthLabel(score: number): ClientViewModel['healthLabel'] {
  if (score >= 70) return 'Healthy';
  if (score >= 40) return 'Warning';
  return 'Critical';
}

function getHealthColor(score: number): ClientViewModel['healthColor'] {
  if (score >= 70) return 'green';
  if (score >= 40) return 'yellow';
  return 'red';
}

function formatRelativeDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Never';

  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  return `${Math.floor(diffDays / 30)} months ago`;
}
