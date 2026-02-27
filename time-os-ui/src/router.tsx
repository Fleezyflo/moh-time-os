/* eslint-disable react-refresh/only-export-components -- Router config exports router instance */
// Router configuration - route definitions only
// Page components are in src/pages/
import { createRouter, createRoute, createRootRoute, Outlet, Link } from '@tanstack/react-router';
import { lazy, Suspense, useState } from 'react';
import { ErrorBoundary, ProtectedRoute, PageSuspense } from './components';

// Lazy load page components for code splitting
const Inbox = lazy(() => import('./pages/Inbox'));
const Snapshot = lazy(() => import('./pages/Snapshot'));
const Issues = lazy(() => import('./pages/Issues'));
const ClientIndex = lazy(() => import('./pages/ClientIndex'));
const ClientDetailSpec = lazy(() => import('./pages/ClientDetailSpec'));
const RecentlyActiveDrilldown = lazy(() => import('./pages/RecentlyActiveDrilldown'));
const ColdClients = lazy(() => import('./pages/ColdClients'));
const Team = lazy(() => import('./pages/Team'));
const TeamDetail = lazy(() => import('./pages/TeamDetail'));
const FixData = lazy(() => import('./pages/FixData'));
const Portfolio = lazy(() => import('./pages/Portfolio'));
const Operations = lazy(() => import('./pages/Operations'));

// Intelligence pages
const CommandCenter = lazy(() => import('./intelligence/pages/CommandCenter'));
const Briefing = lazy(() => import('./intelligence/pages/Briefing'));
const Signals = lazy(() => import('./intelligence/pages/Signals'));
const Patterns = lazy(() => import('./intelligence/pages/Patterns'));
const Proposals = lazy(() => import('./intelligence/pages/Proposals'));
const ClientIntel = lazy(() => import('./intelligence/pages/ClientIntel'));
const PersonIntel = lazy(() => import('./intelligence/pages/PersonIntel'));
const ProjectIntel = lazy(() => import('./intelligence/pages/ProjectIntel'));

// Navigation items — Inbox is primary per spec §1
const NAV_ITEMS = [
  { to: '/', label: 'Inbox' }, // Control Room Inbox (spec §1)
  { to: '/portfolio', label: 'Portfolio' }, // Portfolio overview (Phase 3.1)
  { to: '/intel', label: 'Intel' }, // Intelligence Command Center
  { to: '/clients', label: 'Clients' }, // Client Index (spec §2)
  { to: '/issues', label: 'Issues' },
  { to: '/team', label: 'Team' },
  { to: '/ops', label: 'Ops' },
  { to: '/snapshot', label: 'Snapshot' },
  { to: '/fix-data', label: 'Fix' },
] as const;

// NavLink component
function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className="px-3 py-2 text-sm rounded-md hover:bg-[var(--grey)] transition-colors whitespace-nowrap [&.active]:bg-[var(--grey)] [&.active]:text-white min-h-[44px] flex items-center"
    >
      {children}
    </Link>
  );
}

