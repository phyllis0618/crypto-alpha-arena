# 衍复：备案数据 → 全球扩张路径（统一分析）

_生成时间（UTC）：2026-03-31T06:44:33.371707+00:00_

## 分析逻辑（为何放在一起）

1. **真实侧**：基金业协会备案列表与公示页、管理人页、官网与第三方快照，刻画「衍复现在在卖什么产品、托管与披露结构」。
2. **Research 侧**：在名称与备案信息上做 **DNA 标签**（指增/中性/基准倾向），与 **区域教学原型** 对照，回答「A 股 DNA 与美德港新市场的结构差」。
3. **Global 路线图侧**：在 **不依赖实时行情** 的前提下，用 **可控蒙特卡洛**（默认 **378** 个交易日，约 **18 个月**）推演多资产、容量与加密卫星；**仅作路线图压力测试**，业绩与夏普需替换为机构级历史数据后方可对外。

## 报告主线（你要突出给观众看的顺序）

1. **衍复现在在卖什么**：Harvest + DNA（指增 / 中性 / 基准倾向）——用**真实备案**把策略主轴钉住。
2. **和哪里比**：不是泛泛「全球」，而是四类 **可交易标的轴** —— **美股宽基+小盘（SPX/RUT 代理）、港股科技（恒生科技代理）、新兴市场（印度/越南，结构上类比「十年前 A 股」）、合规 Crypto ETF 卫星（IBIT/ETH 代理）**。
3. **图 A**：同一套 DNA 放在 **美日印** 教学原型旁边，解释「因子与流动性迁移」；有 NAV 时 **绿色**为真夏普。
4. **图 B**：把上述四类 sleeve **放进同一仿真工作台**（夏普、容量、相关性、含 Crypto 的净值路径），用数字支撑「先做哪条赛道、卫星怎么摆」。
5. **第五节**：把表格里的仿真数字与备案标签 **收成一段话**，便于做 PPT / 一页纸。

---

## 一、一次性真实数据（Harvest）

数据来源索引见 `harvest/harvest_manifest.json`。摘要：
- **amac_pof_fund_api**
  - 文件: `harvest/amac_funds_api_full.json`
  - 记录数: 183
- **amac_fund_html_detail**
  - 记录数: 183
- **yanfu_official_html**
  - 文件数: 4
- **amac_manager_html**
  - 文件数: 1
- **simuwang_company_snapshot**
  - 文件: `harvest/raw/simuwang_company_CO00003EOW.html`

Private fund NAV / time series performance (not in AMAC public API)
Holdings, factor loadings, live book (proprietary)
Simuwang 等站点上的结构化业绩/重仓需登录或其商业 API（此处仅保存首屏 HTML 快照）

### 图 A — Research：区域原型 vs 衍复 DNA（真实备案 + 示意参数）

文件：`research/yanfu_comparison_dashboard.png`（当前备案基金约 **183** 只，去重后以 DNA 为准）。

**读图说明：**

1. **左上散点**：横轴为模型里的**年化换手示意**；纵轴为区域原型的**示意夏普**。**红星** = 根据备案基金中「指增/中性」占比对中国原型做的 **名称先验平移**，不是净值回测。「**绿色菱形/虚线**」仅在你提供 `--nav-csv` 净值后出现，为 **NAV 样本内中位数**（rf=0）。
2. **右上柱状**：各**区域原型**的换手水平对比；红线 = 衍复先验换手示意（若加载了净值则另有绿线表示「真实换手中位数」列）。
3. **左下柱状**：各区域**示意夏普** vs 衍复；绿线同上，表示有净值时的夏普中位数。
4. **右下文字**：各区域**因子叙事**与流动性标签（来自 `reference_benchmarks.json`，非公司披露）。

**从 A 到全球路径**：若备案主体为 **A 股指增 + 小盘暴露**，图 A 支持「**出海必须换冲击模型**」。**美股大盘**对应「深盘口 + 另类 alpha」赛道；**港股**在叙事上承接 **离岸中国 beta**；**印度/越南**在框架里承担 **散户占比高、类比旧 A 股** 的迁移试验田 — 与下图 B 的 sleeve 划分一致。

