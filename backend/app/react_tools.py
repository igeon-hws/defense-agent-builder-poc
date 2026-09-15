"""ReAct 에이전트가 선택할 수 있는 도구 목록과 mock 실행 구현."""

from __future__ import annotations

from typing import Any, Callable

from .connectors import connector_for_capability, connectors_for_role


REACT_TOOLS = [
    {"id": "query_operational_db", "name": "작전 DB 조회", "kind": "database", "roles": ["ANALYST", "STAFF"], "description": "권한 범위의 최근 센서 관측과 이상 징후를 조회합니다."},
    {"id": "search_reports", "name": "승인 보고서 검색", "kind": "search", "roles": ["ANALYST", "STAFF", "COMMANDER"], "description": "권한 범위의 승인 보고서와 과거 분석 자료를 검색합니다."},
    {"id": "lookup_region_info", "name": "지역 정보 조회", "kind": "context", "roles": ["ANALYST", "STAFF", "COMMANDER"], "description": "권한 범위의 지형·기상·접경지역 맥락을 조회합니다."},
    {"id": "synthesize_evidence", "name": "근거 종합", "kind": "function", "roles": ["ANALYST", "STAFF"], "description": "수집한 근거를 지휘관 브리핑 초안으로 정리합니다."},
    {"id": "query_personnel_movements", "name": "외출·외박 현황 조회", "kind": "database", "roles": ["ADMIN"], "description": "이번 주 부대원의 외출·외박 신청과 승인 현황을 조회합니다."},
    {"id": "lookup_unit_events", "name": "부대 일정 조회", "kind": "context", "roles": ["ADMIN"], "description": "훈련·당직·행사 등 인원 이동에 영향을 주는 이번 주 부대 일정을 조회합니다."},
    {"id": "search_personnel_rules", "name": "인사 규정 검색", "kind": "search", "roles": ["ADMIN"], "description": "외출·외박 현황 보고에 적용할 인사 행정 기준을 검색합니다."},
    {"id": "generate_weekly_movement_report", "name": "주간 현황 보고 작성", "kind": "function", "roles": ["ADMIN"], "description": "조회된 인사 자료를 인원·유형·상태별로 종합해 주간 보고서를 작성합니다."},
]


DEFAULT_REACT_AGENT_IDS = {
    "ANALYST": "react-paju-briefing",
    "STAFF": "react-weekly-threat-comparison",
    "COMMANDER": "react-commander-default",
    "ADMIN": "react-weekly-movement",
}


DEFAULT_REACT_AGENT_META = {
    "ANALYST": {
        "name": "분석관 기본 에이전트",
        "description": "분석관 권한의 작전 관측, 승인 보고서와 지역 정보를 활용해 다양한 조사 목표를 지원합니다.",
    },
    "STAFF": {
        "name": "참모 기본 에이전트",
        "description": "참모 권한의 접경지역 관측과 승인 보고서를 비교·종합해 상황판단을 지원합니다.",
    },
    "COMMANDER": {
        "name": "지휘관 기본 에이전트",
        "description": "지휘관 권한으로 승인된 보고서와 지역 상황을 조회해 의사결정용 브리핑을 제공합니다.",
    },
    "ADMIN": {
        "name": "행정병 기본 에이전트",
        "description": "행정병 권한의 인사행정 데이터, 부대 일정과 규정을 활용해 다양한 행정 질의를 지원합니다.",
    },
}


SUGGESTED_PROMPTS = {
    "ANALYST": [
        "파주시 최근 이상 징후를 조사하고 지휘관 브리핑을 작성해줘.",
        "최근 센서 관측과 승인 보고서가 서로 일치하는지 확인해줘.",
        "파주시 상황에서 추가 확인이 필요한 근거를 정리해줘.",
    ],
    "STAFF": [
        "이번 주 위협 수준이 지난주보다 높아졌는지 근거와 함께 설명해줘.",
        "최신 승인 보고서를 지역별로 비교해 우선 확인 지역을 알려줘.",
        "접경지역 상황을 참모 종합판단 형식으로 요약해줘.",
    ],
    "COMMANDER": [
        "최신 참모 종합 상황판단의 핵심만 브리핑해줘.",
        "현재 우선 확인해야 할 지역과 근거를 알려줘.",
        "최근 승인 보고서의 위협 수준과 출처를 비교해줘.",
    ],
    "ADMIN": [
        "이번 주차 외출·외박 현황 보고를 작성해줘.",
        "이번 주 부대 일정이 인원 이동에 미치는 영향을 정리해줘.",
        "승인 대기 중인 외출·외박 현황과 적용 규정을 알려줘.",
    ],
}


def tools_for_role(role: str) -> list[dict[str, Any]]:
    tools = []
    for tool in REACT_TOOLS:
        if role not in tool.get("roles", []):
            continue
        connector = connector_for_capability(tool["id"], role)
        capability = next(item for item in connector["capabilities"] if item["id"] == tool["id"])
        tools.append({**tool, "connector_id": connector["id"], "connector_name": connector["name"],
                      "category": connector["category"], "mode": connector["mode"],
                      "access": capability["access"]})
    return tools


