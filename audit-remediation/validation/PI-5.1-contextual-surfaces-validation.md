# PI-5.1 Contextual Surfaces Validation

**Status:** Documented — pending live system test
**Prerequisites:**
- GAP-10-12: Proposal-to-Asana pipeline (AsanaActionHandler)
- GAP-10-13: Proactive email drafts (communication gap signal + EmailHandler)

---

## Test Plan

### 1. Proposal Generation from Communication Gap

**Test:** Verify `sig_client_comm_gap` fires and generates a proposal with `implied_action="draft_email"`.

**Setup:** Entity with no outbound email in 14+ days.

**Expected:** Signal fires → proposal generated → proposal contains `implied_action="draft_email"` and entity context.

### 2. Asana Task Creation from Proposal

**Test:** Approve and execute an Asana task creation action via the ActionFramework pipeline.

**Setup:** Create a proposal with `implied_action="create_task"`, route through ActionFramework.

**Expected:**
- Action proposed in PROPOSED state
- After approval: action moves to APPROVED
- After execution (dry_run): returns success with dry_run=True
- After execution (live): Asana task created with proposal reference in notes

### 3. Proactive Email Draft Generation

**Test:** Approve and execute a draft_email action.

**Setup:** Communication gap signal fires → proposal with draft_email action.

**Expected:**
- Gmail draft created via GmailWriter (or stored locally if no credentials)
- Decision record created in decisions table with requires_approval=1
- Draft includes entity name, days since contact, and contextual body

### 4. Contextual Relevance of Email Drafts

**Test:** Verify draft email body is contextually relevant to the entity.

**Expected:**
- Subject line includes entity name
- Body references the time gap
- If entity context provided, it's incorporated into the draft

### 5. End-to-End: Signal → Proposal → Action → Verification

**Test:** Full chain from signal detection to action execution.

**Sequence:**
1. Communication gap signal fires for "client_acme"
2. Proposal generated with draft_email implied action
3. Proposal surfaced in inbox / daily briefing
4. User approves action
5. Email draft created (dry_run in test)
6. Action logged in action history

---

## Validation Criteria

- [ ] Communication gap signal fires correctly for 14+ day gaps
- [ ] Proposals surface in inbox with correct entity context
- [ ] Asana tasks created via approval flow include proposal reference
- [ ] Email drafts are contextually relevant (entity name, time gap)
- [ ] Action history records all steps from proposal to execution
- [ ] Dry-run mode prevents actual API calls while validating the chain
