/* eslint-disable react-refresh/only-export-components -- Router config exports router instance */
// Router configuration - route definitions only
// Page components are in src/pages/
import {
  createRouter,
  createRoute,
  createRootRoute,
  Outlet,
  Link,
  Navigate,
} from '@tanstack/react-router';
import { lazy, Suspense, useState } from 'react';
import { ErrorBoundary, ProtectedRoute, PageSuspense } from './components';

// Lazy load page components for code splitting
const Inbox = lazy(() => import('./pages/Inbox'));
const Issues = lazy(() => import('./pages/Issues'));
const ClientIndex = lazy(() => import('./pages/ClientIndex'));
const ClientDetailSpec = lazy(() => import('./pages/ClientDetailSpec'));
const Team = lazy(() => import('./pages/Team'));
const TeamDetail = lazy(() => import('./pages/TeamDetail'));
const FixData = lazy(() => import('./pages/FixData'));
const Portfolio = lazy(() => import('./pages/Portfolio'));
const Operations = lazy(() => import('./pages/Operations'));

// Intelligence pages (kept: signals, patterns, client/person/project intel)
const Signals = lazy(() => import('./intelligence/pages/Signals'));
const Patterns = lazy(() => import('./intelligence/pages/Patterns'));
const ClientIntel = lazy(() => import('./intelligence/pages/ClientIntel'));
const PersonIntel = lazy(() => import('./intelligence/pages/PersonIntel'));
const ProjectIntel = lazy(() => import('./intelligence/pages/ProjectIntel'));

// Navigation items — Phase 4 consolidated nav
const NAV_ITEMS = [
  { to: '/', label: 'Inbox' },
  { to: '/portfolio', label: 'Portfolio' },
  { to: '/clients', label: 'Clients' },
  { to: '/issues', label: 'Issues' },
  { to: '/team', label: 'Team' },
  { to: '/intel/signals', label: 'Intel' },
  { to: '/ops', label: 'Ops' },
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

// Redirect: /snapshot → /portfolio (Phase 4)
const snapshotRedirectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/snapshot',
  component: () => <Navigate to="/portfolio" />,
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

// Routes removed in Phase 4: /clients/cold, /clients/:id/recently-active
// Cold client data is accessible via ClientIndex filters.
// Recently-active data is accessible via ClientDetail tabs.

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

// Intelligence routes — redirects for removed pages (Phase 4)
const intelRedirectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel',
  component: () => <Navigate to="/portfolio" />,
});

const intelBriefingRedirectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/briefing',
  component: () => <Navigate to="/portfolio" />,
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

const intelProposalsRedirectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/intel/proposals',
  component: () => <Navigate to="/" />,
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

// Route tree — Phase 4 consolidated
const routeTree = rootRoute.addChildren([
  indexRoute, // Inbox (/)
  portfolioRoute, // Portfolio (/portfolio)
  issuesRoute,
  clientsRoute,
  clientDetailRoute,
  teamRoute,
  teamDetailRoute,
  fixDataRoute, // Still accessible via direct URL, removed from nav
  opsRoute, // Operations (/ops)
  // Intelligence routes (kept)
  intelSignalsRoute,
  intelPatternsRoute,
  intelClientRoute,
  intelPersonRoute,
  intelProjectRoute,
  // Redirects (Phase 4 — old URLs → new destinations)
  snapshotRedirectRoute, // /snapshot → /portfolio
  intelRedirectRoute, // /intel → /portfolio
  intelBriefingRedirectRoute, // /intel/briefing → /portfolio
  intelProposalsRedirectRoute, // /intel/proposals → /
]);

// Router instance
export const router = createRouter({ routeTree });

// Type declarations for router
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
