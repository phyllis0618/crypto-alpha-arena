"""
对衍复演示用：数据流 / Agent 流程图层 + 结论向仪表板。

运行：streamlit run frontend/app.py
数据：PYTHONPATH=src .venv/bin/python scripts/run_yanfu_unified_analysis.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[2]
UBASE = ROOT / "outputs" / "yanfu_unified"
LEGACY_R = ROOT / "outputs" / "yanfu_global_research"
LEGACY_O = ROOT / "outputs"

_EXPANSION_GROUPS: list[tuple[str, list[str]]] = [
    ("A 股备案基线", ["CN_CSI1000", "CN_CSI500"]),
    ("港股", ["HK_HSTECH"]),
    ("美股", ["US_SP500", "US_RUT2000"]),
    ("新兴市场", ["IN_NIFTY50", "VN_VNI"]),
    ("Crypto ETF", ["CRYPTO_ETF_IBIT", "CRYPTO_ETF_ETHW"]),
]

_SLEEVE_ZH = {
    "CN_CSI1000": "CSI1000",
    "CN_CSI500": "CSI500",
    "HK_HSTECH": "恒生科技",
    "US_SP500": "标普500",
    "US_RUT2000": "罗素2000",
    "IN_NIFTY50": "印度",
    "VN_VNI": "越南",
    "CRYPTO_ETF_IBIT": "IBIT",
    "CRYPTO_ETF_ETHW": "ETH ETF",
}

_MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js"


def _pick(primary: Path, *fallbacks: Path) -> Path:
    if primary.is_file():
        return primary
    for f in fallbacks:
        if f.is_file():
            return f
    return primary


def _expansion_frame(metrics: dict) -> pd.DataFrame:
    sharpes = metrics.get("sharpes_by_sleeve") or {}
    rows = []
    for quadrant, codes in _EXPANSION_GROUPS:
        for code in codes:
            rows.append(
                {
                    "象限": quadrant,
                    "Sleeve": _SLEEVE_ZH.get(code, code),
                    "仿真Sharpe": sharpes.get(code),
                }
            )
    return pd.DataFrame(rows)


def _render_mermaid(code: str, height: int = 420) -> None:
    """在页面内嵌 Mermaid（中性主题，适合投影）。"""
    safe = code.strip()
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"/></head><body style="margin:0;background:#fafafa;">
<script src="{_MERMAID_CDN}"></script>
<div class="mermaid" style="font-family:system-ui,sans-serif;">
{safe}
</div>
<script>
mermaid.initialize({{ startOnLoad: true, theme: "neutral", securityLevel: "loose", flowchart: {{ useMaxWidth: true }} }});
</script>
</body></html>"""
    components.html(html, height=height, scrolling=False)


# --- assets ---
HARVEST_MANIFEST = UBASE / "harvest" / "harvest_manifest.json"
RESEARCH_DASH = _pick(UBASE / "research" / "yanfu_comparison_dashboard.png", LEGACY_R / "yanfu_comparison_dashboard.png")
ROADMAP_V2_DASH = _pick(
    UBASE / "expansion" / "yanfu_v2_roadmap_analysis.png",
    LEGACY_O / "yanfu_v2_roadmap_analysis.png",
)
UNIFIED_MD = UBASE / "Yanfu_Unified_Report.md"
REALIZED = _pick(UBASE / "research" / "yanfu_realized_from_nav.json", LEGACY_R / "yanfu_realized_from_nav.json")
GAP = _pick(UBASE / "research" / "gap_analysis_report.json", LEGACY_R / "gap_analysis_report.json")
DNA = _pick(UBASE / "research" / "yanfu_strategy_dna.json", LEGACY_R / "yanfu_strategy_dna.json")
EXP_METRICS_JSON = _pick(
    UBASE / "expansion" / "expansion_sim_metrics.json",
    LEGACY_O / "expansion_sim_metrics.json",
)

st.set_page_config(page_title="衍复 · 分析演示", layout="wide")

st.markdown("## 衍复 · 策略结构、跨市场对照与全球路径")
st.caption("面向汇报：数据来源与推理链路见下图；以下为可直接引用的结论与图表。")

