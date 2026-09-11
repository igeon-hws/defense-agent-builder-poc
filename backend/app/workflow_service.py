"""워크플로우 기본 정의와 LangGraph 실행 상태 전이를 담당한다."""

from __future__ import annotations

import json
from typing import Any

from langgraph.types import Command

from .core import GATEWAY, RUNTIME, now, row, uid
from .gateway import ModelGatewayError


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
ADMIN_NODES = [
    ("leave_request", "정기 휴가 신청 접수", "trigger"),
    ("leave_balance", "잔여 휴가 조회", "data"),
    ("unit_events", "부대 일정 조회", "data"),
    ("leave_summary", "휴가 신청 요약 생성", "ai"),
    ("approval", "행정병 검토·승인", "control"),
    ("intranet_register", "부대 인트라넷 등록", "action"),
]

def graph(role: str) -> dict[str, Any]:
    """역할별 기본 워크플로우 정의를 Builder JSON 형식으로 만든다."""
    source = {"ANALYST": ANALYST_NODES, "STAFF": STAFF_NODES, "ADMIN": ADMIN_NODES}[role]
    nodes = []
    for i, (node_id, label, group) in enumerate(source):
        x = 80 + (i % 4) * 230
        y = 70 + (i // 4) * 150
        config: dict[str, Any] = {}
        if node_id == "filter": config = {"min_confidence": 0.8, "min_object_count": 2}
        elif node_id == "threat": config = {"system_prompt": "대한민국 접경지역 센서 이벤트를 분석해 위협 수준, 근거 요약과 분석관 승인용 지역 보고서 초안을 한국어로 작성하세요."}
        elif node_id == "synthesis": config = {"system_prompt": "승인된 접경지역 보고를 종합해 위협 수준, 우선 대응 지역과 참모 승인용 지휘관 보고서 초안을 한국어로 작성하세요."}
        elif node_id == "leave_summary": config = {"system_prompt": "휴가 신청자의 잔여 휴가, 신청 기간과 부대 일정을 검토해 행정병 승인용 요약을 한국어로 작성하세요. 개인정보는 신청 처리에 필요한 범위로만 표시하세요."}
        elif node_id == "context": config = {"query": "최근 24시간 작전 정보와 관련 관측 기록"}
        if node_id in {"threat", "synthesis", "leave_summary"}: config["model_id"] = GATEWAY.model
        nodes.append({"id": node_id, "type": node_id, "label": label, "group": group,
                      "position": {"x": x, "y": y}, "config": config})
    edges = [{"id": f"e-{i}", "source": source[i][0], "target": source[i+1][0]}
             for i in range(len(source)-1)]
    return {"schema_version": "1", "nodes": nodes, "edges": edges,
            "model": {"provider": "openai", "model_id": GATEWAY.model, "temperature": 0.2}}

def trace(c, eid, node_id, label, status="SUCCEEDED", inp="", out=""):
    t = now()
    c.execute("INSERT INTO trace(execution_id,node_id,label,status,input_summary,output_summary,started_at,ended_at) VALUES(?,?,?,?,?,?,?,?)",
              (eid,node_id,label,status,inp,out,t,t if status != "WAITING" else None))


def invoke_workflow(c, eid: str, agent: dict, trigger_payload: dict, resume: dict | None = None):
    """저장된 정의를 컴파일하고 새 실행 또는 HITL 재개를 수행한다."""
    definition = agent["definition"] if isinstance(agent["definition"], dict) else json.loads(agent["definition"])
    role = agent["role"]
    default_draft = "분석 결과를 기다리고 있습니다."

    def runner(spec, state, phase):
        node_id=spec["id"]; capability=spec.get("type",node_id); label=spec.get("label",node_id)
        if phase == "before_interrupt":
            # 승인 요청은 실행당 한 번만 만들고 LangGraph 체크포인트에서 멈춘다.
            existing=row(c.execute("SELECT * FROM approvals WHERE execution_id=?",(eid,)).fetchone())
            if not existing:
                approval_id=uid("APR")
                draft=state.get("draft",default_draft)
                c.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (approval_id,eid,role,"PENDING",draft,draft,None,None,None,None))
                trace(c,eid,node_id,label,"WAITING",inp=f"보고서 초안 {len(draft)}자",out="명시적 승인 대기")
                c.execute("UPDATE executions SET status=?,updated_at=? WHERE id=?",
                          (f"WAITING_FOR_{role}_APPROVAL",now(),eid))
                reviewer={"ANALYST":"분석관","STAFF":"참모","ADMIN":"행정병"}[role]
                c.execute("INSERT INTO notifications(id,role,title,body,execution_id,created_at) VALUES(?,?,?,?,?,?)",(uid("NTF"),role,f"{reviewer} 승인 요청",
                          "AI가 생성한 검토 요약이 승인을 기다리고 있습니다." if role=="ADMIN" else "AI가 생성한 보고서 초안이 승인을 기다리고 있습니다.",eid,now()))
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
            "leave_request": f"{event.get('member_name','신청자')} · {event.get('leave_type','휴가 신청')}",
            "leave_balance": f"군번 {event.get('service_number','-')}",
            "unit_events": f"{event.get('start_date','-')} ~ {event.get('end_date','-')}",
            "leave_summary": f"신청 {event.get('requested_days','-')}일 · 잔여 {state.get('remaining_days',event.get('remaining_days','-'))}일",
            "intranet_register": f"승인된 휴가 신청 {event.get('leave_request_id','-')}",
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
        elif capability=="leave_balance":
            remaining=int(event.get("remaining_days",12))
            output=f"잔여 휴가 {remaining}일 조회"; updates["remaining_days"]=remaining
        elif capability=="unit_events":
            events=event.get("unit_events",["토요일 당직 편성", "일요일 21시 복귀 인원 점검"])
            output=f"관련 부대 일정 {len(events)}건 조회"; updates["related_unit_events"]=events
        elif capability=="leave_summary":
            request={**event,"remaining_days":state.get("remaining_days",event.get("remaining_days",12)),
                     "unit_events":state.get("related_unit_events",event.get("unit_events",[]))}
            result=GATEWAY.structured(name="leave_request_summary",
                instructions=config.get("system_prompt","휴가 신청의 잔여 일수와 부대 일정을 검토해 승인용 요약을 작성하세요."),
                payload={"leave_request":request},
                schema={"type":"object","properties":{"eligible":{"type":"boolean"},"summary":{"type":"string"},
                        "conflicts":{"type":"array","items":{"type":"string"}},"draft":{"type":"string"}},
                        "required":["eligible","summary","conflicts","draft"],"additionalProperties":False},
                model=config.get("model_id"))
            output=("처리 가능" if result["eligible"] else "확인 필요")+f" · {result['summary']}"; updates.update(result)
        elif capability=="intranet_register":
            output="승인 결과를 모의 부대 인트라넷 인사행정 시스템에 등록"
        elif capability=="generator":
            level=state.get("threat_level","미정"); summary=state.get("summary",default_draft)
            draft=f"[{agent['area']} 상황 보고]\n위협 수준: {level}\n\n{summary}\n\n권고: {config.get('recommendation','관련 감시 자산을 유지하고 승인된 절차에 따라 후속 조치하십시오.')}"
            output="LLM 분석 기반 승인용 보고서 초안 생성"; updates["draft"]=draft
        else: output=f"{label} 처리 완료"
        trace(c,eid,node_id,label,inp=input_text,out=output); c.commit()
        return updates

    # 실행 시작 시 저장된 정의 스냅샷만 사용하므로 이후 편집의 영향을 받지 않는다.
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
              agent["area"],agent["version"],"RUNNING",{"ANALYST":"SENSOR_EVENT","STAFF":"APPROVED_REPORT","ADMIN":"LEAVE_REQUEST"}[agent["role"]],
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
