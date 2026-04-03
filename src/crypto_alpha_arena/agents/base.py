from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from crypto_alpha_arena.models import PricePrediction, TickObservation


class PricePredictorAgent(ABC):
    agent_id: str
    name: str

    @abstractmethod
    def predict(self, obs: TickObservation) -> Optional[PricePrediction]:
        """Forecast next-step return; no future data in obs."""
