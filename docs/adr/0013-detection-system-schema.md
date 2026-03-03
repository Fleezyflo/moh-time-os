# ADR-0013: Detection System Schema Foundation

**Date:** 2026-03-03
**Status:** Accepted
**Context:** Phase 15a

## Decision

Extend the schema to support the factual detection system (collision, drift, bottleneck). This includes formalizing the time_blocks table, adding revenue columns to clients, and extending the calendar block horizon from 1 week to 10 business days.

## Changes

### Schema (lib/schema.py)
- SCHEMA_VERSION 12 to 13
- `time_blocks` table formalized with columns: id, date, start_time, end_time, lane, task_id, is_protected, is_buffer, created_at, updated_at
- Revenue columns added to `clients`: prior_year_revenue, ytd_revenue, lifetime_revenue

### Calendar Sync (lib/time_truth/calendar_sync.py)
- `ensure_blocks_for_horizon()` replaces 7-day window with 10 business day window
- `sync_events()` gains `skip_weekends` parameter to exclude Saturday/Sunday
- Backward alias `ensure_blocks_for_week = ensure_blocks_for_horizon` preserved

## Rationale

The detection system needs time_blocks as a first-class table for collision detection (two-path problem: Molham via time_blocks, team via events). Revenue columns enable bottleneck detection to weight clients by financial impact. Extended horizon gives the drift detector enough forward-looking data.
