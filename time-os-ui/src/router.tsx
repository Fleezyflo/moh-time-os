// Router configuration - route definitions only
// Page components are in src/pages/
import {
  createRouter,
  createRoute,
  createRootRoute,
  Outlet,
  Link,
} from '@tanstack/react-router'
import { Snapshot, Issues, Team, TeamDetail, FixData, type ScopeSearch } from './pages'
import Inbox from './pages/Inbox'
import ClientIndex from './pages/ClientIndex'
import ClientDetailSpec from './pages/ClientDetailSpec'
import RecentlyActiveDrilldown from './pages/RecentlyActiveDrilldown'
import ColdClients from './pages/ColdClients'

// Navigation items — Inbox is primary per spec §1
const NAV_ITEMS = [
  { to: '/', label: 'Inbox' },           // Control Room Inbox (spec §1)
  { to: '/clients', label: 'Clients' },  // Client Index (spec §2)
  { to: '/issues', label: 'Issues' },
  { to: '/team', label: 'Team' },
  { to: '/snapshot', label: 'Snapshot' },
  { to: '/fix-data', label: 'Fix' },
] as const;

// NavLink component
function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className="px-3 py-2 text-sm rounded-md hover:bg-slate-700 transition-colors whitespace-nowrap [&.active]:bg-slate-700 [&.active]:text-white"
    >
      {children}
    </Link>
  );
}

// Root layout with navigation
const rootRoute = createRootRoute({
  component: () => (
    <div className="min-h-screen bg-slate-900 text-slate-200">
      <nav className="sticky top-0 z-50 bg-slate-800/95 backdrop-blur border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-14 sm:h-16">
            <Link to="/" className="font-semibold text-lg">Time OS</Link>
            <div className="flex gap-1 sm:gap-2 overflow-x-auto">
              {NAV_ITEMS.map(item => (
                <NavLink key={item.to} to={item.to}>{item.label}</NavLink>
              ))}
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
        <Outlet />
      </main>
    </div>
  ),
});

// Route definitions

// Inbox is the primary page (Control Room per spec §1)
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: Inbox,
});

// Snapshot moved to /snapshot
const snapshotRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/snapshot',
  validateSearch: (search: Record<string, unknown>): ScopeSearch => ({
    scope: typeof search.scope === 'string' ? search.scope : undefined,
    days: typeof search.days === 'number' ? search.days : 7
  }),
  component: Snapshot,
});

const issuesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/issues',
  component: Issues,
});

const clientsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/clients',
  component: ClientIndex,  // Spec §2 - Three swimlanes
});

const clientDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/clients/$clientId',
  component: ClientDetailSpec,  // Spec §3 - 5 tabs
});

// Recently Active drilldown (§4)
const recentlyActiveDrilldownRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/clients/$clientId/recently-active',
  component: RecentlyActiveDrilldown,
});

// Cold Clients page (§5)
const coldClientsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/clients/cold',
  component: ColdClients,
});

const teamRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/team',
  component: Team,
});

const teamDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/team/$id',
  component: TeamDetail,
});

const fixDataRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/fix-data',
  component: FixData,
});

// Route tree
const routeTree = rootRoute.addChildren([
  indexRoute,       // Inbox (/)
  snapshotRoute,    // Snapshot (/snapshot)
  issuesRoute,
  clientsRoute,
  coldClientsRoute,  // Must be before clientDetailRoute (more specific)
  recentlyActiveDrilldownRoute,
  clientDetailRoute,
  teamRoute,
  teamDetailRoute,
  fixDataRoute,
]);

// Router instance
export const router = createRouter({ routeTree });

// Type declarations for router
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
