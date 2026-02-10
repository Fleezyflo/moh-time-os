-- Migration 007: v2.9 inbox_items updates
-- Spec Section 1.4, 0.5, 7.10

-- Add resurfaced_at column for is_unprocessed() logic
-- This is set when snooze expires and item transitions back to proposed
ALTER TABLE inbox_items ADD COLUMN resurfaced_at TEXT;

-- Add last_refreshed_at for detector enrichment tracking
ALTER TABLE inbox_items ADD COLUMN last_refreshed_at TEXT;

-- Add resolution_reason for audit trail (spec 0.4)
ALTER TABLE inbox_items ADD COLUMN resolution_reason TEXT;

-- Create index for resurfaced_at (used in is_unprocessed calculation)
CREATE INDEX IF NOT EXISTS idx_inbox_items_resurfaced ON inbox_items(resurfaced_at);

-- Check constraint for resolution_reason enum (can't add to existing table, documented for app layer)
-- Valid values: tag, assign, issue_snoozed_directly, issue_resolved_directly,
--               issue_closed_directly, issue_acknowledged_directly,
--               issue_assigned_directly, superseded
