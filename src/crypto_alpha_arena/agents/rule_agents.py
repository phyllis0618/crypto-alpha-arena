from __future__ import annotations

import random
from typing import Optional

from crypto_alpha_arena.agents.base import PricePredictorAgent
from crypto_alpha_arena.models import PricePrediction, TickObservation


class MomentumPredictor(PricePredictorAgent):
    def __init__(self, agent_id: str, symbol: str, lookback_sensitivity: float = 1.0) -> None:
        self.agent_id = agent_id
        self.name = f"Momentum ({symbol})"
        self._symbol = symbol
        self._k = lookback_sensitivity

    def predict(self, obs: TickObservation) -> Optional[PricePrediction]:
        if obs.symbol != self._symbol:
            return None
        pred_r = obs.ret_5 * self._k + obs.ret_1 * 0.5
        conf = min(1.0, abs(pred_r) * 90.0 + 0.15)
        return PricePrediction(
            symbol=self._symbol,
            pred_return_next=pred_r,
            confidence=conf,
            note="mom",
        )


class MeanReversionPredictor(PricePredictorAgent):
    def __init__(self, agent_id: str, symbol: str) -> None:
        self.agent_id = agent_id
        self.name = f"Mean reversion ({symbol})"
        self._symbol = symbol

    def predict(self, obs: TickObservation) -> Optional[PricePrediction]:
        if obs.symbol != self._symbol:
            return None
        pred_r = -obs.ret_20 * 0.55
        conf = min(1.0, abs(obs.ret_20) * 40.0 + 0.2)
        return PricePrediction(
            symbol=self._symbol,
            pred_return_next=pred_r,
            confidence=conf,
            note="mr",
        )


class TrendPredictor(PricePredictorAgent):
    def __init__(self, agent_id: str, symbol: str) -> None:
        self.agent_id = agent_id
        self.name = f"Trend ({symbol})"
        self._symbol = symbol

    def predict(self, obs: TickObservation) -> Optional[PricePrediction]:
        if obs.symbol != self._symbol:
            return None
        pred_r = obs.ret_20 * 0.65 + obs.ret_5 * 0.35
        conf = min(1.0, abs(pred_r) * 70.0 + 0.15)
        return PricePrediction(
            symbol=self._symbol,
            pred_return_next=pred_r,
            confidence=conf,
            note="trend",
        )


class RandomPredictor(PricePredictorAgent):
    """Baseline: noisy return forecasts."""

    def __init__(self, agent_id: str, symbol: str, seed: int = 0) -> None:
        self.agent_id = agent_id
        self.name = f"Noise ({symbol})"
        self._symbol = symbol
        self._rng = random.Random(seed)

    def predict(self, obs: TickObservation) -> Optional[PricePrediction]:
        if obs.symbol != self._symbol:
            return None
        pred_r = self._rng.uniform(-0.02, 0.02)
        conf = self._rng.uniform(0.2, 0.6)
        return PricePrediction(
            symbol=self._symbol,
            pred_return_next=pred_r,
            confidence=conf,
            note="rand",
        )
