# Agent Builder Demo — Architecture

Scope and planning provenance: [PRD.md](PRD.md). Interaction requirements: [UI_SPEC.md](UI_SPEC.md). Verification: [DEMO_SCENARIO.md](DEMO_SCENARIO.md).

## Single application architecture

```text
React / TypeScript / React Flow
    → FastAPI: session, definitions/registry, executions, approvals, reports
        → Definition validator/compiler → LangGraph StateGraph
            → Model Gateway → External provider (actual demo)
            → Capability adapters → Mock Data Fabric / Situation Context
            → SQLite: checkpoints + application records
            → Report Service → persisted Approved Report event → Staff execution
```

Use one backend process and SQLite. Separate modules and interfaces, not deployable services. Builder JSON stays independent of LangGraph classes. AI nodes call the Gateway, never vendor SDKs directly. A simple in-process event dispatcher backed by persisted pending events is sufficient; no Kafka, worker fleet or message broker.

## Agent Definition and compilation

Save JSON containing schema_version, agent_id, workflow_id, name, description, owner, allowed_roles, required_permissions, monitoring_area, trigger, approval_policy, output_type, model, nodes and edges. Model contains separate provider and model_id plus generation settings. A node contains id, type, config and position. Edges contain source, target and an optional named condition branch. Store business node types, not executable Python or vendor-specific objects.

Agent versions carry version, lifecycle_status and the full definition. Minimal lifecycle: DRAFT → PUBLISHED → SUSPENDED. Publish validates and snapshots a draft; Test uses a saved snapshot, even if unpublished. Registry registration is achieved by persistence and publishing; do not build a second formal review workflow. Agent deployment approval and an execution's Human Approval are different concepts. The former is deferred; the latter is mandatory.

Validator checks required configuration, unique IDs, valid endpoints, one supported trigger, supported node types, reachable outputs, no unsupported cycles, named LOW/MEDIUM/HIGH routing, role-compatible nodes, and a required role-specific Human Approval on every route to Send Report. Reject bypasses around approval. Compiler maps only the supported nodes to LangGraph. Canvas-only position changes do not affect execution; config and edge edits do.

Published sensor/report subscriptions use active versions. Each execution pins its version/snapshot so later edits cannot change a running or paused graph. For this demo choose one active Analyst subscription for A-12 and one active Staff report subscription; avoid accidental fan-out to multiple template versions.

## Supported capability contracts

| Group | Nodes and behavior |
| --- | --- |
| Trigger | Sensor Event (Analyst); Approved Report (Staff). User Request is a visible future item, disabled in this demo. Test Run injects a fixture into the supported trigger. |
| Data | Data Fabric Search/Query and Situation Context return deterministic mocked records with stable evidence IDs; Approved Reports returns persisted, approved regional reports only. |
| AI | Threat Analysis and Situation Synthesis use structured Gateway output with evidence references; Report Generator formats a draft from that output (may use the same Gateway if needed). |
| Control | Event Filter checks area/confidence; Condition branches on threat; Human Approval interrupts for the assigned role. |
| Action | Record Event handles LOW/filtered cases; Notification creates an in-app alert; Send Report finalizes/persists approved content; Update Situation Board derives visible results from persisted state. |

Report collection and classification can share the Approved Reports node. Correlation and overall assessment belong to Situation Synthesis; do not require separate nodes for every conceptual step.

## Runtime state and status

State contains execution_id, thread_id, agent_id, version, immutable initiating session_context (user_id/role/area/permissions), event, situation, evidence, source_report_ids, analysis, draft, approval_id/decision, finalized_report_id and error. Staff auto-executions use the registered Staff owner's demo context, not the Analyst browser's current role. The reviewing actor is recorded separately. Role Switch never rewrites running execution context.

Execution statuses: QUEUED → RUNNING → WAITING_FOR_ANALYST_APPROVAL or WAITING_FOR_STAFF_APPROVAL → RUNNING → COMPLETED. Alternate terminal statuses: REJECTED, FAILED. LOW/filtered cases complete with a recorded outcome and no report. Node statuses: PENDING, RUNNING, WAITING, SUCCEEDED, SKIPPED, FAILED. APPROVED is a review decision/report state, not an extra execution terminal state.

Use execution_id as a stable LangGraph thread_id (or persist a one-to-one mapping). Use a SQLite-backed LangGraph checkpointer. Persist trace entries with node_id, sequence, status, timestamps, input/output summaries and errors. Do not expose credentials or claim traces contain private model reasoning; show returned analysis and evidence. Poll execution state and ordered trace from the UI, including after refresh.

