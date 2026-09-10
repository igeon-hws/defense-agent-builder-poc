# Defense Workflow Builder PoC

React Flow로 역할별 워크플로우를 구성하고, FastAPI와 LangGraph로 실행하는 세미나용 데모입니다. 현재 구현 범위와 제한 사항은 [현재 구현 상태](docs/IMPLEMENTATION_STATUS.md)를 먼저 확인하세요.

## 요구 환경

- Python 3.11 이상
- Node.js 20 이상

## 환경 변수

프로젝트 루트의 .env 파일을 백엔드가 자동으로 읽습니다.

~~~dotenv
OPENAI_API_KEY=발급받은_API_키
OPENAI_MODEL=gpt-4.1-mini
OPENAI_ALLOWED_MODELS=gpt-4.1-mini,gpt-5-mini
~~~

기본 실행 모드는 실제 OpenAI Responses API 호출입니다. 키 없이 화면 흐름만 확인할 때는 DEMO_MODEL_MODE=deterministic을 추가합니다.

## 실행

첫 번째 PowerShell에서 백엔드를 실행합니다.

~~~powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
~~~

두 번째 PowerShell에서 프론트엔드를 실행합니다.

~~~powershell
cd frontend
npm install
npm run dev
~~~

브라우저에서 http://localhost:5173 을 엽니다. 최초 실행 시 파주 분석관·정보작전 참모 기본 워크플로우와 연천군·철원군 승인 보고 fixture가 생성됩니다.

## 데모 순서

1. 분석관으로 로그인해 워크플로우 그래프, 이벤트 조건, AI 모델과 프롬프트를 설정하고 저장·검증·게시합니다.
2. 센서 입력에서 파주시 이벤트를 전송하고 AI가 생성한 지역 보고서 초안을 검토·승인합니다.
3. 승인된 지역 보고가 참모 워크플로우를 자동 실행하는지 확인합니다.
4. 정보·작전 참모로 전환해 AI가 생성한 지휘관 보고서 초안을 승인합니다.
5. 지휘관으로 전환해 상황판의 보고서 도착 알림을 클릭하고 최종 보고서를 확인합니다.

## 데이터 초기화

백엔드를 종료한 뒤 다음 파일을 삭제하고 다시 실행합니다.

~~~powershell
cd backend
Remove-Item .\demo.db -ErrorAction SilentlyContinue
Remove-Item .\checkpoints.db, .\checkpoints.db-shm, .\checkpoints.db-wal -ErrorAction SilentlyContinue
python -m uvicorn app.main:app --reload
~~~

.env는 삭제하지 않습니다.

## 문서

- [제품 요구사항](docs/PRD.md)
- [아키텍처](docs/ARCHITECTURE.md)
- [UI 명세](docs/UI_SPEC.md)
- [데모 시나리오](docs/DEMO_SCENARIO.md)
- [현재 구현 상태](docs/IMPLEMENTATION_STATUS.md)
