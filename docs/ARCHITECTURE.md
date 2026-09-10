# Workflow Builder Demo — Architecture

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

ReAct 에이전트는 워크플로우 정의와 분리된 `react_agents` 정의를 사용한다. 정의에는 모델, 시스템 프롬프트, 최대 반복 횟수와 허용 도구 ID만 저장한다. `react_chat_sessions`가 사용자별 대화 경계를 저장하고 `react_agent_runs`와 `react_agent_events`가 요청, 단계별 공개 이벤트와 최종 결과를 저장한다. 실행 API는 NDJSON으로 요청 접수, 판단 요약, 도구 관찰, 응답 청크와 완료 이벤트를 순서대로 스트리밍한다. 같은 세션의 최근 완료 3턴을 `conversation_context`로 모델에 전달하며 세션 간에는 컨텍스트를 공유하지 않는다. 에이전트 실행의 HITL은 첫 구현에서 제외한다.

모델은 매 반복에서 다음 도구 또는 FINAL을 구조화 출력으로 선택한다. 런타임은 연결된 모든 도구의 실행이나 순서를 강제하지 않고 모델의 선택을 그대로 실행한다. 현재 요청과 최근 대화만으로 답할 수 있으면 첫 반복에도 FINAL이 가능하다. 런타임은 허용 목록, 5~8회 반복 제한, 동일 도구 중복 호출 방지와 근거 종합의 최소 입력 계약만 검증한다. 기본 도구는 작전 DB 조회, 승인 보고서 검색, 지역 정보 조회와 근거 종합이며 현재 모두 로컬 SQLite 또는 mock 어댑터다. 실제 MCP transport는 아직 연결하지 않으며 이후 같은 도구 인터페이스에 어댑터로 추가한다.

## Workflow Definition and compilation

Workflow Definition JSON은 schema_version, 설명, 모델 설정, 노드와 edge를 저장한다. 노드는 id, type, label, group, config, position을 가지며 edge는 source와 target을 가진다. 실행 가능한 Python 코드나 API credential은 Definition에 저장하지 않는다.

Workflow versions carry version, lifecycle_status and the full definition. Minimal lifecycle: DRAFT → PUBLISHED → SUSPENDED. Publish validates and snapshots a draft; Test uses a saved snapshot, even if unpublished. Registry registration is achieved by persistence and publishing; do not build a second formal review workflow. Workflow deployment approval and an execution's Human Approval are different concepts. The former is deferred; the latter is mandatory.

`POST /api/agents` creates a new DRAFT with an empty canvas and role-compatible metadata. Template selection is optional and copies business JSON only. `agent_versions` stores every published snapshot under `(agent_id, version)`; publication never overwrites a previous row. Executions reference the exact saved snapshot and version used at start.

현재 Validator는 빈 그래프, 노드 ID 중복, 잘못된 edge endpoint, 단일 시작점, 승인·발행 노드 존재 여부와 시작점에서 해당 노드까지의 도달 가능성을 검사한다. 역할별 노드 노출과 워크플로우 소유권은 API에서 제한한다. 노드별 Input/Output 호환성을 따라가는 정적 데이터 흐름 검증과 일반적인 cycle 검출은 아직 구현되지 않았다. 캔버스 위치 변경은 실행에 영향을 주지 않고 config와 edge 변경은 실행에 반영된다.

The compiler performs a topological walk of Builder edges, creates one LangGraph node for every reachable business node, maps conditional edge labels to routing functions, and compiles with the shared SQLite checkpointer. Capability functions receive and return typed workflow state. The API must not emulate waiting by stopping a Python loop; the checkpoint and pending interrupt are the source of truth.

Published sensor/report subscriptions use active versions. Each execution pins its version/snapshot so later edits cannot change a running or paused graph. For this demo choose one active Analyst subscription for 경기도 파주시 and one active Staff report subscription; avoid accidental fan-out to multiple template versions.

## Supported capability contracts

