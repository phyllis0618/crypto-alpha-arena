"""Pydantic market specs: sessions, settlement, frictions (V2 roadmap validation)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TradingSession(BaseModel):
    """Local cash equity session bounds (illustrative; not exchange rule book)."""

    open_hhmm: str = Field(..., description="e.g. 09:30")
    close_hhmm: str = Field(..., description="e.g. 15:00")
    timezone: str = Field(..., description="IANA name e.g. Asia/Shanghai")


class MarketTradingSpec(BaseModel):
    """
    Exchange-grade knobs for simulation & compliance hooks.
    Crypto sleeves must reference **ETF tickers** only (no wallet / perp keys).
    """

    code: str
    name: str
    benchmark_index: str
    settlement_days: int = Field(ge=0, le=5, description="T+n cash settlement")
    trading_session: TradingSession
    tick_size: float = Field(..., gt=0, description="Minimum price increment (local currency)")
    stamp_duty_bps: float = Field(0.0, description="Turnover-side tax / levy style charge, bps")
    equity_transfer_tax_bps: float = Field(0.0, description="Sell-side or bilateral, bps")
    retail_participation_pct: float = Field(50.0, ge=0, le=100)
    notes: str = ""

    model_config = {"frozen": False}


def default_v2_universe() -> dict[str, MarketTradingSpec]:
    """Curated specs for Stage 1 (SEA mirror) + Stage 2 (US ops) validation narrative."""
    return {
        "CN_CSI1000": MarketTradingSpec(
            code="CN_CSI1000",
            name="China A-share CSI 1000 (T+1)",
            benchmark_index="000852.SH",
            settlement_days=1,
            trading_session=TradingSession(
                open_hhmm="09:30",
                close_hhmm="15:00",
                timezone="Asia/Shanghai",
            ),
            tick_size=0.01,
            stamp_duty_bps=10.0,
            equity_transfer_tax_bps=0.0,
            retail_participation_pct=82.0,
            notes="Baseline Yanfu DNA: high-freq price–vol factors; 2015–2018 retail analogue.",
        ),
        "VN_VNI": MarketTradingSpec(
            code="VN_VNI",
            name="Vietnam VN-Index",
            benchmark_index="VNINDEX",
            settlement_days=2,
            trading_session=TradingSession(
                open_hhmm="09:00",
                close_hhmm="15:00",
                timezone="Asia/Ho_Chi_Minh",
            ),
            tick_size=10.0,
            stamp_duty_bps=0.0,
            equity_transfer_tax_bps=2.0,
            retail_participation_pct=76.0,
            notes="Stage 1 mirror: retail-heavy; T+2 settlement drag on turnover velocity.",
        ),
        "IN_NIFTY": MarketTradingSpec(
            code="IN_NIFTY",
            name="India Nifty 50 + Next 50 sleeve",
            benchmark_index="NIFTY 50",
            settlement_days=2,
            trading_session=TradingSession(
                open_hhmm="09:15",
                close_hhmm="15:30",
                timezone="Asia/Kolkata",
            ),
            tick_size=0.05,
            stamp_duty_bps=0.0,
            equity_transfer_tax_bps=5.0,
            retail_participation_pct=72.0,
            notes="Stage 1 mirror; T+2 rolling settlement — model as 2–3 day effective.",
        ),
        "US_SP500": MarketTradingSpec(
            code="US_SP500",
            name="US S&P 500 (broad indexer baseline — low Sharpe narrative)",
            benchmark_index="SPX",
            settlement_days=2,
            trading_session=TradingSession(
                open_hhmm="09:30",
                close_hhmm="16:00",
                timezone="America/New_York",
            ),
            tick_size=0.01,
            stamp_duty_bps=0.0,
            equity_transfer_tax_bps=0.0,
            retail_participation_pct=25.0,
            notes="Generic index enhancement / beta — **not** Stage 2 Special Op entry point.",
        ),
        "US_RUT2000": MarketTradingSpec(
            code="US_RUT2000",
            name="US Russell 2000 (primary US small-cap benchmark)",
            benchmark_index="RUT",
            settlement_days=2,
            trading_session=TradingSession(
                open_hhmm="09:30",
                close_hhmm="16:00",
                timezone="America/New_York",
            ),
            tick_size=0.01,
            stamp_duty_bps=0.0,
            equity_transfer_tax_bps=0.0,
            retail_participation_pct=35.0,
            notes="Stage 2-C: small-cap quant — A-share style inefficiency hunting.",
        ),
        "CRYPTO_ETF_IBIT": MarketTradingSpec(
            code="CRYPTO_ETF_IBIT",
            name="US-listed spot BTC ETF (IBIT)",
            benchmark_index="IBIT",
            settlement_days=1,
            trading_session=TradingSession(
                open_hhmm="09:30",
                close_hhmm="16:00",
                timezone="America/New_York",
            ),
            tick_size=0.01,
            stamp_duty_bps=0.0,
            equity_transfer_tax_bps=0.0,
            retail_participation_pct=60.0,
            notes="Compliance: **ETF wrapper only** — vol harvest via MR/trend sleeves on ETF NAV premium/discount + beta.",
        ),
        "CRYPTO_ETF_ETHW": MarketTradingSpec(
            code="CRYPTO_ETF_ETHW",
            name="US-listed ETH ETF proxy (ETHW class)",
            benchmark_index="ETHW",
            settlement_days=1,
            trading_session=TradingSession(
                open_hhmm="09:30",
                close_hhmm="16:00",
                timezone="America/New_York",
            ),
            tick_size=0.01,
            stamp_duty_bps=0.0,
            equity_transfer_tax_bps=0.0,
            retail_participation_pct=62.0,
            notes="ETF-only; no direct chain settlement in this framework.",
        ),
        "US_BIOTECH_QUANT": MarketTradingSpec(
            code="US_BIOTECH_QUANT",
            name="US Biotech Quantamental sleeve (XBI / trial-NLP proxy)",
            benchmark_index="XBI",
            settlement_days=2,
            trading_session=TradingSession(
                open_hhmm="09:30",
                close_hhmm="16:00",
                timezone="America/New_York",
            ),
            tick_size=0.01,
            stamp_duty_bps=0.0,
            equity_transfer_tax_bps=0.0,
            retail_participation_pct=28.0,
            notes="Stage 2-A: agentic workflow on PDUFA / p-value / pipeline — non-structured to factor.",
        ),
    }
