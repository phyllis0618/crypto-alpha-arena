# BTC Arena — 单模型架构

## 目标

一个**模型**、多数据源、**预测下一根 K 线方向**、**纸面模拟交易**，不接交易所。

## 目录

| 路径 | 职责 |
|------|------|
| `src/btc_arena/models.py` | `UnifiedMarketSnapshot`、`BTCMarketSnapshot`、`Prediction`、`SimState` |
| `src/alpha_arena/data/coinglass_client.py` | 底层：coins-markets、Fear&Greed、期货 OHLC |
| `src/btc_arena/data/coinglass_full.py` | `fetch_btc_arena_coinglass_full`：上述 + 并行探测多 CoinGlass REST |
| `src/btc_arena/analytics.py` | 由 OHLCV 计算 RSI、成交量、波动等 |
| `src/btc_arena/rumor_chat.py` | 本地 Ollama 从聊天文本提取 rumor；离线时用启发式 |
| `src/btc_arena/data/coinglass_btc.py` | `coin_glass_context_from_snapshot`、可选 `run_coinglass_btc_sync` |
| `src/btc_arena/data/binance.py` | 遗留：直接调 Binance 公共 REST（BTC Arena 默认不再使用） |
| `src/btc_arena/predictor.py` | `predict_single_model`：规则默认，可选 LLM |
| `src/btc_arena/simulator.py` | 用上一价→现价结算上一预测 |
| `src/btc_arena/pipeline.py` | `build_snapshot` + `run_pipeline_tick` |
| `frontend/btc_dashboard.py` | Streamlit：行情、预测、权益 |

## 数据流

1. **CoinGlass**（需 `COINGLASS_API_KEY`）：期货 OHLC、coins-markets、Fear&Greed，以及 **多路并行 REST**（OI、资金费、清算、Taker、全球多空比、ETF、文章、CVD 等，受 `COINGLASS_PROBE_MAX` 限制）。
2. **合并**为 `UnifiedMarketSnapshot`（`market` + `candles` + `analytics` + `coinglass` + `coinglass_endpoints`）→ **单模型**输出 `Prediction`。
3. **Rumor lab**：侧边栏聊天，用本地 Ollama 从用户粘贴文本中抽取 rumor 结构；**不接** OpenAI。
4. **模拟**：Streamlit `session_state` 保存上一时刻价格与预测；下一刷用真实涨跌结算 `SimState`。

## 环境变量

| 变量 | 含义 |
|------|------|
| `COINGLASS_API_KEY` | 必填，CoinGlass Open API v4 |
| `COINGLASS_FUTURES_EXCHANGE` | 可选，默认 `Binance`（CoinGlass 侧选择哪所期货 feed，非直连 Binance API） |
| `COINGLASS_FUTURES_SYMBOL` | 可选，默认 `BTCUSDT` |
| `COINGLASS_FUTURES_INTERVAL` | 可选，默认 `4h` |
| `COINGLASS_FUTURES_OHLC_LIMIT` | 可选，默认 `120` |
| `BTC_ARENA_USE_LLM` | 设为 `1` 使用本地 **Ollama**（Llama），无需 OpenAI |
| `BTC_ARENA_OLLAMA_URL` | 默认 `http://127.0.0.1:11434` |
| `BTC_ARENA_OLLAMA_MODEL` | 默认 `llama3.2`（先 `ollama pull` 对应模型） |
| `FRED_API_KEY` | 与 Alpha Arena 相同：联储 **DFF** 日频有效利率（`macro_agent.py`） |
| `BTC_ARENA_USE_MACRO` | 默认 `1`：把 macro regime（risk_on/off）以小权重并入 **rules** edge；`0` 关闭 |
| `TWITTER_BEARER_TOKEN` | 可选：X API v2 Bearer，配合 `TWITTER_MONITOR_USERNAMES` 拉取用户最近推文 |
| `COINGLASS_PROBE_MAX` | 额外 REST 探测数量，**默认 0**（避免 429）；需要时再改为 8 等 |
| `COINGLASS_PROBE_DELAY_SEC` | 探测间隔（秒），默认 `0.45` |
| `COINGLASS_OHLC_RETRIES` | OHLC 遇 429 时重试次数，默认 `5` |
| `COINGLASS_RETRY_DELAY_SEC` | OHLC 重试基础退避（秒），默认 `1.25` |

## 运行

```bash
cd crypto-alpha-arena
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m streamlit run frontend/btc_dashboard.py
```
