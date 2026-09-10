# Workflow Builder Demo — UI Specification

Use [PRD.md](PRD.md) for scope, [ARCHITECTURE.md](ARCHITECTURE.md) for status/contracts and [DEMO_SCENARIO.md](DEMO_SCENARIO.md) for acceptance. Based on the main Notion plan and its UI 상세 - GPT child, linked in PRD.

## Design and screen map

Desktop-first internal platform, optimized for a 1440×900 presentation display and usable at 1280×720. Use white surfaces, pale gray page backgrounds, restrained borders and high-contrast dark typography. Reserve status colors for workflow state, threat and approval; pair colors with text/icons. Use Korean business labels with consistent domain names. Avoid exposing Python/StateGraph/SDK terminology as node names.

| Screen | Route | Access |
| --- | --- | --- |
| Login | /login | All demo roles |
| Dashboard | /dashboard | 분석관·참모 요약; 지휘관에게는 상황판 단일 메뉴로 표시 |
| Workflow Builder | /builder and /agents/:id/builder (new draft via Dashboard/Registry) | Analyst/Staff own role workflows |
| Workflow Registry | /agents | Analyst/Staff role-filtered workflows |
| Execution | /executions and /executions/:id | Role/area-filtered executions |
| Situation Board | /situation | 분석관·참모; 지휘관 접근은 /dashboard 상황판으로 이동 |
| 센서 입력 | /sensor | Analyst; 좌측 기본 메뉴의 가장 아래 |
| 사용 매뉴얼 | /manual | 모든 역할 |

센서 입력 화면은 센서 ID와 지역을 보여주고, 탐지 개체 수와 신뢰도를 슬라이더로 조절하며, 이벤트 종류를 선택할 수 있어야 한다. `센서 이벤트 전송` 후 생성된 실행 ID와 상태를 표시하고 실행 상세로 이동할 수 있어야 한다. 실제 센서 대신 사용하는 데모 입력기임을 명시한다.

Approval drawer와 report viewer는 overlay로 사용한다. 지휘관은 /dashboard의 상황판과 보고서 viewer만 사용하며 별도의 대시보드나 Builder는 제공하지 않는다.

## Shared shell and header Role Switch

로그인 후 화면은 56px 헤더와 좌측 메뉴를 사용한다. 분석관·참모는 대시보드와 상황판을 각각 사용한다. 지휘관 좌측 메뉴는 /dashboard를 가리키는 상황판 하나만 표시하고 별도 /situation 메뉴는 숨긴다.

헤더 역할 선택에는 파주지역 분석관, 정보·작전 참모, 지휘관을 한국어로 표시한다. 역할을 바꾸면 mock session과 역할별 데이터를 다시 불러오고 해당 역할의 기본 화면으로 이동한다. 지휘관의 기본 화면 명칭은 상황판이다.

## Login

Centered card, approximately 440px wide: title, prominent 'Demo / Mock Login' label, three role radio cards (파주지역 분석관 / 정보·작전 참모 / 지휘관), selected role description and primary Login button. Analyst area is fixed to 경기도 파주시 for the demo; Staff/Commander have multi-area context. No password form. On success open Dashboard; show an inline session error on failure.

## Dashboard

분석관과 참모 대시보드는 현재 역할·지역, 내 워크플로우, 운영 상태, 승인 대기 건수와 앱 내 알림을 보여준다. 최근 실행 목록은 표시하지 않는다. 승인 대기가 있으면 상단 강조 배너와 헤더 종 아이콘의 건수 배지를 표시한다.

Analyst sees the 경기도 파주시 sensor simulator action and Analyst review queue. Staff sees new approved regional reports and Staff review queue. Commander sees final Commander reports with time/threat and a Situation Board link; creation and approval controls are absent. Every alert links to the corresponding execution or report.

## Workflow Builder — visual focus