# ---- Layer 1: Data flow ----
st.markdown("#### 数据来源（Data flow）")
_render_mermaid(
    """
flowchart TB
    subgraph public["公开数据源"]
        AMAC["基金业协会<br/>列表 API + 公示 HTML"]
        WEB["衍复官网 / 咨询页"]
        SW["第三方页面快照"]
    end
    subgraph opt["可选真数据"]
        NAV["NAV / 换手率 CSV"]
    end
    subgraph out["落地产物"]
        HARV["Harvest JSON / HTML"]
        DNA["策略 DNA + Gap"]
        SIM["多市场仿真指标"]
    end
    AMAC --> HARV
    WEB --> HARV
    SW --> HARV
    HARV --> DNA
    NAV --> DNA
    DNA --> SIM
""",
    height=380,
)

st.caption("真实：协会与官网爬取 · 可选净值；仿真：默认蒙特卡洛（可换 ETF 收益）。")

# ---- Layer 2: Agent / pipeline flow ----
st.markdown("#### 分析链路（AI Agent flow）")
_render_mermaid(
    """
flowchart LR
    A["Agent A · Harvest<br/>采集 / 缓存 / 清洗"] --> B["Agent B · Research<br/>备案 DNA · 区域对照 · Gap"]
    B --> C["Agent C · Global<br/>多 sleeve 仿真 · 路线图"]
    C --> D["输出 · 图表与结论"]

    style A fill:#e8f4fc
    style B fill:#e8f8f0
    style C fill:#f4e8fc
    style D fill:#fff8e6
""",
    height=280,
)
st.caption("三条 Agent 对应仓库中 Harvest → Research → Global expansion；非外部黑箱模型，可追溯至脚本与 JSON。")

st.divider()

# ---- Conclusions first（演示口径）----
st.markdown("#### 对衍复的结论摘要")
conclusion_bullets: list[str] = [
    "**备案主轴**：以协会可追溯数据界定当前产品线结构（指增/中性等 DNA），作为一切跨市场比较的起点。",
    "**跨市场对标轴**：港股科技、美股大小盘、新兴市场（印/越）、合规 Crypto ETF — 与 A 股能力圈形成可讲清楚的四条线。",
    "**全球路径**：仿真用于路线图与容量叙事压测；接入一次性 ETF 日收益后，同一套图层可升级为实盘可比版本。",
]

dna_fund_n = 0
top_label_txt = ""
if DNA.is_file():
    raw = json.loads(DNA.read_text(encoding="utf-8"))
    funds = raw.get("funds") or []
    dna_fund_n = len(funds)
    lab_c: Counter[str] = Counter()
    for f in funds:
        for lab in f.get("strategy_labels") or []:
            lab_c[str(lab)] += 1
    if lab_c:
        top_label_txt = "、".join(f"{k}×{v}" for k, v in lab_c.most_common(3))
        conclusion_bullets.insert(
            1,
            f"**当前解析**：{dna_fund_n} 只备案产品；标签频率居前者：{top_label_txt}。",
        )

em_sh = us_sh = cr_sh = None
if EXP_METRICS_JSON.is_file():
    em = json.loads(EXP_METRICS_JSON.read_text(encoding="utf-8"))
    sh = em.get("sharpes_by_sleeve") or {}
    em_vals = [sh.get(c) for c in ("IN_NIFTY50", "VN_VNI") if sh.get(c) is not None]
    if em_vals:
        em_sh = sum(float(x) for x in em_vals) / len(em_vals)
    us_vals = [float(sh[c]) for c in ("US_SP500", "US_RUT2000") if c in sh]
    if us_vals:
        us_sh = max(us_vals)
    cr_sh = sh.get("CRYPTO_ETF_IBIT")
    s0 = em.get("sortino_core_global_blend")
    s1 = em.get("sortino_with_crypto_booster")
    if s0 is not None and s1 is not None:
        conclusion_bullets.append(
            f"**仿真快照**（路线图用语，非业绩承诺）：全球主组合 Sortino ≈ {float(s0):.2f}；加入 Crypto 卫星后 ≈ {float(s1):.2f}。"
        )
    if em_sh is not None and us_sh is not None:
        who = "新兴市场 sleeve" if em_sh > us_sh else "美股 sleeve"
        conclusion_bullets.append(
            f"**本次蒙特卡洛相对强弱**：{who} 在模型 Sharpe 上更高（EM 均 {em_sh:.2f} vs 美股较高 {us_sh:.2f}），用于内部讨论赛道优先级。"
        )
    elif cr_sh is not None:
        conclusion_bullets.append(
            f"**Crypto ETF 卫星**：模型内 Sharpe 示意 {float(cr_sh):.2f}，与 A 股 alpha 相关性低，适合作为尾部形态与配置故事的讨论入口。"
        )

