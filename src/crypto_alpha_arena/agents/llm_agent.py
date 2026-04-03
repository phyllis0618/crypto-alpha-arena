from __future__ import annotations

import json
import os
from typing import Any, Optional

from crypto_alpha_arena.agents.base import PricePredictorAgent
from crypto_alpha_arena.models import PricePrediction, TickObservation
from crypto_alpha_arena.prompts import PREDICTOR_SYSTEM


class LLMPredictorAgent(PricePredictorAgent):
    """Optional OpenAI JSON agent: predicts next-step return."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        default_symbol: str = "BTCUSDT",
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self._symbol = default_symbol
        self._client = None
        if os.getenv("OPENAI_API_KEY"):
            try:
                from openai import OpenAI

                self._client = OpenAI()
            except Exception:
                self._client = None
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def _parse(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:].lstrip()
        return json.loads(text)

    def predict(self, obs: TickObservation) -> Optional[PricePrediction]:
        if obs.symbol != self._symbol or self._client is None:
            return None
        user = json.dumps(
            {
                "step": obs.step,
                "symbol": obs.symbol,
                "mid": obs.mid,
                "ret_1": obs.ret_1,
                "ret_5": obs.ret_5,
                "ret_20": obs.ret_20,
                "equity_usd": obs.equity_usd,
            },
            ensure_ascii=False,
        )
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": PREDICTOR_SYSTEM},
                    {"role": "user", "content": user},
                ],
            )
            raw = resp.choices[0].message.content or "{}"
            data = self._parse(raw)
        except Exception:
            return None

        sym = str(data.get("symbol", self._symbol))
        pred_r = float(data.get("pred_return_next", 0.0))
        conf = float(data.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))
        return PricePrediction(
            symbol=sym,
            pred_return_next=pred_r,
            confidence=conf,
            note=str(data.get("note", ""))[:200],
        )
