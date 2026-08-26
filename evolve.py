# -*- coding: utf-8 -*-
"""
美股策略进化引擎 evolve_us.py

真正的进化闭环（与 A股版完全对等）：
  trade_history.csv → 多维度绩效分析 → AI识别规律
  option_strategies.csv → 期权绩效分析 → 补充策略评估
  → evolved_rules.json → scan.py 注入 prompt → 更好的选股
"""

import pandas as pd
import os
import json
import anthropic
import datetime

EVOLVE_MODEL   = "claude-opus-4-8"
HISTORY_FILE   = "trade_history.csv"
OPTION_FILE    = "option_strategies.csv"   # 【新增】期权账本
EVOLVE_LOG     = "strategy_evolution.json"
EVOLVED_RULES  = "evolved_rules.json"

MIN_CLOSED = 8   # 最小已平仓样本数

CLOSED_STATUSES = {"Dropped", "Stop_Loss_Hit", "Period_Matured", "Forced_Exit"}
ACTIVE_STATUSES = {"Active"}
PRICE_COL  = "Price"
EXIT_COL   = "Exit_Price"
SCORE_COL  = "Score"


# ============================================================
# 1. 多维度绩效指标计算（含期权）
# ============================================================
def safe_float(val, default=None):
    try:
        v = float(str(val).strip().replace(",", "").replace("$", ""))
        return v if v > 0 else default
    except Exception:
        return default


def _load_scan_version_boundaries():
    """读取 scan.py 版本标记文件，把代码逻辑变更日也视为世代分界"""
    version_file = "scan_version.txt"
    if not os.path.exists(version_file):
        return []
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content and "," in content:
            date_str = content.split(",")[1]
            if date_str and len(date_str) == 10:
                return [date_str]
    except Exception:
        pass
    return []


def _load_evolution_boundaries():
    """从 strategy_evolution.json 读取历次进化发生的时间点，作为"世代"分界线。"""
    boundaries = []
    if os.path.exists(EVOLVE_LOG):
        try:
            with open(EVOLVE_LOG, "r", encoding="utf-8") as f:
                history = json.load(f)
            dates = [entry.get("date", "")[:10] for entry in history if entry.get("date")]
            boundaries.extend(dates)
        except Exception:
            pass
    boundaries.extend(_load_scan_version_boundaries())
    return sorted(set(d for d in boundaries if d))


def _segment_by_generation(df_c, boundaries):
    """按进化世代拆分胜率"""
    if not boundaries or "date" not in df_c.columns:
        return {}, None
    df_c = df_c.copy()
    df_c["_dt"] = pd.to_datetime(df_c["date"], errors="coerce")
    bounds_dt = [pd.to_datetime(b) for b in boundaries]
    edges = [pd.Timestamp.min] + bounds_dt + [pd.Timestamp.max]
    segments = {}
    for i in range(len(edges) - 1):
        label = "第0代-进化前(原始策略)" if i == 0 else f"第{i}代-进化后"
        seg = df_c[(df_c["_dt"] >= edges[i]) & (df_c["_dt"] < edges[i + 1])]
        if len(seg) >= 2:
            segments[label] = {
                "样本数":    int(len(seg)),
                "胜率":      round(float((seg["pnl_pct"] > 0).sum() / len(seg) * 100), 1),
                "平均盈亏%": round(float(seg["pnl_pct"].mean()), 2),
            }
    since_last = None
    if len(edges) > 2:
        seg = df_c[df_c["_dt"] >= edges[-2]]
        if len(seg) >= 2:
            since_last = {
                "样本数":    int(len(seg)),
                "胜率":      round(float((seg["pnl_pct"] > 0).sum() / len(seg) * 100), 1),
                "平均盈亏%": round(float(seg["pnl_pct"].mean()), 2),
            }
        elif len(seg) > 0:
            since_last = {"样本数": int(len(seg)), "提示": "样本数不足2笔，暂不单独计算胜率"}
    return segments, since_last


