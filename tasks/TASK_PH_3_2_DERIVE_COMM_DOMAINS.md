# TASK: Derive from_domain and Seed Client Identities
> Brief: PIPELINE_HARDENING | Phase: 3 | Sequence: 3.2 | Status: PENDING

## Context

After PH-1.2 adds `from_domain`, `client_id`, `link_status` columns to `communications`, and PH-2.1 creates `client_identities`, this task populates them:

1. **Derive `from_domain`** from `from_email` for all communications
2. **Seed `client_identities`** with known email domains from client data
3. **Link communications to clients** via domain matching (what the normalizer does, but we pre-populate)

The normalizer (`lib/normalizer.py` lines 232-320) has the logic but can't run until these columns and tables exist and have seed data.

## Objective

Pre-populate `from_domain` and seed `client_identities` so the normalizer's communication linking works.

## Instructions

1. Derive `from_domain` from `from_email`:
   ```sql
   UPDATE communications
   SET from_domain = LOWER(SUBSTR(from_email, INSTR(from_email, '@') + 1))
   WHERE from_email IS NOT NULL
     AND from_email LIKE '%@%'
     AND (from_domain IS NULL OR from_domain = '');
   ```

2. Verify:
   ```sql
   SELECT from_domain, COUNT(*) FROM communications
   WHERE from_domain IS NOT NULL
   GROUP BY from_domain ORDER BY COUNT(*) DESC LIMIT 20;
   ```

3. Seed `client_identities` from known client email patterns:
   ```sql
   -- Extract unique domains from communications linked to known clients (from entity_links or projects)
   INSERT OR IGNORE INTO client_identities (client_id, identity_type, identity_value)
   SELECT DISTINCT c.id, 'domain', comm.from_domain
   FROM communications comm
   JOIN entity_links el ON el.source_type = 'communication' AND el.source_id = comm.source_id
   JOIN clients c ON c.id = el.client_id
   WHERE comm.from_domain IS NOT NULL
     AND el.link_status = 'confirmed';
   ```

   Adjust the JOIN logic based on how entity_links actually references communications (check column names first).

4. If entity_links doesn't have communication references, try deriving from project emails or manual seed:
   ```sql
   -- Seed from known client domains (e.g., hrmny.co → Molham's agency)
   INSERT OR IGNORE INTO client_identities (client_id, identity_type, identity_value)
   SELECT id, 'domain', LOWER(SUBSTR(email, INSTR(email, '@') + 1))
   FROM clients
   WHERE email IS NOT NULL AND email LIKE '%@%';
   ```

5. Run the normalizer's link_communications step to populate `client_id` and `link_status`:
   ```python
   from lib.normalizer import Normalizer
   n = Normalizer()
   n.link_communications()
   ```

## Preconditions
- [ ] PH-1.2 complete (communications columns exist)
- [ ] PH-2.1 complete (client_identities table exists)

## Validation
1. `SELECT COUNT(*) FROM communications WHERE from_domain IS NOT NULL` matches count of emails with @
2. `SELECT COUNT(*) FROM client_identities` > 0
3. `SELECT COUNT(*) FROM communications WHERE link_status = 'linked'` > 0
4. Normalizer link_communications() runs without error
5. `pytest tests/ -q` — no regressions

## Acceptance Criteria
- [ ] from_domain populated for all communications with from_email
- [ ] client_identities seeded with at least domain-based identities
- [ ] Some communications linked to clients
- [ ] No test regressions

## Output
- Modified: live DB (from_domain populated, client_identities seeded, some link_status set)
- Possibly created: seed script for reproducibility
