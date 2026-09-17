# 시스템 아키텍처

제품 범위는 [제품 요구사항](PRD.md), 화면 동작은 [UI 명세](UI_SPEC.md), 현재 구현 여부는 [현재 구현 상태](IMPLEMENTATION_STATUS.md), 검증 절차는 [데모 시나리오](DEMO_SCENARIO.md)를 참고한다.

## 전체 구조

```text
React + TypeScript + React Flow
        │ HTTP / NDJSON
        ▼
FastAPI 단일 애플리케이션
  ├─ 모의 세션·화면 조회 API
  ├─ 워크플로우 정의·실행·승인·보고 API
  ├─ ReAct 에이전트·채팅 API
  ├─ LangGraph 런타임과 SQLite 체크포인터
  ├─ 모델 게이트웨이
  └─ 모의 데이터·외부 시스템 어댑터
        │
        ├─ backend/demo.db
        └─ backend/checkpoints.db
```

백엔드는 하나의 프로세스와 두 SQLite 파일을 사용한다. 모듈은 책임별로 나누지만 별도 배포 서비스로 분리하지 않는다. Kafka, 작업자 프로세스, 실제 MCP 전송 계층은 없다.

## 백엔드 모듈

| 모듈 | 책임 |
| --- | --- |
| `main.py` | FastAPI 앱 생성, CORS, 라우터 등록, 시작 시 DB 초기화 |
| `core.py` | 환경 변수, SQLite 연결, 고정 역할 세션, 공통 ID·시간, 모델·런타임 인스턴스 |
| `database.py` | 테이블 생성, 최소 컬럼 보강, 기본 워크플로우·에이전트·보고서 초기 데이터 |
| `schemas.py` | 워크플로우 HTTP 요청 모델 |
| `view_api.py` | 상태, 모델, 세션, 대시보드, 알림, 상황판 조회 |
| `workflow_api.py` | 워크플로우 CRUD, 검증, 게시, 실행, 승인, 보고서 API |
| `workflow_service.py` | 역할별 기본 정의, 노드 실행 함수, LangGraph 시작·재개 |
| `runtime.py` | Builder JSON을 LangGraph로 컴파일하고 SQLite 체크포인트 연결 |
| `gateway.py` | OpenAI Responses API 및 결정론적 리허설 응답 |
| `connectors.py` | 역할별 데이터·외부 시스템 연동과 capability 매핑 |
| `react_tools.py` | ReAct 도구 목록, 기본 에이전트 정책과 도구 실행 구현 |
| `react_agent.py` | 에이전트 CRUD, 채팅 세션, NDJSON 실행 스트림 |

## 데이터베이스

### 워크플로우 영역

| 테이블 | 저장 내용 |
| --- | --- |
| `agents` | 현재 워크플로우 초안 또는 게시 정의, 소유자, 역할, 버전 |
| `agent_versions` | 게시된 버전별 불변 정의 스냅샷 |
| `executions` | 실행 역할·지역, 트리거, 고정 정의, 상태, 부모·자식 연결 |
| `trace` | 노드별 상태, 입력·출력 요약과 시각 |
| `approvals` | 실행별 승인 초안, 결정, 승인자와 시각 |
| `reports` | 승인된 지역·지휘관 보고서와 출처 |
| `report_events` | 지역 보고 승인과 참모 실행 연결 |
| `notifications` | 역할별 앱 내 알림과 읽음 시각 |
| `sensor_events` | 모의 센서 입력과 실행 ID |
| `leave_requests` | 휴가 신청 원문, 검토 상태와 실행 ID |
| `intranet_registrations` | 승인된 휴가의 모의 인트라넷 등록 |
| `personnel_movements` | 행정 에이전트가 조회하는 외출·외박 초기 데이터 |

### ReAct 영역

