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
    {"id": "search_indicator_library", "name": "징후 패턴 검색", "kind": "search", "roles": ["ANALYST"], "description": "현재 관측과 비교할 과거 침투·정찰 징후 및 오경보 기준을 검색합니다."},
    {"id": "correlate_threat_indicators", "name": "다중 징후 상관분석", "kind": "function", "roles": ["ANALYST"], "description": "센서 관측, 승인 보고서와 과거 패턴의 일치도를 계산해 추가 확인 대상을 제시합니다."},
    {"id": "query_unit_readiness", "name": "대응태세 조회", "kind": "database", "roles": ["STAFF", "COMMANDER"], "description": "지역별 가용 감시자산과 대응부대 준비상태를 조회합니다."},
    {"id": "prioritize_response_options", "name": "대응방안 비교", "kind": "function", "roles": ["STAFF", "COMMANDER"], "description": "승인 보고서와 대응태세를 비교해 우선 대응지역과 방안을 제시합니다."},
    {"id": "inspect_duty_roster", "name": "근무편성 충돌 점검", "kind": "database", "roles": ["ADMIN"], "description": "당직·훈련 일정과 외출·외박 현황 사이의 충돌을 점검합니다."},
    {"id": "draft_roster_adjustment", "name": "근무 조정안 작성", "kind": "function", "roles": ["ADMIN"], "description": "확인된 일정 충돌에 대해 대체 근무자와 조정 사유를 포함한 초안을 작성합니다."},
]


DEFAULT_REACT_AGENT_IDS = {
    "ANALYST": "react-paju-briefing",
    "STAFF": "react-weekly-threat-comparison",
    "COMMANDER": "react-commander-default",
    "ADMIN": "react-weekly-movement",
}

