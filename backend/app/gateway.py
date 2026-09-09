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
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    def status(self) -> dict[str, Any]:
        return {"mode": self.mode, "provider": "openai" if self.mode == "openai" else "deterministic",
                "model": self.model, "configured": bool(os.getenv("OPENAI_API_KEY")) if self.mode == "openai" else True}

    def structured(self, *, name: str, instructions: str, payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        if self.mode == "deterministic":
            return self._deterministic(name, payload)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ModelGatewayError("OPENAI_API_KEY가 설정되지 않았습니다.")
        request = {
            "model": self.model,
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
        if name == "threat_analysis":
            event = payload.get("event", {})
            count, confidence = int(event.get("object_count", 1)), float(event.get("confidence", 0.5))
            level = "HIGH" if count >= 4 and confidence >= .85 else "MEDIUM" if count >= 2 and confidence >= .7 else "LOW"
            return {"threat_level": level, "summary": f"이동체 {count}개, 센서 신뢰도 {confidence:.2f}를 분석했습니다.", "evidence_ids": ["OBS-PJU-017", "CTX-PJU-003"]}
        return {"overall_threat_level": "HIGH", "summary": "파주시 신규 징후를 접경지역 최우선 대응 요소로 평가했습니다.",
                "priority_areas": ["경기도 파주시", "경기도 연천군"], "source_report_ids": payload.get("source_report_ids", [])}
