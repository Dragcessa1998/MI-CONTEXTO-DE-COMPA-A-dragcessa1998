# Nexova Agent Memory — MEM-092

## Decision

The existing `first_line_support` agent now has a small semantic/episodic memory
implemented as a separate SQLite store. This is deliberately not the Qdrant
`nexova_knowledge` collection: company RAG remains curated and read-only, while
approved conversational corrections have their own lifecycle and audit trail.

SQLite fits the bounded set of recurring support procedures, company-client
preferences and incident patterns. It is durable across restarts, transactional,
easy to inspect and does not require another service. A vector database would add
operational cost without improving this small, high-precision allowlist. A
knowledge graph is also unnecessary because the task does not depend on traversing
relationships. The explicit interfaces are `SQLiteMemoryStore.propose`, `pending`,
`resolve`, `write_approved`, `read_all`, `mark_accessed`, `audit_log` and
`consolidate`.

Memory is separated by `business_line=support`. Headhunting and training never
share this store. This avoids retrieving support instructions in a candidate or
training context and matches the identity of the same first-line agent used by
RAG, MCP and WebSocket chat.

## One-agent flow

`MemoryCoordinator` wraps one turn of the existing agent; it is not a second graph
or a multi-agent system.

1. It expires abandoned proposals and reads the one pending proposal for the
   authenticated conversation.
2. If one exists, an explicit structured classifier returns `approve`, `reject`,
   `edit` or `ambiguous`. Full phrases are classified, not substring matches.
3. Approval or a policy-valid edit is audited and consolidated. Rejection is
   audited without writing. Ambiguity and topic changes reject by default, then
   continue answering the new question.
4. Relevant approved entries are read before composing the visible result.
5. A single deterministic self-evaluation checks whether the interaction contains
   a new reusable fact. It emits either one structured proposal or `None`.
6. A proposal is shown inside the assistant response. No entry is written until a
   later explicit decision from the same authenticated user.

An explicit decision followed by a new question in the same message is supported:
`Sí, recuérdalo. ¿Cuál es el SLA de payroll para retail?` both commits the pending
proposal and answers using the newly approved memory.

## Nexova allowlist and denylist

Allowed memory kinds are exactly:

- corrected escalation procedures or SLA rules;
- recurring outsourcing client-company preferences;
- known repeatable helpdesk incident patterns.

The following never produce a proposal and therefore never enter either memory or
its proposal audit:

- candidate CVs, ratings, interview notes or other selection-process data;
- salary information from active headhunting negotiations;
- one-off corrections for one ticket.

Examples that must propose:

1. Payroll tickets for retail clients now resolve in 24 hours rather than 48.
2. A recurring finance client always wants email confirmation before closure.
3. Urgent tickets from premium-contract clients now go directly to a senior agent.

Examples that must return `None`:

1. “How many open tickets are there right now?”
2. “Perfect, thanks for the explanation.”
3. “Summarize this ticket in two lines for Laura's report.”

These six cases and the three forbidden categories are executable in
`services/api/tests/test_agent_memory.py`.

## Authorization and poisoning controls

- The HTTP endpoint already requires a valid Nexova JWT; proposal rows record its
  numeric user ID.
- Only that same authenticated user can approve the pending proposal.
- Content must match the closed support-memory schema both when first proposed and
  after an edit. Candidate/salary/one-off patterns are rejected before storage.
- Only one unresolved proposal is possible per conversation, enforced by a partial
  unique SQLite index.
- An existing semantic key is updated transactionally rather than duplicated, so
  repeated corrections do not create contradictory prompt fragments.
- Every accepted/rejected/ambiguous/expired decision records the original allowed
  message, label and UTC timestamps. Invalid edits are redacted in the audit to
  avoid persisting forbidden content.

This does not claim that user confirmation proves a fact is objectively true. In a
production rollout, the audit supplies the control point for a procedure owner to
review changes. The course intentionally omits that separate governance workflow;
within its scope, authentication, explicit consent, allowlisting, one-owner
confirmation and auditability prevent silent or anonymous poisoning.

## Cleanup and consolidation

`consolidate()` runs at the start and end of memory turns:

- unresolved proposals expire after 24 hours as a non-approval;
- semantic keys are upserted, so a correction replaces an older version;
- approved memory is capped at 200 entries and evicts least-recently-used entries;
- decision audit is capped at 1,000 rows and 730 days; rows still referenced by a
  current memory entry are retained.

This balances a small operational memory with sufficient incident investigation
history and prevents unbounded prompt/store growth.

## Complete evidence cycles

Run:

```bash
PYTHONPATH=.:services/api services/api/.venv/bin/python scripts/demo_agent_memory.py
services/api/.venv/bin/python -m pytest services/api/tests/test_agent_memory.py -q
```

### Approved and recalled

1. Session A says the corrected retail payroll SLA is 24 hours.
2. The response contains a pending `escalation_procedure`; store size remains 0.
3. Session A says `Sí, recuérdalo.`; audit becomes `approved`; store size becomes 1.
4. Fresh Session B asks for the retail payroll SLA and receives the approved
   24-hour fact under `Memoria aprobada relevante`.

### Rejected and unchanged

1. Session C states that a finance client always wants email confirmation.
2. The response contains a pending `client_preference`; store size remains 0.
3. Session C says `No lo recuerdes.`; audit becomes `rejected`.
4. Store size remains 0 and a future session cannot retrieve the rejected fact.

The acceptance test also proves that a topic change is `rejected_ambiguous`, still
answers the new question, and never writes memory.
