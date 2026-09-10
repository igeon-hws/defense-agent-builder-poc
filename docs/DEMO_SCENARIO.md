# Workflow Builder Demo — Scenario and Acceptance

## 센서 입력 및 실제 LLM 확인

1. 분석관으로 로그인하고 좌측 메뉴 최하단의 `센서 입력`을 연다.
2. 탐지 개체 수와 신뢰도를 조절하고 이벤트를 전송한다.
3. 실행 상세에서 입력값과 외부 LLM의 구조화 위협 분석 결과를 확인한다.
4. API 키 누락 또는 공급자 오류 시 승인 초안을 만들지 않고 실행이 `FAILED`가 되는지 확인한다.

Read [PRD.md](PRD.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [UI_SPEC.md](UI_SPEC.md) before implementing or rehearsing. This is the executable demonstration contract, not a claim that the repository is already implemented.

## Preparation

- Run React frontend and FastAPI/LangGraph backend with SQLite persistence and configured external LLM credentials. Check provider connectivity before presenting. Record the provider/model used without exposing secrets.
- Seed a 경기도 파주시 Analyst, Staff and Commander mock identities; Analyst and Staff editable templates; mock Situation Context/Data Fabric evidence; preapproved 경기도 연천군 MEDIUM and 강원특별자치도 철원군 LOW regional reports marked as demo fixtures.
- 연천군/철원군 seeding must not trigger Staff runs. Their preapproved status represents external historical input; it does not bypass approval for the newly generated 파주시 report.
- Publish one Staff Workflow subscription before the Analyst report is approved. Ensure one active Analyst 경기도 파주시 subscription. Use an isolated demo dataset with no previous pending runs; any reset must be explicit and limited to demo data.
- Main sensor fixture below targets MEDIUM/HIGH; do not force an external model result into HIGH. Rehearse with suitable evidence/prompt. If the actual model returns LOW, display that branch honestly and choose a separately labeled test fixture to demonstrate approval. Deterministic test mode cannot satisfy the live external-provider criterion.

```json
{
  "sensor_id": "파주-감시센서-03",
  "type": "이동체 감지",
  "area": "경기도 파주시",
  "object_count": 4,
  "confidence": 0.94
}
```

The backend adds a unique event ID and timestamp. Mock evidence includes three referenced historical observations. Use fictional demonstration data throughout.

## Main flow (about 11 minutes)

| Time | Presenter action | Required visible/system result |
| --- | --- | --- |
| 0:00–1:00 | Login as 파주지역 Analyst; open 파주 감시·위협분석 Workflow | Role-filtered Dashboard, Analyst palette, editable template |
| 1:00–3:00 | Show node composition; edit event confidence/prompt, Apply, Save, Validate and Publish | Saved/published definition reflects the edit; role, model and version visible |
| 3:00–4:30 | 센서 입력에서 규모/신뢰도를 조절해 전송; 실행 상세 열기 | 감시 센서 → 조건 확인 → 작전 정보 → 실제 LLM 위협 분석 순서가 trace에 표시 |
| 4:30–6:00 | Inspect MEDIUM/HIGH alert and approval drawer; edit one report sentence and explicitly approve | Draft pauses at WAITING_FOR_ANALYST_APPROVAL; then same execution resumes with edited content |
| 6:00–7:00 | Inspect approved 파주시 report; switch header to Staff | Report persisted, event dispatched, exactly one linked Staff run starts automatically |
| 7:00–9:00 | Open Staff Builder/execution and inspect source reports | New A report + seeded B/C reports → collection/classification → context/search → Situation Synthesis → Commander draft |
| 9:00–10:00 | Inspect WAITING_FOR_STAFF_APPROVAL and approve | Staff decision resumes same run; final COMMANDER report persisted; no recursive Staff trigger |
| 10:00–11:00 | 지휘관으로 전환하고 보고서 도착 알림 클릭 | 지도·센서 이벤트·도착 알림이 보이고, 알림에서 최종 보고서와 승인자·원본 실행을 확인 |

Before the main flow, demonstrate creation in under one minute: choose `새 Workflow`, enter a name and area, select Blank, add the supported trigger/data/AI/approval/report nodes, connect their handles, save, validate and publish v1. Start a test from v1 and show that the execution detail uses the same pinned graph. Keep the seeded Workflow available as a recovery path for the live seminar.

Each AI node produces its role-specific draft before approval. After each approval, the publication Action persists the approved content and Situation Board reflects persisted records. Publication means in-app delivery. Execution view provides cross-links from the regional report to the Staff run and from the Commander report to its source reports.

## Branches to verify before presenting

1. **낮은 규모 입력:** LLM이 반환한 위협 수준과 근거를 그대로 표시하며 임의로 HIGH로 바꾸지 않는다.
2. **Filtered event:** Wrong area or confidence below 0.8 finishes with a filtered reason before AI analysis; no downstream report.
3. **Analyst Reject:** Pause, reject → REJECTED; audit decision preserved; no new regional report, event or Staff execution.
4. **Staff Reject:** Existing approved regional inputs remain unchanged; Staff run → REJECTED; no Commander report.
5. **Edit without approve:** Edit or close drawer, refresh → execution still waiting; no final report. Approve edited draft → exact edited content survives persistence.
6. **Refresh/restart:** Refresh browser and restart backend while waiting at each approval gate; recover same execution/thread and pending draft; decision resumes once without rerunning the prior LLM analysis.
7. **Duplicate/recovery:** Repeat approval submission/event dispatch, including recovery after a stored decision or report commit → no duplicate decision, final report or Staff run. Conflicting/stale decisions are rejected clearly.
8. **Provider error:** Timeout/invalid structured output → visible FAILED step after bounded retries, with no auto-approval, fake success or downstream report.
9. **Role switch:** Switch away during approval → original execution context stays fixed; wrong role cannot approve or fetch restricted drafts. Switch back → pending review remains available.

## Explicit acceptance criteria

| ID | Given / When | Pass condition |
| --- | --- | --- |
| AC-01 | Login/switch through all three roles | Correct workflow/node/data scope; Commander read-only; no production login infrastructure |
| AC-02 | 지원 노드, edge와 설정을 변경하고 저장·새로고침 | 그래프와 설정이 유지되고 실행에 반영된다. 잘못된 endpoint, 단일 시작점 위반, 승인·발행 노드 누락은 검증에서 실패한다. |
| AC-02A | Create a blank role-compatible Workflow | A new DRAFT is persisted, opens in Builder, survives refresh, and exposes only role-compatible nodes |
| AC-02B | Connect, validate and publish the new Workflow | An immutable version snapshot is created; Registry shows it and the published graph can start a real LangGraph execution |
| AC-03 | Publish then edit an Workflow while a run is paused | Registry shows version/owner/trigger; paused run retains original snapshot |
| AC-04 | Start the main Analyst fixture in actual-demo mode | External Gateway call produces validated output; mocked inputs are labeled; real node trace updates in Builder and Execution |
| AC-05 | Analyst run reaches Human Approval | Durable WAITING_FOR_ANALYST_APPROVAL; no regional final report/event before explicit approval |
| AC-06 | Edit and approve Analyst draft | Same thread resumes; exact edited content, actor and timestamp are persisted in the approved REGIONAL report |
| AC-07 | Commit the new regional report | Exactly one report event starts exactly one active Staff execution; source report ID matches persisted 파주시 output |
| AC-08 | Staff synthesis executes | New 파주시 and approved 연천군/철원군 fixture IDs are recorded as inputs; draft shows synthesis/evidence and pauses at WAITING_FOR_STAFF_APPROVAL |
| AC-09 | 참모가 승인 | 같은 참모 thread가 재개되고 COMMANDER 보고서와 도착 알림이 한 건 생성된다. 지휘관은 알림을 클릭해 보고서를 연다. |
| AC-10 | Reject at either approval gate | Run ends REJECTED; no corresponding final report/downstream action; decision trace remains |
| AC-11 | LOW/filtered fixture runs | Clearly recorded outcome, no accidental approval/report/Staff launch |
| AC-12 | Refresh/restart during either pending review | Same checkpoint/draft recover, same execution resumes; no duplicated pre-approval model call or publishing |
| AC-13 | Duplicate decision/event or crash-window recovery | Unique report and Staff execution invariants hold; stale/conflicting reviews fail visibly |
| AC-14 | Switch roles with dirty graph or waiting review | Save/Discard/Cancel protects edits; role scope refetches; original runtime actor unchanged; backend rejects wrong-role review |
| AC-15 | 지휘관 상황판에서 최종 보고 확인 | 지휘관에게 대시보드·상황판 중복 메뉴가 없고 상황판 단일 메뉴에서 지도, 최근 센서 이벤트와 보고서 도착 알림을 확인한다. |
| AC-16 | Fail the external provider | Clear failed trace with bounded retry; no fabricated output, report or auto-approval |
| AC-17 | 에이전트 빌더에서 도구·모델·프롬프트·반복 제한을 변경하고 게시 | 설정이 저장되고 레지스트리에서 게시 상태와 연결 도구 수를 확인한다. |
| AC-18 | 기본 ReAct 에이전트에 파주시 조사 요청 입력 | 실제 모델이 다음 행동을 선택하고 DB 조회, 보고서 검색, 지역 정보, 근거 종합의 판단 요약과 관찰이 순차 스트리밍된다. |
| AC-19 | ReAct 에이전트가 최종 브리핑 생성 | 응답 청크가 스트리밍되고 실행이 COMPLETED가 되며 최종 내용이 저장된다. 실행 전 입력 중인 프롬프트는 대화 기록에 미리 표시되지 않는다. |
| AC-20 | 채팅 세션 컨텍스트 관리 | 같은 세션의 후속 요청은 최근 완료 3턴을 참조하고, 새 세션은 빈 컨텍스트로 시작한다. 세션 선택 시 기록이 복원되며 삭제 시 해당 실행과 이벤트도 제거된다. |
| AC-21 | 요청별 ReAct 도구 선택 | 단순 후속 요약은 도구 없이 완료할 수 있고, 센서 조회 요청은 작전 DB만 선택할 수 있다. 전체 브리핑 요청은 모델 판단에 따라 필요한 복수 도구를 선택하며 런타임이 미사용 도구를 강제로 실행하지 않는다. |

## Verification evidence and completion

During implementation, record pass/fail plus execution/report IDs for the main flow and both approval decisions, and concise results for the branch checks. Automate the persistence/idempotency and role-review invariants where practical; manually rehearse the visual Builder sequence on the presentation screen. Report gaps explicitly. This documentation change alone does not pass runtime acceptance.
