"""백엔드 전역에서 공유하는 설정, DB 연결과 간단한 역할 정책."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import HTTPException

from .gateway import ModelGateway
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
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def row(record):
    """SQLite 행의 JSON 문자열 필드를 API에서 사용할 객체로 변환한다."""
    if not record:
        return None
    result = dict(record)
    for key in ("definition", "trigger", "snapshot", "initiating_context", "source_report_ids", "payload"):
        if key in result and result[key]:
            try:
                result[key] = json.loads(result[key])
            except (TypeError, json.JSONDecodeError):
                pass
    if "fixture" in result:
        result["fixture"] = bool(result["fixture"])
    return result


def session_for(role: str) -> dict[str, Any]:
    """데모 역할에 대응하는 고정 사용자 세션을 반환한다."""
    role = role.upper()
    if role not in {"ANALYST", "STAFF", "COMMANDER"}:
        raise HTTPException(400, "지원하지 않는 역할입니다.")
    return {
        "user_id": {"ANALYST": "analyst.a12", "STAFF": "staff.ops", "COMMANDER": "commander.demo"}[role],
        "role": role,
        "area": "경기도 파주시" if role == "ANALYST" else "접경지역 전체",
        "permissions": {
            "ANALYST": ["agent:create", "agent:edit", "agent:publish", "agent:delete", "sensor:emit", "review:analyst"],
            "STAFF": ["agent:create", "agent:edit", "agent:publish", "agent:delete", "review:staff"],
            "COMMANDER": ["report:read", "situation:read"],
        }[role],
    }


def require_role(expected: str, role: str | None) -> None:
    if role != expected:
        raise HTTPException(403, f"{expected} 역할만 승인할 수 있습니다.")


def require_agent_owner(agent: dict[str, Any], role: str) -> None:
    require_role(agent["role"], role)
    if agent["owner"] != session_for(role)["user_id"]:
        raise HTTPException(403, "본인 소유 워크플로우만 관리할 수 있습니다.")
