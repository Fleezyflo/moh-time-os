/**
 * EntityLink — Clickable entity reference with type indicator
 */

import { Link } from '@tanstack/react-router';

interface Entity {
  type: string;
  id: string;
  name: string;
}

interface EntityLinkProps {
  entity: Entity;
  showType?: boolean;
}

const ENTITY_ICONS: Record<string, string> = {
  client: '🏢',
  project: '📁',
  person: '👤',
  portfolio: '📊',
};

const ENTITY_ROUTES: Record<string, string> = {
  client: '/clients',
  project: '/clients', // Projects are under clients
  person: '/team',
  portfolio: '/intel',
};

export function EntityLink({ entity, showType = true }: EntityLinkProps) {
  const icon = ENTITY_ICONS[entity.type] || '📌';
  const baseRoute = ENTITY_ROUTES[entity.type] || '/';
  
  // Build the route based on entity type
  let to = baseRoute;
  if (entity.type === 'client') {
    to = `/clients/${entity.id}`;
  } else if (entity.type === 'person') {
    to = `/team/${entity.id}`;
  } else if (entity.type === 'portfolio') {
    to = '/intel';
  }
  
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1.5 text-sm hover:text-white transition-colors group"
    >
      <span>{icon}</span>
      <span className="group-hover:underline">{entity.name}</span>
      {showType && (
        <span className="text-xs text-slate-500">({entity.type})</span>
      )}
    </Link>
  );
}

// Compact version for lists
export function EntityBadge({ entity }: { entity: Entity }) {
  const icon = ENTITY_ICONS[entity.type] || '📌';
  
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-slate-700 px-2 py-0.5 rounded">
      <span>{icon}</span>
      <span>{entity.name}</span>
    </span>
  );
}

// List of entities
export function EntityList({ entities, maxItems = 5 }: { entities: Entity[]; maxItems?: number }) {
  const items = entities.slice(0, maxItems);
  const hasMore = entities.length > maxItems;
  
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((entity, i) => (
        <EntityBadge key={`${entity.type}-${entity.id}-${i}`} entity={entity} />
      ))}
      {hasMore && (
        <span className="text-xs text-slate-500 self-center">
          +{entities.length - maxItems} more
        </span>
      )}
    </div>
  );
}

export default EntityLink;