def load_option_metrics():
    """
    【新增】读取期权账本，计算期权策略绩效指标。
    用于补充策略进化引擎的评估维度。
    """
    if not os.path.exists(OPTION_FILE):
        return None
    try:
        df_opt = pd.read_csv(OPTION_FILE, keep_default_na=False)
        # 筛选已平仓的期权（Status == 'Closed'）
        closed = df_opt[df_opt.get('Status', '') == 'Closed'].copy()
        if closed.empty:
            return None

        # 确保 PnL 列存在且为数值
        if 'PnL' not in closed.columns:
            return None

        # 转换盈亏为数值
        closed['PnL_num'] = pd.to_numeric(closed['PnL'], errors='coerce')
        closed = closed.dropna(subset=['PnL_num'])
        if closed.empty:
            return None

        total = len(closed)
        wins = (closed['PnL_num'] > 0).sum()
        win_rate = round(wins / total * 100, 1)
        avg_pnl = round(closed['PnL_num'].mean(), 2)
        total_pnl = round(closed['PnL_num'].sum(), 2)
        best = closed.loc[closed['PnL_num'].idxmax()] if total > 0 else None
        worst = closed.loc[closed['PnL_num'].idxmin()] if total > 0 else None

        # 按期权类型拆分（CALL vs PUT）
        type_stats = {}
        for opt_type, grp in closed.groupby('OptionType'):
            if len(grp) >= 2:
                type_stats[opt_type] = {
                    "样本数": len(grp),
                    "胜率": round((grp['PnL_num'] > 0).sum() / len(grp) * 100, 1),
                    "平均盈亏": round(grp['PnL_num'].mean(), 2),
                }

        return {
            "total_closed": total,
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "total_pnl": total_pnl,
            "best_trade": f"{best['Ticker']} {best.get('OptionType','')} {best.get('Strike','')} +{best['PnL_num']:.2f}" if best is not None else "无",
            "worst_trade": f"{worst['Ticker']} {worst.get('OptionType','')} {worst.get('Strike','')} {worst['PnL_num']:.2f}" if worst is not None else "无",
            "type_stats": type_stats,
        }
    except Exception as e:
        print(f"⚠️ 读取期权账本失败: {e}")
        return None