def default_react_definition(model_id: str, role: str = "ANALYST") -> dict[str, Any]:
    tools = tools_for_role(role)
    return {
        "schema_version": "1",
        "system_prompt": (
            "부대 인사행정을 지원하는 행정병 기본 에이전트입니다. 현재 권한 안에서 인사 현황, 일정과 규정을 확인하고, 개인정보는 필요한 범위로만 사용해 다양한 행정 질의에 간결한 한국어로 답하세요."
            if role == "ADMIN" else
            "승인된 보고서와 지역 상황을 조회하는 지휘관 기본 에이전트입니다. 현재 권한 안의 승인 정보만 사용하고, 출처와 불확실성을 구분해 의사결정에 필요한 핵심을 간결한 한국어로 답하세요."
            if role == "COMMANDER" else
            "접경지역 정보를 종합하는 정보·작전 참모 기본 에이전트입니다. 현재 권한 안에서 관측과 승인 보고서를 비교하고, 위협 수준의 변화와 판단 근거를 간결한 한국어로 설명하세요."
            if role == "STAFF" else
            "파주시 작전 정보를 조사하는 분석관 기본 에이전트입니다. 현재 권한 안에서 필요한 근거를 먼저 수집하고 다양한 분석 요청에 간결한 한국어로 답하세요."
        ),
        "model": {"provider": "openai", "model_id": model_id},
        "max_iterations": 6,
        "connectors": [connector["id"] for connector in connectors_for_role(role)],
        "tools": [tool["id"] for tool in tools],
        "suggested_prompts": SUGGESTED_PROMPTS[role],
    }


