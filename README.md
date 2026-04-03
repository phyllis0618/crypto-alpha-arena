# Crypto Alpha Arena

## BTC Arena（推荐：单模型 + 实时行情）`src/btc_arena/`

**一个模型**、**CoinGlass**（期货 OHLC + 市场统计 + 资金费/OI/F&G 等）→ 预测下一根 K 线方向 → **纸面模拟**。前端：**Streamlit** 展示价格曲线、预测、模拟权益。

```bash
cd crypto-alpha-arena && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填入 COINGLASS_API_KEY；可选 BTC_ARENA_USE_LLM=1 + 本地 Ollama
PYTHONPATH=src python -m streamlit run frontend/btc_dashboard.py
```

逻辑说明见 `docs/BTC_ARENA_ARCHITECTURE.md`。BTC Arena 行情与 K 线均来自 **CoinGlass**，需配置 `COINGLASS_API_KEY`。

---

多智能体**币价预测 + 模拟多空**大赛：对标 [Alpha Arena](https://alpha-arena.io/) 的观赛形态，但**不接任何实盘交易所**。每个智能体只根据**当前可见的历史特征**预测**下一根 K 线的简单收益率**（`close_{t+1}/close_t - 1`），再根据预测方向做**模拟做多/做空**，在下一根 K 线用真实涨跌结算 PnL。

## 功能概览

- **预测 → 模拟仓位**：预测值超过阈值则做多，低于则做空，否则空仓；仓位权重与 `confidence` 与 |预测| 有关（见 `src/crypto_alpha_arena/prediction_sim.py`）。
- **结算**：下一根 K 线揭晓后，用**该步真实收益率**计算模拟盈亏（仍无实盘连接）。
- **行情**：默认 **合成 GBM**；`USE_BINANCE_FEED=1` 时用 **Binance 公共 K 线**循环回放（无需 API Key）。
- **智能体**：动量、均值回归、趋势、噪声预测器；若配置 `OPENAI_API_KEY` 则加入 **LLM 预测**（JSON 输出预测收益率）。
- **指标**：排行榜含 **方向准确率**、**收益率预测 MAE**、净值与回撤。
- **Streamlit**：排行榜 + 净值曲线。

旧版「撮合下单」实现仍保留在 `paper_exchange.py` 供参考，**默认赛程已改为预测模拟**。

## 快速开始

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

## 环境变量（可选）

| 变量 | 含义 |
|------|------|
| `USE_BINANCE_FEED=1` | 使用 Binance 1m K 线回放（需网络） |
| `OPENAI_API_KEY` | 启用 LLM 预测智能体 |
| `OPENAI_MODEL` | 默认 `gpt-4o-mini` |

## Alpha Arena（量化锦标赛平台）`src/alpha_arena/`

面向 **LLM/规则智能体** 的策略锦标赛：**统一 `MarketState` 输入**、**`TradeAction` JSON 输出**、**异步并发**、**手续费+滑点**、**20% 回撤强平**、**Sharpe/Sortino/MaxDD + 多样性惩罚**、**CSV 回测**、**FastAPI 排行榜**。

```bash
cd crypto-alpha-arena
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env：填入 COINGLASS_API_KEY、FRED_API_KEY（FRED 免费申请见上）

# 启动 API：后台按 LIVE_POLL_INTERVAL_SEC（默认 45）自动拉 CoinGlass + Macro，页面实时刷新
PYTHONPATH=src python -m uvicorn alpha_arena.api.main:app --host 127.0.0.1 --port 8765
# 浏览器 http://127.0.0.1:8765/  · 状态见 /api/live/status

# 可选：仅命令行常驻轮询（无网页）
# PYTHONPATH=src python scripts/run_live_poll.py

# 可选：CSV 回测 + 写 leaderboard
# PYTHONPATH=src python scripts/run_alpha_backtest.py
```

环境变量：**`ENABLE_LIVE_FEED=1`**（默认）开启实时轮询；**`ENABLE_LIVE_FEED=0`** 关闭后台拉取。**`LIVE_POLL_INTERVAL_SEC=45`** 调整间隔。

`uvicorn` 与回测是不同进程，页面从 **`outputs/alpha_arena_leaderboard.json`** 读排行榜（可用环境变量 `ALPHA_ARENA_LEADERBOARD_JSON` 指定路径）。

- **CoinGlass**：`src/alpha_arena/data/coinglass_client.py` 异步拉取（需 `COINGLASS_API_KEY`，Header `CG-API-KEY`）；写入 `outputs/live_context.json`。
- **Macro/News Agent**：`MacroNewsAgent` 读取 FRED `DFF`（需 `FRED_API_KEY`）+ SEC 新闻 RSS，输出全局 **`Market_Regime`**（`risk_on` / `risk_off` / `neutral`），并作为所有交易 Agent 的 `MarketState` 输入；启发式策略会按 regime 缩放仓位。
- **FRED API Key（免费）**：联储官方数据接口，无费用。打开 [申请 API Key](https://fredaccount.stlouisfed.org/apikeys) 注册后复制 Key 到 `.env` 的 `FRED_API_KEY=`。不设 Key 时 Macro Agent 仍会用 **SEC RSS**，只是没有联邦基金利率序列。
- **仅刷新宏观+CoinGlass**（不打回测）：`PYTHONPATH=src python scripts/refresh_live_context.py`
- 示例行情：`data/btc_sample.csv`
- 无效 ticker：扣 `FAILED_TRADE_PENALTY_USD`（默认 50）并记失败单
- 环境变量：`ALLOWED_TICKERS`、`TAKER_FEE_BPS`、`DIVERSITY_PENALTY_STRENGTH`、`MAX_DD_LIQUIDATION_PCT`

## 免责声明

仅供研究与教育用途；不构成投资建议。
