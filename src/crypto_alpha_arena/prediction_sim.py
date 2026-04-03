from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from crypto_alpha_arena.models import PricePrediction, PredictionLogRow


@dataclass
class SimConfig:
    """Map return prediction → simulated long/short size, then settle on realized return."""

    flat_threshold: float = 0.00008
    max_weight: float = 0.28
    min_weight: float = 0.06


def pred_to_side_weight(pred: PricePrediction, cfg: SimConfig) -> tuple[float, float]:
    """
    Returns (signed_weight, 0) where sign = +1 long / -1 short / 0 flat.
    Weight scales with confidence and |predicted return|.
    """
    r = pred.pred_return_next
    if abs(r) < cfg.flat_threshold:
        return 0.0, 0.0
    c = max(0.0, min(1.0, pred.confidence))
    mag = min(1.0, abs(r) * 120.0)
    w = cfg.min_weight + (cfg.max_weight - cfg.min_weight) * c * mag
    w = max(cfg.min_weight, min(cfg.max_weight, w))
    return (w if r > 0 else -w), w


def settle_one(
    *,
    step: int,
    agent_id: str,
    pred: PricePrediction,
    actual_return: float,
    equity: float,
    cfg: SimConfig,
) -> tuple[float, PredictionLogRow]:
    """
    Simulated PnL: long earns `w * equity * r`, short earns `w * equity * (-r)`.
    Returns (delta_equity, log row).
    """
    signed_w, _ = pred_to_side_weight(pred, cfg)
    if signed_w == 0.0:
        hit: Optional[bool] = None
        pnl = 0.0
    else:
        w_mag = abs(signed_w)
        if signed_w > 0:
            pnl = equity * w_mag * actual_return
        else:
            pnl = equity * w_mag * (-actual_return)
        pred_sign = 1 if pred.pred_return_next > 0 else -1
        act_sign = 1 if actual_return > 0 else (-1 if actual_return < 0 else 0)
        hit = pred_sign == act_sign if act_sign != 0 else None

    row = PredictionLogRow(
        step=step,
        agent_id=agent_id,
        symbol=pred.symbol,
        pred_return=pred.pred_return_next,
        actual_return=actual_return,
        direction_hit=hit,
        step_pnl_usd=pnl,
    )
    return pnl, row