## HITL contract

1. Complete analysis and draft generation before a dedicated approval node. Persist the draft and pending approval once, keyed by execution/node occurrence.
2. Call LangGraph interrupt with approval_id, reviewer_role, draft and evidence/source links. This is a real checkpoint-backed pause, not a frontend modal timer.
3. Approve submits a decision for the pending approval. Edit enables draft changes; saving or closing the editor does not resume. An explicit approve submission with edited content records EDIT_APPROVE. Reject records REJECT and terminates without final report or report event.
4. Validate the mock session's role/area against the approval and reject stale/duplicate/conflicting decisions. Persist actor, original draft, final content, decision, time and optional comment.
5. Resume the same thread with the stored decision using LangGraph resume input. Map the approved content back into state before Send Report.

Interrupt nodes can re-enter from their beginning. Keep model calls and publishing outside the interrupt node; make approval creation and downstream writes idempotent. If a crash occurs after saving a decision but before resume, recover from the saved decision and pending checkpoint. A repeated resume must not overwrite a finalized decision or duplicate reports.

## SQLite persistence and event handoff

Minimum logical records (tables can be simplified while retaining these invariants):

| Record | Required information/invariant |
| --- | --- |
| agents / agent_versions | Owner, role exposure, published version, immutable definition snapshot |
| executions | Pinned snapshot/version, initiating context, trigger ID, status, thread ID, parent report/event |
| approvals | Unique execution/node occurrence, assigned role, draft, decision, actor, final content |
| reports | ID, kind REGIONAL/COMMANDER, area, threat, content, source execution, approving actor/time, source report IDs, fixture flag |
| report_events | Event ID, regional report ID, type APPROVED_REPORT_CREATED, pending/dispatched status |
| execution_trace / audit | Ordered node transitions and review/report events with correlation IDs |
| sensor_events | Simulator payload and processing outcome |

Only approved content enters the reports collection; drafts live in runtime/approval state. Send Report commits a REGIONAL report and its pending event in one SQLite transaction. The dispatcher reads the committed report and creates the Staff execution with a uniqueness constraint on (event_id, target_agent_id, target_version). Mark dispatched only after execution creation succeeds; recover pending items on startup. Duplicate notification delivery therefore cannot create a second Staff run. Use a unique finalized report key per execution/output to guard replay.

A COMMANDER report is persisted after Staff approval but must not emit APPROVED_REPORT_CREATED, preventing recursive Staff triggering. B-07 and C-03 are preapproved external seed fixtures; seeding them does not emit runtime events. Staff collects the new A-12 report plus those fixtures from a bounded demo set, deduplicated by report ID, and records the exact input IDs. A fresh A-12 report must actually participate in synthesis.

## Model Gateway

Expose generate(messages, model_config) and structured_generate(messages, schema, model_config). Implement one real external provider. Reserve provider registration as the extension point for vLLM/Ollama/local HF without installing or serving them now. Keep external API credentials in backend environment configuration, never Agent Definition JSON or frontend storage.

Validate structured output. Threat analysis requires threat_level LOW/MEDIUM/HIGH, summary and evidence_ids; synthesis requires overall_threat_level, summary, priority_areas and source_report_ids. Evidence references must resolve to supplied data. Sensor confidence is distinct from model certainty. Use a bounded timeout and at most one automatic retry for transient provider failures; malformed output or exhausted retries fails visibly without fabricated approval or report. Deterministic test/rehearsal output must be labeled as such.

## Minimal API boundaries (implementation defaults)

| API responsibility | Suggested endpoints / contract |
| --- | --- |
| Mock session | POST /api/session, role switch via same operation; return static session context |
| Catalog and definitions | GET /api/nodes; GET/POST /api/agents; GET/PUT /api/agents/{id}; POST .../validate and .../publish |
| Start/test | POST /api/agents/{id}/test with fixture and saved snapshot; POST /api/sensor-events for active published subscription |
| Execution | GET /api/executions and /api/executions/{id}; GET .../trace |
| Approval | POST /api/approvals/{id}/decision with APPROVE, EDIT_APPROVE or REJECT and optional edited content/comment |
| Read models | GET /api/reports, /api/reports/{id}, /api/situation-board, /api/notifications |

Backend applies the same small role/area policy to reads, node validation and approval actions as the frontend. Return clear validation, forbidden-role, conflict/stale-decision and provider error messages. This is demo policy, not a production RBAC/ABAC system. Send to Superior/Commander means in-app report availability, not email or an external system integration.