for b in conclusion_bullets:
    st.markdown(b)

st.divider()

# ---- Evidence slides ----
st.markdown("#### 证据 1 · 策略 DNA 与区域教学原型")
st.caption("灰点/柱：区域原型假设；红星：名称先验；绿点：若已载入 NAV 则为样本内中位数。")
if RESEARCH_DASH.is_file():
    st.image(str(RESEARCH_DASH), use_container_width=True)
else:
    st.warning("请运行统一脚本生成 `yanfu_comparison_dashboard.png`。")

if DNA.is_file() and top_label_txt:
    cols = st.columns(4)
    cols[0].metric("备案基金数", str(dna_fund_n))
    tops = lab_c.most_common(3)
    for i, (name, cnt) in enumerate(tops):
        if i + 1 < len(cols):
            cols[i + 1].metric(str(name), f"{cnt} 只")

st.markdown("#### 证据 2 · 全球路线图 V2（SEA 镜像 + 美股 Special Ops · 约 18 个月）")
st.caption("合成校验图：因子相似度 / IC·IR 与结算摩擦摘要、战略夏普示意、两阶段 pivot 净值（与统一脚本扩张仿真同日数）。")
if ROADMAP_V2_DASH.is_file():
    st.image(str(ROADMAP_V2_DASH), use_container_width=True)
else:
    st.warning("请运行统一脚本生成 `yanfu_v2_roadmap_analysis.png`。")

if EXP_METRICS_JSON.is_file():
    em_data = json.loads(EXP_METRICS_JSON.read_text(encoding="utf-8"))
    st.markdown("#### 跨市场 sleeve 对照（仿真 Sharpe）")
    st.dataframe(
        _expansion_frame(em_data),
        use_container_width=True,
        hide_index=True,
        column_config={"仿真Sharpe": st.column_config.NumberColumn(format="%.2f")},
    )

st.divider()

# ---- Appendix: 技术细节折叠 ----
with st.sidebar:
    st.markdown("**演示者**")
    with st.expander("生成数据命令", expanded=False):
        st.code(
            "cd crypto-alpha-arena\n"
            "PYTHONPATH=src .venv/bin/python scripts/run_yanfu_unified_analysis.py\n"
            "# 净值：  --nav-csv path/to/nav.csv\n"
            "# 强制重爬：  --refresh-crawl",
            language="bash",
        )
    st.caption("页首流程图走 CDN 加载 Mermaid，离线环境可能不显示。")
    st.caption(f"数据目录：`{UBASE.relative_to(ROOT)}`")

with st.expander("附录 · 原始 manifest / Gap / NAV（如需答疑再展开）"):
    if HARVEST_MANIFEST.is_file():
        m = json.loads(HARVEST_MANIFEST.read_text(encoding="utf-8"))
        st.json({"sources": m.get("sources"), "_amac_list_source": m.get("_amac_list_source")}, expanded=True)
    if GAP.is_file():
        st.json(json.loads(GAP.read_text(encoding="utf-8")), expanded=False)
    if REALIZED.is_file():
        rz = json.loads(REALIZED.read_text(encoding="utf-8"))
        if rz.get("has_realized"):
            st.dataframe(pd.DataFrame(rz.get("funds") or []), use_container_width=True, hide_index=True)

with st.expander("附录 · 完整 Markdown 报告"):
    if UNIFIED_MD.is_file():
        st.markdown(UNIFIED_MD.read_text(encoding="utf-8"))
    else:
        st.info("尚无 `Yanfu_Unified_Report.md`。")
