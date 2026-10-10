# -*- coding: utf-8 -*-
"""
quant_filter.py — Scan 角色重定义：严筛层纯函数（零 token、无副作用、可单测）。

判决背景（2026-10-08）：scan 从「全市场推荐」改为「持仓 + 严筛候选」，
AI 只分析 ≤7 只（持仓 ~4 + 严筛候选 ≤3）。token 主节省点 = 收缩 AI 输入，
硬筛层（评分/R-R/止损距离/板块集中度）全程纯程序、零 token。

约束：
- 只含纯函数：不触网、不写文件（load_positions 例外，只读传入路径）。
- 无模块级 sys.exit、无时间门控、无环境变量校验。
- 可在任意 Python 3.12 环境直接 import（不 import scan，避免其模块级副作用）。
"""

import csv
import math
import os

# ============================================================
# 严筛阈值常量（与 OPTIONS_WHEEL_DESIGN / 期权引擎 MIN_REWARD_RISK=2.0 一致）
# ============================================================
MIN_SCORE = 90            # 评分下限
MIN_RR = 2.0              # R/R 下限
MIN_STOP_DIST = 0.02      # 止损距离下限 2%
MAX_STOP_DIST = 0.05      # 止损距离上限 5%
MAX_CANDIDATES = 3        # 每日候选上限（≤3 只）
DEFAULT_STOP_PCT = 0.05   # 缺 Stop_Loss 时按 5% 推导（落在 [2%, 5%] 上沿，保守）
AI_INPUT_MAX = 7          # AI 输入硬顶（持仓 + 候选 ≤7 只）

# generate_ai_report 拼 prompt 时对这些字段做「硬索引」（x['字段']，缺失即 KeyError）。
# 持仓项若不在 pool_data 中（持仓未进入扫描候选池时必然如此），build_ai_input 会退化为
# 空 dict 行，必须兜底补全这些必填字段，否则 scan 首次真实运行会在 2590 行 x['Name'] 崩溃。
# 默认值统一用 "N/A"，与 prompt 中 x.get(..., 'N/A') 的可选字段约定保持一致。
AI_INPUT_REQUIRED_FIELDS = {
    "Name": "N/A",
    "Price": "N/A",
    "RSI": "N/A",
    "乖离率(%)": "N/A",
    "MACD趋势": "N/A",
    "KDJ_J": "N/A",
    "量比": "N/A",
}


# ============================================================
# 纯函数
# ============================================================

def _to_float(v):
    """把任意值安全转为 float，失败返回 None。"""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _last_n_max(values, n):
    """取序列最近 n 个有效数值的最大值；无有效值返回 None。

    values: 类序列（pandas Series / list / tuple）。
    自动丢弃 None 与 NaN（fail-closed：数据不足不凑数）。
    """
    if values is None:
        return None
    try:
        arr = [float(x) for x in values
               if x is not None and not (isinstance(x, float) and math.isnan(x))]
    except (TypeError, ValueError):
        return None
    if not arr:
        return None
    return float(max(arr[-n:]))


def compute_20d_high(df):
    """前 20 日高点 = 日线 High 列最近 20 个有效值的最大值。

    df: 含 ``High`` 列的日线 DataFrame（来自 `_filter_completed_daily_bars` / `get_kline_data`）。
    数据不足 20 根时返回已有区间的最大值（数据不足仍给值，但由调用方结合 fail-closed 判定）；
    High 列缺失 / 全 NaN / 空 → 返回 None。
    """
    if df is None:
        return None
    try:
        high = df["High"]
    except (KeyError, TypeError):
        return None
    if high is None:
        return None
    try:
        if len(high) == 0:
            return None
    except TypeError:
        pass
    return _last_n_max(high, 20)


def compute_rr_ratio(price, stop_loss, target):
    """收益风险比 R/R = (目标价 - 现价) / (现价 - 止损价)。

    参数顺序：(price, stop_loss, target)。
    现价 ≤ 止损价（无下行风险）→ 返回 None（fail-closed）。
    目标 ≤ 现价 → 返回非正比值（严筛按 R/R ≥ 2.0 自然拒绝）。
    """
    p = _to_float(price)
    s = _to_float(stop_loss)
    t = _to_float(target)
    if p is None or s is None or t is None:
        return None
    risk = p - s
    if risk <= 0:
        return None
    return (t - p) / risk


def _stop_distance(price, stop_price):
    """止损距离 = (现价 - 止损价) / 现价，区间 [2%, 5%]。"""
    p = _to_float(price)
    s = _to_float(stop_price)
    if p is None or s is None or p <= 0:
        return None
    return (p - s) / p


def _score_of(item):
    """评分取值：优先 Final_Score → Quant_Score → Score，缺省 0.0。"""
    for k in ("Final_Score", "Quant_Score", "Score"):
        v = _to_float(item.get(k))
        if v is not None:
            return v
    return 0.0


def _price_of(item):
    return _to_float(item.get("Price"))