PURPOSE_REACT_AGENT_IDS = {
    "ANALYST": "react-indicator-correlation",
    "STAFF": "react-response-priority",
    "COMMANDER": "react-command-decision",
    "ADMIN": "react-duty-roster",
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


PURPOSE_REACT_AGENT_META = {
    "ANALYST": {
        "name": "징후 상관분석 에이전트",
        "description": "센서 관측을 과거 징후 패턴 및 승인 보고서와 대조해 오경보 가능성과 추가 확인 대상을 분석합니다.",
        "connectors": ["operational_data", "report_archive", "indicator_library"],
        "system_prompt": "다중 출처의 작전 징후를 상관분석하는 분석관 에이전트입니다. 관측, 승인 보고서와 과거 패턴을 구분해 확인하고 일치도, 불확실성과 추가 확인 대상을 근거 식별자와 함께 제시하세요.",
        "suggested_prompts": [
            "파주시 최근 센서 징후가 과거 침투 패턴과 일치하는지 분석해줘.",
            "최근 관측의 오경보 가능성과 추가 확인 대상을 알려줘.",
            "센서 관측과 승인 보고서 사이의 일치도를 근거와 함께 정리해줘.",
        ],
    },
    "STAFF": {
        "name": "대응 우선순위 에이전트",
        "description": "지역별 승인 보고서와 대응태세를 비교해 제한된 감시·대응 자산의 우선 배치안을 제시합니다.",
        "connectors": ["report_archive", "region_context", "readiness_data", "decision_support"],
        "system_prompt": "접경지역 대응 우선순위를 검토하는 참모 에이전트입니다. 승인된 위협 정보와 실제 가용태세를 함께 비교하고 우선지역, 자산 배치안, 제약과 재검토 조건을 명확히 제시하세요.",
        "suggested_prompts": [
            "현재 가용자산을 기준으로 접경지역 대응 우선순위를 정해줘.",
            "파주와 연천 중 감시자산을 먼저 보강할 지역을 근거와 함께 제안해줘.",
            "승인 보고서와 대응태세를 비교해 오늘의 자산 배치안을 작성해줘.",
        ],
    },
    "COMMANDER": {
        "name": "지휘결심 검토 에이전트",
        "description": "승인된 상황과 가용태세만 사용해 대응방안별 효과, 제약과 결심 필요사항을 비교합니다.",
        "connectors": ["report_archive", "region_context", "readiness_data", "decision_support"],
        "system_prompt": "지휘관의 결심을 지원하는 읽기 전용 에이전트입니다. 승인된 보고서와 가용태세만 사용해 대응방안의 효과, 위험, 자원 제약을 비교하고 최종 결정은 지휘관에게 남겨 두세요.",
        "suggested_prompts": [
            "현재 상황에서 선택 가능한 대응방안 두 가지를 비교해줘.",
            "가용태세를 고려할 때 오늘 결심해야 할 사항을 정리해줘.",
            "파주 우선 보강안의 효과와 다른 지역의 위험을 설명해줘.",
        ],
    },
    "ADMIN": {
        "name": "근무편성 점검 에이전트",
        "description": "당직·훈련 일정과 외출·외박 현황을 대조해 편성 충돌을 찾고 조정 초안을 작성합니다.",
        "connectors": ["personnel_data", "unit_schedule", "duty_roster"],
        "system_prompt": "부대 근무편성 충돌을 점검하는 행정병 에이전트입니다. 일정과 인원 이동 현황을 대조해 충돌 근거를 제시하고, 원본을 변경하지 않는 조정 초안만 작성하세요. 개인정보는 필요한 범위로 제한하세요.",
        "suggested_prompts": [
            "이번 주 당직과 외출·외박 일정의 충돌을 점검해줘.",
            "토요일 당직 공백이 생기지 않도록 근무 조정안을 작성해줘.",
            "승인 대기 인원까지 포함해 이번 주 편성 위험을 알려줘.",
        ],
    },
}


DEFAULT_REACT_AGENT_SPECS = {
    **{agent_id: {"id": agent_id, "role": role, **DEFAULT_REACT_AGENT_META[role], "kind": "GENERAL"}
       for role, agent_id in DEFAULT_REACT_AGENT_IDS.items()},
    **{agent_id: {"id": agent_id, "role": role, **PURPOSE_REACT_AGENT_META[role], "kind": "MISSION"}
       for role, agent_id in PURPOSE_REACT_AGENT_IDS.items()},
}

SYSTEM_DEFAULT_REACT_AGENT_IDS = set(DEFAULT_REACT_AGENT_SPECS)


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


def default_react_definition(model_id: str, role: str = "ANALYST", agent_id: str | None = None) -> dict[str, Any]:
    tools = tools_for_role(role)
    spec = DEFAULT_REACT_AGENT_SPECS.get(agent_id or DEFAULT_REACT_AGENT_IDS[role])
    connector_ids = spec.get("connectors", [connector["id"] for connector in connectors_for_role(role)])
    selected_tools = [tool for tool in tools if tool["connector_id"] in connector_ids]
    return {
        "schema_version": "1",
        "system_prompt": spec.get("system_prompt") or (
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
        "connectors": connector_ids,
        "tools": [tool["id"] for tool in selected_tools],
        "suggested_prompts": spec.get("suggested_prompts", SUGGESTED_PROMPTS[role]),
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
    if tool_name == "search_indicator_library":
        return {"source": "모의 징후 패턴 라이브러리", "patterns": [
                    {"id": "IND-INF-014", "name": "야간 분산 접근", "signals": ["이동체", "저시정", "반복 관측"], "weight": .82},
                    {"id": "IND-REC-008", "name": "열원 동반 정찰", "signals": ["열원", "이동체", "접경 접근로"], "weight": .76},
                    {"id": "IND-FP-003", "name": "민간 통행 오경보", "signals": ["단일 센서", "주간", "도로 인접"], "weight": .41},
                ], "summary": "현재 관측과 비교할 징후 패턴 3건을 찾았습니다."}
    if tool_name == "correlate_threat_indicators":
        sensor = next((item["result"] for item in observations if item["tool"] == "query_operational_db"), {})
        reports = next((item["result"] for item in observations if item["tool"] == "search_reports"), {})
        patterns = next((item["result"] for item in observations if item["tool"] == "search_indicator_library"), {})
        sensor_count = len(sensor.get("records", []))
        report_count = len(reports.get("records", []))
        pattern_ids = [item["id"] for item in patterns.get("patterns", [])[:2]]
        briefing = ("[다중 징후 상관분석]\n\n"
                    f"1. 분석 범위: 최근 센서 관측 {sensor_count}건, 승인·과거 보고서 {report_count}건, 징후 패턴 {len(patterns.get('patterns', []))}건을 대조했습니다.\n"
                    "2. 판단: 이동체와 열원 관측이 야간 분산 접근 패턴과 함께 나타나 상관도는 중간 이상입니다. 단일 센서 오경보만으로 설명하기 어렵습니다.\n"
                    "3. 불확실성: 관측 시간이 제한되어 지속성은 확인되지 않았습니다.\n"
                    f"4. 근거 식별자: OBS-PJU-017, {', '.join(pattern_ids) or 'IND-INF-014'}\n"
                    "5. 추가 확인: 동일 접근로의 후속 열상 관측과 인접 센서 교차확인이 필요합니다.\n\n"
                    "※ 본 결과는 세미나용 모의 데이터를 사용했습니다.")
        return {"source": "징후 패턴 라이브러리", "correlation_level": "MEDIUM_HIGH",
                "false_positive_risk": "LOW_TO_MEDIUM", "briefing": briefing,
                "summary": "센서·보고서·과거 패턴을 대조해 다중 징후 상관분석을 완료했습니다."}
    if tool_name == "query_unit_readiness":
        return {"source": "모의 대응태세 데이터", "units": [
                    {"area": "경기도 파주시", "asset": "기동감시반", "available": 2, "readiness": "90%", "constraint": "1개 반 18시 정비 예정"},
                    {"area": "경기도 연천군", "asset": "열상감시장비", "available": 1, "readiness": "75%", "constraint": "예비장비 없음"},
                    {"area": "강원특별자치도 철원군", "asset": "신속대응반", "available": 1, "readiness": "85%", "constraint": "이동 40분"},
                ], "summary": "접경지역 가용 감시·대응자산 3건의 준비상태를 확인했습니다."}
    if tool_name == "prioritize_response_options":
        reports = next((item["result"] for item in observations if item["tool"] == "search_reports"), {})
        readiness = next((item["result"] for item in observations if item["tool"] == "query_unit_readiness"), {})
        briefing = ("[접경지역 대응방안 비교]\n\n"
                    "1. 우선순위: 파주시 감시 보강을 1순위, 연천군 예비자산 유지를 2순위로 제안합니다.\n"
                    "2. 방안 A — 파주 기동감시반 1개 반 전진배치: 최신 징후 확인 속도가 빠르지만 18시 정비 전 교대가 필요합니다.\n"
                    "3. 방안 B — 연천 열상장비를 파주에 한시 전환: 열원 식별은 강화되지만 연천의 예비장비가 없어 감시 공백 위험이 큽니다.\n"
                    "4. 권고: 방안 A를 우선 적용하고 후속 관측에서 위협이 상승할 때만 방안 B를 재검토합니다.\n"
                    f"5. 근거: 승인 보고 {len(reports.get('records', []))}건, 대응태세 {len(readiness.get('units', []))}건. 최종 결심은 지휘관 승인이 필요합니다.\n\n"
                    "※ 본 결과는 세미나용 모의 데이터를 사용했습니다.")
        return {"source": "모의 지휘결심 지원체계", "priority_area": "경기도 파주시",
                "options": ["기동감시반 전진배치", "열상장비 한시 전환"], "briefing": briefing,
                "summary": "승인 상황과 가용태세를 바탕으로 대응방안 두 가지를 비교했습니다."}
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
    if tool_name == "inspect_duty_roster":
        movements = next((item["result"] for item in observations if item["tool"] == "query_personnel_movements"), {})
        events = next((item["result"] for item in observations if item["tool"] == "lookup_unit_events"), {})
        pending = [item for item in movements.get("records", []) if item.get("status") == "대기"]
        return {"source": "모의 근무편성 관리체계", "conflicts": [
                    {"id": "CONFLICT-01", "slot": "토요일 주간 당직", "severity": "HIGH", "reason": "당직 후보 1명의 승인 외박과 중복"},
                    {"id": "CONFLICT-02", "slot": "일요일 복귀 점검", "severity": "MEDIUM", "reason": "복귀 예정 인원 집중으로 점검 인력 부족"},
                ], "pending_movement_count": len(pending), "event_count": len(events.get("events", [])),
                "summary": "근무편성과 인원 이동을 대조해 충돌 2건을 확인했습니다."}
    if tool_name == "draft_roster_adjustment":
        inspection = next((item["result"] for item in observations if item["tool"] == "inspect_duty_roster"), {})
        briefing = ("[주간 근무편성 조정 초안]\n\n"
                    f"1. 확인된 충돌: {len(inspection.get('conflicts', []))}건\n"
                    "2. 토요일 주간 당직: 외박 승인자 대신 예비근무자 A를 우선 검토합니다.\n"
                    "3. 일요일 복귀 점검: 20~21시 점검 보조 1명을 추가 편성합니다.\n"
                    "4. 처리 조건: 외출·외박 승인 변경 여부를 확인한 뒤 담당 간부 검토를 거쳐야 합니다.\n\n"
                    "※ 원본 근무표는 변경하지 않았으며 본 결과는 세미나용 모의 초안입니다.")
        return {"source": "모의 근무편성 관리체계", "status": "DRAFT", "briefing": briefing,
                "summary": "원본 근무표를 변경하지 않고 충돌 해소 조정 초안을 작성했습니다."}
    raise ValueError(f"지원하지 않는 도구입니다: {tool_name}")
