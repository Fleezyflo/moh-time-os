# CI-4.1 Conversational Intelligence Validation

**Status:** Documented — pending live system test
**Prerequisite:** Phase B wired ConversationalIntelligence to `POST /api/v2/intelligence/conversation`

---

## Test Plan

### 1. Ambiguous Query Handling

**Test:** Send queries that could refer to multiple entities.

```
POST /api/v2/intelligence/conversation
{"session_id": null, "query": "How is the project going?"}
```

**Expected:** Response should ask for clarification or provide a ranked list of projects rather than picking one arbitrarily.

### 2. Error Response Consistency

**Test:** Send malformed requests and verify error format.

```
POST /api/v2/intelligence/conversation
{"session_id": null}
```

**Expected:** 400 response with `{"error": "...", "error_code": "VALIDATION_ERROR"}` — not a 500 HTTPException.

### 3. Multi-Turn Context Retention

**Test:** Chain of queries using the same session_id.

```
# Turn 1: "Tell me about Acme Corp"
# Turn 2 (same session_id): "What about their invoices?"
```

**Expected:** Turn 2 resolves "their" to Acme Corp from session context.

### 4. Unknown Entity Handling

**Test:** Query about a non-existent entity.

```
POST /api/v2/intelligence/conversation
{"session_id": null, "query": "How is Nonexistent Corp doing?"}
```

**Expected:** Graceful "entity not found" response, not a crash.

### 5. Session Isolation

**Test:** Two different session_ids should not share context.

**Expected:** Query referencing "their" in session B should not resolve to session A's entity.

---

## Validation Criteria

- [ ] Ambiguous queries produce clarification or ranked results
- [ ] Malformed requests return structured error responses (not 500s)
- [ ] Multi-turn context resolves pronouns correctly within a session
- [ ] Unknown entities handled gracefully
- [ ] Sessions are isolated from each other
