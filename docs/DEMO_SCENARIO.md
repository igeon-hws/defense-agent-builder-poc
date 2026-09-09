# Agent Builder Demo — Scenario and Acceptance

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
- Publish one Staff Agent subscription before the Analyst report is approved. Ensure one active Analyst 경기도 파주시 subscription. Use an isolated demo dataset with no previous pending runs; any reset must be explicit and limited to demo data.
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
| 0:00–1:00 | Login as 파주지역 Analyst; open 파주 감시·위협분석 Agent | Role-filtered Dashboard, Analyst palette, editable template |
| 1:00–3:00 | Show node composition; edit event confidence/prompt, Apply, Save, Validate and Publish | Saved/published definition reflects the edit; role, model and version visible |
| 3:00–4:30 | 센서 입력에서 규모/신뢰도를 조절해 전송; 실행 상세 열기 | 감시 센서 → 조건 확인 → 작전 정보 → 실제 LLM 위협 분석 순서가 trace에 표시 |
| 4:30–6:00 | Inspect MEDIUM/HIGH alert and approval drawer; edit one report sentence and explicitly approve | Draft pauses at WAITING_FOR_ANALYST_APPROVAL; then same execution resumes with edited content |
| 6:00–7:00 | Inspect approved 파주시 report; switch header to Staff | Report persisted, event dispatched, exactly one linked Staff run starts automatically |
| 7:00–9:00 | Open Staff Builder/execution and inspect source reports | New A report + seeded B/C reports → collection/classification → context/search → Situation Synthesis → Commander draft |
| 9:00–10:00 | Inspect WAITING_FOR_STAFF_APPROVAL and approve | Staff decision resumes same run; final COMMANDER report persisted; no recursive Staff trigger |
| 10:00–11:00 | Switch to Commander; open final report and board | Final report readable with approver and source lineage; no Builder/approval controls |

Before the main flow, demonstrate creation in under one minute: choose `새 Agent`, enter a name and area, select Blank, add the supported trigger/data/AI/approval/report nodes, connect their handles, save, validate and publish v1. Start a test from v1 and show that the execution detail uses the same pinned graph. Keep the seeded Agent available as a recovery path for the live seminar.

Report Generator produces drafts before each approval. After each approval, Send Report finalizes the approved content and Situation Board reflects persisted records. 'Send' means in-app delivery. Execution view provides cross-links from the A report to the Staff run and from the Commander report to its source reports.

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
| AC-01 | Login/switch through all three roles | Correct agent/node/data scope; Commander read-only; no production login infrastructure |
| AC-02 | Change supported nodes, edges and config, save and reload | Graph/config persist; changes drive execution; invalid edges, unsupported cycles and approval bypass fail validation |
| AC-02A | Create a blank role-compatible Agent | A new DRAFT is persisted, opens in Builder, survives refresh, and exposes only role-compatible nodes |
| AC-02B | Connect, validate and publish the new Agent | An immutable version snapshot is created; Registry shows it and the published graph can start a real LangGraph execution |
| AC-03 | Publish then edit an Agent while a run is paused | Registry shows version/owner/trigger; paused run retains original snapshot |
| AC-04 | Start the main Analyst fixture in actual-demo mode | External Gateway call produces validated output; mocked inputs are labeled; real node trace updates in Builder and Execution |
| AC-05 | Analyst run reaches Human Approval | Durable WAITING_FOR_ANALYST_APPROVAL; no regional final report/event before explicit approval |
| AC-06 | Edit and approve Analyst draft | Same thread resumes; exact edited content, actor and timestamp are persisted in the approved REGIONAL report |
| AC-07 | Commit the new regional report | Exactly one report event starts exactly one active Staff execution; source report ID matches persisted 파주시 output |
| AC-08 | Staff synthesis executes | New 파주시 and approved 연천군/철원군 fixture IDs are recorded as inputs; draft shows synthesis/evidence and pauses at WAITING_FOR_STAFF_APPROVAL |
| AC-09 | Staff approves | Same Staff thread resumes; one COMMANDER report created, no recursive Staff event; Commander can read approved result |
| AC-10 | Reject at either approval gate | Run ends REJECTED; no corresponding final report/downstream action; decision trace remains |
| AC-11 | LOW/filtered fixture runs | Clearly recorded outcome, no accidental approval/report/Staff launch |
| AC-12 | Refresh/restart during either pending review | Same checkpoint/draft recover, same execution resumes; no duplicated pre-approval model call or publishing |
| AC-13 | Duplicate decision/event or crash-window recovery | Unique report and Staff execution invariants hold; stale/conflicting reviews fail visibly |
| AC-14 | Switch roles with dirty graph or waiting review | Save/Discard/Cancel protects edits; role scope refetches; original runtime actor unchanged; backend rejects wrong-role review |
| AC-15 | View Situation Board and final report | OpenStreetMap-based 파주·연천·철원 view, approved reports, seed badges and source lineage; no draft shown as final |
| AC-16 | Fail the external provider | Clear failed trace with bounded retry; no fabricated output, report or auto-approval |

## Verification evidence and completion

During implementation, record pass/fail plus execution/report IDs for the main flow and both approval decisions, and concise results for the branch checks. Automate the persistence/idempotency and role-review invariants where practical; manually rehearse the visual Builder sequence on the presentation screen. Report gaps explicitly. This documentation change alone does not pass runtime acceptance.
