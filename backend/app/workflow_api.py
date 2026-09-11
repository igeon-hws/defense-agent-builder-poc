"""워크플로우 CRUD, 실행, 승인과 보고서 HTTP API."""

from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException

from .core import GATEWAY, db, now, require_agent_owner, require_role, row, session_for, uid
from .schemas import AgentCreateIn, AgentIn, DecisionIn, LeaveRequestIn, SensorEventIn
from .workflow_service import ADMIN_NODES, ANALYST_NODES, STAFF_NODES, create_execution, graph, invoke_workflow
from .connectors import WORKFLOW_CONNECTORS, connectors_for_role

router = APIRouter()


@router.get("/api/nodes")
def nodes(role: str, x_demo_role: str = Header(...)):
    if role != x_demo_role: raise HTTPException(403,"현재 역할에서 사용할 수 없는 노드입니다.")
    src = {"ANALYST":ANALYST_NODES,"STAFF":STAFF_NODES,"ADMIN":ADMIN_NODES}.get(role,[])
    defaults={n["type"]:n["config"] for n in graph(role).get("nodes",[])} if src else {}
    connectors={item["id"]:item for item in connectors_for_role(role)}
    result=[]
    for node_type,label,group in src:
        connector=connectors.get(WORKFLOW_CONNECTORS.get(node_type,""))
        result.append({"type":node_type,"label":label,"group":group,"config":defaults.get(node_type,{}),
                       "connector": ({"id":connector["id"],"name":connector["name"],
                                      "category":connector["category"],"mode":connector["mode"]}
                                     if connector else None)})
    return result

@router.get("/api/connectors")
def connectors(x_demo_role: str = Header(...)):
    if x_demo_role not in {"ANALYST","STAFF","ADMIN"}:
        raise HTTPException(403,"연동 카탈로그를 사용할 권한이 없습니다.")
    return connectors_for_role(x_demo_role)

@router.get("/api/agents")
def agents(role: str, x_demo_role: str = Header(...)):
    if role != x_demo_role: raise HTTPException(403,"다른 사용자의 워크플로우 레지스트리에 접근할 수 없습니다.")
    if role == "COMMANDER": return []
    owner=session_for(role)["user_id"]
    with db() as c:
        result=[row(r) for r in c.execute("SELECT * FROM agents WHERE role=? AND owner=? ORDER BY name",(role,owner))]
        for agent in result: agent["deletable"]=agent["id"] not in {"analyst-a12","staff-synthesis","admin-leave-registration"}
        return result

@router.post("/api/agents")
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

@router.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str, x_demo_role: str = Header(...)):
    if agent_id in {"analyst-a12","staff-synthesis","admin-leave-registration"}: raise HTTPException(409,"기본 제공 워크플로우는 삭제할 수 없습니다.")
    with db() as c:
        agent=row(c.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone())
        if not agent: raise HTTPException(404,"워크플로우를 찾을 수 없습니다.")
        require_role(agent["role"],x_demo_role)
        if agent["owner"] != session_for(x_demo_role)["user_id"]: raise HTTPException(403,"본인이 만든 워크플로우만 삭제할 수 있습니다.")
        c.execute("DELETE FROM agent_versions WHERE agent_id=?",(agent_id,))
        c.execute("DELETE FROM agents WHERE id=?",(agent_id,))
    return {"deleted":True,"id":agent_id}

@router.get("/api/agents/{agent_id}")
def get_agent(agent_id: str, x_demo_role: str = Header(...)):
    with db() as c:
        out=row(c.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone())
        if not out: raise HTTPException(404,"워크플로우를 찾을 수 없습니다.")
        require_agent_owner(out,x_demo_role)
        return out

@router.put("/api/agents/{agent_id}")
def save_agent(agent_id: str, body: AgentIn, x_demo_role: str = Header(...)):
    with db() as c:
        agent=row(c.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone())
        if not agent: raise HTTPException(404,"워크플로우 없음")
        require_agent_owner(agent,x_demo_role)
        c.execute("UPDATE agents SET definition=?,lifecycle='DRAFT',updated_at=? WHERE id=?",
                  (json.dumps(body.definition,ensure_ascii=False),now(),agent_id))
    return {"saved":True,"lifecycle":"DRAFT"}

