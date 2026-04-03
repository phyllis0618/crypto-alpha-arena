from __future__ import annotations

from abc import ABC, abstractmethod

from alpha_arena.models import MarketState, TradeAction


class BaseAgent(ABC):
    agent_id: str
    name: str

    @abstractmethod
    async def generate_action(self, state: MarketState) -> TradeAction:
        """Return validated TradeAction (Pydantic)."""