def calculate_metrics(df: pd.DataFrame) -> dict | None:
    if df.empty:
        return None

    status_col = "Status" if "Status" in df.columns else "Tag"
    closed = df[df[status_col].isin(CLOSED_STATUSES)].copy()
    active = df[df[status_col].isin(ACTIVE_STATUSES)].copy()

    if len(closed) < MIN_CLOSED:
        print(f"⚠️ 已平仓记录仅 {len(closed)} 条，不足 {MIN_CLOSED} 条，暂缓进化。")
        return None

    rows = []
    skipped_no_price = []
    for _, row in closed.iterrows():
        buy  = safe_float(row.get(PRICE_COL))
        sell = safe_float(row.get(EXIT_COL))
        if buy is None or sell is None:
            skipped_no_price.append(f"{row.get('Name','')}({row.get('Ticker','')})[{row.get(status_col,'')}]")
            continue
        pnl_pct = round((sell - buy) / buy * 100, 2)

        rows.append({
            "ticker":        str(row.get("Ticker", "")),
            "name":          str(row.get("Name", "")),
            "status":        str(row.get(status_col, "")),
            "score":         safe_float(row.get(SCORE_COL), default=50),
            "pnl_pct":       pnl_pct,
            "buy":           buy,
            "sell":          sell,
            "macd_cross":    str(row.get("MACD金叉", "")),
            "weekly_sync":   str(row.get("周线共振", "")),
            "kdj_rising":    str(row.get("KDJ_J回升", "")),
            "vol_surge":     str(row.get("量能放大", "")),
            "tech_score":    safe_float(row.get("技术评分"), default=0),
            "date":          str(row.get("Date", "")),
            "atr_pct":       safe_float(row.get("ATR_Pct"), default=None),
            "period_resonance": str(row.get("周期共振", "")),
        })

    if not rows:
        print("⚠️ 平仓记录无有效买入/卖出价。")
        return None

    if skipped_no_price:
        print(f"⚠️ {len(skipped_no_price)} 条已平仓记录缺 Price/Exit_Price，被排除在胜率统计外: {skipped_no_price[:15]}")

    df_c = pd.DataFrame(rows)
    wins     = (df_c["pnl_pct"] > 0).sum()
    total    = len(df_c)
    wr       = round(float(wins / total * 100), 1)
    avg_pnl  = round(float(df_c["pnl_pct"].mean()), 2)
    best     = df_c.loc[df_c["pnl_pct"].idxmax()]
    worst    = df_c.loc[df_c["pnl_pct"].idxmin()]

    def _stats(grp):
        return {
            "样本数":    int(len(grp)),
            "胜率":      round(float((grp["pnl_pct"] > 0).sum() / len(grp) * 100), 1),
            "平均盈亏%": round(float(grp["pnl_pct"].mean()), 2),
        }

    # 按评分区间拆分
    def score_bucket(s):
        if s is None:    return "未知"
        if s >= 80:      return "80-100(高信心)"
        elif s >= 65:    return "65-79(中信心)"
        elif s >= 50:    return "50-64(低信心)"
        else:            return "<50(勉强入选)"

    df_c["score_bucket"] = df_c["score"].apply(score_bucket)
    score_stats = {bk: _stats(g) for bk, g in df_c.groupby("score_bucket") if len(g) >= 2}

    # 按技术评分区间拆分
    def tech_bucket(s):
        if s is None: return "无技术评分"
        if s >= 30:   return "30-40(强技术)"
        elif s >= 20: return "20-29(中技术)"
        elif s >= 10: return "10-19(弱技术)"
        else:         return "0-9(无信号)"

    df_c["tech_bucket"] = df_c["tech_score"].apply(tech_bucket)
    tech_score_stats = {bk: _stats(g) for bk, g in df_c.groupby("tech_bucket") if len(g) >= 2}

    # 按ATR波动率分层
    def atr_bucket(a):
        if a is None:  return "无ATR数据(旧记录)"
        if a < 2.5:    return "低波动(ATR<2.5%)"
        elif a < 4.5:  return "中波动(ATR 2.5%-4.5%)"
        else:          return "高波动(ATR>4.5%)"

    df_c["atr_bucket"] = df_c["atr_pct"].apply(atr_bucket)
    atr_stats = {bk: _stats(g) for bk, g in df_c.groupby("atr_bucket") if len(g) >= 2 and bk != "无ATR数据(旧记录)"}

    # 按技术信号拆分
    signal_stats = {}
    for sig_col, label in [("macd_cross", "MACD金叉"), ("weekly_sync", "周线共振"),
                            ("kdj_rising", "KDJ回升"), ("vol_surge", "量能放大"),
                            ("period_resonance", "周期共振")]:
        if sig_col not in df_c.columns:
            continue
        for val, grp in df_c.groupby(sig_col):
            if len(grp) < 2:
                continue
            key = f"{label}={'是' if str(val).lower() in ('true','1','yes') else '否'}"
            signal_stats[key] = _stats(grp)

    # 按退出方式拆分
    exit_map = {"Stop_Loss_Hit": "止损触发", "Period_Matured": "持有到期",
                "Forced_Exit": "突发强清", "Dropped": "主动斩仓"}
    exit_stats = {
        exit_map.get(tag, tag): _stats(g)
        for tag, g in df_c.groupby("status")
        if len(g) >= 1
    }

    # 上一轮规则
    prev_rules = []
    if os.path.exists(EVOLVE_LOG):
        try:
            with open(EVOLVE_LOG, "r", encoding="utf-8") as f:
                history = json.load(f)
                if history:
                    prev_rules = history[-1].get("applied_rules", [])
        except Exception:
            pass

    # 当前持仓
    active_summary = [
        f"{r.get('Name','')}({r.get('Ticker','')}) 评分{r.get(SCORE_COL,'-')}"
        for _, r in active.iterrows()
    ]

    generation_boundaries = _load_evolution_boundaries()
    generation_stats, since_last_evolution = _segment_by_generation(df_c, generation_boundaries)

    # ========== 【新增】加载期权指标 ==========
    option_metrics = load_option_metrics()
    if option_metrics:
        print(f"📊 期权策略绩效：已平仓 {option_metrics['total_closed']} 笔，胜率 {option_metrics['win_rate']}%，总盈亏 ${option_metrics['total_pnl']:.2f}")

    return {
        "total_closed":       total,
        "overall_win_rate":   wr,
        "avg_pnl_pct":        avg_pnl,
        "best_trade":         f"{best['name']}({best['ticker']}) +{best['pnl_pct']}%",
        "worst_trade":        f"{worst['name']}({worst['ticker']}) {worst['pnl_pct']}%",
        "score_stats":        score_stats,
        "tech_score_stats":   tech_score_stats,
        "atr_stats":          atr_stats,
        "signal_stats":       signal_stats,
        "exit_stats":         exit_stats,
        "generation_stats":   generation_stats,
        "since_last_evolution": since_last_evolution,
        "active_count":       len(active),
        "active_summary":     active_summary[:10],
        "prev_rules":         prev_rules,
        "option_metrics":     option_metrics,   # 【新增】
    }


