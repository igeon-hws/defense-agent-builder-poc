"""실제 OpenAI 호출과 반복 가능한 결정론적 데모 응답을 제공한다."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx


class ModelGatewayError(RuntimeError):
    pass


class ModelGateway:
    def __init__(self) -> None:
        self.mode = os.getenv("DEMO_MODEL_MODE", "openai").lower()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        configured = [item.strip() for item in os.getenv("OPENAI_ALLOWED_MODELS", "").split(",") if item.strip()]
        self.allowed_models = list(dict.fromkeys([self.model, *configured, "gpt-4.1-mini", "gpt-5-mini"]))
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    def status(self) -> dict[str, Any]:
        return {"mode": self.mode, "provider": "openai" if self.mode == "openai" else "deterministic",
                "model": self.model, "configured": bool(os.getenv("OPENAI_API_KEY")) if self.mode == "openai" else True}

    def structured(self, *, name: str, instructions: str, payload: dict[str, Any], schema: dict[str, Any],
                   model: str | None = None) -> dict[str, Any]:
        if self.mode == "deterministic":
            return self._deterministic(name, payload)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ModelGatewayError("OPENAI_API_KEY가 설정되지 않았습니다.")
        selected_model = model or self.model
        if selected_model not in self.allowed_models:
            raise ModelGatewayError(f"허용되지 않은 모델입니다: {selected_model}")
        request = {
            "model": selected_model,
            "instructions": instructions,
            "input": json.dumps(payload, ensure_ascii=False),
            "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}},
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(f"{self.base_url}/responses", headers={"Authorization": f"Bearer {api_key}"}, json=request)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            detail = getattr(getattr(exc, "response", None), "text", "")
            raise ModelGatewayError(f"OpenAI Responses API 호출 실패: {detail[:300] or exc}") from exc
        text = data.get("output_text") or self._output_text(data)
        if not text:
            raise ModelGatewayError("OpenAI 응답에 구조화 출력이 없습니다.")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ModelGatewayError("OpenAI 구조화 출력을 해석할 수 없습니다.") from exc

    @staticmethod
    def _output_text(data: dict[str, Any]) -> str:
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text", "")
        return ""

    @staticmethod
    def _deterministic(name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name == "react_next_action":
            observations = payload.get("observations", [])
            completed = {item.get("tool") for item in observations}
            available = {item.get("id") for item in payload.get("available_tools", [])}
            goal = payload.get("goal", "")
            context = payload.get("conversation_context", [])
            follow_up = bool(context) and any(word in goal for word in ("앞", "이전", "방금", "요약", "정리", "짧게", "다시 써"))
            if follow_up:
                previous = context[-1].get("assistant", "")
                return {"thought_summary": "이전 대화 결과만으로 답할 수 있어 추가 도구를 호출하지 않습니다.", "action": "FINAL",
                        "action_input": "", "final_answer": previous or "이전 분석 결과를 확인했습니다."}
            candidates: list[tuple[str, str]] = []
            if any(word in goal for word in ("센서", "이상", "징후", "최근", "작전")):
                candidates.append(("query_operational_db", "요청에 필요한 최근 작전·센서 데이터를 확인합니다."))
            if any(word in goal for word in ("보고서", "비교", "과거", "기존", "브리핑")):
                candidates.append(("search_reports", "요청과 관련된 기존 보고서를 확인합니다."))
            if any(word in goal for word in ("지역", "지형", "기상", "파주", "브리핑")):
                candidates.append(("lookup_region_info", "판단에 필요한 지역 맥락을 확인합니다."))
            if any(word in goal for word in ("브리핑", "종합", "작성")):
                candidates.append(("synthesize_evidence", "선택한 근거를 요청한 형식으로 종합합니다."))
            plan = [(action, summary) for action, summary in candidates if action in available]
            for action, summary in plan:
                if action not in completed:
                    return {"thought_summary": summary, "action": action, "action_input": "경기도 파주시", "final_answer": ""}
            synthesis = next((item.get("result", {}) for item in observations if item.get("tool") == "synthesize_evidence"), {})
            summaries = [item.get("result", {}).get("summary", "") for item in observations if item.get("result", {}).get("summary")]
            return {"thought_summary": "현재 요청에 필요한 정보가 확보되어 답변을 제시합니다.", "action": "FINAL",
                    "action_input": "", "final_answer": synthesis.get("briefing") or "\n".join(summaries) or "요청 내용을 확인했습니다."}
        if name == "threat_analysis":
            event = payload.get("event", {})
            count, confidence = int(event.get("object_count", 1)), float(event.get("confidence", 0.5))
            level = "HIGH" if count >= 4 and confidence >= .85 else "MEDIUM" if count >= 2 and confidence >= .7 else "LOW"
            summary=f"이동체 {count}개, 센서 신뢰도 {confidence:.2f}를 분석했습니다."
            return {"threat_level": level, "summary": summary, "evidence_ids": ["OBS-PJU-017", "CTX-PJU-003"],
                    "draft": f"[파주시 지역 보고]\n위협 수준: {level}\n\n{summary}\n\n관련 감시 자산의 지속 운용을 권고합니다."}
        summary="파주시 신규 징후를 접경지역 최우선 대응 요소로 평가했습니다."
        return {"overall_threat_level": "HIGH", "summary": summary,
                "priority_areas": ["경기도 파주시", "경기도 연천군"], "source_report_ids": payload.get("source_report_ids", []),
                "draft": f"[접경지역 지휘관 보고]\n위협 수준: HIGH\n\n{summary}\n\n파주시 감시 자산 증강을 권고합니다."}
