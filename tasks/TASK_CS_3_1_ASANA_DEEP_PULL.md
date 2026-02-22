# CS-3.1: Asana Collector Deep Pull

## Objective
Expand `lib/collectors/asana.py` from ~40% to ≥90% API coverage. Pull custom fields, subtasks, sections, stories, portfolios, goals, dependencies, and attachments.

## Context
Current Asana collector (117 lines) pulls only tasks and projects with basic fields. Asana's API exposes rich data — custom fields define client workflows, subtasks carry real work, stories contain decision history, dependencies map critical paths.

## Current State (lib/collectors/asana.py)
- Pulls: projects (name, gid, team), tasks (name, gid, assignee, due_on, completed, notes, projects)
- Missing: custom_fields, subtasks, sections, stories/comments, portfolios, goals, dependencies, attachments, tags

## Implementation

### New Data to Pull

1. **Custom Fields** — `GET /tasks/{id}?opt_fields=custom_fields` → store in `asana_custom_fields`
2. **Subtasks** — `GET /tasks/{id}/subtasks` → store in `asana_subtasks`
3. **Sections** — `GET /projects/{id}/sections` → store in `asana_sections`, update `tasks.section_id`
4. **Stories/Comments** — `GET /tasks/{id}/stories?opt_fields=type,text,created_by,created_at` → store in `asana_stories`
5. **Dependencies** — `GET /tasks/{id}/dependencies` → store in `asana_task_dependencies`
6. **Portfolios** — `GET /portfolios?workspace={id}` → store in `asana_portfolios`
7. **Goals** — `GET /goals?workspace={id}` → store in `asana_goals`
8. **Attachments** — `GET /tasks/{id}/attachments` → store in `asana_attachments`

### Optimization
- Use `opt_fields` parameter on every request to minimize payload
- Batch subtask/story/attachment fetches — only for tasks modified since last sync
- Use `modified_since` parameter on project task listings
- Store `last_synced_at` per project for incremental pulls

### Rate Limiting
Asana allows 1500 requests/minute. With resilience infrastructure (CS-2.1):
- Track request count per minute
- Back off when approaching 1400
- Honor `Retry-After` headers on 429 responses

## Validation
- [ ] Custom fields stored for tasks that have them
- [ ] Subtask count matches Asana UI for sampled tasks
- [ ] All project sections captured with correct ordering
- [ ] Stories include both comments and system events
- [ ] Dependencies create correct task→task links
- [ ] Portfolios and goals pulled at workspace level
- [ ] Attachments metadata stored (no file downloads)
- [ ] Incremental sync works — second run is faster than first

## Files Modified
- `lib/collectors/asana.py` — major expansion (~300-400 lines added)

## Estimated Effort
Large — most complex collector expansion due to nested resources