def validate_definition(d):
    """데모에서 지원하는 최소 실행 그래프 규칙을 검사한다."""
    errors=[]; nodes=d.get("nodes",[]); edges=d.get("edges",[]); ids=[n.get("id") for n in nodes]
    if len(ids)!=len(set(ids)): errors.append("노드 ID가 중복되었습니다.")
    if not nodes: errors.append("워크플로에 노드가 필요합니다.")
    if any(e.get("source") not in ids or e.get("target") not in ids for e in edges): errors.append("연결되지 않은 edge endpoint가 있습니다.")
    if not any("approval" in (n.get("type","")+n.get("id","")) for n in nodes): errors.append("Human Approval 노드가 필요합니다.")
    send_ids={n.get("id") for n in nodes if any(action in (n.get("type","")+n.get("id","")) for action in ("send","intranet_register"))}
    if not send_ids: errors.append("보고서 발행 또는 시스템 등록 노드가 필요합니다.")
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

@router.post("/api/agents/{agent_id}/validate")
def validate(agent_id: str, body: AgentIn, x_demo_role: str = Header(...)):
    with db() as c:
        agent=row(c.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone())
        if not agent: raise HTTPException(404,"워크플로우 없음")
        require_agent_owner(agent,x_demo_role)
    return {"valid":not (e:=validate_definition(body.definition)),"errors":e}

@router.post("/api/agents/{agent_id}/publish")
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

@router.post("/api/agents/{agent_id}/test")
def test_agent(agent_id: str, x_demo_role: str = Header(default="ANALYST")):
    with db() as c:
        a=row(c.execute("SELECT * FROM agents WHERE id=?",(agent_id,)).fetchone())
        if not a: raise HTTPException(404,"워크플로우 없음")
        require_role(a["role"],x_demo_role)
        errors=validate_definition(a["definition"])
        if errors: raise HTTPException(422,{"errors":errors})
        fixture=({"leave_request_id":"LEAVE-TEST","service_number":"23-12345678","member_name":"김민준","unit":"제1행정부대 본부중대",
                  "leave_type":"정기 휴가","start_date":"2026-09-18","end_date":"2026-09-20","requested_days":3,"remaining_days":12,
                  "unit_events":["토요일 당직 편성","일요일 21시 복귀 인원 점검"]}
                 if a["role"]=="ADMIN" else
                 {"sensor_id":"파주-감시센서-03","type":"이동체 감지","area":"경기도 파주시","object_count":4,"confidence":0.94})
        eid=create_execution(c,a,fixture,session_for(x_demo_role))
        return {"execution_id":eid}

@router.post("/api/sensor-events")
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
        c.execute("INSERT INTO notifications(id,role,title,body,execution_id,created_at) VALUES(?,?,?,?,?,?)",(uid("NTF"),"COMMANDER","파주시 센서 이벤트",
                  f"{body.type} · 탐지 {body.object_count}개 · 신뢰도 {body.confidence:.2f}",eid,now()))
        status=c.execute("SELECT status FROM executions WHERE id=?",(eid,)).fetchone()[0]
        return {"event_id":event_id,"execution_id":eid,"status":status}

@router.post("/api/leave-requests")
def leave_request(body: LeaveRequestIn, x_demo_role: str = Header(default="ADMIN")):
    require_role("ADMIN",x_demo_role)
    if not 1 <= body.requested_days <= 15: raise HTTPException(422,"신청 일수는 1~15일 범위여야 합니다.")
    if body.end_date < body.start_date: raise HTTPException(422,"종료일은 시작일보다 빠를 수 없습니다.")
    remaining_days=12
    unit_events=["토요일 당직 편성 인원 확인", "일요일 21시 복귀 인원 점검"]
    with db() as c:
        agent=row(c.execute("SELECT * FROM agents WHERE role='ADMIN' AND lifecycle='PUBLISHED' ORDER BY updated_at DESC LIMIT 1").fetchone())
        if not agent: raise HTTPException(409,"게시된 휴가 검토 워크플로우가 없습니다.")
        request_id=uid("LEV")
        payload={**body.model_dump(),"leave_request_id":request_id,"remaining_days":remaining_days,"unit_events":unit_events}
        eid=create_execution(c,agent,payload,session_for("ADMIN"))
        c.execute("INSERT INTO leave_requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (request_id,body.service_number,body.member_name,body.unit,body.leave_type,body.start_date,body.end_date,
                   body.requested_days,remaining_days," · ".join(unit_events),"REVIEWING",eid,now()))
        status=c.execute("SELECT status FROM executions WHERE id=?",(eid,)).fetchone()[0]
        return {"leave_request_id":request_id,"execution_id":eid,"status":status,"remaining_days":remaining_days}

