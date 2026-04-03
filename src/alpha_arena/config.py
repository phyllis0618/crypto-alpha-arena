from __future__ import annotations

import os
from dataclasses import dataclass, field


def _tickers() -> tuple[str, ...]:
    raw = os.getenv("ALLOWED_TICKERS", "BTC/USDT,ETH/USDT,SOL/USDT")
    return tuple(t.strip() for t in raw.split(",") if t.strip())


@dataclass(frozen=True)
class Settings:
    allowed_tickers: tuple[str, ...] = field(default_factory=_tickers)
    taker_fee_bps: float = float(os.getenv("TAKER_FEE_BPS", "5"))
    failed_trade_penalty_usd: float = float(os.getenv("FAILED_TRADE_PENALTY_USD", "50"))
    max_drawdown_liquidation_pct: float = float(os.getenv("MAX_DD_LIQUIDATION_PCT", "0.20"))
    diversity_penalty_strength: float = float(os.getenv("DIVERSITY_PENALTY_STRENGTH", "0.35"))
    bars_per_year: float = float(os.getenv("BARS_PER_YEAR", str(252 * 24 * 60)))


settings = Settings()