def execute_react_tool(db: Callable, tool_name: str, observations: list[dict[str, Any]], goal: str = "", role: str = "ANALYST") -> dict[str, Any]:
    if tool_name == "query_operational_db":
        with db() as connection:
            records = [dict(item) for item in connection.execute(
                "SELECT sensor_id,type,area,object_count,confidence,created_at FROM sensor_events "
                "WHERE area='경기도 파주시' ORDER BY created_at DESC LIMIT 5")]
        if not records:
            records = [
                {"sensor_id": "파주-감시센서-03", "type": "이동체 감지", "area": "경기도 파주시", "object_count": 4, "confidence": .94, "created_at": "최근 30분"},
                {"sensor_id": "파주-열상센서-07", "type": "열원 감지", "area": "경기도 파주시", "object_count": 2, "confidence": .87, "created_at": "최근 2시간"},
            ]
        return {"source": "모의 작전 DB", "records": records, "summary": f"파주시 최근 센서 관측 {len(records)}건을 확인했습니다."}
    if tool_name == "search_reports":
        with db() as connection:
            where = "kind='COMMANDER'" if role == "COMMANDER" else "kind='REGIONAL'" if role == "STAFF" else "area='경기도 파주시'"
            records = [dict(item) for item in connection.execute(
                "SELECT id,title,area,threat,content,approved_at FROM reports "
                f"WHERE {where} ORDER BY approved_at DESC LIMIT 6")]
        if not records and role != "COMMANDER":
            records = [{"id": "RPT-PJU-HIST-01", "title": "파주시 북부 감시 동향", "area": "경기도 파주시",
                        "threat": "MEDIUM", "content": "최근 7일간 야간 이동 징후가 간헐적으로 증가했습니다.", "approved_at": "데모 과거자료"}]
        return {"source": "승인 보고서 저장소", "records": records,
                "weekly_baseline": {"period": "지난주", "threat_level": "MEDIUM", "anomaly_count": 3,
                                    "average_confidence": 0.76, "evidence_id": "RPT-BORDER-W35"},
                "summary": f"관련 승인·과거 보고서 {len(records)}건과 지난주 비교 기준을 찾았습니다."}
    if tool_name == "lookup_region_info":
        area = "경기도 파주시" if role == "ANALYST" else "접경지역 전체"
        return {"source": "모의 지역정보 시스템", "area": area, "terrain": "임진강과 접경 산악·평야가 혼재",
                "weather": "야간 저시정, 북동풍", "operational_note": "민간 접근로와 감시 취약 구간을 함께 고려해야 합니다.",
                "summary": "파주시 접경 지형과 현재 작전 맥락을 확인했습니다."}
    if tool_name == "synthesize_evidence":
        sensor = next((item["result"] for item in observations if item["tool"] == "query_operational_db"), {})
        reports = next((item["result"] for item in observations if item["tool"] == "search_reports"), {})
        region = next((item["result"] for item in observations if item["tool"] == "lookup_region_info"), {})
        sensor_count, report_count = len(sensor.get("records", [])), len(reports.get("records", []))
        weekly_comparison = any(word in goal for word in ("지난주", "이번 주", "비교", "높아"))
        if weekly_comparison:
            records = sensor.get("records", [])
            average = sum(float(item.get("confidence", 0)) for item in records) / len(records) if records else 0
            baseline = reports.get("weekly_baseline", {"threat_level": "MEDIUM", "anomaly_count": 3,
                                                        "average_confidence": .76, "evidence_id": "RPT-BORDER-W35"})
            direction = "높아졌습니다" if len(records) >= baseline["anomaly_count"] or average > baseline["average_confidence"] else "높아졌다고 보기 어렵습니다"
            briefing = ("[주간 접경지역 위협 수준 비교]\n\n"
                        f"1. 결론: 이번 주 위협 수준은 지난주보다 {direction}.\n\n"
                        f"2. 이번 주 근거: 최근 주요 관측 {len(records)}건, 평균 신뢰도 {average:.2f}이며 이동체·열원 징후가 확인되었습니다.\n\n"
                        f"3. 지난주 기준: 위협 수준 {baseline['threat_level']}, 주요 이상 징후 {baseline['anomaly_count']}건, 평균 신뢰도 {baseline['average_confidence']:.2f}였습니다.\n\n"
                        f"4. 근거 식별자: OBS-PJU-W36, {baseline['evidence_id']}\n\n"
                        "5. 판단: 단기 증가 여부는 확인되었으나 지속 추세 판단을 위해 후속 관측이 필요합니다.\n\n"
                        "※ 본 결과는 세미나용 모의 데이터를 사용했습니다.")
        else:
            briefing = ("[파주시 최근 이상 징후 지휘관 브리핑]\n\n"
                    f"1. 상황: 최근 파주시 센서 관측 {sensor_count}건과 관련 보고서 {report_count}건을 확인했습니다. "
                    "이동체 및 열원 징후가 과거 야간 이동 증가 패턴과 일부 일치합니다.\n\n"
                    f"2. 판단: {region.get('terrain', '접경 지형')}과 {region.get('weather', '현재 기상')}을 고려할 때 추가 확인이 필요한 중간 수준 징후입니다.\n\n"
                    "3. 권고: 파주시 북부 감시 자산을 유지하고 동일 구간의 후속 센서 관측과 기존 보고 간 상관성을 재확인하십시오.\n\n"
                    "※ 본 결과는 세미나용 모의 데이터를 사용했습니다.")
        return {"source": "근거 종합 기능", "evidence_count": sensor_count + report_count + 1,
                "briefing": briefing, "summary": ("이번 주와 지난주 위협 근거를 비교했습니다." if weekly_comparison else "수집한 근거를 지휘관 브리핑 초안으로 종합했습니다.")}
    if tool_name == "query_personnel_movements":
        with db() as connection:
            records = [dict(item) for item in connection.execute(
                "SELECT member_name,unit,movement_type,start_at,end_at,status,reason FROM personnel_movements "
                "ORDER BY start_at DESC LIMIT 20")]
        return {"source": "모의 인사행정 DB", "records": records,
                "summary": f"이번 주 외출·외박 기록 {len(records)}건을 확인했습니다."}
    if tool_name == "lookup_unit_events":
        return {"source": "모의 부대 일정 시스템", "events": [
                    {"date": "금요일", "title": "주간 전투체육", "impact": "17시 이후 외출 가능"},
                    {"date": "토요일", "title": "당직 편성", "impact": "당직 인원 외박 제한"},
                    {"date": "일요일", "title": "복귀 인원 점검", "impact": "21시까지 복귀"},
                ], "summary": "이번 주 외출·외박에 영향을 주는 부대 일정 3건을 확인했습니다."}
    if tool_name == "search_personnel_rules":
        return {"source": "모의 인사 규정 저장소", "rules": [
                    "승인된 외출·외박만 현황에 포함", "당직 편성 인원은 제한 사유 표기", "복귀 예정 시각과 승인 상태를 함께 보고",
                ], "summary": "주간 현황 보고 적용 기준 3건을 확인했습니다."}
    if tool_name == "generate_weekly_movement_report":
        movements = next((item["result"] for item in observations if item["tool"] == "query_personnel_movements"), {})
        records = movements.get("records", [])
        outings = [item for item in records if item.get("movement_type") == "외출"]
        overnights = [item for item in records if item.get("movement_type") == "외박"]
        approved = [item for item in records if item.get("status") == "승인"]
        pending = [item for item in records if item.get("status") == "대기"]
        briefing = ("[이번 주 외출·외박 현황 보고]\n\n"
                    f"1. 총괄: 총 {len(records)}건(외출 {len(outings)}건, 외박 {len(overnights)}건)입니다.\n"
                    f"2. 상태: 승인 {len(approved)}건, 승인 대기 {len(pending)}건입니다.\n"
                    "3. 확인사항: 토요일 당직 편성 인원과 일요일 21시 복귀 예정 준수 여부를 확인해야 합니다.\n\n"
                    "※ 본 결과는 세미나용 모의 인사행정 데이터를 사용했습니다.")
        return {"source": "주간 현황 보고 작성 기능", "record_count": len(records), "briefing": briefing,
                "summary": "이번 주 외출·외박 현황 보고서를 작성했습니다."}
    raise ValueError(f"지원하지 않는 도구입니다: {tool_name}")
