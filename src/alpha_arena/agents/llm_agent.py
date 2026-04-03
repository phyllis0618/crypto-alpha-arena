from __future__ import annotations

import json
import os
from typing import Any

from alpha_arena.agents.base import BaseAgent
from alpha_arena.agents.prompts import CRYPTO_ALPHA_SYSTEM
from alpha_arena.models import MarketState, TradeAction


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) >= 2 else text
        if text.startswith("json"):
            text = text[4:].lstrip()
    return json.loads(text)


class LLMStrategyAgent(BaseAgent):
    """OpenAI-compatible JSON agent; requires OPENAI_API_KEY."""

    def __init__(self, agent_id: str, name: str, model: str | None = None) -> None:
        self.agent_id = agent_id
        self.name = name
        self._model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._client = None
        if os.getenv("OPENAI_API_KEY"):
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI()
            except Exception:
                self._client = None

    async def generate_action(self, state: MarketState) -> TradeAction:
        if self._client is None:
            return TradeAction(
                ticker=state.primary_ticker,
                signal="NEUTRAL",
                confidence=0.0,
                reasoning="LLM disabled (no OPENAI_API_KEY)",
                execution={"type": "MARKET", "size_pct": 0.0, "take_profit": None, "stop_loss": None},
            )
        payload = state.model_dump(mode="json")
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                temperature=0.15,
                messages=[
                    {"role": "system", "content": CRYPTO_ALPHA_SYSTEM},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            )
            raw = resp.choices[0].message.content or "{}"
            data = _parse_json(raw)
            return TradeAction.model_validate(data)
        except Exception as e:
            return TradeAction(
                ticker=state.primary_ticker,
                signal="NEUTRAL",
                confidence=0.0,
                reasoning=f"parse_error:{e!s}",
                execution={"type": "MARKET", "size_pct": 0.0, "take_profit": None, "stop_loss": None},
            )
