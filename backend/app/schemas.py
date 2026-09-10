"""워크플로우 HTTP API에서 사용하는 요청 스키마."""

from typing import Any, Literal

from pydantic import BaseModel


class SessionIn(BaseModel):
    role: Literal["ANALYST", "STAFF", "COMMANDER"]


class AgentIn(BaseModel):
    definition: dict[str, Any]


class AgentCreateIn(BaseModel):
    name: str
    description: str = ""
    role: Literal["ANALYST", "STAFF"]
    area: str
    template: Literal["BLANK", "ANALYST", "STAFF"] = "BLANK"


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
