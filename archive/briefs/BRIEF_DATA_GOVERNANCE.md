# Brief 16: Data Governance & Compliance

## Status: DESIGNED
## Priority: P2 — Operational maturity
## Dependencies: Brief 9 (schema), Brief 10 (lifecycle), Brief 13 (security)

## Problem Statement

MOH Time OS ingests and stores sensitive business data — emails, invoices, team capacity, client financials — but has zero data governance infrastructure. No export API, no anonymization, no classification, no compliance reporting. The system can't answer: "What data do we hold on client X?" or "Delete everything related to person Y." For a production system handling PII and financial data, this is a liability.

## Success Criteria

- Every data entity exportable via API (JSON + CSV)
- Subject access requests answerable in <30 seconds (all data for entity X)
- Data deletion/anonymization for any person or client, verified complete
- Retention policies enforced automatically with audit trail
- Compliance report generation on demand
- Data classification labels on all tables

## Scope

### Phase 1: Data Classification & Inventory (DG-1.1)
Classify every table and column by sensitivity level (public, internal, confidential, restricted). Build a queryable data catalog.

### Phase 2: Data Export API (DG-2.1)
Bulk export endpoints for all major entities — clients, team members, communications, tasks, invoices, patterns, actions. JSON and CSV formats. Streaming for large exports.

### Phase 3: Subject Access & Deletion (DG-3.1)
"Right to be forgotten" implementation. Given a person identifier (email, name, client), find all related records across all tables, export them, then anonymize or delete with verification.

### Phase 4: Retention Policy Enforcement (DG-4.1)
Build on Brief 10's data lifecycle (AO-4.1) with governance-grade enforcement: policy-per-table configuration, automatic archival, deletion certificates, and exception handling for legal holds.

### Phase 5: Compliance Reporting (DG-5.1)
Generate compliance audit reports: what data is held, retention status, access patterns, deletion requests processed, policy violations detected.

## Architecture

```
Data Catalog (DG-1.1)
  ├── Table classifications
  ├── Column sensitivity labels
  └── Data lineage (source → table → derived)

Export API (DG-2.1)
  ├── /api/v1/export/{entity_type}
  ├── Streaming JSON/CSV
  └── Field-level filtering by classification

Subject Access (DG-3.1)
  ├── /api/v1/governance/subject-search
  ├── /api/v1/governance/subject-export
  ├── /api/v1/governance/subject-delete
  └── Cross-table entity resolution

Retention (DG-4.1)
  ├── Policy-per-table config
  ├── Archive → Delete pipeline
  ├── Legal hold override
  └── Deletion certificates

Compliance (DG-5.1)
  ├── /api/v1/governance/compliance-report
  ├── Data inventory summary
  ├── Retention compliance status
  └── Access and deletion audit trail
```

## Files Created
- `lib/governance/catalog.py` — data classification and inventory
- `lib/governance/export.py` — bulk export engine
- `lib/governance/subject_access.py` — subject search, export, delete
- `lib/governance/retention.py` — policy enforcement engine
- `lib/governance/compliance.py` — report generation
- `api/governance_router.py` — all governance API endpoints
- `tasks/TASK_DG_*.md` — individual task files

## Estimated Total Effort
Large — ~800 lines across 5 task phases
