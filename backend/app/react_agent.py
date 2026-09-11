"""ReAct 에이전트 CRUD, 채팅 세션과 NDJSON 실행 스트림 API."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .gateway import ModelGateway, ModelGatewayError
from .react_tools import default_react_definition, execute_react_tool, tools_for_role
from .connectors import hydrate_react_definition


class ReactAgentCreateIn(BaseModel):
    name: str
    description: str = ""


class ReactAgentIn(BaseModel):
    name: str
    description: str = ""
    definition: dict[str, Any]


class ReactSessionCreateIn(BaseModel):
    title: str = "새 대화"


class ReactRunIn(BaseModel):
    prompt: str
    session_id: str


def create_react_router(*, db: Callable, deserialize: Callable, session_for: Callable, gateway: ModelGateway,
                        now: Callable[[], str], uid: Callable[[str], str]) -> APIRouter:
    router = APIRouter(prefix="/api")

    def hydrate_agent(agent: dict[str, Any] | None) -> dict[str, Any] | None:
        if agent:
            agent["definition"] = hydrate_react_definition(agent["definition"], agent["role"])
        return agent

    def require_agent(agent: dict[str, Any] | None, role: str) -> None:
        if not agent:
            raise HTTPException(404, "에이전트를 찾을 수 없습니다.")
        if agent["role"] != role or agent["owner"] != session_for(role)["user_id"]:
            raise HTTPException(403, "본인 소유 에이전트만 사용할 수 있습니다.")

    def save_event(run_id: str, event_type: str, title: str, content: str,
                   tool_name: str | None = None, payload: Any = None) -> dict[str, Any]:
        # 스트리밍한 공개 이벤트를 저장해 실행 후에도 같은 과정을 조회할 수 있게 한다.
        created_at = now()
        with db() as connection:
            cursor = connection.execute(
                "INSERT INTO react_agent_events(run_id,event_type,title,content,tool_name,payload,created_at) VALUES(?,?,?,?,?,?,?)",
                (run_id, event_type, title, content, tool_name,
                 json.dumps(payload, ensure_ascii=False) if payload is not None else None, created_at),
            )
            event_id = cursor.lastrowid
        return {"id": event_id, "run_id": run_id, "type": event_type, "title": title,
                "content": content, "tool_name": tool_name, "payload": payload, "created_at": created_at}

    def stream(agent: dict[str, Any], prompt: str, run_id: str, context: list[dict[str, str]]):
        """LLM이 선택한 도구를 반복 실행하고 각 단계를 한 줄씩 스트리밍한다."""
        definition = hydrate_react_definition(agent["definition"], agent["role"])
        enabled = definition.get("tools", [])
        max_iterations = max(5, min(8, int(definition.get("max_iterations", 6))))
        observations: list[dict[str, Any]] = []
        role_tools = tools_for_role(agent["role"])
        catalog = [{"id": tool["id"], "name": tool["name"], "description": tool["description"]}
                   for tool in role_tools if tool["id"] in enabled]
        yield json.dumps(save_event(run_id, "run_started", "요청 접수", prompt,
                                    payload={"run_id": run_id, "context_turns": len(context), "context_window": 3}), ensure_ascii=False) + "\n"
        try:
            for iteration in range(1, max_iterations + 1):
                decision = gateway.structured(
                    name="react_next_action", model=definition.get("model", {}).get("model_id"),
                    instructions=(definition.get("system_prompt", "") + "\n사용자의 목표를 달성하기 위해 허용된 도구 중 다음 행동 하나를 선택하세요. "
                                  "thought_summary에는 사용자에게 공개 가능한 짧은 판단 근거만 작성하고 내부 사고 과정은 작성하지 마세요. "
                                  "conversation_context에는 같은 채팅 세션의 최근 대화가 있으며, 현재 요청을 해석할 때만 참고하세요. "
                                  "현재 요청에 필요한 도구만 선택하고, 컨텍스트나 이미 수집한 관찰만으로 답할 수 있으면 즉시 FINAL을 선택하세요. "
                                  "모든 도구를 사용할 필요는 없으며 같은 도구를 반복 호출하지 마세요. 근거 종합은 조회된 근거가 있을 때만 사용하세요."),
                    payload={"goal": prompt, "conversation_context": context, "available_tools": catalog,
                             "iteration": iteration, "observations": observations},
                    schema={"type": "object", "additionalProperties": False, "properties": {
                        "thought_summary": {"type": "string"}, "action": {"type": "string", "enum": [*enabled, "FINAL"]},
                        "action_input": {"type": "string"}, "final_answer": {"type": "string"}},
                        "required": ["thought_summary", "action", "action_input", "final_answer"]},
                )
                action = decision.get("action", "FINAL")
                completed = {item["tool"] for item in observations if item.get("tool") in enabled}
                yield json.dumps(save_event(run_id, "reasoning", "판단 요약", decision.get("thought_summary", "다음 행동을 선택했습니다."),
                                            payload={"iteration": iteration, "action": action}), ensure_ascii=False) + "\n"
                time.sleep(.15)
                if action == "FINAL":
                    answer = decision.get("final_answer") or next((item["result"].get("briefing") for item in reversed(observations)
                                                                   if item["result"].get("briefing")), "조사를 완료했습니다.")
                    for chunk in [answer[index:index + 45] for index in range(0, len(answer), 45)]:
                        yield json.dumps({"type": "answer_chunk", "run_id": run_id, "content": chunk}, ensure_ascii=False) + "\n"
                        time.sleep(.04)
                    with db() as connection:
                        connection.execute("UPDATE react_agent_runs SET status='COMPLETED',answer=?,updated_at=? WHERE id=?", (answer, now(), run_id))
                    yield json.dumps(save_event(run_id, "completed", "분석 완료", "최종 브리핑 생성을 완료했습니다.", payload={"answer": answer}), ensure_ascii=False) + "\n"
                    return
                if action in completed:
                    # 같은 조회를 반복하지 않도록 모델에 검증 결과를 다시 관찰로 제공한다.
                    validation = {"error": f"{action} 도구는 이미 실행했습니다. 기존 관찰을 사용하거나 다른 도구 또는 FINAL을 선택하세요."}
                    observations.append({"tool": "runtime_validation", "result": validation})
                    yield json.dumps(save_event(run_id, "tool_result", "도구 호출 생략", validation["error"], action, validation), ensure_ascii=False) + "\n"
                    continue
                synthesis_inputs = {
                    "synthesize_evidence": {"query_operational_db", "search_reports", "lookup_region_info"},
                    "generate_weekly_movement_report": {"query_personnel_movements", "lookup_unit_events", "search_personnel_rules"},
                }
                if action in synthesis_inputs and not completed.intersection(synthesis_inputs[action]):
                    validation = {"error": "근거 종합 전에 요청에 필요한 조회 도구를 하나 이상 실행해야 합니다."}
                    observations.append({"tool": "runtime_validation", "result": validation})
                    yield json.dumps(save_event(run_id, "tool_result", "입력 조건 확인", validation["error"], action, validation), ensure_ascii=False) + "\n"
                    continue
                result = execute_react_tool(db, action, observations, prompt)
                observations.append({"tool": action, "result": result})
                meta = next(tool for tool in role_tools if tool["id"] == action)
                yield json.dumps(save_event(run_id, "tool_result", meta["name"], result.get("summary", "조회가 완료되었습니다."), action, result), ensure_ascii=False) + "\n"
                time.sleep(.18)
            raise ModelGatewayError(f"최대 반복 횟수({max_iterations}) 안에 응답을 완료하지 못했습니다.")
        except Exception as exc:
            with db() as connection:
                connection.execute("UPDATE react_agent_runs SET status='FAILED',updated_at=? WHERE id=?", (now(), run_id))
            yield json.dumps(save_event(run_id, "error", "실행 실패", str(exc)), ensure_ascii=False) + "\n"

    @router.get("/react-tools")
    def tools(x_demo_role: str = Header(...)):
        if x_demo_role not in {"ANALYST", "STAFF", "ADMIN"}:
            raise HTTPException(403, "에이전트 도구를 사용할 권한이 없습니다.")
        return tools_for_role(x_demo_role)

    @router.get("/react-agents")
    def agents(role: str, x_demo_role: str = Header(...)):
        if role != x_demo_role or role not in {"ANALYST", "STAFF", "ADMIN"}:
            raise HTTPException(403, "에이전트 레지스트리에 접근할 권한이 없습니다.")
        with db() as connection:
            return [hydrate_agent(deserialize(item)) for item in connection.execute(
                "SELECT * FROM react_agents WHERE role=? AND owner=? ORDER BY updated_at DESC", (role, session_for(role)["user_id"]))]

    @router.post("/react-agents")
    def create_agent(body: ReactAgentCreateIn, x_demo_role: str = Header(...)):
        if x_demo_role not in {"ANALYST", "STAFF", "ADMIN"}:
            raise HTTPException(403, "에이전트를 만들 권한이 없습니다.")
        agent_id = uid("RAG").lower()
        with db() as connection:
            connection.execute("INSERT INTO react_agents VALUES(?,?,?,?,?,?,?,?,?)",
                               (agent_id, body.name.strip() or "새 조사 에이전트", body.description, x_demo_role,
                                session_for(x_demo_role)["user_id"], "DRAFT", 0,
                                json.dumps(default_react_definition(gateway.model, x_demo_role), ensure_ascii=False), now()))
        return {"id": agent_id}

    @router.get("/react-agents/{agent_id}")
    def get_agent(agent_id: str, x_demo_role: str = Header(...)):
        with db() as connection:
            agent = hydrate_agent(deserialize(connection.execute("SELECT * FROM react_agents WHERE id=?", (agent_id,)).fetchone()))
        require_agent(agent, x_demo_role)
        return agent

    @router.put("/react-agents/{agent_id}")
    def save_agent(agent_id: str, body: ReactAgentIn, x_demo_role: str = Header(...)):
        with db() as connection:
            agent = hydrate_agent(deserialize(connection.execute("SELECT * FROM react_agents WHERE id=?", (agent_id,)).fetchone()))
            require_agent(agent, x_demo_role)
            definition = hydrate_react_definition(body.definition, x_demo_role)
            if not definition["connectors"] or not definition["tools"]:
                raise HTTPException(422, "데이터 또는 외부 시스템을 하나 이상 연결해야 합니다.")
            definition["max_iterations"] = max(5, min(8, int(definition.get("max_iterations", 6))))
            definition.pop("require_approval", None)
            connection.execute("UPDATE react_agents SET name=?,description=?,definition=?,lifecycle='DRAFT',updated_at=? WHERE id=?",
                               (body.name, body.description, json.dumps(definition, ensure_ascii=False), now(), agent_id))
        return {"saved": True, "lifecycle": "DRAFT"}

    @router.post("/react-agents/{agent_id}/publish")
    def publish_agent(agent_id: str, x_demo_role: str = Header(...)):
        with db() as connection:
            agent = hydrate_agent(deserialize(connection.execute("SELECT * FROM react_agents WHERE id=?", (agent_id,)).fetchone()))
            require_agent(agent, x_demo_role)
            version = int(agent["version"]) + 1
            connection.execute("UPDATE react_agents SET lifecycle='PUBLISHED',version=?,updated_at=? WHERE id=?", (version, now(), agent_id))
        return {"published": True, "version": version}

    @router.delete("/react-agents/{agent_id}")
    def delete_agent(agent_id: str, x_demo_role: str = Header(...)):
        if agent_id in {"react-paju-briefing", "react-weekly-movement", "react-weekly-threat-comparison"}:
            raise HTTPException(409, "기본 제공 에이전트는 삭제할 수 없습니다.")
        with db() as connection:
            agent = hydrate_agent(deserialize(connection.execute("SELECT * FROM react_agents WHERE id=?", (agent_id,)).fetchone()))
            require_agent(agent, x_demo_role)
            connection.execute("DELETE FROM react_agents WHERE id=?", (agent_id,))
        return {"deleted": True}

    @router.get("/react-agents/{agent_id}/sessions")
    def list_sessions(agent_id: str, x_demo_role: str = Header(...)):
        with db() as connection:
            agent = hydrate_agent(deserialize(connection.execute("SELECT * FROM react_agents WHERE id=?", (agent_id,)).fetchone()))
            require_agent(agent, x_demo_role)
            return [dict(item) for item in connection.execute(
                "SELECT s.*,count(r.id) AS turn_count FROM react_chat_sessions s LEFT JOIN react_agent_runs r "
                "ON r.session_id=s.id AND r.status='COMPLETED' WHERE s.react_agent_id=? AND s.user_id=? "
                "GROUP BY s.id ORDER BY s.updated_at DESC", (agent_id, session_for(x_demo_role)["user_id"]))]

    @router.post("/react-agents/{agent_id}/sessions")
    def create_session(agent_id: str, body: ReactSessionCreateIn, x_demo_role: str = Header(...)):
        with db() as connection:
            agent = hydrate_agent(deserialize(connection.execute("SELECT * FROM react_agents WHERE id=?", (agent_id,)).fetchone()))
            require_agent(agent, x_demo_role)
            session_id, timestamp, title = uid("CHAT"), now(), body.title.strip() or "새 대화"
            connection.execute("INSERT INTO react_chat_sessions VALUES(?,?,?,?,?,?)",
                               (session_id, agent_id, session_for(x_demo_role)["user_id"], title, timestamp, timestamp))
        return {"id": session_id, "title": title, "turn_count": 0, "created_at": timestamp, "updated_at": timestamp}

    def require_session(connection, agent_id: str, session_id: str, role: str):
        chat = connection.execute("SELECT * FROM react_chat_sessions WHERE id=? AND react_agent_id=? AND user_id=?",
                                  (session_id, agent_id, session_for(role)["user_id"])).fetchone()
        if not chat:
            raise HTTPException(404, "채팅 세션을 찾을 수 없습니다.")
        return dict(chat)

    @router.get("/react-agents/{agent_id}/sessions/{session_id}")
    def get_session(agent_id: str, session_id: str, x_demo_role: str = Header(...)):
        with db() as connection:
            agent = hydrate_agent(deserialize(connection.execute("SELECT * FROM react_agents WHERE id=?", (agent_id,)).fetchone()))
            require_agent(agent, x_demo_role)
            chat = require_session(connection, agent_id, session_id, x_demo_role)
            messages = [dict(item) for item in connection.execute(
                "SELECT id,prompt,answer,status,created_at FROM react_agent_runs WHERE session_id=? ORDER BY created_at", (session_id,))]
        return {**chat, "messages": messages, "context_window": 3}

    @router.delete("/react-agents/{agent_id}/sessions/{session_id}")
    def delete_session(agent_id: str, session_id: str, x_demo_role: str = Header(...)):
        with db() as connection:
            agent = hydrate_agent(deserialize(connection.execute("SELECT * FROM react_agents WHERE id=?", (agent_id,)).fetchone()))
            require_agent(agent, x_demo_role)
            require_session(connection, agent_id, session_id, x_demo_role)
            run_ids = [item["id"] for item in connection.execute("SELECT id FROM react_agent_runs WHERE session_id=?", (session_id,))]
            if run_ids:
                placeholders = ",".join("?" for _ in run_ids)
                connection.execute(f"DELETE FROM react_agent_events WHERE run_id IN ({placeholders})", run_ids)
            connection.execute("DELETE FROM react_agent_runs WHERE session_id=?", (session_id,))
            connection.execute("DELETE FROM react_chat_sessions WHERE id=?", (session_id,))
        return {"deleted": True}

    @router.post("/react-agents/{agent_id}/runs/stream")
    def start_run(agent_id: str, body: ReactRunIn, x_demo_role: str = Header(...)):
        if not body.prompt.strip():
            raise HTTPException(422, "요청 내용을 입력하세요.")
        with db() as connection:
            agent = deserialize(connection.execute("SELECT * FROM react_agents WHERE id=?", (agent_id,)).fetchone())
            require_agent(agent, x_demo_role)
            if agent["lifecycle"] != "PUBLISHED":
                raise HTTPException(409, "게시된 에이전트만 실행할 수 있습니다.")
            user_id = session_for(x_demo_role)["user_id"]
            chat = require_session(connection, agent_id, body.session_id, x_demo_role)
            # 같은 세션의 최근 완료 3턴만 모델 컨텍스트로 전달한다.
            prior = list(connection.execute("SELECT prompt,answer FROM react_agent_runs WHERE session_id=? AND status='COMPLETED' "
                                            "ORDER BY created_at DESC LIMIT 3", (body.session_id,)))
            context = [{"user": item["prompt"], "assistant": item["answer"]} for item in reversed(prior)]
            run_id, timestamp = uid("RUN"), now()
            connection.execute("INSERT INTO react_agent_runs(id,react_agent_id,user_id,status,prompt,answer,created_at,updated_at,session_id) "
                               "VALUES(?,?,?,?,?,?,?,?,?)", (run_id, agent_id, user_id, "RUNNING", body.prompt, "", timestamp, timestamp, body.session_id))
            title = body.prompt.strip()[:32] if chat["title"] == "새 대화" else chat["title"]
            connection.execute("UPDATE react_chat_sessions SET title=?,updated_at=? WHERE id=?", (title, timestamp, body.session_id))
        return StreamingResponse(stream(agent, body.prompt, run_id, context), media_type="application/x-ndjson",
                                 headers={"X-Run-Id": run_id, "Cache-Control": "no-cache"})

    @router.get("/react-agent-runs/{run_id}")
    def get_run(run_id: str, x_demo_role: str = Header(...)):
        with db() as connection:
            item = connection.execute("SELECT r.*,a.role,a.owner FROM react_agent_runs r JOIN react_agents a "
                                      "ON a.id=r.react_agent_id WHERE r.id=?", (run_id,)).fetchone()
            run = deserialize(item)
            if not run or run["role"] != x_demo_role or run["owner"] != session_for(x_demo_role)["user_id"]:
                raise HTTPException(404, "에이전트 실행을 찾을 수 없습니다.")
            events = [deserialize(item) for item in connection.execute("SELECT * FROM react_agent_events WHERE run_id=? ORDER BY id", (run_id,))]
        return {**run, "events": events}

    return router
