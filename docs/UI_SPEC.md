# Agent Builder Demo — UI Specification

Use [PRD.md](PRD.md) for scope, [ARCHITECTURE.md](ARCHITECTURE.md) for status/contracts and [DEMO_SCENARIO.md](DEMO_SCENARIO.md) for acceptance. Based on the main Notion plan and its UI 상세 - GPT child, linked in PRD.

## Design and screen map

Desktop-first internal platform, optimized for a 1440×900 presentation display and usable at 1280×720. Dark navy/charcoal surfaces, restrained borders, readable dense typography, minimal gradients. Reserve status colors for workflow state, threat and approval; pair colors with text/icons. Use Korean business labels with consistent domain names. Avoid exposing Python/StateGraph/SDK terminology as node names.

| Screen | Route | Access |
| --- | --- | --- |
| Login | /login | All demo roles |
| Dashboard | /dashboard | Role-specific summary |
| Agent Builder | /agents/:id/builder (new draft via Dashboard/Registry) | Analyst/Staff own role agents |
| Agent Registry | /agents | Analyst/Staff role-filtered agents |
| Execution | /executions and /executions/:id | Role/area-filtered executions |
| Situation Board | /situation | Analyst own area; Staff/Commander all seeded areas |

Approval drawer and report viewer are overlays, not extra primary screens. Commander report reading uses Dashboard/Situation Board plus report viewer; no Commander Builder.

## Shared shell and header Role Switch

Logged-in pages have a 56px header: product title left, page title/breadcrumb center, notifications and current role/area right. A 176–200px navigation rail links Dashboard, Builder/Registry, Execution and Situation Board where allowed. Builder may collapse the rail to preserve canvas width.

Header menu: Analyst A-12, Staff, Commander, Logout. Switching roles updates mock session and refetches role-scoped data; clears selected restricted entities, closes approval drawers and navigates to Dashboard if the current page is inaccessible. Prompt Save/Discard/Cancel for dirty Builder edits before switching. Switching does not cancel an execution, resume approval, or change the execution's original actor. Logout returns to Login.

## Login

Centered card, approximately 440px wide: title, prominent 'Demo / Mock Login' label, three role radio cards (A지역 분석관 / 정보·작전 참모 / 지휘관), selected role description and primary Login button. Analyst area is fixed to A-12 for the demo; Staff/Commander have multi-area context. No password form. On success open Dashboard; show an inline session error on failure.

## Dashboard

Top row: page heading, current role/area and Analyst/Staff '새 Agent 만들기'. Second row: compact counts for my agents, active executions and pending approvals. Main 2/3 width: my Agent cards and recent executions; right 1/3: in-app notifications and approval queue. Each card provides Open Builder and View Execution when applicable. Empty states link to the role's template.

Analyst sees A-12 sensor simulator action and Analyst review queue. Staff sees new approved regional reports and Staff review queue. Commander sees final Commander reports with time/threat and a Situation Board link; creation and approval controls are absent. Every alert links to the corresponding execution or report.

## Agent Builder — visual focus

```text
Header                                   Role / Area / Switch
Agent name · Draft/version       [Save] [Validate] [Publish]
+----------------+-----------------------------+------------------+
| Node Palette   | React Flow Canvas           | Config Panel     |
| ~200px         | flexible, largest area      | ~300px           |
| Trigger        | Trigger → Context → Data    | Selected node    |
| Data/Context   |              ↓              | Config / Output  |
| AI             |          AI → Condition     | [Apply]          |
| Logic/Control  |              ↓              |                  |
| Actions        |       Approval → Send       |                  |
+----------------+-----------------------------+------------------+
| [Test Run] Fixture ▼  execution ID / status [Open Execution]     |
| Expandable trace: steps | selected step input/output/error       |
+----------------------------------------------------------------+
```

Bottom test bar is always visible; expanded trace uses roughly 180–240px height. Panels scroll independently; keep canvas visible at 1280×720. Canvas supports drag/add or click-to-add, connect handles, select/configure, delete, pan, zoom and fit view. Named condition handles distinguish LOW and MEDIUM/HIGH. Load Analyst/Staff templates, but allow meaningful config/connection changes. No arbitrary-code node.

Palette role exposure:

| Group | Analyst | Staff |
| --- | --- | --- |
| Trigger | Sensor Event | Approved Report |
| Data/Context | Data Fabric Search/Query, Situation Context | Same + Approved Reports |
| AI | Threat Analysis | Situation Synthesis |
| Logic/Control | Event Filter, Condition, Human Approval (Analyst) | Human Approval (Staff) |
| Actions | Record Event, Notification, Report Generator, Send Report, Update Situation Board | Notification, Report Generator, Send Report, Update Situation Board |

