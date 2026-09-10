# 현재 구현 상태

기준일: 2026-09-10

이 문서는 데모 코드의 현재 동작을 요약한다. 제품 범위는 [PRD.md](PRD.md), 런타임 구조는 [ARCHITECTURE.md](ARCHITECTURE.md), 화면 동작은 [UI_SPEC.md](UI_SPEC.md), 발표 흐름은 [DEMO_SCENARIO.md](DEMO_SCENARIO.md)를 따른다.

## 역할과 화면

| 역할 | 주요 화면 | 권한 |
| --- | --- | --- |
| 파주지역 분석관 | 대시보드, 워크플로우 빌더·레지스트리, 실행 모니터링, 상황판, 센서 입력 | 본인 워크플로우 관리, 센서 이벤트 실행, 지역 보고서 승인 |
| 정보·작전 참모 | 대시보드, 워크플로우 빌더·레지스트리, 실행 모니터링, 상황판 | 본인 워크플로우 관리, 지역 보고 종합, 지휘관 보고서 승인 |
| 지휘관 | 상황판, 사용 매뉴얼 | 센서 이벤트와 보고서 도착 알림 확인, 승인된 보고서 열람 |

역할 선택과 업무 명칭은 UI에서 한국어로 표시한다. 레지스트리는 현재 세션의 사용자 ID와 역할로 분리한다. 사용자가 만든 워크플로우는 삭제할 수 있고 기본 제공 워크플로우는 보호한다.

## 기본 워크플로

분석관:

~~~text
감시 센서 이벤트
→ 이벤트 조건 확인
→ 작전 정보 조회
→ 위협 분석·초안 생성
→ 분석관 검토·승인
→ 지역 보고서 발행
~~~

참모:

~~~text
승인 지역보고 접수
→ 승인 지역보고 수집
→ 접경지역 작전상황 조회
→ 위협 종합·초안 생성
→ 참모 검토·승인
→ 지휘관 보고서 발행
~~~

AI 노드는 판단 결과와 승인용 보고서 초안을 함께 생성한다. Action 노드는 승인된 결과를 SQLite에 저장하고 다음 애플리케이션 이벤트를 발생시키는 발행 단계다.

## LangGraph 상태와 승인

Builder JSON은 실행 시 실제 LangGraph StateGraph로 컴파일된다. 주요 state 필드는 event, evidence_ids, source_report_ids, filtered, threat_level, summary, draft, approval_id, approval_decision, edited_content이다.

승인 노드는 interrupt()로 중단하고 SQLite checkpointer에 상태를 저장한다. 승인, 수정 승인, 반려는 같은 execution/thread ID에 Command(resume=...)를 전달한다. 실행 상세는 노드별 실제 입력·출력 요약을 보여준다. 설계상의 Input/Output 계약은 노드를 선택했을 때 우측 설정 패널에서 확인한다.

## 모델 호출

기본 모드는 OpenAI Responses API 호출이다. API 키와 기본 모델은 프로젝트 루트의 .env에서 읽는다.

~~~dotenv
OPENAI_API_KEY=발급받은_API_키
OPENAI_MODEL=gpt-4.1-mini
OPENAI_ALLOWED_MODELS=gpt-4.1-mini,gpt-5-mini
~~~

AI 노드에서 허용된 모델과 시스템 프롬프트를 선택할 수 있다. 선택값은 Workflow Definition에 저장되고 실제 실행에 사용된다. DEMO_MODEL_MODE=deterministic은 키 없이 화면과 흐름을 점검하는 명시적 리허설 모드다.

## 지휘관 전달 흐름

참모가 지휘관 보고서를 승인하면 최종 보고서가 저장되고 **새 지휘관 보고서 도착** 알림이 생성된다. 지휘관은 /dashboard 경로를 상황판 단일 메뉴로 사용한다. 별도의 대시보드·상황판 중복 메뉴 없이 다음을 표시한다.

- 접경지역 지도
- 최근 센서 이벤트
- 보고서 도착 알림

보고서 도착 알림은 원본 실행 ID로 최종 보고서를 찾아 연결하며, 클릭하면 읽기 전용 보고서 상세가 열린다.

## 현재 검증 범위

게시 전 검증은 노드 ID 중복, edge endpoint, 단일 시작점, 승인 노드와 발행 노드 존재 여부, 시작점에서 필수 노드까지의 도달 가능성을 확인한다. 노드별 required_inputs와 produced_outputs를 따라가는 정적 데이터 흐름 검증은 아직 구현되지 않았다. Input/Output 표시는 현재 설계와 실행 추적을 이해하기 위한 계약 정보다.

## 실행과 초기화

백엔드와 프론트엔드는 별도 터미널에서 실행한다.

~~~powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
~~~

~~~powershell
cd frontend
npm install
npm run dev
~~~

데이터 초기화는 백엔드를 종료한 뒤 backend/demo.db, backend/checkpoints.db, backend/checkpoints.db-shm, backend/checkpoints.db-wal을 삭제하고 백엔드를 다시 시작한다. 프로젝트 루트의 .env는 삭제하지 않는다.
