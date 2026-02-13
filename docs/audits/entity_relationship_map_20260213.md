# Entity Relationship Map — 2026-02-13

## Core Entities
| Entity | Table | Primary Key | Row Count |
|--------|-------|-------------|-----------|
| Calendar | `calendar_events` | id | 38,643 |
| Chat | `chat_messages` | id | 183,244 |
| Client | `clients` | id | 160 |
| Drive | `drive_files` | id | 17,722 |
| Gmail | `gmail_messages` | id | 255 |
| Inbox | `inbox_items_v29` | id | 121 |
| Invoice | `invoices` | id | 1,254 |
| Issue | `issues` | issue_id | 10 |
| Person | `people` | id | 71 |
| Project | `projects` | id | 354 |
| Task | `tasks` | id | 3,946 |

## Relationship Matrix

Legend: DIRECT (FK), IMPLICIT (joinable field), REVERSE (FK from target), INDIRECT (via junction), MISSING (no path), UNKNOWN (table not found)

| From \ To | Clie | Proj | Task | Pers | Gmai | Chat | Cale | Driv | Invo | Issu | Inbo |
|-----------|------|------|------|------|------|------|------|------|------|------|------|
| Client | REVE |
| Project | INDI |
| Task | IMPL |
| Person | IMPL |
| Gmail | IMPL |
| Chat | IMPL |
| Calendar | IMPL |
| Drive | IMPL |
| Invoice | INDI |
| Issue | INDI |
| Inbox | -    |

## Connection Paths (Documented)