```text
Header                                   Role / Area / Switch
Workflow name · Draft/version       [Save] [Validate] [Publish]
+----------------+-----------------------------+------------------+
| Node Palette   | React Flow Canvas           | Config Panel     |
| ~200px         | flexible, largest area      | ~300px           |
| Trigger        | Trigger → Filter → Context  | Selected node    |
| Data/Context   |              ↓              | Config / Output  |
| AI             |       AI 분석·초안 생성      | [Apply]          |
| Logic/Control  |              ↓              |                  |
| Actions        |       Approval → Send       |                  |
+----------------+-----------------------------+------------------+
| [Test Run] Fixture ▼  execution ID / status [Open Execution]     |
| Expandable trace: steps | selected step input/output/error       |
+----------------------------------------------------------------+
```

Bottom test bar is always visible; expanded trace uses roughly 180–240px height. Panels scroll independently; keep canvas visible at 1280×720. Canvas supports drag/add or click-to-add, connect handles, select/configure, delete, pan, zoom and fit view. Load Analyst/Staff templates, but allow meaningful config/connection changes. No arbitrary-code node.

Palette role exposure:

| Group | Analyst | Staff |
| --- | --- | --- |
| Trigger | Sensor Event | Approved Report |
| Data/Context | 작전 정보 조회 | 승인 지역보고 수집, 접경지역 작전상황 조회 |
| AI | Threat Analysis | Situation Synthesis |
| Logic/Control | Event Filter, Human Approval (Analyst) | Human Approval (Staff) |
| Actions | 지역 보고서 발행 | 지휘관 보고서 발행 |

If displayed, User Request is disabled with '추후 지원'. Commander has no palette. Out-of-role capabilities must not be selectable; backend validation also rejects them.

Config panel has Workflow settings when no node is selected: name, role/goal, area, trigger, provider/model, version metadata. Node selection shows label, business description and type-specific fields:

Input/Output state 계약은 캔버스를 단순하게 유지하기 위해 노드를 선택했을 때 설정 패널에만 표시한다. 실행 상세에서는 같은 노드의 실제 input_summary와 output_summary를 함께 보여 Builder 설계와 LangGraph state 변화를 대응시킬 수 있어야 한다. AI 노드는 백엔드가 허용한 모델 목록에서 모델을 선택할 수 있고, 선택값은 Workflow Definition에 저장되어 실제 호출에 사용된다.

지휘관 상황판은 완료 실행 목록을 표시하지 않고 지도, 최근 센서 이벤트와 지휘관 대상 알림을 함께 표시한다.

분석관·참모 대시보드에서도 최근 실행 목록은 표시하지 않는다. 승인 대기가 있으면 페이지 상단에 높은 대비의 승인 요청 배너를 표시하고 헤더 종 아이콘에 대기 건수 배지를 붙인다. 배너와 종 아이콘은 실행 모니터링으로 이동한다.

- Sensor/Event Filter: area 경기도 파주시, event type, minimum confidence (default 0.8).
- Data: fixture query/filter, visible mocked-data badge, output preview.
- AI: provider/model dropdown from backend configuration, system prompt, input source selections, fixed output schema name, temperature (default 0.2). No credential fields.
- Approval: assigned role and editable report fields; role is constrained to workflow type.
- Report/Send: REGIONAL or COMMANDER output and recipient label, constrained by workflow type.

Apply validates and changes the draft; Save persists it. Show dirty/saved state. Publish is blocked by validation errors and creates an immutable version; editing a published workflow opens a new draft. Do not label publishing as execution approval. Test Run saves/validates a snapshot, selects an explicit fixture and starts a real execution. Disable duplicate starts while the request is pending.

Overlay actual node status on canvas: pending gray, running blue, waiting approval amber, succeeded green, skipped subdued, failed red. Use icons/text as well as color. Selecting a running node shows output/trace without editing the pinned execution. Approval waiting exposes '검토' in the bottom bar and on its node. No simulated progress when backend state is unavailable.

## Workflow Registry

