# Workflow Builder Demo — Product Requirements

## Source and authority

Planning source: [세미나 준비안](https://www.notion.so/3d5a13906bdf812ebfb8d6a5a3a0c967), fetched 2026-09-09; reported last edit 2026-09-08T08:36:53.650Z. UI companion: [UI 상세 - GPT](https://www.notion.so/3d5a13906bdf80a79249f84d8c37d367), reported last edit 2026-09-08T08:15:54.848Z.

These documents translate the retrieved planning pages and the user's explicit scope into implementable requirements. Explicit user decisions take precedence over broader platform aspirations in Notion. Routes, persistence contracts, seed fixtures and lifecycle simplifications below are implementation defaults, not verbatim source requirements. PRD owns scope, ARCHITECTURE owns runtime contracts, UI_SPEC owns interactions, and DEMO_SCENARIO owns acceptance. Read all four together.

## Goal and constraints

Build a **1-week seminar demo** for a roughly 40-minute presentation, with about 11 minutes for the live demo. Show that users can compose role-specific workflows in one shared Workflow Builder, run them, review AI output, and connect workflows through approved reports.

The visual focus is the Workflow Builder and the separate ReAct Agent Builder, not the Situation Board. Both Analyst and Staff use role-scoped builders and registries. Workflows execute declared edges; agents select among connected tools to achieve a user goal.

Required stack: React + TypeScript + React Flow frontend; FastAPI + LangGraph + SQLite backend/runtime. Actual demo reasoning uses an external LLM through a Model Gateway/provider abstraction. Future local models require a provider implementation, not a workflow redesign; local serving is out of scope.

## Users and role experience

| Role | Available experience | Review responsibility |
| --- | --- | --- |
| 분석관 | 경기도 파주시 센서 이벤트, 위협 분석, 본인 워크플로우와 지역 보고서 | 지역 보고서 승인 |
| 정보·작전 참모 | 승인된 지역 보고 수집, 다지역 위협 종합, 본인 워크플로우 | 지휘관 보고서 승인 |
| 지휘관 | 지도, 참모 종합 판단, 보고서 도착 알림과 최종 보고서 | 빌더 편집·승인 권한 없음 |

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
8. Situation Board shows an OpenStreetMap base map for 경기도 파주시, 경기도 연천군 and 강원특별자치도 철원군 together with approved reports. 지휘관 화면은 원시 센서 이벤트 대신 최신 참모 종합보고의 위협 수준, 핵심 판단, 참조 지역과 보고 시각을 표시한다. Notifications stay inside the application.

## ReAct 에이전트 첫 구현

워크플로우와 별도로 에이전트 빌더와 에이전트 레지스트리를 제공한다. 사용자는 역할별 **연동 카탈로그**에서 데이터와 외부 시스템을 선택하고, 선택한 연동이 제공하는 기능 도구만 에이전트에 허용한다. 카탈로그에는 연동 이름, 설명, `DATA`/`SYSTEM`, `MOCK`/`LIVE`, `READ`/`SEARCH`/`WRITE`와 승인 필요 여부를 표시한다. 모델, 시스템 프롬프트와 최대 반복 횟수를 설정해 게시하며, 게시된 에이전트는 레지스트리에서 채팅 화면으로 열 수 있다.

기본 시나리오는 “파주시 최근 이상 징후를 조사하고 지휘관 브리핑을 작성해줘”이다. ReAct 런타임은 모델에게 매 반복의 다음 행동을 선택하게 하고, 선택된 작전 DB 조회·기존 보고서 검색·지역 정보 조회·근거 종합 결과를 다시 관찰로 제공한다. 연결된 도구 전체나 고정 순서를 강제하지 않으며, 현재 요청과 대화 컨텍스트만으로 답할 수 있으면 도구 호출 없이 완료할 수 있다. 런타임은 허용 목록, 중복 호출과 종합 도구의 최소 입력 계약만 검증한다. 화면은 비공개 chain-of-thought가 아니라 공개 가능한 판단 요약, 선택한 도구, 관찰 결과와 최종 응답 청크를 스트리밍하고 분석 완료 상태로 종료한다. 에이전트 HITL은 후속 범위다.

정보·작전 참모에게는 기본 게시 에이전트 `주간 위협 수준 비교 에이전트`를 제공한다. “이번 주 위협 수준이 지난주보다 높아졌는지 근거와 함께 설명해줘.”라는 요청에 현재 작전 관측과 지난주 승인 보고 기준을 조회하고, 주간 위협 변화와 근거 식별자를 포함한 비교 결과를 생성한다.

에이전트 채팅은 사용자별·에이전트별 세션으로 저장한다. 같은 세션의 후속 요청에는 최근 완료 대화 3턴만 모델 컨텍스트로 전달하고, 새 대화에서는 이전 컨텍스트를 사용하지 않는다. 사용자는 세션을 선택해 대화를 복원하거나 새로 만들고 삭제할 수 있다.

첫 구현의 외부 시스템은 SQLite 데이터와 명시적으로 표시된 mock 어댑터다. 실제 MCP 서버 연결, 임의 도구 등록, 장기 메모리와 다중 에이전트 협업은 후속 범위다.

워크플로우 빌더는 기존의 역할별 최소 노드 수를 유지한다. 대신 팔레트와 노드 설정에서 각 노드가 사용하는 데이터 또는 외부 시스템과 mock 상태를 보여준다. 분석관·참모는 작전 관측 데이터, 승인 보고서 저장소, 지역 상황 정보와 지휘 보고 체계를 사용하고, 행정병은 인사행정 데이터, 부대 일정·규정과 부대 인트라넷을 사용한다. 지휘관은 연동을 편집하지 않는다.

## Scope boundaries

| Treatment | Components |
| --- | --- |
| Implement | Workflow Builder/Registry, ReAct Agent Builder/Registry/Chat, external LLM + Gateway, LangGraph workflow runtime, agent step and result streaming, workflow HITL, report persistence/event linkage, trace |
| Mock | Login/permission data, Sensor Simulator, Data Fabric Search/Query, Situation Context, external regional report fixtures |
| Minimal | Static role filtering, in-app notifications, report viewer, Situation Board, Commander read-only view, audit history |
| Excluded unless explicitly requested | Kafka/message broker, Kubernetes, advanced military GIS layers, real Data Fabric, real sensors, production auth, full RBAC/ABAC, local-model serving |

행정병용 병역관리·인사행정 데모를 포함한다. 실제 MCP 연동, 별도 마이크로서비스, 임의 코드 노드와 복잡한 Workflow 배포 승인은 후속 범위다.

## 행정병 유즈케이스

- `ADMIN` 데모 사용자는 본인 소유 워크플로우·ReAct 에이전트와 인사행정 데이터만 사용한다.
- 정기 휴가 신청이 들어오면 잔여 휴가와 신청 기간의 부대 일정을 조회하고 LLM이 승인용 요약을 작성한다.
- LangGraph HITL에서 행정병이 승인하면 모의 부대 인트라넷 등록을 생성하고, 반려하면 등록하지 않는다.
- “이번 주차 외출/외박 현황 보고 작성해줘” 요청은 인사행정 DB, 부대 일정과 관련 규정을 필요한 순서로 조회해 주간 보고서를 스트리밍한다.
- 군번·성명 등 개인정보는 데모용 가상 데이터이며 처리 목적에 필요한 범위로만 표시한다.

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
