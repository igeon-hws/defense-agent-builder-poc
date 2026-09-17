"""워크플로우 HTTP API에서 사용하는 요청 스키마."""

from typing import Any, Literal

from pydantic import BaseModel


class SessionIn(BaseModel):
    role: Literal["ANALYST", "STAFF", "COMMANDER", "ADMIN"]


class AgentIn(BaseModel):
    definition: dict[str, Any]


class AgentCreateIn(BaseModel):
    name: str
    description: str = ""
    role: Literal["ANALYST", "STAFF", "ADMIN"]
    area: str
    template: Literal["BLANK", "ANALYST", "STAFF", "ADMIN"] = "BLANK"


class DecisionIn(BaseModel):
    decision: Literal["APPROVE", "EDIT_APPROVE", "REJECT"]
    content: str | None = None
    comment: str | None = None


class SensorEventIn(BaseModel):
    sensor_id: str = "파주-감시센서-03"
    type: str = "이동체 감지"
    area: str = "경기도 파주시"
    object_count: int
    confidence: float


class LeaveRequestIn(BaseModel):
    service_number: str = "23-12345678"
    member_name: str = "김민준"
    unit: str = "제1행정부대 본부중대"
    leave_type: Literal["정기 휴가", "포상 휴가", "청원 휴가"] = "정기 휴가"
    start_date: str
    end_date: str
    requested_days: int
