"""상태, 모델, 대시보드, 알림과 상황판 조회 API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from .core import DB_PATH, GATEWAY, db, now, row, session_for
from .schemas import SessionIn

router = APIRouter()
@router.get("/api/health")
def health(): return {"status":"ok",**GATEWAY.status(),"database":str(DB_PATH)}

@router.get("/api/models")
def models(x_demo_role: str = Header(...)):
    if x_demo_role not in {"ANALYST","STAFF"}: raise HTTPException(403,"워크플로우 편집 권한이 없습니다.")
    return [{"id":model,"label":model,"default":model==GATEWAY.model} for model in GATEWAY.allowed_models]

@router.post("/api/session")
def set_session(body: SessionIn): return session_for(body.role)

@router.get("/api/dashboard")
def dashboard(role: str):
    with db() as c:
        agents=c.execute("SELECT count(*) n FROM agents WHERE role=? AND owner=?",(role,session_for(role)["user_id"])).fetchone()[0]
        pending=c.execute("SELECT count(*) FROM approvals WHERE reviewer_role=? AND status='PENDING'",(role,)).fetchone()[0]
        active=c.execute("SELECT count(*) FROM executions WHERE status NOT IN ('COMPLETED','REJECTED','FAILED')").fetchone()[0]
        notes=[row(r) for r in c.execute("SELECT * FROM notifications WHERE role=? ORDER BY created_at DESC LIMIT 5",(role,))]
        unread_query="SELECT count(*) FROM notifications WHERE role=? AND read_at IS NULL"
        unread_params: tuple[Any,...]=(role,)
        if role=="COMMANDER":
            unread_query+=" AND title='새 지휘관 보고서 도착'"
        unread=c.execute(unread_query,unread_params).fetchone()[0]
        return {"agent_count":agents,"pending_count":pending,"active_count":active,"unread_count":unread,"notifications":notes}


@router.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: str, x_demo_role: str = Header(...)):
    if x_demo_role not in {"ANALYST","STAFF","COMMANDER"}:
        raise HTTPException(403,"알림을 확인할 권한이 없습니다.")
    with db() as c:
        notification=c.execute("SELECT * FROM notifications WHERE id=? AND role=?",(notification_id,x_demo_role)).fetchone()
        if not notification:
            raise HTTPException(404,"알림을 찾을 수 없습니다.")
        read_at=notification["read_at"] or now()
        c.execute("UPDATE notifications SET read_at=? WHERE id=?",(read_at,notification_id))
        return {"id":notification_id,"status":"READ","read_at":read_at}

@router.get("/api/situation-board")
def situation_board(role: str):
    if role not in {"ANALYST","STAFF","COMMANDER"}: raise HTTPException(400,"지원하지 않는 역할입니다.")
    with db() as c:
        events=[row(r) for r in c.execute("SELECT * FROM sensor_events ORDER BY created_at DESC LIMIT 8")]
        notes=[row(r) for r in c.execute("SELECT * FROM notifications WHERE role=? ORDER BY created_at DESC LIMIT 8",(role,))]
        return {"events":events,"notifications":notes}
