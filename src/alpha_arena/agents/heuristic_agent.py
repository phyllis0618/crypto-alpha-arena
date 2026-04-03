from __future__ import annotations

from alpha_arena.agents.base import BaseAgent
from alpha_arena.models import MarketState, TradeAction


class HeuristicAgent(BaseAgent):
    """Rule-based agent for tests without API keys."""

    def __init__(self, agent_id: str, name: str, bias_long: bool = True) -> None:
        self.agent_id = agent_id
        self.name = name
        self._bias_long = bias_long

    async def generate_action(self, state: MarketState) -> TradeAction:
        bars = state.ohlcv_1m
        if len(bars) < 3:
            return TradeAction(
                ticker=state.primary_ticker,
                signal="NEUTRAL",
                confidence=0.2,
                reasoning="insufficient bars",
                execution={"type": "MARKET", "size_pct": 0.0, "take_profit": None, "stop_loss": None},
            )
        r1 = bars[-1].close / bars[-2].close - 1.0
        r5 = bars[-1].close / bars[-6].close - 1.0 if len(bars) >= 6 else r1
        edge = 0.6 * r5 + 0.4 * r1 + (0.001 if self._bias_long else -0.001)
        if abs(edge) < 0.0004:
            sig = "NEUTRAL"
            conf = 0.15
            sz = 0.0
        elif edge > 0:
            sig = "LONG"
            conf = min(0.95, 0.35 + abs(edge) * 80)
            sz = min(0.2, 0.08 + abs(edge) * 40)
        else:
            sig = "SHORT"
            conf = min(0.95, 0.35 + abs(edge) * 80)
            sz = min(0.2, 0.08 + abs(edge) * 40)
        last = bars[-1].close
        if sig == "LONG":
            tp, sl = last * (1 + 0.012), last * (1 - 0.008)
        elif sig == "SHORT":
            tp, sl = last * (1 - 0.012), last * (1 + 0.008)
        else:
            tp, sl = None, None
        # Global macro regime from Macro/News Agent (passed in MarketState)
        if state.macro_regime == "risk_off" and sig == "LONG":
            sz *= 0.45
            conf *= 0.85
        elif state.macro_regime == "risk_on" and sig == "SHORT":
            sz *= 0.55
            conf *= 0.9
        return TradeAction(
            ticker=state.primary_ticker,
            signal=sig,
            confidence=min(0.95, conf),
            reasoning=(
                f"mom_edge={edge:.6f}; macro={state.macro_regime} "
                f"(cg_funding={state.coinglass.funding_rate_avg!s})"
            ),
            execution={
                "type": "MARKET",
                "size_pct": min(0.25, max(0.0, sz)),
                "take_profit": tp,
                "stop_loss": sl,
            },
        )
