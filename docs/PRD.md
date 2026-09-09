# Agent Builder Demo — Product Requirements

## Source and authority

Planning source: [세미나 준비안](https://www.notion.so/3d5a13906bdf812ebfb8d6a5a3a0c967), fetched 2026-09-09; reported last edit 2026-09-08T08:36:53.650Z. UI companion: [UI 상세 - GPT](https://www.notion.so/3d5a13906bdf80a79249f84d8c37d367), reported last edit 2026-09-08T08:15:54.848Z.

These documents translate the retrieved planning pages and the user's explicit scope into implementable requirements. Explicit user decisions take precedence over broader platform aspirations in Notion. Routes, persistence contracts, seed fixtures and lifecycle simplifications below are implementation defaults, not verbatim source requirements. PRD owns scope, ARCHITECTURE owns runtime contracts, UI_SPEC owns interactions, and DEMO_SCENARIO owns acceptance. Read all four together.

## Goal and constraints

Build a **1-week seminar demo** for a roughly 40-minute presentation, with about 11 minutes for the live demo. Show that users can compose role-specific workflows in one shared Agent Builder, run them, review AI output, and connect workflows through approved reports.

The visual focus is the Agent Builder, not the Situation Board. Both Analyst and Staff use the same Builder / Registry / Runtime with different definitions, triggers, capabilities and reviewers.

Required stack: React + TypeScript + React Flow frontend; FastAPI + LangGraph + SQLite backend/runtime. Actual demo reasoning uses an external LLM through a Model Gateway/provider abstraction. Future local models require a provider implementation, not a workflow redesign; local serving is out of scope.

## Users and role experience

| Role | Available experience | Review responsibility |
| --- | --- | --- |
| ANALYST | A-12 sensor events, Threat Analysis, own agents, regional context and reports | Analyst report approval |
| STAFF | Approved regional report feed, Situation Synthesis, Staff agents, multi-region context | Commander report approval |
| COMMANDER | Read-only final Commander reports and simple Situation Board | No workflow approval or Builder editing |

Provide Mock Login and a persistent header Role Switch. Session fields: user_id, role, area, permissions. Role and area determine visible agents, nodes, data and review actions through a small static policy. This demonstrates role experience; it is not production authentication or a full authorization engine.

## Required behavior

1. Compose workflows by adding, connecting, configuring and removing business-capability nodes on React Flow. Include Analyst and Staff templates; graph edits must affect validated runtime behavior.
2. Save Agent Definitions, validate them, test a saved snapshot, and publish a version to the Agent Registry. Show owner, role, trigger, capabilities and version. Published versions are immutable; editing creates a draft.
3. Simulate a sensor event, filter area/confidence, retrieve mocked context/data, call the external LLM for structured threat analysis, and route LOW to record-only or MEDIUM/HIGH to notification, report draft and Analyst HITL.
4. Pause with LangGraph interrupt and SQLite-backed checkpoint. Approve resumes; Edit changes the draft and requires explicit approval; Reject ends without publishing a report. Persist the review decision and final edited content.
5. Persist the approved regional report before emitting its Approved Report event. This event starts the published Staff Agent, which combines it with seeded approved B/C reports and mocked context, performs synthesis, drafts a Commander report, and pauses for Staff HITL.
6. Only Staff approval makes the Commander report visible in the Commander report list. Keep source report links and reviewer provenance.
7. Show actual node execution status, input/output summaries, timing, errors and approvals inside Builder and in a dedicated Execution view. Refresh must recover waiting executions from backend state.
8. Situation Board shows sector cards, recent events and approved reports. Notifications stay inside the application.

## Scope boundaries

| Treatment | Components |
| --- | --- |
| Implement | Builder, definition validation/compilation, Registry, external LLM + Gateway, LangGraph runtime, durable checkpoints, HITL, report persistence/event linkage, trace |
| Mock | Login/permission data, Sensor Simulator, Data Fabric Search/Query, Situation Context, external regional report fixtures |
| Minimal | Static role filtering, in-app notifications, report viewer, Situation Board, Commander read-only view, audit history |
| Excluded unless explicitly requested | Kafka/message broker, Kubernetes, real GIS, real Data Fabric, real sensors, production auth, full RBAC/ABAC, local-model serving |

Do not add an administrative/office workflow, real MCP integrations, separate microservices, arbitrary code nodes, or elaborate Agent deployment approval. These are future examples/platform capabilities, not requirements for this week.

## Delivery order (five working days)

| Day | Reviewable outcome |
| --- | --- |
| 1 | App shell, Mock Login/Role Switch, static role policy, seeded data and Builder layout |
| 2 | Editable templates, node configuration, save/validation, Registry/published snapshots |
| 3 | FastAPI/LangGraph execution, external Model Gateway, trace, persisted interrupt/resume |
| 4 | Analyst and Staff approvals, Approved Report event linkage, report viewer and board |
| 5 | End-to-end acceptance, reject/edit/retry checks, restart recovery, rehearsal and fixes |

Prefer a narrow supported graph grammar over general-purpose orchestration. Use polling unless a stronger transport is demonstrably needed. No exact model ID or vendor is prescribed; choose one configured external provider with structured output and keep credentials on the backend. A labeled deterministic test provider is allowed for automated checks/rehearsal, but cannot count as the actual external-LLM demo.

## Done

All acceptance criteria in [DEMO_SCENARIO.md](DEMO_SCENARIO.md) pass. Builder changes reach execution, both approval gates stop publication, edits survive resume, rejected reports do not trigger downstream work, and the completed Commander report links to its approved regional inputs. Report tested behavior and remaining limitations honestly; do not count a visual-only animation as runtime integration.
