from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from crypto_alpha_arena.models import AgentAccount, Fill, OrderIntent, Position, Side


class PaperExchange:
    """Signed spot-style positions; PnL marks to mid for equity."""

    def __init__(
        self,
        fee_bps: float = 5.0,
        slippage_bps: float = 3.0,
    ) -> None:
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self._accounts: dict[str, AgentAccount] = {}
        self._fills: list[Fill] = []
        self._step = 0

    def register(self, agent_id: str, name: str, initial_cash: float) -> None:
        self._accounts[agent_id] = AgentAccount(
            agent_id=agent_id,
            name=name,
            cash_usd=initial_cash,
        )

    @property
    def step(self) -> int:
        return self._step

    def set_step(self, step: int) -> None:
        self._step = step

    def accounts(self) -> dict[str, AgentAccount]:
        return {k: v.model_copy(deep=True) for k, v in self._accounts.items()}

    def fills(self) -> list[Fill]:
        return list(self._fills)

    def _fill_price(self, side: Side, mid: float) -> float:
        slip = self.slippage_bps / 10_000.0
        if side == Side.BUY:
            return mid * (1 + slip)
        return mid * (1 - slip)

    def _fee(self, notional: float) -> float:
        return abs(notional) * (self.fee_bps / 10_000.0)

    @staticmethod
    def unrealized(pos: Position, mid: float) -> float:
        return pos.qty * (mid - pos.entry_price)

    def equity(self, agent_id: str, prices: dict[str, float]) -> float:
        acc = self._accounts[agent_id]
        eq = acc.cash_usd
        for sym, pos in acc.positions.items():
            mid = prices.get(sym, pos.entry_price)
            eq += self.unrealized(pos, mid)
        return eq

    def unrealized_for_symbol(self, agent_id: str, symbol: str, mid: float) -> float:
        pos = self._accounts[agent_id].positions.get(symbol)
        if not pos:
            return 0.0
        return self.unrealized(pos, mid)

    def position_qty(self, agent_id: str, symbol: str) -> float:
        pos = self._accounts[agent_id].positions.get(symbol)
        return pos.qty if pos else 0.0

    def execute(
        self,
        agent_id: str,
        intent: OrderIntent,
        mid_price: float,
        prices: Optional[dict[str, float]] = None,
    ) -> Optional[Fill]:
        if intent.notional_usd <= 0:
            return None
        acc = self._accounts[agent_id]
        if prices is not None:
            eq = self.equity(agent_id, prices)
            if eq < 0 and not intent.reduce_only:
                return None
        price = self._fill_price(intent.side, mid_price)
        raw_qty = intent.notional_usd / price
        trade_qty = raw_qty if intent.side == Side.BUY else -raw_qty
        sym = intent.symbol
        pos = acc.positions.get(sym)

        if intent.reduce_only and pos:
            max_notional = abs(pos.qty) * price
            if intent.notional_usd > max_notional + 1e-9:
                intent = intent.model_copy(update={"notional_usd": max_notional})
                price = self._fill_price(intent.side, mid_price)
                raw_qty = intent.notional_usd / price
                trade_qty = raw_qty if intent.side == Side.BUY else -raw_qty
            if pos.qty > 0 and trade_qty > 0:
                return None
            if pos.qty < 0 and trade_qty < 0:
                return None

        notional = abs(trade_qty) * price
        fee = self._fee(notional)
        acc.cash_usd -= trade_qty * price + fee

        if pos is None or abs(pos.qty) < 1e-12:
            acc.positions[sym] = Position(
                symbol=sym,
                qty=trade_qty,
                entry_price=price,
                leverage=intent.leverage,
            )
        else:
            new_qty = pos.qty + trade_qty
            same_dir = pos.qty * trade_qty > 0
            if same_dir:
                entry = (pos.entry_price * abs(pos.qty) + price * abs(trade_qty)) / (
                    abs(pos.qty) + abs(trade_qty)
                )
                acc.positions[sym] = Position(
                    symbol=sym,
                    qty=new_qty,
                    entry_price=entry,
                    leverage=intent.leverage,
                )
            else:
                # Opposite: realize on overlap, remainder opens at `price`
                closed = min(abs(pos.qty), abs(trade_qty))
                if pos.qty > 0:
                    acc.realized_pnl_usd += closed * (price - pos.entry_price)
                else:
                    acc.realized_pnl_usd += closed * (pos.entry_price - price)

                if abs(new_qty) < 1e-12:
                    del acc.positions[sym]
                elif (pos.qty > 0 > trade_qty and new_qty < 0) or (
                    pos.qty < 0 < trade_qty and new_qty > 0
                ):
                    acc.positions[sym] = Position(
                        symbol=sym,
                        qty=new_qty,
                        entry_price=price,
                        leverage=intent.leverage,
                    )
                else:
                    acc.positions[sym] = Position(
                        symbol=sym,
                        qty=new_qty,
                        entry_price=pos.entry_price,
                        leverage=pos.leverage,
                    )

        fill = Fill(
            symbol=sym,
            side=intent.side,
            qty=abs(trade_qty),
            price=price,
            fee_usd=fee,
            agent_id=agent_id,
            step=self._step,
            ts=datetime.now(timezone.utc),
        )
        self._fills.append(fill)
        return fill

    def flatten_all(self, agent_id: str, prices: dict[str, float]) -> list[Fill]:
        """Close every position at current mid (reduce-only)."""
        out: list[Fill] = []
        for sym in list(self._accounts[agent_id].positions.keys()):
            mid = prices.get(sym)
            if mid is None:
                continue
            pos = self._accounts[agent_id].positions.get(sym)
            if not pos or abs(pos.qty) < 1e-12:
                continue
            side = Side.SELL if pos.qty > 0 else Side.BUY
            intent = OrderIntent(
                symbol=sym,
                side=side,
                notional_usd=abs(pos.qty) * mid,
                leverage=pos.leverage,
                reduce_only=True,
                rationale="flatten",
            )
            f = self.execute(agent_id, intent, mid, prices)
            if f:
                out.append(f)
        return out

    def resolve_insolvent(self, agent_id: str, prices: dict[str, float]) -> None:
        """Flatten; if cash is still negative, write off to zero."""
        acc = self._accounts[agent_id]
        self.flatten_all(agent_id, prices)
        if acc.cash_usd < 0:
            acc.realized_pnl_usd += acc.cash_usd
            acc.cash_usd = 0.0
