# Crypto Alpha Arena

Research and education codebase for **paper-only** crypto prediction and multi-agent tournaments. **No live exchange trading** is implemented.

- **[About this project](docs/ABOUT.md)** — scope, components, disclaimer.

---

## BTC Arena (recommended) — single model + CoinGlass

**One model**, **CoinGlass** (futures OHLC, market stats, funding / OI / Fear & Greed, optional REST probes) → predict next candle direction → **paper simulation**. **Streamlit** UI for price, prediction, and equity.

```bash
cd crypto-alpha-arena && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set COINGLASS_API_KEY; optional BTC_ARENA_USE_LLM=1 + local Ollama
PYTHONPATH=src python -m streamlit run frontend/btc_dashboard.py
```

Architecture: [`docs/BTC_ARENA_ARCHITECTURE.md`](docs/BTC_ARENA_ARCHITECTURE.md). Market data is sourced from **CoinGlass** (`COINGLASS_API_KEY` required).

---

Multi-agent **return prediction + simulated long/short** in the spirit of [Alpha Arena](https://alpha-arena.io/) — **no live exchange**. Each agent uses only **visible history** to predict the **next bar simple return** (`close_{t+1}/close_t - 1`), then simulates long/short; the next bar settles PnL with realized returns.

### Features

- **Prediction → simulated position**: long if prediction above threshold, short if below, flat otherwise; weight scales with confidence (see `src/crypto_alpha_arena/prediction_sim.py`).
- **Settlement**: next bar uses **realized** return for hypothetical PnL (still not live).
- **Feed**: default **synthetic GBM**; `USE_BINANCE_FEED=1` uses **Binance public klines** (no API key).
- **Agents**: momentum, mean reversion, trend, noise; with `OPENAI_API_KEY`, an **LLM** predictor (JSON return).
- **Metrics**: leaderboard with **direction accuracy**, **return MAE**, equity and drawdown.
- **Streamlit**: leaderboard + equity curve (`frontend/app.py`).

Legacy order-book code remains in `paper_exchange.py` for reference; the default competition path is **prediction simulation**.

### Quick start (classic arena)

```bash
cd crypto-alpha-arena
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

```bash
PYTHONPATH=src python scripts/run_arena.py --steps 300
python -m streamlit run frontend/app.py
```

### Optional environment (classic arena)

| Variable | Meaning |
|----------|---------|
| `USE_BINANCE_FEED=1` | Binance 1m kline replay (network) |
| `OPENAI_API_KEY` | Enable LLM prediction agent |
| `OPENAI_MODEL` | Default `gpt-4o-mini` |

---

## Alpha Arena (tournament platform) — `src/alpha_arena/`

Tournament for **LLM / rule agents**: shared `MarketState`, `TradeAction` JSON, async execution, fees and slippage, **20% drawdown liquidation**, Sharpe/Sortino/MaxDD + diversity penalty, CSV backtest, **FastAPI** leaderboard.

```bash
cd crypto-alpha-arena
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: COINGLASS_API_KEY, FRED_API_KEY (free at https://fredaccount.stlouisfed.org/apikeys )

PYTHONPATH=src python -m uvicorn alpha_arena.api.main:app --host 127.0.0.1 --port 8765
# http://127.0.0.1:8765/  · status: /api/live/status
```

- **`ENABLE_LIVE_FEED=1`** (default): background poll; **`ENABLE_LIVE_FEED=0`** disables it. **`LIVE_POLL_INTERVAL_SEC=45`** adjusts interval.
- Leaderboard file: **`outputs/alpha_arena_leaderboard.json`** (override with `ALPHA_ARENA_LEADERBOARD_JSON`).
- **CoinGlass**: `src/alpha_arena/data/coinglass_client.py` (header `CG-API-KEY`) → `outputs/live_context.json`.
- **Macro agent**: FRED `DFF` + SEC RSS → global regime for agents; optional FRED key improves macro series.
- Refresh macro + CoinGlass only: `PYTHONPATH=src python scripts/refresh_live_context.py`
- Sample data: `data/btc_sample.csv`

---

## Related repository

**Yanfu fund research** (AMAC harvest, strategy DNA vs global benchmarks, expansion simulations) is maintained separately: **`yanfu-research`** — not included here.

---

## Disclaimer

For research and education only; not investment advice.