| 테이블 | 저장 내용 |
| --- | --- |
| `react_agents` | 에이전트 정의, 역할, 소유자, 생명주기와 버전 |
| `react_chat_sessions` | 사용자·에이전트별 대화 경계와 시작·갱신 시각 |
| `react_agent_runs` | 요청, 최종 응답, 상태와 세션 연결 |
| `react_agent_events` | 공개 가능한 판단, 도구 관찰, 완료·오류 이벤트 |

`core.row()`는 DB에 JSON 문자열로 저장한 정의, 트리거, 스냅샷과 payload를 API 객체로 변환한다.

## 워크플로우 정의

정의는 다음 주요 필드를 가진다.

```json
{
  "schema_version": "1",
  "description": "업무 설명",
  "model": {
    "provider": "openai",
    "model_id": "환경 변수로 선택된 모델",
    "temperature": 0.2
  },
  "nodes": [],
  "edges": []
}
```

노드는 `id`, `type`, `label`, `group`, `position`, `config`를 가진다. 연결은 `source`와 `target`을 사용한다. API 키, 임의 Python 코드와 사용자 입력 endpoint는 정의에 저장하지 않는다.

현재 생명주기는 다음과 같다.

```text
DRAFT → PUBLISHED
```

게시된 정의를 다시 저장하면 현재 행은 `DRAFT`로 바뀌지만 이전 `agent_versions` 행은 유지된다. 다시 게시하면 버전 번호를 올리고 새 스냅샷을 추가한다. `SUSPENDED` 상태는 없다.

## 정의 검증과 컴파일

게시와 시험 실행 전에 다음 조건을 검사한다.

1. 노드가 하나 이상 있어야 한다.
2. 노드 ID가 중복되지 않아야 한다.
3. 연결의 양 끝이 실제 노드를 가리켜야 한다.
4. 연결된 시작 노드가 정확히 하나여야 한다.
5. 승인 노드와 발행 또는 등록 노드가 있어야 한다.
6. 시작 노드에서 승인·발행 노드에 도달할 수 있어야 한다.

컴파일러는 정의의 모든 노드를 LangGraph 노드로 등록하고 연결을 그대로 추가한다. 시작점은 들어오는 연결이 없는 단일 노드다. 필터 노드는 조건 미달 시 종료로, 승인 노드는 반려 시 종료로 분기한다. 그 외 노드는 정의의 다음 노드로 진행한다.

일반 순환 검출과 정적 데이터 타입 검증은 없다. 잘못된 복잡한 그래프는 검증을 통과하더라도 LangGraph 컴파일 또는 실행 단계에서 실패할 수 있다.

## 실행 상태

워크플로우 상태에는 필요한 필드만 선택적으로 담는다.

- 실행 ID, 역할, 지역과 입력 이벤트
- 근거 ID와 원본 보고서 ID
- 위협 수준, 요약, 우선 지역과 보고서 초안
- 승인 ID, 승인 결정과 수정 내용
- 휴가 잔여 일수, 관련 일정, 처리 가능 여부와 충돌 목록
- 필터 결과

실행은 `execution_id`를 LangGraph `thread_id`로 사용한다. 실행 시작 시 정의 전체를 `executions.snapshot`에 고정하고, 같은 스냅샷으로 승인 후 재개한다.

주요 상태 흐름은 다음과 같다.

```text
RUNNING
→ WAITING_FOR_ANALYST_APPROVAL
→ RUNNING
→ COMPLETED
```

역할에 따라 대기 상태의 역할명만 `STAFF` 또는 `ADMIN`으로 바뀐다. 반려와 모델 오류의 종료 상태는 각각 `REJECTED`, `FAILED`다. 필터 미달은 보고서를 만들지 않고 `COMPLETED`로 끝난다.

노드 trace 상태는 주로 `WAITING`, `SUCCEEDED`, `FAILED`를 사용한다. UI에서 정의한 `PENDING` 또는 `RUNNING` 스타일이 있더라도 현재 서버 trace가 모든 중간 상태를 세밀하게 저장하는 것은 아니다.