---

## 二、Research：衍复策略 DNA 与差距摘要（真实备案 + 名称工程）

> **策略主轴（标签出现次数 TOP）**：`index_enhancement` ×109、`unknown` ×39、`market_neutral` ×27 — 下文所有「对标美股/港股/EM/Crypto」都以这一备案结构为起点。

### 备案策略标签（按基金条数计数）

- `index_enhancement`: **109**
- `unknown`: **39**
- `market_neutral`: **27**
- `small_cap_alpha`: **23**
- `multi_strategy`: **3**

### Gap 报告摘句

- index_enhancement: 109
- unknown: 39
- market_neutral: 27
- small_cap_alpha: 23
- multi_strategy: 3

> **流动性/容量**：High-turnover CN index enhancement + small-cap sleeves consume top-of-book depth faster than the same nominal turnover in US large-cap tapes.

### 净值

_未提供 nav CSV — 图中无绿色 NAV-backed 点。_

---

## 三、Global 路线图（蒙特卡洛仿真 · 默认 378 个交易日 ≈ 18 个月 — 非真实行情）

### 图 B — 全球路线图 V2（SEA 镜像 + 美股 Special Ops）

文件：`expansion/yanfu_v2_roadmap_analysis.png`

**读图说明：**

1. **上排左**：**Alpha 相似度热力图**（因子收益相关，CN ↔ SEA 镜像与美/港等 sleeve 对照）。
2. **上排右**：**Stage 1 摘要文本** — 各市场合成 IC/IR、SEA vs US 衰减比、结算与换手摩擦示意。
3. **中排**：**Strategic Sharpness** — 宽基标普 vs 「Special Ops」切入点的示意夏普（Stage 2 叙事）。
4. **下排**：**约 18 个月 pivot 净值** — SEA 侧重阶段、美区加码 ramp、 plateau 区间标注；**合成曲线非承诺**。

### 跨市场对照表（仿真夏普 — 默认随机路径，见免责声明）

| 资产象限 | Sleeve | 仿真 Sharpe（β 中性后示意） |
|----------|--------|----------------------------|
| A 股（备案主体 · CSI 指增 DNA 基线） | CSI1000 (`CN_CSI1000`) | 1.12 |
| A 股（备案主体 · CSI 指增 DNA 基线） | CSI500 (`CN_CSI500`) | 1.09 |
| 港股（恒生科技类敞口 · T+0 · 南向/ADR 联动） | 恒生科技 (`HK_HSTECH`) | 0.24 |
| 美股（大/小盘量化赛道 · SPX / RUT） | 美股大盘 (`US_SP500`) | 0.48 |
| 美股（大/小盘量化赛道 · SPX / RUT） | 美股小盘 (`US_RUT2000`) | 0.61 |
| 新兴市场（散户与冲击结构更接近「十年前 A 股」类比） | 印度 Nifty (`IN_NIFTY50`) | 0.91 |
| 新兴市场（散户与冲击结构更接近「十年前 A 股」类比） | 越南 VNI (`VN_VNI`) | 0.97 |
| 合规 Crypto ETF 卫星（IBIT / ETH 类代理） | BTC ETF (`CRYPTO_ETF_IBIT`) | 0.60 |
| 合规 Crypto ETF 卫星（IBIT / ETH 类代理） | ETH ETF (`CRYPTO_ETF_ETHW`) | 0.58 |

### 仿真原始 JSON（便于复核）

```json
{
  "sharpes_by_sleeve": {
    "CN_CSI1000": 1.1200000000634984,
    "CN_CSI500": 1.0896000000720703,
    "HK_HSTECH": 0.24303756634297363,
    "US_SP500": 0.4824000000478615,
    "US_RUT2000": 0.6113189030256091,
    "IN_NIFTY50": 0.9056000000798673,
    "VN_VNI": 0.9700000000699924,
    "CRYPTO_ETF_IBIT": 0.6020000000173753,
    "CRYPTO_ETF_ETHW": 0.5836000000149424
  },
  "sortino_core_global_blend": 2.5371358607322687,
  "sortino_with_crypto_booster": 2.415464164938767,
  "beta_neutral_meta_sample": {
    "HK_HSTECH": 0.5893590106674261,
    "US_SP500": 1.0,
    "US_RUT2000": 0.18583932803734715
  }
}
```

