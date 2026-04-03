# About Crypto Alpha Arena

**Crypto Alpha Arena** is a research and education workspace for **paper-traded** crypto and multi-agent experiments. Nothing here connects to a live exchange for order placement; simulations use historical or vendor feeds (e.g. CoinGlass, optional Binance public candles) for **next-bar return prediction** and **hypothetical PnL**.

## What lives in this repository

| Component | Role |
|-----------|------|
| **BTC Arena** (`src/btc_arena/`) | Single-model pipeline: CoinGlass (and optional macro / X) → `UnifiedMarketSnapshot` → rules or local **Ollama** prediction → paper simulator. Streamlit UI: `frontend/btc_dashboard.py`. |
| **Alpha Arena** (`src/alpha_arena/`) | Tournament-style agents with `MarketState` / `TradeAction`, fees, drawdown rules, FastAPI leaderboard, optional live CoinGlass + macro poll. |
| **Classic arena** (`src/crypto_alpha_arena/`) | Original next-bar return arena with synthetic GBM or Binance replay; Streamlit: `frontend/app.py`. |

Yanfu-specific fund research (AMAC harvest, DNA benchmarks, expansion roadmap) lives in a **separate repository**: **`yanfu-research`** — do not mix the two codebases.

## Principles

- **Separation of concerns**: market data ingestion, prediction, and simulation are explicit modules with typed models (`pydantic` where used).
- **No hidden live trading**: environment variables gate API keys; defaults favor rate-limit safety (e.g. `COINGLASS_PROBE_MAX=0`).
- **English** documentation and UI copy in this repo unless a file is explicitly legacy.

## Disclaimer

For research and education only; not investment advice. Vendor data and simulations may be incomplete or delayed. Past or simulated performance does not imply future results.
