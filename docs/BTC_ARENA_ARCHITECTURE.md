# BTC Arena — single-model architecture

## Goals

**One model**, multiple data sources, **next-candle direction prediction**, **paper trading** — no exchange order routing.

## Layout

| Path | Role |
|------|------|
| `src/btc_arena/models.py` | `UnifiedMarketSnapshot`, `BTCMarketSnapshot`, `Prediction`, `SimState` |
| `src/alpha_arena/data/coinglass_client.py` | Low-level: coins-markets, Fear & Greed, futures OHLC |
| `src/btc_arena/data/coinglass_full.py` | `fetch_btc_arena_coinglass_full`: above + parallel REST probes |
| `src/btc_arena/analytics.py` | RSI, volume, volatility from OHLCV |
| `src/btc_arena/rumor_chat.py` | Local Ollama rumor extract + validation; heuristic fallback offline |
| `src/btc_arena/data/coinglass_btc.py` | `coin_glass_context_from_snapshot`, optional sync helper |
| `src/btc_arena/data/binance.py` | Legacy direct Binance REST (not default for BTC Arena) |
| `src/btc_arena/predictor.py` | `predict_single_model`: rules by default, optional LLM |
| `src/btc_arena/simulator.py` | Settle prior prediction with price move |
| `src/btc_arena/pipeline.py` | `build_snapshot` + `run_pipeline_tick` |
| `frontend/btc_dashboard.py` | Streamlit: market, prediction, equity |

## Data flow

1. **CoinGlass** (`COINGLASS_API_KEY`): futures OHLC, coins-markets, Fear & Greed, optional **parallel REST probes** (OI, funding, liquidations, taker, long/short, ETF, articles, CVD, etc.), limited by `COINGLASS_PROBE_MAX`.
2. **Merge** into `UnifiedMarketSnapshot` (`market` + `candles` + `analytics` + `coinglass` + `coinglass_endpoints`) → **single model** → `Prediction`.
3. Optional **macro** (FRED DFF, SEC RSS) and **X** (Twitter API v2) enrich the snapshot.
4. **Rumor lab** (sidebar): paste text → Ollama extract → validation JSON; **not** OpenAI.
5. **Simulation**: Streamlit `session_state` holds last price and prediction; each refresh settles `SimState` with realized move.

## Environment variables

| Variable | Meaning |
|----------|---------|
| `COINGLASS_API_KEY` | Required — CoinGlass Open API v4 |
| `COINGLASS_FUTURES_EXCHANGE` | Optional, default `Binance` (which feed on CoinGlass, not your Binance API key) |
| `COINGLASS_FUTURES_SYMBOL` | Optional, default `BTCUSDT` |
| `COINGLASS_FUTURES_INTERVAL` | Optional, default `4h` |
| `COINGLASS_FUTURES_OHLC_LIMIT` | Optional, default `120` |
| `BTC_ARENA_USE_LLM` | Set `1` for local **Ollama** (Llama), no OpenAI |
| `BTC_ARENA_OLLAMA_URL` | Default `http://127.0.0.1:11434` |
| `BTC_ARENA_OLLAMA_MODEL` | Default `llama3.2` (`ollama pull` first) |
| `FRED_API_KEY` | Same as Alpha Arena — Fed **DFF** (`macro_agent.py`) |
| `BTC_ARENA_USE_MACRO` | Default `1`: blend macro regime into **rules** edge; `0` off |
| `TWITTER_BEARER_TOKEN` | Optional: X API v2 Bearer + `TWITTER_MONITOR_USERNAMES` |
| `COINGLASS_PROBE_MAX` | Extra REST probes — **default `0`** (avoid 429); raise slowly (e.g. 8) if needed |
| `COINGLASS_PROBE_DELAY_SEC` | Delay between probes (seconds), default `0.45` |
| `COINGLASS_OHLC_RETRIES` | Retries on OHLC 429, default `5` |
| `COINGLASS_RETRY_DELAY_SEC` | Base backoff for OHLC retries (seconds), default `1.25` |

## Run

```bash
cd crypto-alpha-arena
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m streamlit run frontend/btc_dashboard.py
```