### 执行摘要（仿真附录）

全文见 `expansion/Executive_Summary.md`（含 18 个月三阶段里程碑 0–6m / 6–12m / 12–18m 与 $5B 叙事框架）。

---

## 四、如何把「真实」再往前推（一次性能做的）

1. **Harvest**：已含协会公示页 HTML + 解析表；可人工抽检字段。
2. **Research**：对管理人/代销拿到的 **净值 CSV** 使用 `--nav-csv`，绿线/绿菱形变为 **样本内真实夏普与换手率（若填列）**。
3. **Expansion**：将 `simulation_engine.generate_paths` 替换为 **下载一次的 ETF/指数日收益 CSV**（如 SPY、QQQ、港股科技ETF、VNM/INDA、IBIT），再在 `CrossMarketBacktester` 中接入 — 当前仓库默认为快速蒙特卡洛。

## 五、结论：衍复策略 → 跨市场数据叙事 → 全球路径

### 1. 衍复「当下」在数据里长什么样（真实备案侧）

- 当前解析到的备案基金约 **183** 只；名称/DNA 标签出现频率前几类：**index_enhancement（109 只）、unknown（39 只）、market_neutral（27 只）**。
- 这对应市场沟通里的 **A 股指增 + 量化中性** 主轴；Research 图 A 把这一先验与美日印等**教学原型**对照。
- 若尚未提供净值 CSV，图 A 仅有红星先验；建议补 `--nav-csv` 以叠真实业绩形态。

### 2. 美股 / 港股 / 新兴市场 / Crypto ETF 在仿真里扮演的角色

- **港股（恒生科技代理）**：在模型里承担 **离岸人民币资产 beta 与 T+0 微观结构**；与 A 股 sleeve 相关但仍可作 **南下书 + 港股通额度** 下的第二张表。
- **美股（SPX / RUT）**：代表 **深盘口、低冲击** 环境；同名 alpha 往往需偏向 **另类数据 / 量化基本面**，与 A 股「反转+小盘」迁移度低 — 与图 A 因子叙事一致。
- **新兴市场（印、越）**：参数上刻意保留 **散户占比高、冲击成本高** — 用作 **「类似十年前 A 股」的类比赛道**；若仿真里 EM sleeve Sharpe 高于美股，叙事上支持 **「容量与因子形态优先落地 EM」** 的路线（仍以替换真实 ETF 收益为准）。
- **Crypto ETF（IBIT/ETH 代理）**：与 A 股 alpha **低相关**，在报告中用于 **卫星仓位 + Sortino 改善** 的压力测试（见仿真 `sortino_with_crypto`）。

**本次仿真快照（内部路线图用语，非对外业绩）**：印/越平均仿真 Sharpe ≈ **0.94**；美股 sleeve 较高仿真 Sharpe ≈ **0.61**；港股恒生科技仿真 Sharpe ≈ **0.24**；BTC ETF 卫星仿真 Sharpe ≈ **0.60**

- **全球主组合 Sortino（仿真）** ≈ 2.54；**加 Crypto 卫星后** ≈ 2.42 —— 用于说明「低相关卫星」在 **尾部风险形状** 上的假设收益，非承诺。

### 3. 可对外部读者复述的「一句话路径」

> **先用备案与 NAV 把「衍复现在在卖什么」钉死** → 用图 A 说明 **A 股 DNA 在美德港环境下的摩擦** → 用图 B 把 **港股科技（离岸）+ 美股赛道（深盘口）+ EM（十年 A 股类比）+ Crypto ETF（合规卫星）** 串成一条 **有数据附录** 的全球叙事；**真 ETF/指数日收益替换蒙特卡洛后**，同一套结构即为「一页纸机构投资者版」报告。

_以上均为研究框架与仿真输出，不构成投资建议或对管理人业绩的预测。_