// Root layout with responsive navigation
function RootLayout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-[var(--black)] text-[var(--white)]">
        {/* Skip to content link for accessibility */}
        <a
          href="#main-content"
          className="absolute left-0 top-0 -translate-y-full focus:translate-y-0 focus:z-50 bg-blue-600 text-white px-4 py-2 rounded transition-transform"
        >
          Skip to main content
        </a>

        {/* Navigation Bar */}
        <nav
          role="navigation"
          aria-label="Main navigation"
          className="sticky top-0 z-50 bg-[var(--grey-dim)]/95 backdrop-blur border-b border-[var(--grey)]"
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6">
            <div className="flex items-center justify-between h-14 sm:h-16">
              <Link to="/" className="font-semibold text-lg">
                Time OS
              </Link>

              {/* Desktop Navigation */}
              <div className="hidden md:flex gap-1 sm:gap-2">
                {NAV_ITEMS.map((item) => (
                  <NavLink key={item.to} to={item.to}>
                    {item.label}
                  </NavLink>
                ))}
              </div>

              {/* Mobile Menu Toggle */}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="md:hidden p-2 hover:bg-[var(--grey)] rounded transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                aria-label="Toggle navigation menu"
                aria-expanded={mobileMenuOpen}
                aria-controls="mobile-nav"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d={mobileMenuOpen ? 'M6 18L18 6M6 6l12 12' : 'M4 6h16M4 12h16M4 18h16'}
                  />
                </svg>
              </button>
            </div>

            {/* Mobile Navigation Menu */}
            {mobileMenuOpen && (
              <div id="mobile-nav" className="md:hidden pb-4 space-y-1">
                {NAV_ITEMS.map((item) => (
                  <Link
                    key={item.to}
                    to={item.to}
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 text-base rounded-md hover:bg-[var(--grey)] transition-colors [&.active]:bg-[var(--grey)] [&.active]:text-white"
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </nav>

        {/* Main Content */}
        <main id="main-content" role="main" className="max-w-7xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
          <ErrorBoundary>
            <Suspense
              fallback={
                <PageSuspense>
                  <div />
                </PageSuspense>
              }
            >
              <Outlet />
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </ProtectedRoute>
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
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Inbox />
    </Suspense>
  ),
});

// Snapshot moved to /snapshot
const snapshotRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/snapshot',
  validateSearch: (search: Record<string, unknown>) => ({
    scope: typeof search.scope === 'string' ? search.scope : undefined,
    days: typeof search.days === 'number' ? search.days : 7,
  }),
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Snapshot />
    </Suspense>
  ),
});

const issuesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/issues',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Issues />
    </Suspense>
  ),
});

const clientsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/clients',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <ClientIndex />
    </Suspense>
  ),
});

const clientDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/clients/$clientId',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <ClientDetailSpec />
    </Suspense>
  ),
});

// Recently Active drilldown (§4)
const recentlyActiveDrilldownRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/clients/$clientId/recently-active',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <RecentlyActiveDrilldown />
    </Suspense>
  ),
});

// Cold Clients page (§5)
const coldClientsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/clients/cold',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <ColdClients />
    </Suspense>
  ),
});

const teamRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/team',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Team />
    </Suspense>
  ),
});

const teamDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/team/$id',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <TeamDetail />
    </Suspense>
  ),
});

const fixDataRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/fix-data',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <FixData />
    </Suspense>
  ),
});

// Portfolio page (Phase 3.1)
const portfolioRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/portfolio',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Portfolio />
    </Suspense>
  ),
});

// Operations page (Phase 3.5)
const opsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/ops',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Operations />
    </Suspense>
  ),
});

// Intelligence routes
const intelRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <CommandCenter />
    </Suspense>
  ),
});

const intelBriefingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/briefing',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Briefing />
    </Suspense>
  ),
});

const intelSignalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/signals',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Signals />
    </Suspense>
  ),
});

const intelPatternsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/patterns',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Patterns />
    </Suspense>
  ),
});

const intelProposalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/proposals',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Proposals />
    </Suspense>
  ),
});

const intelClientRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/client/$clientId',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <ClientIntel />
    </Suspense>
  ),
});

const intelPersonRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/person/$personId',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <PersonIntel />
    </Suspense>
  ),
});

const intelProjectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/project/$projectId',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <ProjectIntel />
    </Suspense>
  ),
});

// Route tree
const routeTree = rootRoute.addChildren([
  indexRoute, // Inbox (/)
  portfolioRoute, // Portfolio (/portfolio)
  snapshotRoute, // Snapshot (/snapshot)
  issuesRoute,
  clientsRoute,
  coldClientsRoute, // Must be before clientDetailRoute (more specific)
  recentlyActiveDrilldownRoute,
  clientDetailRoute,
  teamRoute,
  teamDetailRoute,
  fixDataRoute,
  opsRoute, // Operations (/ops)
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
