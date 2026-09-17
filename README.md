# Defense Workflow Builder PoC

국방 에이전트 빌더 데모입니다.
유저 별로 서로 다른 워크플로우와 에이전트를 빌드하여 사용할 수 있습니다.

## UI

![Agent Builder](assets/agent_builder.png)

![Workflow Builder](assets/workflow_builder.png)

## 요구 환경

- Python 3.11 이상
- Node.js 20 이상

## 환경 변수

프로젝트 루트의 .env 파일을 백엔드가 자동으로 읽습니다.

~~~dotenv
OPENAI_API_KEY=발급받은_API_키
OPENAI_MODEL=gpt-5.4-mini

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

브라우저에서 http://localhost:5173 을 엽니다. 


## 문서

- [제품 요구사항](docs/PRD.md)
- [아키텍처](docs/ARCHITECTURE.md)
- [UI 명세](docs/UI_SPEC.md)
- [데모 시나리오](docs/DEMO_SCENARIO.md)
- [현재 구현 상태](docs/IMPLEMENTATION_STATUS.md)
