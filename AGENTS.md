# Defense Agent Builder Demo 개발 지침

이 프로젝트는 세미나용 데모다. 운영 환경 수준의 범용성보다 시연 안정성, 이해하기 쉬운 UI와 코드 흐름을 우선한다.

## 작업 전 확인

구현 결정을 내리기 전에 다음 문서를 함께 읽는다.

1. `docs/PRD.md`: 범위와 사용자 요구사항
2. `docs/ARCHITECTURE.md`: 런타임과 데이터 계약
3. `docs/UI_SPEC.md`: 화면과 상호작용
4. `docs/DEMO_SCENARIO.md`: 검증 기준

사용자의 명시적인 최신 요청이 문서보다 우선한다. 동작하는 기존 기능과 사용자 변경사항을 먼저 확인하고 수정한다.

## 기술과 구조

- Frontend: React, TypeScript, React Flow
- Backend: FastAPI, LangGraph, SQLite
- 실제 데모 LLM 호출은 백엔드 `ModelGateway`를 통한다.
- `main.py`는 앱 생성과 라우터 등록만 담당한다.
- HTTP 처리는 `*_api.py`, 실행 규칙은 `*_service.py`, 공통 기능은 `core.py`와 `database.py`에 둔다.
- 자격 증명은 `.env`와 백엔드에서만 관리한다.


## 데모 범위

별도 요청이 없으면 실제 센서, Data Fabric, MCP 서버, Kafka, Kubernetes, 운영 인증, 전체 RBAC/ABAC, 고급 GIS와 로컬 모델 서빙을 구현하지 않는다. 문서에서 mock으로 정한 데이터와 외부 시스템은 mock임을 명확히 표시한다.

## 구현 원칙

- 현재 데모 시나리오를 만족하는 가장 단순한 구현을 선택한다.
- 새 인프라나 추상화 계층을 필요 이상으로 추가하지 않는다.
- API 경로와 저장 형식을 변경할 때 프론트엔드 사용처와 기존 DB 마이그레이션을 함께 확인한다.
- JSON DB 필드는 API 응답 전에 공통 `row()` 함수로 역직렬화한다.
- 내부 chain-of-thought를 노출하지 않고 공개 가능한 판단 요약과 도구 결과만 표시한다.
- 범위나 동작이 바뀌면 관련 문서도 같은 작업에서 갱신한다.

## 검증

- 변경한 Python 모듈의 구문과 FastAPI import를 확인한다.
- 프론트 변경 시 TypeScript 검사와 Vite 빌드를 실행한다.
- 관련 API의 응답 형식과 역할 제한을 확인한다.
- 실행·승인 변경은 `docs/DEMO_SCENARIO.md`의 해당 흐름으로 검증한다.
- 실제 외부 모델 결과와 결정론적 테스트 결과를 구분해 보고한다.
