# defense-agent-builder-poc

## 실제 LLM 설정

프로젝트 루트의 `.env`에 API 키를 설정합니다.

```dotenv
OPENAI_API_KEY=발급받은_API_키
OPENAI_MODEL=gpt-4.1-mini
```

백엔드는 시작할 때 이 파일을 자동으로 읽습니다. 키 없이 UI만 점검할 때는 `DEMO_MODEL_MODE=deterministic`을 추가합니다. 기본값은 실제 OpenAI Responses API 호출인 `openai`입니다.
defense-agent-builder poc 

# To-do - agent builder poc 개발
- Project Setting (Python, Github)
- vibe coding Setting (AGENTS.md, ..)
- notion source of truth -> local docs, 실행 명세 남기기

# 지침
- PoC, Demo 성격에 맞게, 너무 과도하게 하지 않기, 간단하게.

## 실행

요구 환경은 Python 3.11+와 Node.js 20+입니다.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

새 터미널에서 프론트엔드를 실행합니다.

```powershell
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:5173`을 엽니다. 최초 실행 시 파주 분석관/정보작전 참모 Agent와 연천군, 철원군 승인 보고 fixture가 SQLite에 자동으로 생성됩니다.

현재 구현은 화면과 승인 흐름을 안정적으로 리허설하기 위한 `DETERMINISTIC_REHEARSAL` 모드입니다. 외부 모델 API 연결 전에는 실제 외부 LLM 결과로 간주하지 않습니다.

## 데모 순서

1. Analyst로 로그인해 Agent Builder에서 그래프를 편집하고 저장·검증·게시합니다.
2. Test Run으로 파주시 센서 fixture를 실행하고 분석관 승인 화면에서 초안을 수정·승인합니다.
3. 생성된 지역 보고가 Staff 실행을 자동 시작하는지 연결된 실행에서 확인합니다.
4. 역할을 Staff로 바꾸고 지휘관 보고 초안을 승인합니다.
5. Commander로 전환해 상황판에서 승인된 최종 보고와 출처 계보를 확인합니다.

## 신규 에이전트와 LangGraph 실행

Agent Registry의 `새 에이전트`에서 빈 캔버스 또는 역할별 템플릿을 선택할 수 있습니다. 빈 캔버스는 미완성 상태로도 초안 저장이 가능하며, 노드를 배치하고 연결한 뒤 검증을 통과해야 게시할 수 있습니다.

게시할 때 `agent_versions`에 불변 스냅샷이 저장됩니다. 시험 실행은 Builder JSON을 실제 LangGraph `StateGraph`로 컴파일하고 SQLite checkpointer에 실행 상태를 기록합니다. 승인 노드는 `interrupt()`로 중단되며 승인·수정승인·반려는 같은 thread ID에 `Command(resume=...)`를 전달해 재개합니다.