@router.get("/api/leave-requests")
def leave_requests(x_demo_role: str = Header(default="ADMIN")):
    require_role("ADMIN",x_demo_role)
    with db() as c:
        return [row(item) for item in c.execute("SELECT * FROM leave_requests ORDER BY created_at DESC")]

@router.get("/api/executions")
def executions(role: str):
    with db() as c:
        q="SELECT * FROM executions"
        params=()
        if role=="ANALYST": q+=" WHERE role='ANALYST' AND area='경기도 파주시'"
        elif role=="STAFF": q+=" WHERE role IN ('ANALYST','STAFF')"
        elif role=="COMMANDER": q+=" WHERE status='COMPLETED'"
        elif role=="ADMIN": q+=" WHERE role='ADMIN'"
        return [row(r) for r in c.execute(q+" ORDER BY created_at DESC",params)]

@router.get("/api/executions/{eid}")
def execution(eid: str):
    with db() as c:
        e=row(c.execute("SELECT * FROM executions WHERE id=?",(eid,)).fetchone())
        if not e: raise HTTPException(404,"실행 없음")
        e["trace"]=[row(r) for r in c.execute("SELECT * FROM trace WHERE execution_id=? ORDER BY id",(eid,))]
        e["approval"]=row(c.execute("SELECT * FROM approvals WHERE execution_id=?",(eid,)).fetchone())
        e["reports"]=[row(r) for r in c.execute("SELECT * FROM reports WHERE source_execution_id=?",(eid,))]
        e["intranet_registration"]=row(c.execute(
            "SELECT ir.* FROM intranet_registrations ir JOIN leave_requests lr ON lr.id=ir.leave_request_id WHERE lr.execution_id=?",(eid,)).fetchone())
        return e

@router.post("/api/approvals/{approval_id}/decision")
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
            c.execute("UPDATE executions SET status='REJECTED',updated_at=? WHERE id=?",(now(),eid))
            if e["role"]=="ADMIN":
                c.execute("UPDATE leave_requests SET status='REJECTED' WHERE id=?",(e["trigger"].get("leave_request_id"),))
            return {"status":"REJECTED"}
        c.execute("UPDATE executions SET status='RUNNING',updated_at=? WHERE id=?",(now(),eid)); c.commit()
        invoke_workflow(c,eid,agent,e["trigger"],{"approval_decision":body.decision,"edited_content":content})
        if e["role"]=="ADMIN":
            leave_request_id=e["trigger"].get("leave_request_id")
            registration_id=uid("INTRA")
            c.execute("UPDATE leave_requests SET status='REGISTERED' WHERE id=?",(leave_request_id,))
            c.execute("INSERT OR IGNORE INTO intranet_registrations VALUES(?,?,?,?,?,?)",
                      (registration_id,leave_request_id,"REGISTERED",content,actor,now()))
            c.execute("UPDATE executions SET status='COMPLETED',updated_at=? WHERE id=?",(now(),eid))
            c.execute("INSERT INTO notifications(id,role,title,body,execution_id,created_at) VALUES(?,?,?,?,?,?)",
                      (uid("NTF"),"ADMIN","휴가 신청 등록 완료",f"{e['trigger'].get('member_name','신청자')}의 휴가 신청이 모의 부대 인트라넷에 등록되었습니다.",eid,now()))
            return {"status":"COMPLETED","registration_id":registration_id,"leave_request_id":leave_request_id}
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
            c.execute("INSERT INTO notifications(id,role,title,body,execution_id,created_at) VALUES(?,?,?,?,?,?)",(uid("NTF"),"COMMANDER","새 지휘관 보고서 도착",
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

@router.get("/api/reports")
def reports(role: str):
    with db() as c:
        if role=="ADMIN": return []
        q="SELECT * FROM reports"
        if role=="ANALYST": q+=" WHERE area='경기도 파주시'"
        elif role=="COMMANDER": q+=" WHERE kind IN ('REGIONAL','COMMANDER')"
        return [row(r) for r in c.execute(q+" ORDER BY approved_at DESC")]