| Group | Nodes and behavior |
| --- | --- |
| Trigger | Sensor Event (Analyst); Approved Report (Staff). User Request is a visible future item, disabled in this demo. Test Run injects a fixture into the supported trigger. |
| Data | 작전 정보 조회는 고정 근거 ID가 있는 모의 기록을 반환한다. 승인 지역보고 수집은 승인·저장된 지역 보고만 반환한다. |
| AI | Threat Analysis and Situation Synthesis use structured Gateway output with evidence references and create the role-specific approval draft. |
| Control | Event Filter checks area/confidence; Human Approval interrupts for the assigned role. |
| Action | Report publication persists approved content and emits the appropriate in-app report event. Situation Board reads persisted results. |

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
| react_agents / react_chat_sessions / react_agent_runs | ReAct 설정, 소유자, 사용자별 채팅 세션, 사용자 목표와 최종 상태 |
| react_agent_events | 공개 가능한 판단·도구 관찰 스트림과 최종 브리핑 완료 이벤트 |

Only approved content enters the reports collection; drafts live in runtime/approval state. Send Report commits a REGIONAL report and its pending event in one SQLite transaction. The dispatcher reads the committed report and creates the Staff execution with a uniqueness constraint on (event_id, target_agent_id, target_version). Mark dispatched only after execution creation succeeds; recover pending items on startup. Duplicate notification delivery therefore cannot create a second Staff run. Use a unique finalized report key per execution/output to guard replay.

A COMMANDER report is persisted after Staff approval but must not emit APPROVED_REPORT_CREATED, preventing recursive Staff triggering. 경기도 연천군 and 강원특별자치도 철원군 are preapproved external seed fixtures; seeding them does not emit runtime events. Staff collects the new 경기도 파주시 report plus those fixtures from a bounded demo set, deduplicated by report ID, and records the exact input IDs. A fresh 파주시 report must actually participate in synthesis.

## Model Gateway

기본 실행 모드는 `openai`이며 백엔드의 `OPENAI_API_KEY`로 Responses API를 호출한다. 기본 모델은 `gpt-4.1-mini`이고 `OPENAI_MODEL`, `OPENAI_BASE_URL`로 교체할 수 있다. 위협 분석과 상황 종합은 `text.format.type=json_schema` 구조화 출력을 사용한다. `DEMO_MODEL_MODE=deterministic`은 키 없이 UI를 점검하는 명시적 리허설 모드이며 화면과 health 응답에 표시한다.

Expose generate(messages, model_config) and structured_generate(messages, schema, model_config). Implement one real external provider. Reserve provider registration as the extension point for vLLM/Ollama/local HF without installing or serving them now. Keep external API credentials in backend environment configuration, never Workflow Definition JSON or frontend storage.

구조화 출력을 검증한다. 위협 분석 출력은 threat_level, summary, evidence_ids, draft를 포함하고 상황 종합 출력은 overall_threat_level, summary, priority_areas, source_report_ids, draft를 포함한다. Sensor confidence는 모델 판단과 별개의 입력이다. 호출 실패나 잘못된 출력은 승인·보고서를 만들지 않고 실행 실패로 표시한다. 리허설 출력은 deterministic 모드로 명시한다.

## Minimal API boundaries (implementation defaults)

| API responsibility | Suggested endpoints / contract |
| --- | --- |
| Mock session | POST /api/session, role switch via same operation; return static session context |
| Catalog and definitions | GET /api/nodes, GET /api/models; GET/POST/DELETE /api/agents; GET/PUT /api/agents/{id}; POST .../validate and .../publish |
| Start/test | POST /api/agents/{id}/test with fixture and saved snapshot; POST /api/sensor-events for active published subscription |
| Execution | GET /api/executions and /api/executions/{id}; GET .../trace |
| Approval | POST /api/approvals/{id}/decision with APPROVE, EDIT_APPROVE or REJECT and optional edited content/comment |
| Read models | GET /api/reports, /api/situation-board, /api/dashboard |

Backend applies the same small role/area policy to reads, node validation and approval actions as the frontend. Return clear validation, forbidden-role, conflict/stale-decision and provider error messages. This is demo policy, not a production RBAC/ABAC system. Send to Superior/Commander means in-app report availability, not email or an external system integration.
