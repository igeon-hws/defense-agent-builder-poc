"""ReAct 에이전트가 선택할 수 있는 도구 목록과 mock 실행 구현."""

from __future__ import annotations

from typing import Any, Callable


REACT_TOOLS = [
    {"id": "query_operational_db", "name": "작전 DB 조회", "kind": "database", "description": "최근 파주시 센서 관측과 이상 징후를 조회합니다."},
    {"id": "search_reports", "name": "기존 보고서 검색", "kind": "search", "description": "승인 보고서와 과거 파주시 분석 자료를 검색합니다."},
    {"id": "lookup_region_info", "name": "지역 정보 조회", "kind": "context", "description": "파주시 지형·기상·접경지역 맥락을 조회합니다."},
    {"id": "synthesize_evidence", "name": "근거 종합", "kind": "function", "description": "수집한 근거를 지휘관 브리핑 초안으로 정리합니다."},
]


def default_react_definition(model_id: str) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "system_prompt": "파주시 작전 정보를 조사하는 국방 분석 에이전트입니다. 근거를 먼저 수집하고 간결한 한국어 지휘관 브리핑을 작성하세요.",
        "model": {"provider": "openai", "model_id": model_id},
        "max_iterations": 6,
        "tools": [tool["id"] for tool in REACT_TOOLS],
    }


def execute_react_tool(db: Callable, tool_name: str, observations: list[dict[str, Any]]) -> dict[str, Any]:
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
            records = [dict(item) for item in connection.execute(
                "SELECT id,title,area,threat,content,approved_at FROM reports "
                "WHERE area='경기도 파주시' ORDER BY approved_at DESC LIMIT 4")]
        if not records:
            records = [{"id": "RPT-PJU-HIST-01", "title": "파주시 북부 감시 동향", "area": "경기도 파주시",
                        "threat": "MEDIUM", "content": "최근 7일간 야간 이동 징후가 간헐적으로 증가했습니다.", "approved_at": "데모 과거자료"}]
        return {"source": "승인 보고서 저장소", "records": records, "summary": f"관련 승인·과거 보고서 {len(records)}건을 찾았습니다."}
    if tool_name == "lookup_region_info":
        return {"source": "모의 지역정보 시스템", "area": "경기도 파주시", "terrain": "임진강과 접경 산악·평야가 혼재",
                "weather": "야간 저시정, 북동풍", "operational_note": "민간 접근로와 감시 취약 구간을 함께 고려해야 합니다.",
                "summary": "파주시 접경 지형과 현재 작전 맥락을 확인했습니다."}
    if tool_name == "synthesize_evidence":
        sensor = next((item["result"] for item in observations if item["tool"] == "query_operational_db"), {})
        reports = next((item["result"] for item in observations if item["tool"] == "search_reports"), {})
        region = next((item["result"] for item in observations if item["tool"] == "lookup_region_info"), {})
        sensor_count, report_count = len(sensor.get("records", [])), len(reports.get("records", []))
        briefing = ("[파주시 최근 이상 징후 지휘관 브리핑]\n\n"
                    f"1. 상황: 최근 파주시 센서 관측 {sensor_count}건과 관련 보고서 {report_count}건을 확인했습니다. "
                    "이동체 및 열원 징후가 과거 야간 이동 증가 패턴과 일부 일치합니다.\n\n"
                    f"2. 판단: {region.get('terrain', '접경 지형')}과 {region.get('weather', '현재 기상')}을 고려할 때 추가 확인이 필요한 중간 수준 징후입니다.\n\n"
                    "3. 권고: 파주시 북부 감시 자산을 유지하고 동일 구간의 후속 센서 관측과 기존 보고 간 상관성을 재확인하십시오.\n\n"
                    "※ 본 결과는 세미나용 모의 데이터를 사용했습니다.")
        return {"source": "근거 종합 기능", "evidence_count": sensor_count + report_count + 1,
                "briefing": briefing, "summary": "수집한 근거를 지휘관 브리핑 초안으로 종합했습니다."}
    raise ValueError(f"지원하지 않는 도구입니다: {tool_name}")