If displayed, User Request is disabled with '추후 지원'. Commander has no palette. Out-of-role capabilities must not be selectable; backend validation also rejects them.

Config panel has Agent settings when no node is selected: name, role/goal, area, trigger, provider/model, version metadata. Node selection shows label, business description and type-specific fields:

- Sensor/Event Filter: area A-12, event type, minimum confidence (default 0.8).
- Data: fixture query/filter, visible mocked-data badge, output preview.
- AI: provider/model dropdown from backend configuration, system prompt, input source selections, fixed output schema name, temperature (default 0.2). No credential fields.
- Condition: LOW → record; MEDIUM/HIGH → approval path.
- Approval: assigned role and editable report fields; role is constrained to workflow type.
- Report/Send: REGIONAL or COMMANDER output and recipient label, constrained by workflow type.

Apply validates and changes the draft; Save persists it. Show dirty/saved state. Publish is blocked by validation errors and creates an immutable version; editing a published agent opens a new draft. Do not label publishing as execution approval. Test Run saves/validates a snapshot, selects an explicit fixture and starts a real execution. Disable duplicate starts while the request is pending.

Overlay actual node status on canvas: pending gray, running blue, waiting approval amber, succeeded green, skipped subdued, failed red. Use icons/text as well as color. Selecting a running node shows output/trace without editing the pinned execution. Approval waiting exposes '검토' in the bottom bar and on its node. No simulated progress when backend state is unavailable.

## Agent Registry

Top: role/area label, search, lifecycle/trigger filter and Create Agent. Below: table with Name, Owner, Area/Role, Version, Trigger, Capabilities, Lifecycle status and actions. Row opens a detail panel with workflow preview and Open Builder/Test/View Executions. Published subscriptions show Active; suspended versions do not receive new triggers. Keep Draft/Published/Suspended separate from execution and report approval statuses. Show seeded templates explicitly. Empty/loading/error states stay inside the table area.

## HITL approval drawer

Right drawer approximately 520–600px wide, full available height, shared by Builder and Execution. Header shows Analyst or Staff approval required, execution ID and waiting status. Body scrolls; footer with Reject / Edit / Approve remains fixed.

Display area, threat, sensor confidence where applicable, event details, AI analysis summary, evidence references and report draft. Staff additionally sees source regional reports and links to their approved originals. Draft starts read-only. Edit enables a text editor; changed content requires explicit '수정 내용 승인' (EDIT_APPROVE). Closing or saving an edit leaves execution waiting. Reject may include a reason and ends the run without report publication. Approve submits unchanged content.

Disable decision buttons during submission and after a decision; refresh on stale-decision conflict. Failure keeps the drawer/content available with retry guidance. A wrong-role view may inspect permitted information but never offers an enabled approval action. Show approver/time/decision after success and resume node visualization from backend state. Do not expose unapproved Commander drafts to Commander.

## Execution view

List: filters for agent, status and role/area; columns ID, Agent/version, Trigger, Started, Status, and approval action. Detail header: execution ID, pinned version, initiating role, status and links to source report/child execution where present. Left approximately 60%: read-only graph with live node statuses. Right 40%: chronological trace and selected step details (input, output, timing, error). Footer/panel: linked reports and audit decisions.

Waiting state provides the same approval drawer. Refresh restores state from persisted execution/checkpoint. FAILED identifies the step and allows a clearly labeled new test execution; never silently replays a previously approved report action. LOW and filtered events explain why no report was created.

## Situation Board and report viewer

Top: role/area scope and last updated time. Sector card row: A-12, B-07, C-03 with threat, recent event count and latest approved report time; Analyst sees A-12 only. Lower two columns: Recent Events and Approved Reports. Use sector cards, not a real map/GIS. Threat summaries derive from approved reports; raw event processing/waiting badges must not imply approval.

Report click opens a read-only viewer with kind, title, approved content, approver/time, source execution and original report links. Staff can inspect approved regional inputs. Commander report list includes only final approved COMMANDER reports; draft and rejected content never appear as final. B/C fixtures carry a visible 'Demo seed' badge. Board refresh after finalization uses backend records, not local optimistic fake reports.

## Shared failure and accessibility behavior

Preserve valid user input on API errors. Show contextual loading/empty/error states; unavailable LLM reports a real failure. Label deterministic rehearsal mode prominently. Use keyboard-focusable buttons, explicit labels and visible focus; preserve readable contrast and provide text for all status colors. Keep decorative work secondary to Builder clarity and reliable live demonstration.
