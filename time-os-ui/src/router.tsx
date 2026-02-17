/* eslint-disable react-refresh/only-export-components -- Router config exports router instance */
// Router configuration - route definitions only
// Page components are in src/pages/
import { useState } from 'react';
import { createRouter, createRoute, createRootRoute, Outlet, Link } from '@tanstack/react-router';
import { Snapshot, Issues, Team, TeamDetail, FixData, type ScopeSearch } from './pages';
import Inbox from './pages/Inbox';
import ClientIndex from './pages/ClientIndex';
import ClientDetailSpec from './pages/ClientDetailSpec';
import RecentlyActiveDrilldown from './pages/RecentlyActiveDrilldown';
import ColdClients from './pages/ColdClients';
import { ErrorBoundary } from './components/ErrorBoundary';

// Intelligence pages
import {
  CommandCenter,
  Briefing,
  Signals,
  Patterns,
  Proposals,
  ClientIntel,
  PersonIntel,
  ProjectIntel,
} from './intelligence/pages';

// Navigation items — Inbox is primary per spec §1
const NAV_ITEMS = [
  { to: '/', label: 'Inbox' }, // Control Room Inbox (spec §1)
  { to: '/intel', label: 'Intel' }, // Intelligence Command Center
  { to: '/clients', label: 'Clients' }, // Client Index (spec §2)
  { to: '/issues', label: 'Issues' },
  { to: '/team', label: 'Team' },
  { to: '/snapshot', label: 'Snapshot' },
  { to: '/fix-data', label: 'Fix' },
] as const;

// NavLink component — responsive touch targets
function NavLink({
  to,
  children,
  onClick,
}: {
  to: string;
  children: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className="px-3 py-2 min-h-[44px] flex items-center text-sm rounded-md hover:bg-slate-700 transition-colors whitespace-nowrap [&.active]:bg-slate-700 [&.active]:text-white"
    >
      {children}
    </Link>
  );
}

// Hamburger icon
function HamburgerIcon({ open }: { open: boolean }) {
  return (
    <svg
      className="w-6 h-6"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      {open ? (
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M6 18L18 6M6 6l12 12"
        />
      ) : (
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M4 6h16M4 12h16M4 18h16"
        />
      )}
    </svg>
  );
}

// Root layout with responsive navigation
function RootLayout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const closeMobileMenu = () => setMobileMenuOpen(false);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-200">
      <nav className="sticky top-0 z-50 bg-slate-800/95 backdrop-blur border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-14 sm:h-16">
            <Link to="/" className="font-semibold text-lg" onClick={closeMobileMenu}>
              Time OS
            </Link>

            {/* Desktop nav */}
            <div className="hidden sm:flex gap-1 sm:gap-2">
              {NAV_ITEMS.map((item) => (
                <NavLink key={item.to} to={item.to}>
                  {item.label}
                </NavLink>
              ))}
            </div>

            {/* Mobile hamburger button */}
            <button
              type="button"
              className="sm:hidden p-2 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md hover:bg-slate-700 transition-colors"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-expanded={mobileMenuOpen}
              aria-label="Toggle navigation"
            >
              <HamburgerIcon open={mobileMenuOpen} />
            </button>
          </div>
        </div>

        {/* Mobile nav menu */}
        {mobileMenuOpen && (
          <div className="sm:hidden border-t border-slate-700 bg-slate-800">
            <div className="px-4 py-2 space-y-1">
              {NAV_ITEMS.map((item) => (
                <NavLink key={item.to} to={item.to} onClick={closeMobileMenu}>
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        )}
      </nav>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
    </div>
  );
}

const rootRoute = createRootRoute({
  component: RootLayout,
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
    days: typeof search.days === 'number' ? search.days : 7,
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
  component: ClientIndex, // Spec §2 - Three swimlanes
});

const clientDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/clients/$clientId',
  component: ClientDetailSpec, // Spec §3 - 5 tabs
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

// Intelligence routes
const intelRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel',
  component: CommandCenter,
});

const intelBriefingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/briefing',
  component: Briefing,
});

const intelSignalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/signals',
  component: Signals,
});

const intelPatternsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/patterns',
  component: Patterns,
});

const intelProposalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/proposals',
  component: Proposals,
});

const intelClientRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/client/$clientId',
  component: ClientIntel,
});

const intelPersonRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/person/$personId',
  component: PersonIntel,
});

const intelProjectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/project/$projectId',
  component: ProjectIntel,
});

// Route tree
const routeTree = rootRoute.addChildren([
  indexRoute, // Inbox (/)
  snapshotRoute, // Snapshot (/snapshot)
  issuesRoute,
  clientsRoute,
  coldClientsRoute, // Must be before clientDetailRoute (more specific)
  recentlyActiveDrilldownRoute,
  clientDetailRoute,
  teamRoute,
  teamDetailRoute,
  fixDataRoute,
  // Intelligence routes
  intelRoute,
  intelBriefingRoute,
  intelSignalsRoute,
  intelPatternsRoute,
  intelProposalsRoute,
  intelClientRoute,
  intelPersonRoute,
  intelProjectRoute,
]);

// Router instance
export const router = createRouter({ routeTree });

// Type declarations for router
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