## 승인 중단과 재개

승인 노드는 다음 순서로 동작한다.

1. 실행당 승인 요청이 이미 있는지 확인한다.
2. 없으면 초안과 검토 역할을 `approvals`에 저장한다.
3. trace와 실행 상태를 승인 대기로 바꾸고 알림을 만든다.
4. LangGraph `interrupt()`로 체크포인트에 중단한다.
5. 승인 API가 결정과 승인자를 저장한다.
6. `Command(resume=...)`로 같은 thread를 재개한다.
7. 승인 또는 수정 승인은 후속 발행 노드를 실행하고, 반려는 종료한다.

승인 API는 승인 요청의 `reviewer_role`과 `X-Demo-Role`을 비교한다. 이미 처리된 승인 요청은 `409`로 거부한다.

## 보고서와 후속 실행

### 지역 보고서

분석관 승인 후 `REGIONAL` 보고서를 저장한다. 같은 처리 안에서 `report_events` 행을 만들고 게시된 참모 워크플로우를 찾아 새 실행을 만든다. 분석관 실행에는 `child_execution_id`, 참모 실행에는 `source_report_id`를 기록한다.

현재 별도 이벤트 디스패처가 없으므로 승인 API 요청 안에서 후속 실행을 동기적으로 시작한다. DB의 유일 제약은 중복 보고서와 이벤트 생성을 막지만, 운영 수준 재시도 큐는 제공하지 않는다.

### 지휘관 보고서

참모 승인 후 `COMMANDER` 보고서를 저장하고 `새 지휘관 보고서 도착` 알림을 만든다. 이 보고서에는 승인 시점의 최신 지역 보고서 최대 세 건을 `source_report_ids`로 기록한다. 지휘관 보고서는 새 `report_events`를 만들지 않는다.

### 행정 등록

행정병 승인 후 `leave_requests.status`를 `REGISTERED`로 바꾸고 `intranet_registrations`를 만든다. 인트라넷은 로컬 DB로 구현한 모의 시스템이다.

## 모델 게이트웨이

`ModelGateway`는 백엔드 환경 변수만 읽는다.

| 환경 변수 | 의미 | 코드 기본값 |
| --- | --- | --- |
| `DEMO_MODEL_MODE` | `openai` 또는 `deterministic` | `openai` |
| `OPENAI_MODEL` | 기본 모델 ID | `gpt-4.1-mini` |
| `OPENAI_ALLOWED_MODELS` | 추가 허용 모델 목록 | 빈 값 |
| `OPENAI_BASE_URL` | Responses API 기준 URL | `https://api.openai.com/v1` |
| `OPENAI_API_KEY` | 실제 호출 자격 증명 | 없음 |

허용 모델에는 선택된 기본 모델과 `gpt-4.1-mini`, `gpt-5-mini`가 항상 포함된다. 워크플로우의 위협 분석, 상황 종합, 휴가 요약과 에이전트의 다음 행동 선택은 `json_schema` 구조화 출력을 사용한다. HTTP 제한 시간은 30초다.

`deterministic` 모드는 입력 키워드와 저장된 모의 데이터를 바탕으로 반복 가능한 결과를 반환한다. 모델 호출 오류는 워크플로우를 `FAILED`로, ReAct 실행을 `FAILED` 이벤트로 기록한다. 현재 자동 재시도는 구현하지 않았다.

## ReAct 에이전트 구조

에이전트 정의에는 다음 내용을 저장한다.

- 모델 설정
- 시스템 프롬프트
- 최대 반복 횟수
- 선택한 연동(`connector`) ID
- 연동에서 계산한 허용 도구 ID
- 추천 질문

저장할 때 서버는 역할에 허용된 연동만 남기고 도구 목록을 다시 계산한다. 클라이언트가 임의 도구 ID를 추가해도 그대로 사용하지 않는다. `intranet_register`는 워크플로우 전용이므로 ReAct 도구 목록에서 제외한다.