# ============================================================
# 2. AI 分析 + 生成规则补丁（已包含期权数据）
# ============================================================
def evolve_strategy(metrics: dict):
    print(f"🧬 启动策略进化引擎（{EVOLVE_MODEL}）...")
    client = anthropic.Anthropic(
        api_key=os.environ.get("CLAWSOCKET_API_KEY"),
        base_url=os.environ.get("CLAWSOCKET_BASE_URL"),
    )

    # 【新增】期权绩效文本
    option_text = "无期权数据（尚未平仓或 option_strategies.csv 不存在）"
    if metrics.get("option_metrics"):
        opt = metrics["option_metrics"]
        option_text = f"""
【期权策略绩效】（独立于股票持仓，用于评估期权附加策略的有效性）：
- 已平仓期权：{opt['total_closed']} 笔
- 期权胜率：{opt['win_rate']}%
- 平均盈亏：${opt['avg_pnl']}
- 总盈亏：${opt['total_pnl']}
- 最佳：{opt['best_trade']}
- 最差：{opt['worst_trade']}
- 按类型拆分（CALL/PUT）：{json.dumps(opt.get('type_stats', {}), ensure_ascii=False, indent=2)}
"""

    prompt = f"""
你是一个美股量化策略进化系统。根据以下交易绩效数据，生成具体可执行的选股规则补丁。

【当前绩效报告】：
- 已平仓股票：{metrics['total_closed']} 笔 | 总体胜率（全部历史混合，仅供参考）：{metrics['overall_win_rate']}% | 平均盈亏：{metrics['avg_pnl_pct']}%
- 最佳：{metrics['best_trade']} | 最差：{metrics['worst_trade']}
- 当前持仓：{metrics['active_count']} 只

{option_text}

【按进化世代拆分股票胜率】（重点看这个，而不是上面混合了所有历史的总胜率——
能看出每一轮规则调整之后胜率到底是变好还是变差了）：
{json.dumps(metrics['generation_stats'], ensure_ascii=False, indent=2) if metrics['generation_stats'] else "尚无进化历史，这是第一轮"}

【最近一次进化之后的战绩】（当前生效规则的真实表现，样本量可能还小）：
{json.dumps(metrics['since_last_evolution'], ensure_ascii=False, indent=2) if metrics['since_last_evolution'] else "尚无数据或样本不足"}

【AI综合评分（0-100）胜率分布】（判断高分是否真的对应高胜率）：
{json.dumps(metrics['score_stats'], ensure_ascii=False, indent=2)}

【技术评分（0-40分）胜率分布】（判断技术面40分权重是否设置合理）：
{json.dumps(metrics['tech_score_stats'], ensure_ascii=False, indent=2)}

【按ATR波动率分层胜率】（验证止损从固定-5%改成ATR动态算这个改动有没有用——如果
高波动分层的胜率明显提升，说明方向正确；同时结合期权胜率看，高波动股票对应的期权
是否也表现更好，还是期权被波动率吞噬了）：
{json.dumps(metrics['atr_stats'], ensure_ascii=False, indent=2) if metrics['atr_stats'] else "样本不足或还没有ATR数据的已平仓记录"}

【技术信号有效性分析】（判断MACD金叉/周线共振等信号是否真的有效）：
{json.dumps(metrics['signal_stats'], ensure_ascii=False, indent=2)}

【退出方式分布】（判断止损位/持股周期是否合理）：
{json.dumps(metrics['exit_stats'], ensure_ascii=False, indent=2)}

【上一轮已应用规则】：
{json.dumps(metrics['prev_rules'], ensure_ascii=False, indent=2) if metrics['prev_rules'] else "无（首次进化）"}

【分析思路】：
0. 优先看"按进化世代拆分胜率"：如果最近一代相比上一代胜率下降了，说明上一轮规则
   可能是错的或用力过猛，这一轮应考虑撤销或调整方向。
1. 如果高技术评分（30-40分）的胜率 < 低技术评分（0-9分），说明技术面权重过高（40分），需要降低
2. 如果MACD金叉=是的胜率远高于=否，说明金叉信号有效，应该提高MACD金叉的推荐权重
3. 如果止损触发次数多且亏损较大，说明止损位设得太紧，建议适当放宽
4. 【新增】结合期权绩效分析：
   - 如果期权总盈亏为负但股票胜率尚可，说明期权策略（行权价/到期日选择）存在缺陷，应调整期权生成逻辑
   - 如果高波动股票的期权胜率明显低于低波动股票，应建议 scan.py 对高波动股票使用更保守的期权参数
   - 如果 CALL 和 PUT 的胜率差异显著，应建议扫描器优先选择胜率更高的方向

必须只返回以下 JSON，不要输出其他文字：
{{
    "assessment": "总体策略表现评估（3句话以内，要有数据，如涉及期权需一并评价）",
    "key_findings": [
        "发现1（数据支撑）",
        "发现2",
        "发现3"
    ],
    "identified_flaws": "最关键的逻辑缺陷（指出根因）",
    "applied_rules": [
        {{
            "rule_id": "rule_{datetime.date.today().strftime('%Y%m%d')}_001",
            "type": "TECH_WEIGHT_ADJUST 或 SIGNAL_BOOST 或 STOPLOSS_ADJUST 或 HOLD_PERIOD_ADJUST 或 OPTION_ADJUST 或 CONDITION_ADD 或 CONDITION_REMOVE",
            "description": "规则说明",
            "prompt_patch": "注入 scan.py AI prompt 的具体文字（可执行，如：'历史数据显示MACD金叉标的胜率达71%，当出现MACD金叉信号时，消息面评分可适当上浮5-8分'）",
            "evidence": "支撑数据",
            "expires_after_trades": 20
        }}
    ],
    "next_focus": "下一轮进化应重点观察什么（如涉及期权也需说明）"
}}
"""

    try:
        response = client.messages.create(
            model=EVOLVE_MODEL,
            max_tokens=2000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        text_block = next((b for b in response.content if hasattr(b, "text")), None)
        if text_block is None:
            print("❌ AI 未返回文本内容（只有 ThinkingBlock）")
            return
        text = text_block.text.strip()
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start == -1 or end == 0:
            print("❌ AI 未返回有效 JSON")
            return

        result = json.loads(text[start:end])
        result["date"]    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        result["metrics"] = {k: v for k, v in metrics.items()
                             if k not in ("prev_rules", "active_summary")}

        log_data = []
        if os.path.exists(EVOLVE_LOG):
            try:
                with open(EVOLVE_LOG, "r", encoding="utf-8") as f:
                    log_data = json.load(f)
            except Exception:
                pass
        log_data.append(result)
        with open(EVOLVE_LOG, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        print(f"📚 进化日志已追加（历史共 {len(log_data)} 轮）")

        all_rules = []
        total_now = metrics["total_closed"]
        for entry in log_data:
            for rule in entry.get("applied_rules", []):
                created_at = entry.get("metrics", {}).get("total_closed", 0)
                expires    = rule.get("expires_after_trades", 20)
                if total_now - created_at < expires:
                    all_rules.append(rule)

        seen = {}
        for r in reversed(all_rules):
            seen.setdefault(r["rule_id"], r)
        deduped = list(reversed(seen.values()))

        evolved_output = {
            "last_updated":            result["date"],
            "total_closed_at_update":  total_now,
            "overall_win_rate":        metrics["overall_win_rate"],
            "recent_win_rate":         metrics.get("since_last_evolution"),
            "option_win_rate":         metrics.get("option_metrics", {}).get("win_rate") if metrics.get("option_metrics") else None,
            "active_rules":            deduped,
            "prompt_patches":          [r["prompt_patch"] for r in deduped],
        }
        with open(EVOLVED_RULES, "w", encoding="utf-8") as f:
            json.dump(evolved_output, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 进化完成！共 {len(deduped)} 条有效规则 → {EVOLVED_RULES}")
        for i, rule in enumerate(deduped, 1):
            print(f"  规则{i} [{rule['type']}] {rule['description']}")
            print(f"    证据: {rule.get('evidence','')}")
        print(f"\n📋 评估: {result.get('assessment','')}")
        print(f"🎯 下轮重点: {result.get('next_focus','')}")

    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
    except Exception as e:
        print(f"❌ 进化引擎出错: {e}")


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    if not os.path.exists(HISTORY_FILE):
        print(f"未检测到 {HISTORY_FILE}，进化中止。")
        exit()

    df_raw = pd.read_csv(HISTORY_FILE, keep_default_na=False)

    _INVALID = {"", "n/a", "nan", "none"}
    for col in ["Hold_Period", "Stop_Loss", SCORE_COL]:
        if col not in df_raw.columns:
            df_raw[col] = ""
    valid_mask = (
        df_raw["Hold_Period"].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID) &
        df_raw["Stop_Loss"].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID)
    )
    no_score_count = df_raw[SCORE_COL].astype(str).str.strip().str.lower().isin(_INVALID).sum()
    if no_score_count > 0:
        print(f"⚠️ {no_score_count} 条记录 Score=N/A（可能是历史评分bug所致），仍纳入胜率统计。")
    dropped = (~valid_mask).sum()
    if dropped > 0:
        print(f"🗂️ 过滤 {dropped} 条不完整记录。")
    df = df_raw[valid_mask].copy()

    if df.empty:
        print("⚠️ 过滤后无有效记录，进化中止。")
        exit()

    metrics = calculate_metrics(df)
    if metrics is None:
        exit()

    print(f"\n📊 绩效概览：")
    print(f"  已平仓股票 {metrics['total_closed']} 笔 | 总体胜率(全部历史) {metrics['overall_win_rate']}% | 平均盈亏 {metrics['avg_pnl_pct']}%")
    print(f"  当前持仓 {metrics['active_count']} 只")
    if metrics.get("option_metrics"):
        opt = metrics["option_metrics"]
        print(f"  期权已平仓 {opt['total_closed']} 笔 | 期权胜率 {opt['win_rate']}% | 总盈亏 ${opt['total_pnl']:.2f}")
    if metrics["generation_stats"]:
        print(f"  按进化世代拆分：{metrics['generation_stats']}")
    if metrics["since_last_evolution"]:
        print(f"  最近一次进化之后：{metrics['since_last_evolution']}")
    if metrics["tech_score_stats"]:
        print(f"  技术评分分层胜率: {metrics['tech_score_stats']}")
    if metrics["signal_stats"]:
        print(f"  信号有效性: {metrics['signal_stats']}")

    evolve_strategy(metrics)
