from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from pydantic import BaseModel
from dotenv import load_dotenv

from .gateway import ModelGateway, ModelGatewayError
from .runtime import LangGraphRuntime

load_dotenv(Path(__file__).parents[2] / ".env")

DB_PATH = Path(os.getenv("DEMO_DB_PATH", Path(__file__).parents[1] / "demo.db"))
RUNTIME = LangGraphRuntime(DB_PATH.with_name("checkpoints.db"))
GATEWAY = ModelGateway()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


ANALYST_NODES = [
    ("sensor", "감시 센서 이벤트", "trigger"), ("filter", "이벤트 조건 확인", "control"),
    ("context", "작전 정보 조회", "data"), ("threat", "위협 분석·초안 생성", "ai"),
    ("approval", "분석관 검토·승인", "control"), ("send", "지역 보고서 발행", "action"),
]
STAFF_NODES = [
    ("report_trigger", "승인 지역보고 접수", "trigger"), ("reports", "승인 지역보고 수집", "data"),
    ("context", "접경지역 작전상황 조회", "data"), ("synthesis", "위협 종합·초안 생성", "ai"),
    ("approval", "참모 검토·승인", "control"), ("send", "지휘관 보고서 발행", "action"),
]


def graph(role: str) -> dict[str, Any]:
    source = ANALYST_NODES if role == "ANALYST" else STAFF_NODES
    nodes = []
    for i, (node_id, label, group) in enumerate(source):
        x = 80 + (i % 4) * 230
        y = 70 + (i // 4) * 150
        config: dict[str, Any] = {}
        if node_id == "filter": config = {"min_confidence": 0.8, "min_object_count": 2}
        elif node_id == "threat": config = {"system_prompt": "대한민국 접경지역 센서 이벤트를 분석해 위협 수준, 근거 요약과 분석관 승인용 지역 보고서 초안을 한국어로 작성하세요."}
        elif node_id == "synthesis": config = {"system_prompt": "승인된 접경지역 보고를 종합해 위협 수준, 우선 대응 지역과 참모 승인용 지휘관 보고서 초안을 한국어로 작성하세요."}
        elif node_id == "context": config = {"query": "최근 24시간 작전 정보와 관련 관측 기록"}
        if node_id in {"threat", "synthesis"}: config["model_id"] = GATEWAY.model
        nodes.append({"id": node_id, "type": node_id, "label": label, "group": group,
                      "position": {"x": x, "y": y}, "config": config})
    edges = [{"id": f"e-{i}", "source": source[i][0], "target": source[i+1][0]}
             for i in range(len(source)-1)]
    return {"schema_version": "1", "nodes": nodes, "edges": edges,
            "model": {"provider": "openai", "model_id": GATEWAY.model, "temperature": 0.2}}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY, name TEXT, role TEXT, area TEXT, owner TEXT,
          lifecycle TEXT, version INTEGER, definition TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS agent_versions(agent_id TEXT, version INTEGER, definition TEXT, published_at TEXT,
          PRIMARY KEY(agent_id,version));
        CREATE TABLE IF NOT EXISTS executions(id TEXT PRIMARY KEY, agent_id TEXT, agent_name TEXT, role TEXT,
          area TEXT, version INTEGER, status TEXT, trigger_type TEXT, trigger TEXT, snapshot TEXT,
          initiating_context TEXT, source_report_id TEXT, child_execution_id TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS trace(id INTEGER PRIMARY KEY AUTOINCREMENT, execution_id TEXT, node_id TEXT,
          label TEXT, status TEXT, input_summary TEXT, output_summary TEXT, started_at TEXT, ended_at TEXT);
        CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, execution_id TEXT UNIQUE, reviewer_role TEXT,
          status TEXT, draft TEXT, original_draft TEXT, decision TEXT, actor TEXT, comment TEXT, decided_at TEXT);
        CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, kind TEXT, title TEXT, area TEXT, threat TEXT,
          content TEXT, source_execution_id TEXT UNIQUE, approved_by TEXT, approved_at TEXT,
          source_report_ids TEXT, fixture INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS report_events(id TEXT PRIMARY KEY, report_id TEXT UNIQUE, status TEXT,
          child_execution_id TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY, role TEXT, title TEXT, body TEXT,
          execution_id TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS sensor_events(id TEXT PRIMARY KEY, sensor_id TEXT, type TEXT, area TEXT,
          object_count INTEGER, confidence REAL, execution_id TEXT, created_at TEXT);
        """)
        if not c.execute("SELECT 1 FROM agents").fetchone():
            for agent_id, name, role, area, owner in [
                ("analyst-a12", "파주 감시·위협분석 워크플로우", "ANALYST", "경기도 파주시", "analyst.a12"),
                ("staff-synthesis", "접경지역 상황종합 워크플로우", "STAFF", "접경지역 전체", "staff.ops"),
            ]:
                c.execute("INSERT INTO agents VALUES(?,?,?,?,?,?,?,?,?)", (agent_id, name, role, area, owner,
                          "PUBLISHED", 1, json.dumps(graph(role), ensure_ascii=False), now()))
                c.execute("INSERT OR IGNORE INTO agent_versions VALUES(?,?,?,?)",
                          (agent_id, 1, json.dumps(graph(role), ensure_ascii=False), now()))
        if not c.execute("SELECT 1 FROM reports WHERE fixture=1").fetchone():
            for rid, area, threat, content in [
                ("RPT-B07-SEED", "경기도 연천군", "MEDIUM", "연천군 북부에서 반복 이동 징후가 식별되었습니다."),
                ("RPT-C03-SEED", "강원특별자치도 철원군", "LOW", "철원군 일대는 특이 동향 없이 안정적입니다."),
            ]:
                c.execute("INSERT INTO reports VALUES(?,?,?,?,?,?,?,?,?,?,1)",
                          (rid, "REGIONAL", f"{area} 지역 분석 보고", area, threat, content, None,
                           "seed.system", now(), "[]"))
        # 기존 데모 DB의 구조와 사용자 설정은 유지하고 표시용 기본 데이터만 새 명칭으로 이관한다.
        for agent_id, name, area, owner, role in [
            ("analyst-a12", "파주 감시·위협분석 워크플로우", "경기도 파주시", "analyst.a12", "ANALYST"),
            ("staff-synthesis", "접경지역 상황종합 워크플로우", "접경지역 전체", "staff.ops", "STAFF"),
        ]:
            saved = c.execute("SELECT definition FROM agents WHERE id=?", (agent_id,)).fetchone()
            if saved:
                definition = graph(role)
                c.execute("UPDATE agents SET name=?,area=?,owner=?,definition=? WHERE id=?",
                          (name, area, owner, json.dumps(definition, ensure_ascii=False), agent_id))
                current=c.execute("SELECT version,lifecycle FROM agents WHERE id=?",(agent_id,)).fetchone()
                if current and current["lifecycle"]=="PUBLISHED":
                    c.execute("INSERT OR IGNORE INTO agent_versions VALUES(?,?,?,?)",
                              (agent_id,current["version"],json.dumps(definition,ensure_ascii=False),now()))
        c.execute("UPDATE reports SET area='경기도 연천군',title='연천군 위협분석 보고',content='연천군 북부에서 반복 이동 징후가 식별되었습니다.' WHERE id='RPT-B07-SEED'")
        c.execute("UPDATE reports SET area='강원특별자치도 철원군',title='철원군 위협분석 보고',content='철원군 일대는 특이 동향 없이 안정적입니다.' WHERE id='RPT-C03-SEED'")
        c.execute("UPDATE reports SET area='경기도 파주시',title=replace(title,'A-12 지역','파주시') WHERE area='A-12'")
        c.execute("UPDATE executions SET area='경기도 파주시' WHERE area='A-12'")
        c.execute("UPDATE executions SET area='접경지역 전체' WHERE area='ALL'")


def row(r):
    if not r: return None
    d = dict(r)
    for key in ("definition", "trigger", "snapshot", "initiating_context", "source_report_ids"):
        if key in d and d[key]:
            try: d[key] = json.loads(d[key])
            except Exception: pass
    if "fixture" in d: d["fixture"] = bool(d["fixture"])
    return d


def session_for(role: str):
    role = role.upper()
    if role not in {"ANALYST", "STAFF", "COMMANDER"}: raise HTTPException(400, "지원하지 않는 역할입니다.")
    return {"user_id": {"ANALYST":"analyst.a12","STAFF":"staff.ops","COMMANDER":"commander.demo"}[role],
            "role": role, "area": "경기도 파주시" if role == "ANALYST" else "접경지역 전체",
            "permissions": {
                "ANALYST":["agent:create","agent:edit","agent:publish","agent:delete","sensor:emit","review:analyst"],
                "STAFF":["agent:create","agent:edit","agent:publish","agent:delete","review:staff"],
                "COMMANDER":["report:read","situation:read"],
            }[role]}


def require_role(expected: str, role: str | None):
    if role != expected: raise HTTPException(403, f"{expected} 역할만 승인할 수 있습니다.")

def require_agent_owner(agent: dict[str, Any], role: str):
    require_role(agent["role"],role)
    if agent["owner"] != session_for(role)["user_id"]: raise HTTPException(403,"본인 소유 워크플로우만 관리할 수 있습니다.")


def trace(c, eid, node_id, label, status="SUCCEEDED", inp="", out=""):
    t = now()
    c.execute("INSERT INTO trace(execution_id,node_id,label,status,input_summary,output_summary,started_at,ended_at) VALUES(?,?,?,?,?,?,?,?)",
              (eid,node_id,label,status,inp,out,t,t if status != "WAITING" else None))


def invoke_workflow(c, eid: str, agent: dict, trigger_payload: dict, resume: dict | None = None):
    definition = agent["definition"] if isinstance(agent["definition"], dict) else json.loads(agent["definition"])
    role = agent["role"]
    default_draft = "분석 결과를 기다리고 있습니다."

    def runner(spec, state, phase):
        node_id=spec["id"]; capability=spec.get("type",node_id); label=spec.get("label",node_id)
        if phase == "before_interrupt":
            existing=row(c.execute("SELECT * FROM approvals WHERE execution_id=?",(eid,)).fetchone())
            if not existing:
                approval_id=uid("APR")
                draft=state.get("draft",default_draft)
                c.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (approval_id,eid,role,"PENDING",draft,draft,None,None,None,None))
                trace(c,eid,node_id,label,"WAITING",inp=f"보고서 초안 {len(draft)}자",out="명시적 승인 대기")
                c.execute("UPDATE executions SET status=?,updated_at=? WHERE id=?",
                          (f"WAITING_FOR_{role}_APPROVAL",now(),eid))
                reviewer="분석관" if role=="ANALYST" else "참모"
                c.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?)",(uid("NTF"),role,f"{reviewer} 승인 요청",
                          "AI가 생성한 보고서 초안이 승인을 기다리고 있습니다.",eid,now()))
                c.commit(); existing={"id":approval_id,"draft":draft}
            return {"approval_id":existing["id"],"reviewer_role":role,"draft":existing["draft"]}
        if phase == "after_interrupt":
            decision=state.get("approval_decision","APPROVE")
            c.execute("UPDATE trace SET status=?,ended_at=?,output_summary=? WHERE execution_id=? AND node_id=?",
                      ("FAILED" if decision=="REJECT" else "SUCCEEDED",now(),decision,eid,node_id))
            c.commit()
            return {"approval_decision":decision,"draft":state.get("edited_content") or state.get("draft",default_draft)}
        output=""
        updates={}
        config=spec.get("config",{})
        event=state.get("event",{})
        input_text={
            "sensor": f"{event.get('sensor_id','센서')} · {event.get('type','이벤트')}",
            "filter": f"신뢰도 {event.get('confidence','-')} · 탐지 {event.get('object_count','-')}개",
            "context": f"{state.get('area',agent['area'])} · {config.get('query','작전 정보')}",
            "threat": f"센서 이벤트 + 근거 {len(state.get('evidence_ids',[]))}건",
            "report_trigger": f"승인 보고 {event.get('report_id','-')}",
            "reports": f"보고 이벤트 {event.get('event_id','-')}",
            "synthesis": f"승인 지역보고 {len(state.get('source_report_ids',[]))}건",
            "generator": f"위협 {state.get('threat_level','-')} · 분석 요약",
            "send": f"승인된 초안 {len(state.get('draft',''))}자",
        }.get(capability,f"{label} state")
        if capability=="filter":
            min_conf=float(config.get("min_confidence",.8)); min_count=int(config.get("min_object_count",2))
            passed=float(event.get("confidence",0))>=min_conf and int(event.get("object_count",0))>=min_count
            output=(f"조건 통과 · 신뢰도 {event.get('confidence')} ≥ {min_conf}, 탐지 {event.get('object_count')} ≥ {min_count}" if passed else
                    f"조건 미달 · 신뢰도 {event.get('confidence')} / 탐지 {event.get('object_count')}"); updates["filtered"]=not passed
        elif capability=="context": output=f"{config.get('query','작전 정보')} · 모의 근거 2건 조회"; updates["evidence_ids"]=["OBS-PJU-017","CTX-PJU-003"]
        elif capability=="threat":
            result=GATEWAY.structured(name="threat_analysis",
                instructions=config.get("system_prompt","센서 이벤트를 분석해 위협 수준, 요약과 승인용 보고서 초안을 한국어로 작성하세요."),
                payload={"event":state.get("event",{}),"evidence_ids":state.get("evidence_ids",[])},
                schema={"type":"object","properties":{"threat_level":{"type":"string","enum":["LOW","MEDIUM","HIGH"]},"summary":{"type":"string"},"evidence_ids":{"type":"array","items":{"type":"string"}},"draft":{"type":"string"}},"required":["threat_level","summary","evidence_ids","draft"],"additionalProperties":False},
                model=config.get("model_id"))
            output=f"{result['threat_level']} · {result['summary']}"; updates.update(result)
        elif capability=="reports": output="파주·연천·철원 승인 보고서 수집"; updates["source_report_ids"]=["파주 신규보고","RPT-B07-SEED","RPT-C03-SEED"]
        elif capability=="synthesis":
            result=GATEWAY.structured(name="situation_synthesis",
                instructions=config.get("system_prompt","승인된 접경지역 보고를 종합해 위협 수준, 요약과 승인용 지휘관 보고서 초안을 한국어로 작성하세요."),
                payload={"source_report_ids":state.get("source_report_ids",[])},
                schema={"type":"object","properties":{"overall_threat_level":{"type":"string","enum":["LOW","MEDIUM","HIGH"]},"summary":{"type":"string"},"priority_areas":{"type":"array","items":{"type":"string"}},"source_report_ids":{"type":"array","items":{"type":"string"}},"draft":{"type":"string"}},"required":["overall_threat_level","summary","priority_areas","source_report_ids","draft"],"additionalProperties":False},
                model=config.get("model_id"))
            output=f"{result['overall_threat_level']} · {result['summary']}"; updates.update(result); updates["threat_level"]=result["overall_threat_level"]
        elif capability=="generator":
            level=state.get("threat_level","미정"); summary=state.get("summary",default_draft)
            draft=f"[{agent['area']} 상황 보고]\n위협 수준: {level}\n\n{summary}\n\n권고: {config.get('recommendation','관련 감시 자산을 유지하고 승인된 절차에 따라 후속 조치하십시오.')}"
            output="LLM 분석 기반 승인용 보고서 초안 생성"; updates["draft"]=draft
        else: output=f"{label} 처리 완료"
        trace(c,eid,node_id,label,inp=input_text,out=output); c.commit()
        return updates

    compiled=RUNTIME.compile(definition,runner)
    config=RUNTIME.config(eid)
    if resume is None:
        initial={"execution_id":eid,"role":role,"area":agent["area"],"event":trigger_payload,"draft":default_draft}
        return compiled.invoke(initial,config=config)
    return compiled.invoke(Command(resume=resume),config=config)


def create_execution(c, agent, trigger_payload, initiating, source_report_id=None):
    eid = uid("EXE")
    snap = agent["definition"] if isinstance(agent["definition"], str) else json.dumps(agent["definition"], ensure_ascii=False)
    c.execute("INSERT INTO executions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,agent["id"],agent["name"],agent["role"],
              agent["area"],agent["version"],"RUNNING","SENSOR_EVENT" if agent["role"]=="ANALYST" else "APPROVED_REPORT",
              json.dumps(trigger_payload,ensure_ascii=False),snap,json.dumps(initiating),source_report_id,None,now(),now()))
    c.commit()
    try:
        result=invoke_workflow(c,eid,{**agent,"definition":json.loads(snap)},trigger_payload)
        if result.get("filtered"):
            c.execute("UPDATE executions SET status='COMPLETED',updated_at=? WHERE id=?",(now(),eid))
    except ModelGatewayError as exc:
        trace(c,eid,"model_gateway","외부 LLM 호출","FAILED",out=str(exc))
        c.execute("UPDATE executions SET status='FAILED',updated_at=? WHERE id=?",(now(),eid))
    return eid


app = FastAPI(title="Defense Workflow Builder Demo")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup(): init_db()


class SessionIn(BaseModel): role: Literal["ANALYST","STAFF","COMMANDER"]
class AgentIn(BaseModel): definition: dict[str, Any]
class AgentCreateIn(BaseModel):
    name: str
    description: str = ""
    role: Literal["ANALYST","STAFF"]
    area: str
    template: Literal["BLANK","ANALYST","STAFF"] = "BLANK"
class DecisionIn(BaseModel): decision: Literal["APPROVE","EDIT_APPROVE","REJECT"]; content: str | None = None; comment: str | None = None
class SensorEventIn(BaseModel):
    sensor_id: str = "파주-감시센서-03"
    type: str = "이동체 감지"
    area: str = "경기도 파주시"
    object_count: int
    confidence: float


@app.get("/api/health")
def health(): return {"status":"ok",**GATEWAY.status(),"database":str(DB_PATH)}

@app.get("/api/models")
def models(x_demo_role: str = Header(...)):
    if x_demo_role not in {"ANALYST","STAFF"}: raise HTTPException(403,"워크플로우 편집 권한이 없습니다.")
    return [{"id":model,"label":model,"default":model==GATEWAY.model} for model in GATEWAY.allowed_models]

@app.post("/api/session")
def set_session(body: SessionIn): return session_for(body.role)

@app.get("/api/nodes")
def nodes(role: str, x_demo_role: str = Header(...)):
    if role != x_demo_role: raise HTTPException(403,"현재 역할에서 사용할 수 없는 노드입니다.")
    src = ANALYST_NODES if role == "ANALYST" else STAFF_NODES if role == "STAFF" else []
    defaults={n["type"]:n["config"] for n in graph(role).get("nodes",[])} if src else {}
    return [{"type":n,"label":l,"group":g,"config":defaults.get(n,{})} for n,l,g in src]

@app.get("/api/agents")
def agents(role: str, x_demo_role: str = Header(...)):
    if role != x_demo_role: raise HTTPException(403,"다른 사용자의 워크플로우 레지스트리에 접근할 수 없습니다.")
    if role == "COMMANDER": return []
    owner=session_for(role)["user_id"]
    with db() as c:
        result=[row(r) for r in c.execute("SELECT * FROM agents WHERE role=? AND owner=? ORDER BY name",(role,owner))]
        for agent in result: agent["deletable"]=agent["id"] not in {"analyst-a12","staff-synthesis"}
        return result

@app.post("/api/agents")
def create_agent(body: AgentCreateIn, x_demo_role: str = Header(...)):
    require_role(body.role, x_demo_role)
    agent_id=uid("AGT").lower()
    definition=graph(body.role) if body.template == body.role else {
        "schema_version":"1", "description":body.description, "nodes":[], "edges":[],
        "model":{"provider":"openai","model_id":GATEWAY.model,"temperature":0.2},
    }
    definition["description"]=body.description
    owner=session_for(body.role)["user_id"]
    with db() as c:
        c.execute("INSERT INTO agents VALUES(?,?,?,?,?,?,?,?,?)",(agent_id,body.name,body.role,body.area,owner,
                  "DRAFT",0,json.dumps(definition,ensure_ascii=False),now()))
    return {"id":agent_id,"lifecycle":"DRAFT","version":0}

@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str, x_demo_role: str = Header(...)):
    if agent_id in {"analyst-a12","staff-synthesis"}: raise HTTPException(409,"기본 제공 워크플로우는 삭제할 수 없습니다.")
    with db() as c:
        agent=row(c.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone())
        if not agent: raise HTTPException(404,"워크플로우를 찾을 수 없습니다.")
        require_role(agent["role"],x_demo_role)
        if agent["owner"] != session_for(x_demo_role)["user_id"]: raise HTTPException(403,"본인이 만든 워크플로우만 삭제할 수 있습니다.")
        c.execute("DELETE FROM agent_versions WHERE agent_id=?",(agent_id,))
        c.execute("DELETE FROM agents WHERE id=?",(agent_id,))
    return {"deleted":True,"id":agent_id}

@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: str, x_demo_role: str = Header(...)):
    with db() as c:
        out=row(c.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone())
        if not out: raise HTTPException(404,"워크플로우를 찾을 수 없습니다.")
        require_agent_owner(out,x_demo_role)
        return out

@app.put("/api/agents/{agent_id}")
def save_agent(agent_id: str, body: AgentIn, x_demo_role: str = Header(...)):
    with db() as c:
        agent=row(c.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone())
        if not agent: raise HTTPException(404,"워크플로우 없음")
        require_agent_owner(agent,x_demo_role)
        c.execute("UPDATE agents SET definition=?,lifecycle='DRAFT',updated_at=? WHERE id=?",
                  (json.dumps(body.definition,ensure_ascii=False),now(),agent_id))
    return {"saved":True,"lifecycle":"DRAFT"}

def validate_definition(d):
    errors=[]; nodes=d.get("nodes",[]); edges=d.get("edges",[]); ids=[n.get("id") for n in nodes]
    if len(ids)!=len(set(ids)): errors.append("노드 ID가 중복되었습니다.")
    if not nodes: errors.append("워크플로에 노드가 필요합니다.")
    if any(e.get("source") not in ids or e.get("target") not in ids for e in edges): errors.append("연결되지 않은 edge endpoint가 있습니다.")
    if not any("approval" in (n.get("type","")+n.get("id","")) for n in nodes): errors.append("Human Approval 노드가 필요합니다.")
    send_ids={n.get("id") for n in nodes if "send" in (n.get("type","")+n.get("id",""))}
    if not send_ids: errors.append("Send Report 노드가 필요합니다.")
    if nodes and edges:
        incoming={node_id:0 for node_id in ids}; outgoing={node_id:[] for node_id in ids}
        for edge in edges:
            if edge.get("source") in outgoing and edge.get("target") in incoming:
                outgoing[edge["source"]].append(edge["target"]); incoming[edge["target"]]+=1
        starts=[node_id for node_id,count in incoming.items() if count==0]
        if len(starts)!=1: errors.append("연결된 시작 노드는 정확히 하나여야 합니다.")
        reachable=set(starts); stack=list(starts)
        while stack:
            for target in outgoing.get(stack.pop(),[]):
                if target not in reachable: reachable.add(target); stack.append(target)
        if send_ids and not send_ids.intersection(reachable): errors.append("시작 노드에서 보고서 확정 노드까지 연결해야 합니다.")
        approval_ids={n.get("id") for n in nodes if "approval" in (n.get("type","")+n.get("id",""))}
        if not approval_ids.intersection(reachable): errors.append("승인 노드가 실행 경로에 연결되어야 합니다.")
    return errors

@app.post("/api/agents/{agent_id}/validate")
def validate(agent_id: str, body: AgentIn, x_demo_role: str = Header(...)):
    with db() as c:
        agent=row(c.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone())
        if not agent: raise HTTPException(404,"워크플로우 없음")
        require_agent_owner(agent,x_demo_role)
    return {"valid":not (e:=validate_definition(body.definition)),"errors":e}

@app.post("/api/agents/{agent_id}/publish")
def publish(agent_id: str, x_demo_role: str = Header(...)):
    with db() as c:
        a=row(c.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone())
        if not a: raise HTTPException(404,"워크플로우 없음")
        require_agent_owner(a,x_demo_role)
        errors=validate_definition(a["definition"])
        if errors: raise HTTPException(422,{"errors":errors})
        version=a["version"]+1 if a["lifecycle"]=="DRAFT" else a["version"]
        c.execute("INSERT OR IGNORE INTO agent_versions VALUES(?,?,?,?)",
                  (agent_id,version,json.dumps(a["definition"],ensure_ascii=False),now()))
        c.execute("UPDATE agents SET lifecycle='PUBLISHED',version=?,updated_at=? WHERE id=?",(version,now(),agent_id))
        return {"published":True,"version":version}

@app.post("/api/agents/{agent_id}/test")
def test_agent(agent_id: str, x_demo_role: str = Header(default="ANALYST")):
    with db() as c:
        a=row(c.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone())
        if not a: raise HTTPException(404,"워크플로우 없음")
        require_role(a["role"],x_demo_role)
        errors=validate_definition(a["definition"])
        if errors: raise HTTPException(422,{"errors":errors})
        fixture={"sensor_id":"파주-감시센서-03","type":"이동체 감지","area":"경기도 파주시","object_count":4,"confidence":0.94}
        eid=create_execution(c,a,fixture,session_for(x_demo_role))
        return {"execution_id":eid}

@app.post("/api/sensor-events")
def sensor_event(body: SensorEventIn, x_demo_role: str = Header(default="ANALYST")):
    require_role("ANALYST",x_demo_role)
    if not 1 <= body.object_count <= 12: raise HTTPException(422,"탐지 개체 수는 1~12 범위여야 합니다.")
    if not .5 <= body.confidence <= .99: raise HTTPException(422,"신뢰도는 0.50~0.99 범위여야 합니다.")
    if body.area != "경기도 파주시": raise HTTPException(422,"이 데모 센서는 경기도 파주시만 지원합니다.")
    with db() as c:
        agent=row(c.execute("SELECT * FROM agents WHERE role='ANALYST' AND area=? AND lifecycle='PUBLISHED' ORDER BY updated_at DESC LIMIT 1",(body.area,)).fetchone())
        if not agent: raise HTTPException(409,"게시된 파주시 분석 워크플로우가 없습니다.")
        payload=body.model_dump(); event_id=uid("SNS"); payload["event_id"]=event_id
        eid=create_execution(c,agent,payload,session_for("ANALYST"))
        c.execute("INSERT INTO sensor_events VALUES(?,?,?,?,?,?,?,?)",(event_id,body.sensor_id,body.type,body.area,body.object_count,body.confidence,eid,now()))
        c.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?)",(uid("NTF"),"COMMANDER","파주시 센서 이벤트",
                  f"{body.type} · 탐지 {body.object_count}개 · 신뢰도 {body.confidence:.2f}",eid,now()))
        status=c.execute("SELECT status FROM executions WHERE id=?",(eid,)).fetchone()[0]
        return {"event_id":event_id,"execution_id":eid,"status":status}

@app.get("/api/executions")
def executions(role: str):
    with db() as c:
        q="SELECT * FROM executions"
        params=()
        if role=="ANALYST": q+=" WHERE role='ANALYST' AND area='경기도 파주시'"
        elif role=="STAFF": q+=" WHERE role IN ('ANALYST','STAFF')"
        elif role=="COMMANDER": q+=" WHERE status='COMPLETED'"
        return [row(r) for r in c.execute(q+" ORDER BY created_at DESC",params)]

@app.get("/api/executions/{eid}")
def execution(eid: str):
    with db() as c:
        e=row(c.execute("SELECT * FROM executions WHERE id=?",(eid,)).fetchone())
        if not e: raise HTTPException(404,"실행 없음")
        e["trace"]=[row(r) for r in c.execute("SELECT * FROM trace WHERE execution_id=? ORDER BY id",(eid,))]
        e["approval"]=row(c.execute("SELECT * FROM approvals WHERE execution_id=?",(eid,)).fetchone())
        e["reports"]=[row(r) for r in c.execute("SELECT * FROM reports WHERE source_execution_id=?",(eid,))]
        return e

@app.post("/api/approvals/{approval_id}/decision")
def decision(approval_id: str, body: DecisionIn, x_demo_role: str = Header(...)):
    with db() as c:
        a=row(c.execute("SELECT * FROM approvals WHERE id=?",(approval_id,)).fetchone())
        if not a: raise HTTPException(404,"승인 요청 없음")
        require_role(a["reviewer_role"],x_demo_role)
        if a["status"]!="PENDING": raise HTTPException(409,"이미 처리된 승인입니다.")
        content=body.content if body.decision=="EDIT_APPROVE" and body.content else a["draft"]
        actor=session_for(x_demo_role)["user_id"]
        c.execute("UPDATE approvals SET status=?,decision=?,actor=?,comment=?,draft=?,decided_at=? WHERE id=?",
                  ("REJECTED" if body.decision=="REJECT" else "APPROVED",body.decision,actor,body.comment,content,now(),approval_id))
        eid=a["execution_id"]
        e=row(c.execute("SELECT * FROM executions WHERE id=?",(eid,)).fetchone())
        agent={"id":e["agent_id"],"name":e["agent_name"],"role":e["role"],"area":e["area"],
               "version":e["version"],"definition":e["snapshot"]}
        c.commit()
        if body.decision=="REJECT":
            invoke_workflow(c,eid,agent,e["trigger"],{"approval_decision":"REJECT","edited_content":content})
            c.execute("UPDATE executions SET status='REJECTED',updated_at=? WHERE id=?",(now(),eid)); return {"status":"REJECTED"}
        c.execute("UPDATE executions SET status='RUNNING',updated_at=? WHERE id=?",(now(),eid)); c.commit()
        invoke_workflow(c,eid,agent,e["trigger"],{"approval_decision":body.decision,"edited_content":content})
        report_id=uid("RPT")
        kind="REGIONAL" if e["role"]=="ANALYST" else "COMMANDER"
        source_ids=[]
        if kind=="COMMANDER":
            source_ids=[r["id"] for r in c.execute("SELECT id FROM reports WHERE kind='REGIONAL' ORDER BY approved_at DESC LIMIT 3")]
        ai_node="threat" if kind=="REGIONAL" else "synthesis"
        ai_trace=c.execute("SELECT output_summary FROM trace WHERE execution_id=? AND node_id=? AND status='SUCCEEDED' ORDER BY id DESC LIMIT 1",(eid,ai_node)).fetchone()
        threat=(ai_trace["output_summary"].split(" · ",1)[0] if ai_trace and ai_trace["output_summary"] else "MEDIUM")
        c.execute("INSERT OR IGNORE INTO reports VALUES(?,?,?,?,?,?,?,?,?,?,0)",(report_id,kind,
                  "파주시 위협분석 보고" if kind=="REGIONAL" else "접경지역 종합상황 보고",e["area"],threat,content,eid,actor,now(),json.dumps(source_ids)))
        c.execute("UPDATE executions SET status='COMPLETED',updated_at=? WHERE id=?",(now(),eid))
        if kind=="COMMANDER":
            c.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?)",(uid("NTF"),"COMMANDER","새 지휘관 보고서 도착",
                      "접경지역 종합상황 보고서가 승인되어 지휘관에게 전달되었습니다.",eid,now()))
        child=None
        if kind=="REGIONAL":
            event_id=uid("EVT")
            c.execute("INSERT OR IGNORE INTO report_events VALUES(?,?,?,?,?)",(event_id,report_id,"PENDING",None,now()))
            staff=row(c.execute("SELECT * FROM agents WHERE role='STAFF' AND lifecycle='PUBLISHED' LIMIT 1").fetchone())
            child=create_execution(c,staff,{"report_id":report_id,"event_id":event_id},session_for("STAFF"),report_id)
            c.execute("UPDATE report_events SET status='DISPATCHED',child_execution_id=? WHERE report_id=?",(child,report_id))
            c.execute("UPDATE executions SET child_execution_id=? WHERE id=?",(child,eid))
        return {"status":"COMPLETED","report_id":report_id,"child_execution_id":child}

@app.get("/api/reports")
def reports(role: str):
    with db() as c:
        q="SELECT * FROM reports"
        if role=="ANALYST": q+=" WHERE area='경기도 파주시'"
        elif role=="COMMANDER": q+=" WHERE kind IN ('REGIONAL','COMMANDER')"
        return [row(r) for r in c.execute(q+" ORDER BY approved_at DESC")]

@app.get("/api/dashboard")
def dashboard(role: str):
    with db() as c:
        agents=c.execute("SELECT count(*) n FROM agents WHERE role=? AND owner=?",(role,session_for(role)["user_id"])).fetchone()[0]
        pending=c.execute("SELECT count(*) FROM approvals WHERE reviewer_role=? AND status='PENDING'",(role,)).fetchone()[0]
        active=c.execute("SELECT count(*) FROM executions WHERE status NOT IN ('COMPLETED','REJECTED','FAILED')").fetchone()[0]
        notes=[row(r) for r in c.execute("SELECT * FROM notifications WHERE role=? ORDER BY created_at DESC LIMIT 5",(role,))]
        return {"agent_count":agents,"pending_count":pending,"active_count":active,"notifications":notes}

@app.get("/api/situation-board")
def situation_board(role: str):
    if role not in {"ANALYST","STAFF","COMMANDER"}: raise HTTPException(400,"지원하지 않는 역할입니다.")
    with db() as c:
        events=[row(r) for r in c.execute("SELECT * FROM sensor_events ORDER BY created_at DESC LIMIT 8")]
        notes=[row(r) for r in c.execute("SELECT * FROM notifications WHERE role=? ORDER BY created_at DESC LIMIT 8",(role,))]
        return {"events":events,"notifications":notes}

init_db()
