-- Migration 004: issue_transitions and engagement_transitions
-- Spec Sections 6.5, 6.7

-- Issue transitions audit trail
CREATE TABLE IF NOT EXISTS issue_transitions (
  id TEXT PRIMARY KEY,
  issue_id TEXT NOT NULL,
  previous_state TEXT NOT NULL,
  new_state TEXT NOT NULL,
  transition_reason TEXT NOT NULL CHECK (transition_reason IN (
    'user', 'system_timer', 'system_signal', 'system_threshold', 'system_aggregation'
  )),
  trigger_signal_id TEXT,
  trigger_rule TEXT,
  actor TEXT NOT NULL,  -- 'system' or user_id
  actor_note TEXT,
  transitioned_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issue_transitions_issue ON issue_transitions(issue_id);
CREATE INDEX IF NOT EXISTS idx_issue_transitions_timestamp ON issue_transitions(transitioned_at);
CREATE INDEX IF NOT EXISTS idx_issue_transitions_reason ON issue_transitions(transition_reason);

-- Engagement transitions audit trail
CREATE TABLE IF NOT EXISTS engagement_transitions (
  id TEXT PRIMARY KEY,
  engagement_id TEXT NOT NULL,
  previous_state TEXT NOT NULL,
  new_state TEXT NOT NULL,
  transition_reason TEXT NOT NULL CHECK (transition_reason IN (
    'user', 'system_timer', 'system_signal', 'system_threshold', 'system_aggregation'
  )),
  trigger_signal_id TEXT,
  trigger_rule TEXT,
  actor TEXT NOT NULL,  -- 'system' or user_id
  actor_note TEXT,
  transitioned_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_engagement_transitions_engagement ON engagement_transitions(engagement_id);
CREATE INDEX IF NOT EXISTS idx_engagement_transitions_timestamp ON engagement_transitions(transitioned_at);