범용 기본 에이전트는 역할에 허용된 전체 연동을 사용하고, 임무 특화형은 정책에 정의된 연동만 사용한다. 서버 시작 시 기본 정의를 다시 반영하므로 기본 에이전트는 사용자 설정을 보존하지 않는다.

### 실행 반복

1. 사용자 요청과 같은 세션의 최근 완료 3턴을 준비한다.
2. 모델에 허용 도구 목록과 지금까지의 관찰을 전달한다.
3. 모델이 도구 하나 또는 `FINAL`을 선택한다.
4. 허용 여부와 중복 호출을 검사한다.
5. 도구 결과를 관찰 목록과 이벤트 테이블에 저장한다.
6. 최대 5~8회 안에 최종 응답을 만들지 못하면 실패한다.

스트림의 미디어 타입은 `application/x-ndjson`이다. 요청 접수, 판단 요약, 도구 결과, 응답 청크, 완료 또는 오류 이벤트를 한 줄 JSON으로 보낸다.

## 주요 API

### 공통 조회

| 메서드와 경로 | 기능 |
| --- | --- |
| `GET /api/health` | 모델 모드·모델·DB 상태 |
| `POST /api/session` | 역할 기반 고정 세션 생성 |
| `GET /api/models` | 허용 모델 목록 |
| `GET /api/dashboard` | 역할별 지표와 최근 알림 |
| `GET /api/situation-board` | 센서 이벤트 또는 지휘관용 빈 이벤트 목록, 알림 |
| `POST /api/notifications/{id}/read` | 알림 읽음 처리 |

### 워크플로우

| 메서드와 경로 | 기능 |
| --- | --- |
| `GET /api/nodes` | 역할별 노드 카탈로그 |
| `GET /api/connectors` | 역할별 연동 카탈로그 |
| `GET/POST /api/agents` | 워크플로우 목록·생성 |
| `GET/PUT/DELETE /api/agents/{id}` | 조회·저장·삭제 |
| `POST /api/agents/{id}/validate` | 정의 검증 |
| `POST /api/agents/{id}/publish` | 버전 게시 |
| `POST /api/agents/{id}/test` | 고정 입력으로 시험 실행 |
| `POST /api/sensor-events` | 분석관 센서 실행 |
| `POST/GET /api/leave-requests` | 행정병 휴가 신청·목록 |
| `GET /api/executions` | 역할 인자 기준 실행 목록 |
| `GET /api/executions/{id}` | 실행, trace, 승인, 보고서 상세 |
| `POST /api/approvals/{id}/decision` | 승인·수정 승인·반려 |
| `GET /api/reports` | 역할별 보고서 목록 |

### ReAct 에이전트

| 메서드와 경로 | 기능 |
| --- | --- |
| `GET /api/react-tools` | 역할별 도구 목록 |
| `GET/POST /api/react-agents` | 에이전트 목록·생성 |
| `GET/PUT/DELETE /api/react-agents/{id}` | 조회·저장·삭제 |
| `POST /api/react-agents/{id}/publish` | 커스텀 에이전트 게시 |
| `GET/POST /api/react-agents/{id}/sessions` | 채팅 세션 목록·생성 |
| `GET/DELETE /api/react-agents/{id}/sessions/{session_id}` | 세션 복원·삭제 |
| `POST /api/react-agents/{id}/runs/stream` | NDJSON 실행 시작 |
| `GET /api/react-agent-runs/{run_id}` | 저장된 실행과 이벤트 조회 |

## 보안과 운영상 제한

현재 역할 정책은 세미나 흐름을 보여주기 위한 정적 정책이다. 워크플로우·에이전트 소유권과 승인 역할에는 검사가 있지만 모든 조회 API가 일관된 운영 수준 권한 검사를 제공하지는 않는다. 실제 배포 전에는 인증, 권한, 감사, 비밀 관리, 입력 검증과 동시성 제어를 별도로 설계해야 한다.