def _stop_of(item):
    """止损价取值：Stop_Loss / stop_price，容忍 "$" 与千分位逗号，缺失返回 None。"""
    s = item.get("Stop_Loss") or item.get("stop_price")
    if s in (None, "", "N/A", "观望"):
        return None
    return _to_float(str(s).replace("$", "").replace(",", ""))


def strict_filter(rows):
    """严筛层（零 token）：评分≥90 & R/R≥2.0 & 2%≤止损距离≤5% & ≤1只/板块 → ≤3 只。

    rows: 已过 entry 质量闸口的候选池（每只需预置 ``target_price``（前20日高点）；
          缺则回退用 ``highs`` 字段补算；两者皆无则跳过，fail-closed）。
    返回严筛后候选列表（按评分降序，最多 MAX_CANDIDATES 只），
    每项附加 ``_rr`` / ``_stop_dist`` 诊断字段（不改变原有字段）。
    """
    used_sectors = set()
    out = []
    for it in (rows or []):
        ticker = str(it.get("Ticker", "")).upper()
        score = _score_of(it)
        if score < MIN_SCORE:
            continue
        price = _price_of(it)
        if price is None or price <= 0:
            continue
        stop_price = _stop_of(it)
        if stop_price is None:
            stop_price = price * (1 - DEFAULT_STOP_PCT)
        target = it.get("target_price")
        if target is None and "highs" in it:
            target = _last_n_max(it.get("highs"), 20)
        if target is None:
            continue
        rr = compute_rr_ratio(price, stop_price, target)
        if rr is None or rr < MIN_RR:
            continue
        sd = _stop_distance(price, stop_price)
        if sd is None or sd < MIN_STOP_DIST or sd > MAX_STOP_DIST:
            continue
        sector = (it.get("Sector") or "").strip()
        if sector and sector in used_sectors:
            continue  # 板块集中度 ≤1 只/板块
        if sector:
            used_sectors.add(sector)
        out.append(dict(it, _rr=round(rr, 3), _stop_dist=round(sd, 4)))
    out.sort(key=_score_of, reverse=True)
    return out[:MAX_CANDIDATES]


def load_positions(path):
    """读 ``portfolio_50000_positions.csv``，返回持仓 Ticker 列表（大写、去重）。

    防御容错：文件缺失 / 解析失败 / 空行 → 返回 []，不抛异常、不阻断 scan 主流程。
    仅保留 Status 为 OPEN/ACTIVE（含空值视为 OPEN）的持仓行。
    """
    if not path or not os.path.exists(path):
        return []
    tickers = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                t = (r.get("Ticker") or "").strip().upper()
                if not t:
                    continue
                status = (r.get("Status") or "").strip().upper()
                if status and status not in ("OPEN", "ACTIVE"):
                    continue
                if t not in tickers:
                    tickers.append(t)
        return tickers
    except Exception:
        return []


def build_ai_input(pool_data, positions, candidates):
    """收缩 AI 输入：持仓（强制, 从 pool_data 补全字段）+ 严筛候选（≤3）→ ≤7 只。

    pool_data: 全量（已过闸口）候选池，用于给持仓补全行情/技术/AI 分析字段（每日重评分）。
    positions: 持仓 Ticker 列表（load_positions 产出）。
    candidates: 严筛候选（strict_filter 产出）。
    按 Ticker 去重（持仓优先）；持仓项标记 Tag="Core_Dragon" + _is_position=True，
    候选项标记 Tag="Candidate"。
    """
    pool_by = {}
    for x in (pool_data or []):
        t = str(x.get("Ticker", "")).upper()
        if t:
            pool_by[t] = x

    seen = set()
    out = []
    for t in (positions or []):
        t = str(t).upper()
        if not t or t in seen:
            continue
        seen.add(t)
        # 持仓未必在 pool_data 中（持仓未进入扫描候选池时必然如此）：
        # pool_by.get(t) 命中则复制完整行，未命中则用空 dict —— 必须兜底补全
        # generate_ai_report 硬索引的必填字段，否则 2590 行 x['Name'] 等会 KeyError。
        row = dict(pool_by.get(t) or {})
        row["Ticker"] = t
        row["Tag"] = "Core_Dragon"
        row["_is_position"] = True
        for k, v in AI_INPUT_REQUIRED_FIELDS.items():
            row.setdefault(k, v)
        out.append(row)

    for c in (candidates or []):
        t = str(c.get("Ticker", "")).upper()
        if not t or t in seen:
            continue
        seen.add(t)
        row = dict(c, Tag="Candidate")
        # 候选同样兜底补全，防止 strict_filter 输出缺字段时 prompt 崩溃
        for k, v in AI_INPUT_REQUIRED_FIELDS.items():
            row.setdefault(k, v)
        out.append(row)

    # #4 浮动只数（§0.9）：持仓恒优先保留，候选上限 = min(3, AI_INPUT_MAX - 持仓数)。
    # 显式拆分避免 out[:AI_INPUT_MAX] 在候选过多时截断持仓（持仓优先于候选）。
    positions = [x for x in out if x.get("_is_position")]
    candidates = [x for x in out if not x.get("_is_position")]
    cand_cap = min(3, AI_INPUT_MAX - len(positions))
    return positions + candidates[:max(0, cand_cap)]