- **Calendar → Chat**: IMPLICIT — `calendar_events.subject_email → chat_messages (email_field)`
- **Calendar → Client**: IMPLICIT — `calendar_events.subject_email → clients (email_field)`
- **Calendar → Drive**: IMPLICIT — `calendar_events.subject_email → drive_files (email_field)`
- **Calendar → Gmail**: IMPLICIT — `calendar_events.subject_email → gmail_messages (email_field)`
- **Calendar → Inbox**: IMPLICIT — `calendar_events.subject_email → inbox_items_v29 (email_field)`
- **Calendar → Invoice**: IMPLICIT — `calendar_events.subject_email → invoices (email_field)`
- **Calendar → Issue**: IMPLICIT — `calendar_events.subject_email → issues (email_field)`
- **Calendar → Person**: IMPLICIT — `calendar_events.subject_email → people (email_field)`
- **Calendar → Project**: IMPLICIT — `calendar_events.subject_email → projects (email_field)`
- **Calendar → Task**: IMPLICIT — `calendar_events.subject_email → tasks (email_field)`
- **Chat → Calendar**: IMPLICIT — `chat_messages.subject_email → calendar_events (email_field)`
- **Chat → Client**: IMPLICIT — `chat_messages.subject_email → clients (email_field)`
- **Chat → Drive**: IMPLICIT — `chat_messages.subject_email → drive_files (email_field)`
- **Chat → Gmail**: IMPLICIT — `chat_messages.subject_email → gmail_messages (email_field)`
- **Chat → Inbox**: IMPLICIT — `chat_messages.subject_email → inbox_items_v29 (email_field)`
- **Chat → Invoice**: IMPLICIT — `chat_messages.subject_email → invoices (email_field)`
- **Chat → Issue**: IMPLICIT — `chat_messages.subject_email → issues (email_field)`
- **Chat → Person**: IMPLICIT — `chat_messages.subject_email → people (email_field)`
- **Chat → Project**: IMPLICIT — `chat_messages.subject_email → projects (email_field)`
- **Chat → Task**: IMPLICIT — `chat_messages.subject_email → tasks (email_field)`
- **Client → Calendar**: INDIRECT — `Via entity_links table`
- **Client → Chat**: INDIRECT — `Via entity_links table`
- **Client → Drive**: INDIRECT — `Via entity_links table`
- **Client → Gmail**: INDIRECT — `Via entity_links table`
- **Client → Inbox**: REVERSE — `inbox_items_v29.client_id = clients.id (reverse)`
- **Client → Invoice**: INDIRECT — `Via entity_links table`
- **Client → Issue**: INDIRECT — `Via entity_links table`
- **Client → Person**: REVERSE — `people.client_id = clients.id (reverse)`
- **Client → Project**: REVERSE — `projects.client_id = clients.id (reverse)`
- **Client → Task**: INDIRECT — `Via entity_links table`
- **Drive → Calendar**: IMPLICIT — `drive_files.subject_email → calendar_events (email_field)`
- **Drive → Chat**: IMPLICIT — `drive_files.subject_email → chat_messages (email_field)`
- **Drive → Client**: IMPLICIT — `drive_files.subject_email → clients (email_field)`
- **Drive → Gmail**: IMPLICIT — `drive_files.subject_email → gmail_messages (email_field)`
- **Drive → Inbox**: IMPLICIT — `drive_files.subject_email → inbox_items_v29 (email_field)`
- **Drive → Invoice**: IMPLICIT — `drive_files.subject_email → invoices (email_field)`
- **Drive → Issue**: IMPLICIT — `drive_files.subject_email → issues (email_field)`
- **Drive → Person**: IMPLICIT — `drive_files.subject_email → people (email_field)`
- **Drive → Project**: IMPLICIT — `drive_files.subject_email → projects (email_field)`
- **Drive → Task**: IMPLICIT — `drive_files.subject_email → tasks (email_field)`
- **Gmail → Calendar**: IMPLICIT — `gmail_messages.subject_email → calendar_events (email_field)`
- **Gmail → Chat**: IMPLICIT — `gmail_messages.subject_email → chat_messages (email_field)`
- **Gmail → Client**: IMPLICIT — `gmail_messages.subject_email → clients (email_field)`
- **Gmail → Drive**: IMPLICIT — `gmail_messages.subject_email → drive_files (email_field)`
- **Gmail → Inbox**: IMPLICIT — `gmail_messages.subject_email → inbox_items_v29 (email_field)`
- **Gmail → Invoice**: IMPLICIT — `gmail_messages.subject_email → invoices (email_field)`
- **Gmail → Issue**: IMPLICIT — `gmail_messages.subject_email → issues (email_field)`
- **Gmail → Person**: IMPLICIT — `gmail_messages.subject_email → people (email_field)`
- **Gmail → Project**: IMPLICIT — `gmail_messages.subject_email → projects (email_field)`
- **Gmail → Task**: IMPLICIT — `gmail_messages.subject_email → tasks (email_field)`
- **Inbox → Calendar**: INDIRECT — `Via entity_links table`
- **Inbox → Chat**: INDIRECT — `Via entity_links table`
- **Inbox → Client**: DIRECT — `inbox_items_v29.client_id = clients.id`
- **Inbox → Drive**: INDIRECT — `Via entity_links table`
- **Inbox → Gmail**: INDIRECT — `Via entity_links table`
- **Inbox → Invoice**: INDIRECT — `Via entity_links table`
- **Inbox → Issue**: INDIRECT — `Via entity_links table`
- **Inbox → Person**: INDIRECT — `Via entity_links table`
- **Inbox → Project**: INDIRECT — `Via entity_links table`
- **Inbox → Task**: INDIRECT — `Via entity_links table`
- **Invoice → Calendar**: INDIRECT — `Via entity_links table`
- **Invoice → Chat**: INDIRECT — `Via entity_links table`
- **Invoice → Client**: IMPLICIT — `invoices.client_id → clients (id_column)`
- **Invoice → Drive**: INDIRECT — `Via entity_links table`
- **Invoice → Gmail**: INDIRECT — `Via entity_links table`
- **Invoice → Inbox**: INDIRECT — `Via entity_links table`
- **Invoice → Issue**: INDIRECT — `Via entity_links table`
- **Invoice → Person**: INDIRECT — `Via entity_links table`
- **Invoice → Project**: INDIRECT — `Via entity_links table`
- **Invoice → Task**: INDIRECT — `Via entity_links table`
- **Issue → Calendar**: INDIRECT — `Via entity_links table`
- **Issue → Chat**: INDIRECT — `Via entity_links table`
- **Issue → Client**: INDIRECT — `Via entity_links table`
- **Issue → Drive**: INDIRECT — `Via entity_links table`
- **Issue → Gmail**: INDIRECT — `Via entity_links table`
- **Issue → Inbox**: INDIRECT — `Via entity_links table`
- **Issue → Invoice**: INDIRECT — `Via entity_links table`
- **Issue → Person**: INDIRECT — `Via entity_links table`
- **Issue → Project**: INDIRECT — `Via entity_links table`
- **Issue → Task**: INDIRECT — `Via entity_links table`
- **Person → Calendar**: IMPLICIT — `people.email → calendar_events (email_field)`
- **Person → Chat**: IMPLICIT — `people.email → chat_messages (email_field)`
- **Person → Client**: DIRECT — `people.client_id = clients.id`
- **Person → Drive**: IMPLICIT — `people.email → drive_files (email_field)`
- **Person → Gmail**: IMPLICIT — `people.email → gmail_messages (email_field)`
- **Person → Inbox**: IMPLICIT — `people.email → inbox_items_v29 (email_field)`
- **Person → Invoice**: IMPLICIT — `people.email → invoices (email_field)`
- **Person → Issue**: IMPLICIT — `people.email → issues (email_field)`
- **Person → Project**: IMPLICIT — `people.email → projects (email_field)`
- **Person → Task**: IMPLICIT — `people.email → tasks (email_field)`
- **Project → Calendar**: INDIRECT — `Via entity_links table`
- **Project → Chat**: INDIRECT — `Via entity_links table`
- **Project → Client**: DIRECT — `projects.client_id = clients.id`
- **Project → Drive**: INDIRECT — `Via entity_links table`
- **Project → Gmail**: INDIRECT — `Via entity_links table`
- **Project → Inbox**: INDIRECT — `Via entity_links table`
- **Project → Invoice**: INDIRECT — `Via entity_links table`
- **Project → Issue**: INDIRECT — `Via entity_links table`
- **Project → Person**: INDIRECT — `Via entity_links table`
- **Project → Task**: INDIRECT — `Via entity_links table`
- **Task → Calendar**: IMPLICIT — `tasks.assignee → calendar_events (person_reference)`
- **Task → Chat**: IMPLICIT — `tasks.assignee → chat_messages (person_reference)`
- **Task → Client**: IMPLICIT — `tasks.assignee → clients (person_reference)`
- **Task → Drive**: IMPLICIT — `tasks.assignee → drive_files (person_reference)`
- **Task → Gmail**: IMPLICIT — `tasks.assignee → gmail_messages (person_reference)`
- **Task → Inbox**: IMPLICIT — `tasks.assignee → inbox_items_v29 (person_reference)`
- **Task → Invoice**: IMPLICIT — `tasks.assignee → invoices (person_reference)`
- **Task → Issue**: IMPLICIT — `tasks.assignee → issues (person_reference)`
- **Task → Person**: IMPLICIT — `tasks.assignee → people (person_reference)`
- **Task → Project**: IMPLICIT — `tasks.assignee → projects (person_reference)`

## Missing Connections
| From | To | Priority | Data Needed | Resolution Path |
|------|-----|----------|-------------|-----------------|

## Key Findings

### What We Can Traverse
- Direct FK relationships: 3
- Implicit relationships: 60
- Indirect/reverse relationships: 47
- Missing relationships: 0

### Critical Gaps
- Many entity pairs lack direct relationships
- The `entity_links` table may provide indirect connections
- Email-based matching can connect people to communications

### Recommendations
1. Review `entity_links` table for existing junction relationships
2. Consider adding views that normalize implicit relationships
3. Prioritize HIGH-priority missing connections for Phase 2.3