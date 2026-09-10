# Workflow Builder Demo — Product Requirements

## Source and authority

Planning source: [세미나 준비안](https://www.notion.so/3d5a13906bdf812ebfb8d6a5a3a0c967), fetched 2026-09-09; reported last edit 2026-09-08T08:36:53.650Z. UI companion: [UI 상세 - GPT](https://www.notion.so/3d5a13906bdf80a79249f84d8c37d367), reported last edit 2026-09-08T08:15:54.848Z.

These documents translate the retrieved planning pages and the user's explicit scope into implementable requirements. Explicit user decisions take precedence over broader platform aspirations in Notion. Routes, persistence contracts, seed fixtures and lifecycle simplifications below are implementation defaults, not verbatim source requirements. PRD owns scope, ARCHITECTURE owns runtime contracts, UI_SPEC owns interactions, and DEMO_SCENARIO owns acceptance. Read all four together.

## Goal and constraints

Build a **1-week seminar demo** for a roughly 40-minute presentation, with about 11 minutes for the live demo. Show that users can compose role-specific workflows in one shared Workflow Builder, run them, review AI output, and connect workflows through approved reports.

The visual focus is the Workflow Builder, not the Situation Board. Both Analyst and Staff use the same Builder / Registry / Runtime with different definitions, triggers, capabilities and reviewers.

Required stack: React + TypeScript + React Flow frontend; FastAPI + LangGraph + SQLite backend/runtime. Actual demo reasoning uses an external LLM through a Model Gateway/provider abstraction. Future local models require a provider implementation, not a workflow redesign; local serving is out of scope.

## Users and role experience

| Role | Available experience | Review responsibility |
| --- | --- | --- |
| 분석관 | 경기도 파주시 센서 이벤트, 위협 분석, 본인 워크플로우와 지역 보고서 | 지역 보고서 승인 |
| 정보·작전 참모 | 승인된 지역 보고 수집, 다지역 위협 종합, 본인 워크플로우 | 지휘관 보고서 승인 |
| 지휘관 | 지도, 최근 센서 이벤트, 보고서 도착 알림과 최종 보고서 | 빌더 편집·승인 권한 없음 |

Provide Mock Login and a persistent header Role Switch. Session fields: user_id, role, area, permissions. Role and area determine visible workflows, nodes, data and review actions through a small static policy. This demonstrates role experience; it is not production authentication or a full authorization engine.

Workflow Registry는 현재 세션의 사용자 ID를 기준으로 소유 워크플로우만 표시한다. 분석관과 참모는 자신의 워크플로우를 생성·편집·게시·삭제할 수 있으며 기본 제공 워크플로우는 삭제할 수 없다. 지휘관은 Builder와 Registry에 접근하지 않고 승인된 지휘관 보고서만 열람한다. 역할 선택과 권한 설명은 사용자 화면에서 한국어로 표시한다.

모든 역할이 접근할 수 있는 사용 매뉴얼 화면을 제공한다. 매뉴얼은 역할별 권한, 접근 가능한 메뉴, 사용할 수 있는 노드, 워크플로우 생성부터 센서 실행·승인·보고서 확인까지의 순서를 설명한다.

## Required behavior

데모의 1차 진입점은 좌측 메뉴 최하단의 **센서 입력** 화면이다. 분석관은 파주시 감시 센서의 탐지 개체 수(1~12)와 신뢰도(0.50~0.99)를 조절한 뒤 이벤트를 전송한다. 전송값은 게시된 분석 워크플로우의 실제 LangGraph 실행과 외부 LLM 분석 입력으로 전달되어야 한다.

노드 팔레트는 역할별 핵심 6개 노드만 제공한다. AI 노드가 판단 결과와 승인용 보고서 초안을 함께 생성한다. Action은 계산이나 문서 작성이 아니라 승인 이후 애플리케이션 상태를 변경하는 단계다. 분석관은 `감시 센서 이벤트 → 이벤트 조건 확인 → 작전 정보 조회 → 위협 분석·초안 생성 → 분석관 검토·승인 → 지역 보고서 발행`, 참모는 `승인 지역보고 접수 → 승인 지역보고 수집 → 접경지역 위협 종합·초안 생성 → 참모 검토·승인 → 지휘관 보고서 발행` 흐름을 사용한다.

1. Create a new role-specific Workflow from the Dashboard or Workflow Registry. The creation form requires name, role, monitoring area and description, then opens a blank Builder canvas.
2. Compose workflows by adding, connecting, configuring and removing business-capability nodes on React Flow. Include Analyst and Staff templates as optional starting points; graph edits and edge topology must affect validated LangGraph runtime behavior.
3. Save Workflow Definitions as drafts, validate them, test a saved draft snapshot, and publish an immutable version to the Workflow Registry. Show owner, role, trigger, capabilities and version. Editing a published Workflow creates or updates its draft without modifying published versions.
4. Compile the selected saved or published definition into a real LangGraph `StateGraph`. Accept an adjustable sensor event, filter area/confidence, retrieve mocked context/data, call the configured Model Gateway, create a report draft and pause for Analyst HITL.
5. Pause with LangGraph `interrupt()` and a SQLite-backed checkpointer. Approve resumes the same thread with `Command(resume=...)`; Edit changes the draft and requires explicit approval; Reject ends without publishing a report. Persist the review decision and final edited content.
5. Persist the approved regional report before emitting its Approved Report event. This event starts the published Staff Workflow, which combines it with seeded approved B/C reports and mocked context, performs synthesis, drafts a Commander report, and pauses for Staff HITL.
6. 참모 승인 후에만 지휘관 보고서를 저장하고 지휘관에게 도착 알림을 생성한다. 지휘관은 알림을 클릭해 보고서를 열며, 보고서는 원본 실행과 승인자 정보를 유지한다.
7. Show actual node execution status, input/output summaries, timing, errors and approvals inside Builder and in a dedicated Execution view. Refresh must recover waiting executions from backend state.
8. Situation Board shows an OpenStreetMap base map for 경기도 파주시, 경기도 연천군 and 강원특별자치도 철원군 together with recent events and approved reports. Notifications stay inside the application.

## Scope boundaries

| Treatment | Components |
| --- | --- |
| Implement | Builder, definition validation/compilation, Registry, external LLM + Gateway, LangGraph runtime, durable checkpoints, HITL, report persistence/event linkage, trace |
| Mock | Login/permission data, Sensor Simulator, Data Fabric Search/Query, Situation Context, external regional report fixtures |
| Minimal | Static role filtering, in-app notifications, report viewer, Situation Board, Commander read-only view, audit history |
| Excluded unless explicitly requested | Kafka/message broker, Kubernetes, advanced military GIS layers, real Data Fabric, real sensors, production auth, full RBAC/ABAC, local-model serving |

Do not add an administrative/office workflow, real MCP integrations, separate microservices, arbitrary code nodes, or elaborate Workflow deployment approval. These are future examples/platform capabilities, not requirements for this week.

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