Top: role/area label, search, lifecycle/trigger filter and Create Workflow. Below: table with Name, Owner, Area/Role, Version, Trigger, Capabilities, Lifecycle status and actions. Row opens a detail panel with workflow preview and Open Builder/Test/View Executions. Published subscriptions show Active; suspended versions do not receive new triggers. Keep Draft/Published/Suspended separate from execution and report approval statuses. Show seeded templates explicitly. Empty/loading/error states stay inside the table area.

Create Workflow opens a modal with Workflow name, description, role, monitoring area and starting point (Blank, Analyst template or Staff template). Role controls the available templates and node palette. Submit creates a DRAFT and navigates to its Builder. A blank Workflow has no nodes or edges and cannot publish until validation passes. The Builder navigation item opens the current role's most recently edited draft, or the creation modal when none exists.

Publishing shows a concise validation summary and creates an immutable numbered version. Registry actions clearly distinguish `초안 편집`, `게시 버전 보기`, `시험 실행` and `게시`. A published Workflow can be used by the sensor/report subscriptions immediately; later canvas edits remain in the draft until another version is published.

## HITL approval drawer

Right drawer approximately 520–600px wide, full available height, shared by Builder and Execution. Header shows Analyst or Staff approval required, execution ID and waiting status. Body scrolls; footer with Reject / Edit / Approve remains fixed.

Display area, threat, sensor confidence where applicable, event details, AI analysis summary, evidence references and report draft. Staff additionally sees source regional reports and links to their approved originals. Draft starts read-only. Edit enables a text editor; changed content requires explicit '수정 내용 승인' (EDIT_APPROVE). Closing or saving an edit leaves execution waiting. Reject may include a reason and ends the run without report publication. Approve submits unchanged content.

Disable decision buttons during submission and after a decision; refresh on stale-decision conflict. Failure keeps the drawer/content available with retry guidance. A wrong-role view may inspect permitted information but never offers an enabled approval action. Show approver/time/decision after success and resume node visualization from backend state. Do not expose unapproved Commander drafts to Commander.

## Execution view

List: filters for workflow, status and role/area; columns ID, Workflow/version, Trigger, Started, Status, and approval action. Detail header: execution ID, pinned version, initiating role, status and links to source report/child execution where present. Left approximately 60%: read-only graph with live node statuses. Right 40%: chronological trace and selected step details (input, output, timing, error). Footer/panel: linked reports and audit decisions.

Waiting state provides the same approval drawer. Refresh restores state from persisted execution/checkpoint. FAILED identifies the step and allows a clearly labeled new test execution; never silently replays a previously approved report action. LOW and filtered events explain why no report was created.

## Situation Board and report viewer

역할·지역 범위와 실제 OpenStreetMap 지도를 표시한다. 파주시, 연천군, 철원군을 선택할 수 있고 분석관은 파주시만 본다. 일반 상황판에서는 지도 아래 승인 보고서를 열람할 수 있다. 지휘관 상황판은 승인 지역 보고서 목록 대신 최근 센서 이벤트와 클릭 가능한 최종 보고서 도착 알림을 표시한다. 고급 군사 GIS layer는 데모 범위에서 제외한다.

보고서 클릭은 종류, 제목, 승인 내용, 승인자·시각과 원본 실행을 읽기 전용 상세로 연다. 참모는 승인된 지역 입력을 확인할 수 있다. 지휘관 상황판은 지도, 최근 센서 이벤트, 보고서 도착 알림을 보여주며 승인 지역 보고서 카드 목록은 표시하지 않는다. 참모 승인으로 최종 보고서가 전달되면 도착 알림을 만들고, 알림을 클릭하면 해당 COMMANDER 보고서 상세를 연다. 초안과 반려된 내용은 표시하지 않는다.

## Shared failure and accessibility behavior

Preserve valid user input on API errors. Show contextual loading/empty/error states; unavailable LLM reports a real failure. Label deterministic rehearsal mode prominently. Use keyboard-focusable buttons, explicit labels and visible focus; preserve readable contrast and provide text for all status colors. Keep decorative work secondary to Builder clarity and reliable live demonstration.
