"""역할별 데이터·외부 시스템 연동 카탈로그와 capability 매핑."""

from __future__ import annotations

from typing import Any


CONNECTORS: list[dict[str, Any]] = [
    {"id": "operational_data", "name": "작전 관측 데이터", "category": "DATA", "mode": "MOCK",
     "roles": ["ANALYST", "STAFF"], "description": "파주시 센서 관측과 최근 이상 징후 데이터",
     "capabilities": [{"id": "query_operational_db", "name": "최근 관측 조회", "access": "READ"}]},
    {"id": "report_archive", "name": "승인 보고서 저장소", "category": "DATA", "mode": "MOCK",
     "roles": ["ANALYST", "STAFF"], "description": "지역별 승인 보고서와 과거 분석 자료",
     "capabilities": [{"id": "search_reports", "name": "보고서 검색", "access": "SEARCH"}]},
    {"id": "region_context", "name": "지역 상황 정보", "category": "DATA", "mode": "MOCK",
     "roles": ["ANALYST", "STAFF"], "description": "파주·연천·철원의 지형, 기상과 작전 맥락",
     "capabilities": [{"id": "lookup_region_info", "name": "지역 정보 조회", "access": "READ"}]},
    {"id": "briefing_system", "name": "지휘 보고 체계", "category": "EXTERNAL_SYSTEM", "mode": "MOCK",
     "roles": ["ANALYST", "STAFF"], "description": "수집 근거를 종합해 지휘관 브리핑을 생성하는 모의 체계",
     "capabilities": [{"id": "synthesize_evidence", "name": "근거 종합·브리핑 생성", "access": "WRITE"}]},
    {"id": "personnel_data", "name": "인사행정 데이터", "category": "DATA", "mode": "MOCK",
     "roles": ["ADMIN"], "description": "부대원 외출·외박 신청과 승인 현황",
     "capabilities": [{"id": "query_personnel_movements", "name": "외출·외박 현황 조회", "access": "READ"}]},
    {"id": "unit_schedule", "name": "부대 일정 데이터", "category": "DATA", "mode": "MOCK",
     "roles": ["ADMIN"], "description": "훈련·당직·행사와 복귀 점검 일정",
     "capabilities": [{"id": "lookup_unit_events", "name": "부대 일정 조회", "access": "READ"}]},
    {"id": "personnel_rules", "name": "인사 규정 저장소", "category": "DATA", "mode": "MOCK",
     "roles": ["ADMIN"], "description": "외출·외박 및 휴가 처리에 적용하는 모의 규정",
     "capabilities": [{"id": "search_personnel_rules", "name": "인사 규정 검색", "access": "SEARCH"}]},
    {"id": "unit_intranet", "name": "부대 인트라넷", "category": "EXTERNAL_SYSTEM", "mode": "MOCK",
     "roles": ["ADMIN"], "description": "주간 현황 보고 작성과 승인된 휴가 신청 등록",
     "capabilities": [
         {"id": "generate_weekly_movement_report", "name": "주간 현황 보고 작성", "access": "WRITE"},
         {"id": "intranet_register", "name": "휴가 신청 등록", "access": "WRITE", "hitl_required": True,
          "workflow_only": True},
     ]},
]


WORKFLOW_CONNECTORS = {
    "sensor": "operational_data", "context": "region_context", "reports": "report_archive",
    "report_trigger": "report_archive", "send": "briefing_system", "threat": "briefing_system",
    "synthesis": "briefing_system", "leave_request": "personnel_data", "leave_balance": "personnel_data",
    "unit_events": "unit_schedule", "leave_summary": "unit_intranet", "intranet_register": "unit_intranet",
}


def connectors_for_role(role: str) -> list[dict[str, Any]]:
    """현재 역할에 허용된 카탈로그 항목만 반환한다."""
    return [connector for connector in CONNECTORS if role in connector["roles"]]


def connector_for_capability(capability_id: str, role: str | None = None) -> dict[str, Any] | None:
    for connector in CONNECTORS:
        if role and role not in connector["roles"]:
            continue
        if any(item["id"] == capability_id for item in connector["capabilities"]):
            return connector
    return None


def tool_ids_for_connectors(connector_ids: list[str], role: str) -> list[str]:
    """선택한 연동에서 ReAct 런타임에 노출할 도구 ID를 계산한다."""
    selected = set(connector_ids)
    return [capability["id"] for connector in connectors_for_role(role) if connector["id"] in selected
            for capability in connector["capabilities"] if capability["id"] != "intranet_register"]


def connector_ids_for_tools(tool_ids: list[str], role: str) -> list[str]:
    selected = set(tool_ids)
    return [connector["id"] for connector in connectors_for_role(role)
            if any(capability["id"] in selected for capability in connector["capabilities"])]


def hydrate_react_definition(definition: dict[str, Any], role: str) -> dict[str, Any]:
    """이전 DB 정의도 connector 기반 계약으로 읽을 수 있게 보완한다."""
    result = {**definition}
    connector_ids = result.get("connectors")
    if connector_ids is None:
        connector_ids = connector_ids_for_tools(result.get("tools", []), role)
    allowed_ids = {item["id"] for item in connectors_for_role(role)}
    result["connectors"] = [item for item in connector_ids if item in allowed_ids]
    result["tools"] = tool_ids_for_connectors(result["connectors"], role)
    return result
