# ADR-0009: Phase 13 Collector Data Depth

## Status
Accepted

## Context
Phase 13 surfaces data from 22 collector secondary tables (gmail_participants, gmail_attachments, gmail_labels, asana_custom_fields, asana_subtasks, asana_stories, asana_task_dependencies, asana_attachments, asana_portfolios, asana_goals, calendar_attendees, calendar_recurrence_rules, chat_reactions, chat_attachments, chat_space_metadata, chat_space_members, xero_line_items, xero_contacts, xero_credit_notes, xero_bank_transactions, xero_tax_rates, asana_sections) through the API to frontend detail pages. These tables already exist in `lib/schema.py` and are populated by collectors, but had no read paths.

## Decision
Wire collector secondary tables through 8 new QueryEngine methods, 8 new spec_router endpoints, and 8 frontend hooks into 5 existing pages:

1. Add 8 read-only QueryEngine methods to `lib/query_engine.py` for cross-entity secondary data queries
2. Add 8 GET endpoints to `api/spec_router.py` using a lazy QueryEngine singleton pattern
3. Add 8 fetch functions + 16 TypeScript interfaces to `time-os-ui/src/lib/api.ts`
4. Add 8 hooks to `time-os-ui/src/lib/hooks.ts`
5. Add tabs/sections to 5 pages: ClientDetailSpec (3 tabs), TeamDetail (1 tab), TaskDetail (1 tab), Operations (1 tab), Portfolio (2 sections)

The lazy QueryEngine singleton in spec_router avoids repeated DB path resolution and connection setup across the 8 endpoints.

## Consequences
- API surface grows by 8 endpoints (all read-only GET)
- System map grows from 195 to 203 API routes
- Pages with new tabs load additional data on tab switch (no upfront cost)
- Empty state handling covers collectors that haven't run yet
