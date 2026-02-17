/**
 * UI Component Tests
 *
 * Tests for intelligence components using Vitest + Testing Library.
 * Focus on unit testing component rendering and behavior.
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Components without router dependencies
import {
  EmptyState,
  NoSignals,
  NoPatterns,
  NoBriefing,
  NoIntelData,
  SuccessState,
  AllClear,
  NoPatternsDetected,
  NoActiveSignals,
} from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import {
  SeverityBadge,
  UrgencyBadge,
  PatternSeverityBadge,
} from '../intelligence/components/Badges';

// =============================================================================
// EMPTY STATE TESTS
// =============================================================================

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No items" description="Nothing to show here" />);

    expect(screen.getByText('No items')).toBeInTheDocument();
    expect(screen.getByText('Nothing to show here')).toBeInTheDocument();
  });

  it('renders custom icon', () => {
    render(<EmptyState title="Test" icon="🚀" />);

    expect(screen.getByRole('img', { hidden: true })).toHaveTextContent('🚀');
  });

  it('renders action button when provided', () => {
    const handleClick = vi.fn();
    render(<EmptyState title="Test" action={{ label: 'Click me', onClick: handleClick }} />);

    const button = screen.getByRole('button', { name: 'Click me' });
    fireEvent.click(button);

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('does not render description when not provided', () => {
    render(<EmptyState title="No desc" />);

    expect(screen.getByText('No desc')).toBeInTheDocument();
    expect(screen.queryByRole('paragraph')).not.toBeInTheDocument();
  });
});

describe('Intelligence Empty State Presets', () => {
  it('NoSignals shows correct message', () => {
    render(<NoSignals />);

    expect(screen.getByText('No active signals')).toBeInTheDocument();
    expect(screen.getByText(/All systems are operating normally/)).toBeInTheDocument();
  });

  it('NoSignals filtered shows filter message', () => {
    render(<NoSignals filtered />);

    expect(screen.getByText('No signals match filters')).toBeInTheDocument();
    expect(screen.getByText(/Try adjusting/)).toBeInTheDocument();
  });

  it('NoPatterns shows correct message', () => {
    render(<NoPatterns />);

    expect(screen.getByText('No patterns detected')).toBeInTheDocument();
  });

  it('NoBriefing shows correct message', () => {
    render(<NoBriefing />);

    expect(screen.getByText('No briefing available')).toBeInTheDocument();
  });

  it('NoIntelData shows generic message without entity', () => {
    render(<NoIntelData />);

    expect(screen.getByText(/Intelligence data is not available/)).toBeInTheDocument();
  });

  it('NoIntelData shows entity-specific message', () => {
    render(<NoIntelData entityType="client" />);

    expect(screen.getByText(/No intelligence data found for this client/)).toBeInTheDocument();
  });
});

describe('Success State Presets', () => {
  it('SuccessState renders with correct content', () => {
    render(<SuccessState title="All good" description="Nothing to worry about" />);

    expect(screen.getByText('All good')).toBeInTheDocument();
    expect(screen.getByText('Nothing to worry about')).toBeInTheDocument();
  });

  it('AllClear shows correct message', () => {
    render(<AllClear />);

    expect(screen.getByText('All Clear')).toBeInTheDocument();
    expect(screen.getByText(/No critical items/)).toBeInTheDocument();
  });

  it('NoPatternsDetected shows success message', () => {
    render(<NoPatternsDetected />);

    expect(screen.getByText('No patterns detected')).toBeInTheDocument();
    expect(screen.getByText(/Portfolio structure looks healthy/)).toBeInTheDocument();
  });

  it('NoActiveSignals shows success message', () => {
    render(<NoActiveSignals />);

    expect(screen.getByText('No active signals')).toBeInTheDocument();
    expect(screen.getByText(/All systems operating normally/)).toBeInTheDocument();
  });
});

// =============================================================================
// ERROR STATE TESTS
// =============================================================================

describe('ErrorState', () => {
  it('renders error title and message', () => {
    const error = new Error('Test error message');
    render(<ErrorState error={error} />);

    // ErrorState uses getErrorInfo which returns title + message
    // Title is "Something went wrong" for generic errors
    // Message is the error.message
    expect(screen.getAllByText(/Something went wrong|Test error message/).length).toBeGreaterThan(
      0
    );
  });

  it('renders retry button when onRetry provided and error is retryable', () => {
    const handleRetry = vi.fn();
    const error = new Error('Test error');
    render(<ErrorState error={error} onRetry={handleRetry} />);

    const button = screen.getByRole('button', { name: /try again/i });
    fireEvent.click(button);

    expect(handleRetry).toHaveBeenCalledTimes(1);
  });

  it('shows banner style when hasData is true', () => {
    const error = new Error('Test error');
    const { container } = render(<ErrorState error={error} hasData />);

    // When hasData is true, it renders a smaller banner
    expect(container.querySelector('.bg-amber-900\\/20')).toBeInTheDocument();
  });
});

// =============================================================================
// BADGE TESTS
// =============================================================================

describe('SeverityBadge', () => {
  it('renders critical with correct text', () => {
    render(<SeverityBadge severity="critical" />);

    const badge = screen.getByText('critical');
    expect(badge).toBeInTheDocument();
  });

  it('renders warning with correct text', () => {
    render(<SeverityBadge severity="warning" />);

    const badge = screen.getByText('warning');
    expect(badge).toBeInTheDocument();
  });

  it('renders watch with correct text', () => {
    render(<SeverityBadge severity="watch" />);

    const badge = screen.getByText('watch');
    expect(badge).toBeInTheDocument();
  });

  it('critical badge has red styling', () => {
    const { container } = render(<SeverityBadge severity="critical" />);

    const badge = container.querySelector('span');
    expect(badge?.className).toContain('red');
  });

  it('warning badge has amber styling', () => {
    const { container } = render(<SeverityBadge severity="warning" />);

    const badge = container.querySelector('span');
    expect(badge?.className).toContain('amber');
  });
});

describe('UrgencyBadge', () => {
  it('renders immediate with capitalized text', () => {
    render(<UrgencyBadge urgency="immediate" />);

    // Component renders capitalized labels
    expect(screen.getByText('Immediate')).toBeInTheDocument();
  });

  it('renders this_week as "This Week"', () => {
    render(<UrgencyBadge urgency="this_week" />);

    expect(screen.getByText('This Week')).toBeInTheDocument();
  });

  it('renders monitor with capitalized text', () => {
    render(<UrgencyBadge urgency="monitor" />);

    expect(screen.getByText('Monitor')).toBeInTheDocument();
  });

  it('immediate badge has red styling', () => {
    const { container } = render(<UrgencyBadge urgency="immediate" />);

    const badge = container.querySelector('span');
    expect(badge?.className).toContain('red');
  });

  it('this_week badge has amber styling', () => {
    const { container } = render(<UrgencyBadge urgency="this_week" />);

    const badge = container.querySelector('span');
    expect(badge?.className).toContain('amber');
  });
});

describe('PatternSeverityBadge', () => {
  it('renders structural severity', () => {
    render(<PatternSeverityBadge severity="structural" />);

    expect(screen.getByText('structural')).toBeInTheDocument();
  });

  it('renders operational severity', () => {
    render(<PatternSeverityBadge severity="operational" />);

    expect(screen.getByText('operational')).toBeInTheDocument();
  });

  it('renders informational severity', () => {
    render(<PatternSeverityBadge severity="informational" />);

    expect(screen.getByText('informational')).toBeInTheDocument();
  });
});

// =============================================================================
// CARD COMPONENT STRUCTURE TESTS (without router)
// =============================================================================

// Import card components for structural tests
import { SignalCard } from '../intelligence/components/SignalCard';
import { PatternCard } from '../intelligence/components/PatternCard';
import { ProposalCard } from '../intelligence/components/ProposalCard';

// Mock the router Link component to avoid router context issues
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

describe('SignalCard', () => {
  const mockSignal = {
    signal_id: 'sig-001',
    name: 'Overdue Task Count Exceeded',
    severity: 'critical' as const,
    entity_type: 'project',
    entity_id: 'proj-123',
    entity_name: 'Project Alpha',
    evidence: '15 tasks are overdue (threshold: 5)',
    implied_action: 'Review and prioritize overdue tasks',
    detected_at: '2024-01-15T10:30:00Z',
  };

  it('renders signal name', () => {
    render(<SignalCard signal={mockSignal} />);

    expect(screen.getByText('Overdue Task Count Exceeded')).toBeInTheDocument();
  });

  it('renders severity badge', () => {
    render(<SignalCard signal={mockSignal} />);

    expect(screen.getByText('critical')).toBeInTheDocument();
  });

  it('renders entity type', () => {
    render(<SignalCard signal={mockSignal} />);

    expect(screen.getByText('project')).toBeInTheDocument();
  });

  it('renders entity name', () => {
    render(<SignalCard signal={mockSignal} />);

    expect(screen.getByText('Project Alpha')).toBeInTheDocument();
  });

  it('expands on click to show evidence', () => {
    render(<SignalCard signal={mockSignal} />);

    // Initially evidence should not be visible
    expect(screen.queryByText(/15 tasks are overdue/)).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(screen.getByText('Overdue Task Count Exceeded'));

    // Now evidence should be visible
    expect(screen.getByText(/15 tasks are overdue/)).toBeInTheDocument();
  });

  it('shows implied action when expanded', () => {
    render(<SignalCard signal={mockSignal} />);

    fireEvent.click(screen.getByText('Overdue Task Count Exceeded'));

    expect(screen.getByText('Review and prioritize overdue tasks')).toBeInTheDocument();
  });

  it('calls onClick handler when provided', () => {
    const handleClick = vi.fn();
    render(<SignalCard signal={mockSignal} onClick={handleClick} />);

    fireEvent.click(screen.getByText('Overdue Task Count Exceeded'));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('compact mode renders truncated', () => {
    render(<SignalCard signal={mockSignal} compact />);

    expect(screen.getByText('Overdue Task Count Exceeded')).toBeInTheDocument();
    expect(screen.getByText('critical')).toBeInTheDocument();
  });
});

describe('PatternCard', () => {
  const mockPattern = {
    pattern_id: 'pat-001',
    name: 'Revenue Concentration',
    type: 'concentration',
    severity: 'structural' as const,
    description: 'Top 2 clients represent 60% of revenue',
    affected_entities: [
      { type: 'client', id: 'client-1', name: 'Acme Corp' },
      { type: 'client', id: 'client-2', name: 'Globex Inc' },
    ],
    implied_action: 'Diversify client base',
    metrics: { concentration_pct: 60 },
  };

  it('renders pattern name', () => {
    render(<PatternCard pattern={mockPattern} />);

    expect(screen.getByText('Revenue Concentration')).toBeInTheDocument();
  });

  it('renders severity badge', () => {
    render(<PatternCard pattern={mockPattern} />);

    expect(screen.getByText('structural')).toBeInTheDocument();
  });

  it('renders description', () => {
    render(<PatternCard pattern={mockPattern} />);

    expect(screen.getByText(/Top 2 clients represent 60%/)).toBeInTheDocument();
  });
});

describe('ProposalCard', () => {
  const mockProposal = {
    id: 'prop-001',
    type: 'resource_rebalance',
    urgency: 'immediate' as const,
    headline: 'Rebalance Team Workload',
    summary: 'Person X is overloaded with 15 active tasks',
    entity: { type: 'person', id: 'person-1', name: 'John Doe' },
    evidence: [
      {
        source: 'signal',
        source_id: 'sig-001',
        description: 'Workload exceeds threshold',
        data: {},
      },
      {
        source: 'pattern',
        source_id: 'pat-001',
        description: 'Consistent overload pattern',
        data: {},
      },
    ],
    implied_action: 'Redistribute 5 tasks to available team members',
    confidence: 'high',
  };

  it('renders headline', () => {
    render(<ProposalCard proposal={mockProposal} />);

    expect(screen.getByText('Rebalance Team Workload')).toBeInTheDocument();
  });

  it('renders urgency badge with capitalized text', () => {
    render(<ProposalCard proposal={mockProposal} />);

    expect(screen.getByText('Immediate')).toBeInTheDocument();
  });

  it('renders entity type and name', () => {
    render(<ProposalCard proposal={mockProposal} />);

    // Entity is rendered as "type: name"
    expect(screen.getByText(/person/)).toBeInTheDocument();
    expect(screen.getByText(/John Doe/)).toBeInTheDocument();
  });

  it('expands on click to show summary', () => {
    render(<ProposalCard proposal={mockProposal} />);

    // Summary is only visible when expanded
    expect(screen.queryByText(/15 active tasks/)).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(screen.getByText('Rebalance Team Workload'));

    // Now summary should be visible
    expect(screen.getByText(/Person X is overloaded/)).toBeInTheDocument();
  });
});
