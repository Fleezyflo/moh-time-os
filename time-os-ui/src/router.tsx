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
import { NotificationBadge } from './components/notifications/NotificationBadge';
import { SearchOverlay } from './components/governance/SearchOverlay';

// Lazy load page components for code splitting
const Inbox = lazy(() => import('./pages/Inbox'));
const Issues = lazy(() => import('./pages/Issues'));
const ClientIndex = lazy(() => import('./pages/ClientIndex'));
const ClientDetailSpec = lazy(() => import('./pages/ClientDetailSpec'));
const Team = lazy(() => import('./pages/Team'));
const TeamDetail = lazy(() => import('./pages/TeamDetail'));
const Portfolio = lazy(() => import('./pages/Portfolio'));
const Operations = lazy(() => import('./pages/Operations'));
const TaskList = lazy(() => import('./pages/TaskList'));
const TaskDetail = lazy(() => import('./pages/TaskDetail'));
const Priorities = lazy(() => import('./pages/Priorities'));
const Schedule = lazy(() => import('./pages/Schedule'));
const Capacity = lazy(() => import('./pages/Capacity'));
const Commitments = lazy(() => import('./pages/Commitments'));
const NotificationsPage = lazy(() => import('./pages/Notifications'));
const DigestPage = lazy(() => import('./pages/Digest'));
const ProjectEnrollment = lazy(() => import('./pages/ProjectEnrollment'));
const GovernancePage = lazy(() => import('./pages/Governance'));
const ApprovalsPage = lazy(() => import('./pages/Approvals'));
const DataQualityPage = lazy(() => import('./pages/DataQuality'));
const CommandCenter = lazy(() => import('./pages/CommandCenter'));
const NotFound = lazy(() => import('./pages/NotFound'));

// Intelligence pages (kept: signals, patterns, client/person/project intel)
const Signals = lazy(() => import('./intelligence/pages/Signals'));
const Patterns = lazy(() => import('./intelligence/pages/Patterns'));
const ClientIntel = lazy(() => import('./intelligence/pages/ClientIntel'));
const PersonIntel = lazy(() => import('./intelligence/pages/PersonIntel'));
const ProjectIntel = lazy(() => import('./intelligence/pages/ProjectIntel'));

// Navigation items — Phase 11 updated nav
const NAV_ITEMS: Array<{ to: string; label: string; badge?: boolean }> = [
  { to: '/command', label: 'Command' },
  { to: '/', label: 'Inbox' },
  { to: '/portfolio', label: 'Portfolio' },
  { to: '/tasks', label: 'Tasks' },
  { to: '/priorities', label: 'Priorities' },
  { to: '/schedule', label: 'Schedule' },
  { to: '/capacity', label: 'Capacity' },
  { to: '/commitments', label: 'Commitments' },
  { to: '/notifications', label: 'Notifications', badge: true },
  { to: '/digest', label: 'Digest' },
  { to: '/clients', label: 'Clients' },
  { to: '/issues', label: 'Issues' },
  { to: '/team', label: 'Team' },
  { to: '/projects/enrollment', label: 'Enrollment' },
  { to: '/intel/signals', label: 'Intel' },
  { to: '/ops', label: 'Ops' },
  { to: '/admin/governance', label: 'Admin' },
];

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
                    {item.badge && (
                      <span className="ml-1">
                        <NotificationBadge />
                      </span>
                    )}
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
                    className="flex items-center gap-2 px-3 py-2 text-base rounded-md hover:bg-[var(--grey)] transition-colors [&.active]:bg-[var(--grey)] [&.active]:text-white"
                  >
                    {item.label}
                    {item.badge && <NotificationBadge />}
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

        {/* Global search overlay (Cmd/Ctrl+K) */}
        <SearchOverlay />
      </div>
    </ProtectedRoute>
  );
}

const rootRoute = createRootRoute({
  component: RootLayout,
});

// Route definitions

// Inbox is the primary page (Control Room per spec §1)
const commandCenterRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/command',
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

// Redirect: /fix-data → /ops (accessible via Operations "Data Quality" tab)
const fixDataRedirectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/fix-data',
  component: () => <Navigate to="/ops" />,
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

// Task Management routes (Phase 6)
const tasksRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/tasks',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <TaskList />
    </Suspense>
  ),
});

const taskDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/tasks/$taskId',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <TaskDetail />
    </Suspense>
  ),
});

// Priorities Workspace route (Phase 7)
const prioritiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/priorities',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Priorities />
    </Suspense>
  ),
});

// Schedule page (Phase 8)
const scheduleRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/schedule',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Schedule />
    </Suspense>
  ),
});

// Capacity page (Phase 8)
const capacityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/capacity',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Capacity />
    </Suspense>
  ),
});

// Commitments page (Phase 9)
const commitmentsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/commitments',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <Commitments />
    </Suspense>
  ),
});

// Notifications page (Phase 10)
const notificationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/notifications',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <NotificationsPage />
    </Suspense>
  ),
});

// Digest page (Phase 10)
const digestRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/digest',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <DigestPage />
    </Suspense>
  ),
});

// Project Enrollment page (Phase 12)
const enrollmentRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/projects/enrollment',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <ProjectEnrollment />
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

// Admin routes (Phase 11)
const governanceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin/governance',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <GovernancePage />
    </Suspense>
  ),
});

const approvalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin/approvals',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <ApprovalsPage />
    </Suspense>
  ),
});

const dataQualityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin/data-quality',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <DataQualityPage />
    </Suspense>
  ),
});

// 404 catch-all route (Phase D)
const notFoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '*',
  component: () => (
    <Suspense
      fallback={
        <PageSuspense>
          <div />
        </PageSuspense>
      }
    >
      <NotFound />
    </Suspense>
  ),
});

// Route tree — Phase 4 consolidated
const routeTree = rootRoute.addChildren([
  commandCenterRoute, // Command Center (/command)
  indexRoute, // Inbox (/)
  portfolioRoute, // Portfolio (/portfolio)
  issuesRoute,
  clientsRoute,
  clientDetailRoute,
  teamRoute,
  teamDetailRoute,
  fixDataRedirectRoute, // /fix-data → /ops
  opsRoute, // Operations (/ops)
  tasksRoute, // Tasks (/tasks) — Phase 6
  taskDetailRoute, // Task detail (/tasks/:taskId) — Phase 6
  prioritiesRoute, // Priorities (/priorities) — Phase 7
  scheduleRoute, // Schedule (/schedule) — Phase 8
  capacityRoute, // Capacity (/capacity) — Phase 8
  commitmentsRoute, // Commitments (/commitments) — Phase 9
  notificationsRoute, // Notifications (/notifications) — Phase 10
  digestRoute, // Digest (/digest) — Phase 10
  enrollmentRoute, // Project Enrollment (/projects/enrollment) — Phase 12
  governanceRoute, // Governance (/admin/governance) — Phase 11
  approvalsRoute, // Approvals (/admin/approvals) — Phase 11
  dataQualityRoute, // Data Quality (/admin/data-quality) — Phase 11
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
  // 404 catch-all (must be last)
  notFoundRoute,
]);

// Router instance
export const router = createRouter({ routeTree });

// Type declarations for router
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
