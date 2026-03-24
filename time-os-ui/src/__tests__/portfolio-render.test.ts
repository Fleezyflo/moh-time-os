// @vitest-environment jsdom
/**
 * Portfolio progressive rendering — component behavior tests.
 *
 * Mounts the real Portfolio component with mocked hooks and child components,
 * then asserts visible DOM output under realistic partial-load / partial-failure
 * / empty-data scenarios.
 *
 * Proves:
 *  1. Progressive rendering — content appears while some hooks are still loading
 *  2. Partial failure — errored hooks show error banner, successful sections render
 *  3. Empty-state rendering — null/empty data shows visible placeholder, not blank
 *  4. No global loading dependency — page never requires all hooks to resolve first
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';

// ---------------------------------------------------------------------------
// Hook mock factories (vi.hoisted so they exist before vi.mock runs)
// ---------------------------------------------------------------------------
const {
  mockPortfolioScore,
  mockCriticalItems,
  mockPortfolioIntel,
  mockPortfolioOverview,
  mockPortfolioRisks,
  mockFinancialDetail,
  mockAsanaContext,
} = vi.hoisted(() => ({
  mockPortfolioScore: vi.fn(),
  mockCriticalItems: vi.fn(),
  mockPortfolioIntel: vi.fn(),
  mockPortfolioOverview: vi.fn(),
  mockPortfolioRisks: vi.fn(),
  mockFinancialDetail: vi.fn(),
  mockAsanaContext: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Default return shapes — reused across tests
// ---------------------------------------------------------------------------
function hookLoading() {
  return {
    data: null,
    loading: true,
    error: null,
    hasLoaded: false,
    errorCode: undefined,
    computedAt: null,
    refetch: vi.fn(),
  };
}
function hookError(msg: string) {
  return {
    data: null,
    loading: false,
    error: new Error(msg),
    hasLoaded: false,
    errorCode: undefined,
    computedAt: null,
    refetch: vi.fn(),
  };
}
function hookSuccess<T>(data: T) {
  return {
    data,
    loading: false,
    error: null,
    hasLoaded: true,
    errorCode: undefined,
    computedAt: '2025-01-01T00:00:00Z',
    refetch: vi.fn(),
  };
}
// useFetch-based hooks return the same shape minus hasLoaded/errorCode/computedAt
function fetchLoading() {
  return { data: null, loading: true, error: null, refetch: vi.fn(), resetError: vi.fn() };
}
function fetchSuccess<T>(data: T) {
  return { data, loading: false, error: null, refetch: vi.fn(), resetError: vi.fn() };
}
// ---------------------------------------------------------------------------
// Mock ALL modules imported by Portfolio.tsx
// ---------------------------------------------------------------------------

// Intelligence hooks
vi.mock('../intelligence/hooks', () => ({
  usePortfolioScore: () => mockPortfolioScore(),
  useCriticalItems: () => mockCriticalItems(),
  usePortfolioIntelligence: () => mockPortfolioIntel(),
}));

// Lib hooks
vi.mock('../lib/hooks', () => ({
  usePortfolioOverview: () => mockPortfolioOverview(),
  usePortfolioRisks: () => mockPortfolioRisks(),
  useFinancialDetail: () => mockFinancialDetail(),
  useAsanaPortfolioContext: () => mockAsanaContext(),
}));

// Lib API namespace (imported as `* as api` for type annotations in Portfolio)
vi.mock('../lib/api', () => ({}));

// Layout components — render children with identifiable wrappers
vi.mock('../components/layout/PageLayout', () => ({
  PageLayout: (props: { title: string; children: ReactNode }) =>
    createElement('div', { 'data-testid': 'page-layout' }, props.children),
}));
vi.mock('../components/layout/SummaryGrid', () => ({
  SummaryGrid: (props: { children: ReactNode }) =>
    createElement('div', { 'data-testid': 'summary-grid' }, props.children),
}));
vi.mock('../components/layout/MetricCard', () => ({
  MetricCard: (props: { label: string; value: unknown }) =>
    createElement('span', { 'data-testid': `metric-${props.label}` }, String(props.value)),
}));

// Domain components — render a single identifiable element
vi.mock('../components/portfolio/CriticalItemList', () => ({
  CriticalItemList: () =>
    createElement('div', { 'data-testid': 'critical-items' }, 'CriticalItemList'),
}));
vi.mock('../components/portfolio/ClientDistributionChart', () => ({
  ClientDistributionChart: () =>
    createElement('div', { 'data-testid': 'client-distribution' }, 'ClientDistributionChart'),
}));
vi.mock('../components/portfolio/RiskList', () => ({
  RiskList: () => createElement('div', { 'data-testid': 'risk-list' }, 'RiskList'),
}));
vi.mock('../components/portfolio/ARAgingSummary', () => ({
  ARAgingSummary: () => createElement('div', { 'data-testid': 'ar-aging' }, 'ARAgingSummary'),
}));
vi.mock('../intelligence/components/Scorecard', () => ({
  Scorecard: () => createElement('div', { 'data-testid': 'scorecard' }, 'Scorecard'),
}));

// ---------------------------------------------------------------------------
// Import the component under test AFTER mocks are registered
// ---------------------------------------------------------------------------
const { Portfolio } = await import('../pages/Portfolio');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function renderPortfolio() {
  return render(createElement(Portfolio));
}

// Sample data fixtures
const SCORE_DATA = {
  composite_score: 72,
  dimensions: {},
  scored_at: '2025-01-01',
  data_completeness: 1,
  entity_type: 'portfolio',
  entity_id: 'p',
  entity_name: 'Portfolio',
};
const CRITICAL_ITEMS = [
  {
    id: '1',
    headline: 'Overdue invoice',
    severity: 'high',
    entity_type: 'client',
    entity_id: 'c1',
  },
];
const OVERVIEW_DATA = {
  by_tier: {},
  by_health: {},
  totals: { total_ar: 1000, total_annual_value: 5000 },
  overdue_ar: { count: 2, total: 500 },
};
const RISKS_DATA = {
  clients: [{ client_id: 'c1', client_name: 'Acme', health_score: 30 }],
  threshold: 50,
};
const INTEL_DATA = {
  signal_summary: { total_active: 3 },
  structural_patterns: [],
  top_proposals: [],
};

// ---------------------------------------------------------------------------
// Default: everything loading
// ---------------------------------------------------------------------------
beforeEach(() => {
  mockPortfolioScore.mockReturnValue(hookLoading());
  mockCriticalItems.mockReturnValue(hookLoading());
  mockPortfolioIntel.mockReturnValue(hookLoading());
  mockPortfolioOverview.mockReturnValue(fetchLoading());
  mockPortfolioRisks.mockReturnValue(fetchLoading());
  mockFinancialDetail.mockReturnValue(fetchLoading());
  mockAsanaContext.mockReturnValue(fetchLoading());
});

// ============================= TEST SUITES =================================

describe('Portfolio — progressive rendering', () => {
  it('renders metric cards immediately even when all hooks are loading', () => {
    renderPortfolio();
    // MetricCards use '--' fallback when data is null
    expect(screen.getByTestId('metric-Health Score').textContent).toBe('--');
    expect(screen.getByTestId('metric-Critical Items').textContent).toBe('--');
    expect(screen.getByTestId('metric-Active Signals').textContent).toBe('--');
    expect(screen.getByTestId('metric-Structural Patterns').textContent).toBe('--');
  });

  it('renders per-section loading placeholders while hooks load', () => {
    renderPortfolio();
    // Each section with a loading guard should show "Loading..."
    const loadingEls = screen.getAllByText('Loading...');
    expect(loadingEls.length).toBeGreaterThanOrEqual(3);
  });

  it('renders Portfolio Health with data while other hooks are still loading', () => {
    mockPortfolioScore.mockReturnValue(hookSuccess(SCORE_DATA));
    // criticalItems, portfolioIntel, portfolioOverview remain loading
    renderPortfolio();

    // Scorecard section should be visible
    expect(screen.getByTestId('scorecard')).toBeTruthy();
    expect(screen.getByText('Portfolio Health')).toBeTruthy();

    // Other sections should still show loading placeholders
    const loadingEls = screen.getAllByText('Loading...');
    expect(loadingEls.length).toBeGreaterThanOrEqual(2);
  });

  it('renders Client Distribution with data while intelligence hooks are still loading', () => {
    mockPortfolioOverview.mockReturnValue(fetchSuccess(OVERVIEW_DATA));
    // intelligence hooks remain loading
    renderPortfolio();

    expect(screen.getByTestId('client-distribution')).toBeTruthy();
    expect(screen.getByTestId('ar-aging')).toBeTruthy();
  });

  it('renders Critical Items while score and overview are still loading', () => {
    mockCriticalItems.mockReturnValue(hookSuccess(CRITICAL_ITEMS));
    renderPortfolio();

    expect(screen.getByTestId('critical-items')).toBeTruthy();
    // Score and overview should still be loading
    expect(screen.getAllByText('Loading...').length).toBeGreaterThanOrEqual(2);
  });
});

describe('Portfolio — partial failure', () => {
  it('shows error banner when one hook errors, while successful sections still render', () => {
    mockPortfolioScore.mockReturnValue(hookError('Score endpoint down'));
    mockCriticalItems.mockReturnValue(hookSuccess(CRITICAL_ITEMS));
    mockPortfolioOverview.mockReturnValue(fetchSuccess(OVERVIEW_DATA));
    mockPortfolioIntel.mockReturnValue(hookSuccess(INTEL_DATA));
    mockPortfolioRisks.mockReturnValue(fetchSuccess(RISKS_DATA));
    mockFinancialDetail.mockReturnValue(fetchSuccess(null));
    mockAsanaContext.mockReturnValue(fetchSuccess(null));

    renderPortfolio();

    // Error banner visible
    expect(screen.getByText('Failed to load some portfolio data')).toBeTruthy();
    expect(screen.getByText('Score endpoint down')).toBeTruthy();

    // Successful sections still render
    expect(screen.getByTestId('critical-items')).toBeTruthy();
    expect(screen.getByTestId('client-distribution')).toBeTruthy();
    expect(screen.getByTestId('risk-list')).toBeTruthy();
  });

  it('shows error banner but does not blank the entire page', () => {
    mockPortfolioIntel.mockReturnValue(hookError('Intel timeout'));
    mockPortfolioScore.mockReturnValue(hookSuccess(SCORE_DATA));
    mockCriticalItems.mockReturnValue(hookSuccess([]));
    mockPortfolioOverview.mockReturnValue(fetchSuccess(OVERVIEW_DATA));
    mockPortfolioRisks.mockReturnValue(fetchSuccess(RISKS_DATA));
    mockFinancialDetail.mockReturnValue(fetchSuccess(null));
    mockAsanaContext.mockReturnValue(fetchSuccess(null));

    renderPortfolio();

    // Error banner for intel
    expect(screen.getByText('Intel timeout')).toBeTruthy();

    // Other sections still render
    expect(screen.getByTestId('scorecard')).toBeTruthy();
    expect(screen.getByTestId('client-distribution')).toBeTruthy();
  });

  it('Retry button is present in error banner', () => {
    mockPortfolioScore.mockReturnValue(hookError('fail'));
    renderPortfolio();

    expect(screen.getByText('Retry')).toBeTruthy();
  });
});

describe('Portfolio — empty-state rendering', () => {
  it('shows "No score data available." when score hook returns null', () => {
    mockPortfolioScore.mockReturnValue(hookSuccess(null));
    renderPortfolio();

    expect(screen.getByText('No score data available.')).toBeTruthy();
  });

  it('shows "No client data available." when overview hook returns null', () => {
    mockPortfolioOverview.mockReturnValue(fetchSuccess(null));
    renderPortfolio();

    expect(screen.getByText('No client data available.')).toBeTruthy();
  });

  it('does not render Top Risks section when critical items is empty array', () => {
    mockCriticalItems.mockReturnValue(hookSuccess([]));
    renderPortfolio();

    // CriticalItemList should NOT be in the document
    expect(screen.queryByTestId('critical-items')).toBeNull();
    // And there should be no "Top Risks" heading (it only appears when loading or with data)
    // When not loading AND empty data, the section returns null
    expect(screen.queryByText('Top Risks')).toBeNull();
  });

  it('shows empty-state messages instead of blank space', () => {
    // All hooks resolved, but with null/empty data
    mockPortfolioScore.mockReturnValue(hookSuccess(null));
    mockCriticalItems.mockReturnValue(hookSuccess([]));
    mockPortfolioIntel.mockReturnValue(hookSuccess(null));
    mockPortfolioOverview.mockReturnValue(fetchSuccess(null));
    mockPortfolioRisks.mockReturnValue(fetchSuccess({ clients: [], threshold: 50 }));
    mockFinancialDetail.mockReturnValue(fetchSuccess(null));
    mockAsanaContext.mockReturnValue(fetchSuccess(null));

    renderPortfolio();

    // Key sections show their empty state
    expect(screen.getByText('No score data available.')).toBeTruthy();
    expect(screen.getByText('No client data available.')).toBeTruthy();
    // Page layout rendered — not blank
    expect(screen.getByTestId('page-layout')).toBeTruthy();
    expect(screen.getByTestId('summary-grid')).toBeTruthy();
  });
});

describe('Portfolio — no global loading dependency', () => {
  it('page layout and summary grid render even when ALL hooks are loading', () => {
    // Default beforeEach: everything loading
    renderPortfolio();

    expect(screen.getByTestId('page-layout')).toBeTruthy();
    expect(screen.getByTestId('summary-grid')).toBeTruthy();
    // Metric cards show '--' fallbacks
    expect(screen.getByTestId('metric-Health Score').textContent).toBe('--');
  });

  it('successful section renders even if 3 of 4 primary hooks are still loading', () => {
    // Only overview resolves
    mockPortfolioOverview.mockReturnValue(fetchSuccess(OVERVIEW_DATA));

    renderPortfolio();

    // Client Distribution and AR Aging visible
    expect(screen.getByTestId('client-distribution')).toBeTruthy();
    expect(screen.getByTestId('ar-aging')).toBeTruthy();

    // Score and critical items still loading
    expect(screen.getAllByText('Loading...').length).toBeGreaterThanOrEqual(2);
  });

  it('does NOT have a combined loading gate that hides all content', () => {
    // One hook loading, others succeeded
    mockPortfolioScore.mockReturnValue(hookLoading());
    mockCriticalItems.mockReturnValue(hookSuccess(CRITICAL_ITEMS));
    mockPortfolioOverview.mockReturnValue(fetchSuccess(OVERVIEW_DATA));
    mockPortfolioIntel.mockReturnValue(hookSuccess(INTEL_DATA));
    mockPortfolioRisks.mockReturnValue(fetchSuccess(RISKS_DATA));
    mockFinancialDetail.mockReturnValue(fetchSuccess(null));
    mockAsanaContext.mockReturnValue(fetchSuccess(null));

    renderPortfolio();

    // If a global gate existed, ALL content would be hidden because score is loading.
    // Prove it is NOT hidden:
    expect(screen.getByTestId('critical-items')).toBeTruthy();
    expect(screen.getByTestId('client-distribution')).toBeTruthy();
    expect(screen.getByTestId('risk-list')).toBeTruthy();

    // Score section should show its own loading placeholder
    const scoreSection = screen.getAllByText('Portfolio Health');
    expect(scoreSection.length).toBe(1);
    // And there should be a loading indicator for score (not content)
    expect(screen.queryByTestId('scorecard')).toBeNull();
  });
});
