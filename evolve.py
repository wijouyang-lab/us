# -*- coding: utf-8 -*-
"""
美股策略进化引擎 evolve_us.py

真正的进化闭环（与 A股版完全对等）：
  trade_history.csv → 多维度绩效分析 → AI识别规律
  → evolved_rules.json → scan.py 注入 prompt → 更好的选股
"""

import pandas as pd
import os
import json
from clawsocket_compat import ClawSocketClient
import datetime
import math

EVOLVE_MODEL   = os.environ.get("GPT_MODEL") or "gpt-6-astra"
CLAUDE_AUDIT_MODEL = os.environ.get("CLAUDE_AUDIT_MODEL") or "claude-opus-5"
HISTORY_FILE   = "trade_history.csv"
EVOLVE_LOG     = "strategy_evolution.json"
EVOLVED_RULES  = "evolved_rules.json"

MIN_CLOSED = 8   # 最小已平仓样本数

CLOSED_STATUSES = {"Dropped", "Stop_Loss_Hit", "Period_Matured", "Forced_Exit"}
ACTIVE_STATUSES = {"Active"}
PRICE_COL  = "Price"
EXIT_COL   = "Exit_Price"
SCORE_COL  = "Score"


# ============================================================
# 1. 多维度绩效指标计算（股票）
# ============================================================
def safe_float(val, default=None):
    try:
        if val is None: return default
        s=str(val).strip().replace(",","").replace("$","")
        if s.lower() in {"","nan","none","null","n/a","na"}: return default
        x=float(s)
        return x if math.isfinite(x) else default
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



def evaluate_score_thresholds_oos(df_c):
    """时间顺序 60/40 切分，用推荐事件的历史 Score 做简单门槛验证；不足样本时不自动改参数。"""
    work=df_c.copy()
    work["score_num"]=pd.to_numeric(work["score"],errors="coerce")
    work=work.dropna(subset=["score_num","pnl_pct"]).sort_values("date")
    if len(work)<30:
        return {"eligible":False,"reason":"样本不足30笔"}
    cut=max(1,int(len(work)*0.6)); val=work.iloc[cut:].copy(); base=float(STRATEGY_PARAMS["scoring"].get("core_min_score",65))
    def ev(g): return float(g["pnl_pct"].mean()) if len(g) else None
    base_g=val[val["score_num"]>=base]
    base_ev=ev(base_g)
    results=[]
    for t in (55,60,62,65,68,70,72,75):
        g=val[val["score_num"]>=t]
        results.append({"threshold":t,"n":int(len(g)),"win_rate":round(float((g["pnl_pct"]>0).mean()*100),1) if len(g) else None,"ev":round(ev(g),2) if len(g) else None})
    eligible=[r for r in results if r["n"]>=8 and r["ev"] is not None]
    best=max(eligible,key=lambda r:r["ev"]) if eligible else None
    return {"eligible":bool(best is not None and (base_ev is None or best["ev"]>=base_ev)),"baseline_threshold":base,"baseline_n":int(len(base_g)),"baseline_ev":round(base_ev,2) if base_ev is not None else None,"candidates":results,"best":best}

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
    threshold_validation = evaluate_score_thresholds_oos(df_c)
    loss_examples = df_c.sort_values("pnl_pct").head(8)[["ticker","name","score","tech_score","pnl_pct"]].to_dict("records")
    win_examples = df_c.sort_values("pnl_pct",ascending=False).head(8)[["ticker","name","score","tech_score","pnl_pct"]].to_dict("records")

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
        "threshold_validation": threshold_validation,
        "loss_examples": loss_examples,
        "win_examples": win_examples,
    }


# ============================================================
# 2. AI 分析 + 生成规则补丁（已包股票数据）
# ============================================================
def claude_red_team_audit(metrics: dict, proposed_result: dict):
    """Claude 只做独立红队审查；不直接修改策略参数。"""
    try:
        client = ClawSocketClient(
            api_key=os.environ.get("CLAWSOCKET_API_KEY"),
            base_url=os.environ.get("CLAWSOCKET_BASE_URL"),
        )
        prompt = f"""你是独立的美股量化策略红队审计员。
不要提出新的选股结论，只审查另一个模型提出的规则是否存在过拟合、样本不足、数据泄漏、因果倒置或不可执行问题。

OOS验证：
{json.dumps(metrics.get('threshold_validation'), ensure_ascii=False, indent=2)}

历史失败样本：
{json.dumps(metrics.get('loss_examples'), ensure_ascii=False, indent=2)}

历史成功样本：
{json.dumps(metrics.get('win_examples'), ensure_ascii=False, indent=2)}

GPT提出的结果：
{json.dumps(proposed_result, ensure_ascii=False, indent=2)}

只输出JSON：{{"approve":true或false,"risk_level":"low|medium|high","reasons":["..."],"required_conditions":["..."]}}
"""
        response = client.messages.create(model=CLAUDE_AUDIT_MODEL, max_tokens=1800, messages=[{"role":"user","content":prompt}])
        text = next((b.text for b in getattr(response,"content",[]) if getattr(b,"text",None)), "").strip()
        start, end = text.find("{"), text.rfind("}")+1
        if start < 0 or end <= start:
            return {"approve": False, "risk_level": "high", "reasons": ["Claude未返回有效JSON"]}
        obj=json.loads(text[start:end])
        return obj if isinstance(obj,dict) else {"approve":False,"risk_level":"high","reasons":["Claude返回格式异常"]}
    except Exception as e:
        print(f"⚠️ Claude红队审计失败：{type(e).__name__}: {e}")
        return {"approve": False, "risk_level": "high", "reasons": [f"审计调用失败：{type(e).__name__}: {e}"]}


def evolve_strategy(metrics: dict):
    print(f"🧬 启动策略进化引擎（{EVOLVE_MODEL}）...")
    client = ClawSocketClient(
        api_key=os.environ.get("CLAWSOCKET_API_KEY"),
        base_url=os.environ.get("CLAWSOCKET_BASE_URL"),
    )



    prompt = f"""
你是一个美股量化策略进化系统。根据以下交易绩效数据，生成具体可执行的选股规则补丁。

【当前绩效报告】：
- 已平仓股票：{metrics['total_closed']} 笔 | 总体胜率（全部历史混合，仅供参考）：{metrics['overall_win_rate']}% | 平均盈亏：{metrics['avg_pnl_pct']}%
- 最佳：{metrics['best_trade']} | 最差：{metrics['worst_trade']}
- 当前持仓：{metrics['active_count']} 只



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
{json.dumps(metrics['atr_stats'], ensure_ascii=False, indent=2) if metrics['atr_stats'] else "样本不足或还没有ATR数据的已平仓记录"}

【技术信号有效性分析】（判断MACD金叉/周线共振等信号是否真的有效）：
{json.dumps(metrics['signal_stats'], ensure_ascii=False, indent=2)}

【退出方式分布】（判断止损位/持股周期是否合理）：
{json.dumps(metrics['exit_stats'], ensure_ascii=False, indent=2)}

【OOS 门槛验证】
{json.dumps(metrics.get("threshold_validation"), ensure_ascii=False, indent=2)}

【失败样本】
{json.dumps(metrics.get("loss_examples"), ensure_ascii=False, indent=2)}

【成功样本】
{json.dumps(metrics.get("win_examples"), ensure_ascii=False, indent=2)}

【上一轮已应用规则】：
{json.dumps(metrics['prev_rules'], ensure_ascii=False, indent=2) if metrics['prev_rules'] else "无（首次进化）"}

【分析思路】：
0. 优先看"按进化世代拆分胜率"：如果最近一代相比上一代胜率下降了，说明上一轮规则
   可能是错的或用力过猛，这一轮应考虑撤销或调整方向。
1. 如果高技术评分（30-40分）的胜率 < 低技术评分（0-9分），说明技术面权重过高（40分），需要降低
2. 如果MACD金叉=是的胜率远高于=否，说明金叉信号有效，应该提高MACD金叉的推荐权重
3. 如果止损触发次数多且亏损较大，说明止损位设得太紧，建议适当放宽
   - 如果 CALL 和 PUT 的胜率差异显著，应建议扫描器优先选择胜率更高的方向

代码级参数只允许从白名单中选择：core_min_score、observation_min_score、min_technical_confirmations、stressed_min_technical_confirmations；只有 OOS 验证样本足够且 EV 不差于当前基线时才允许自动应用。止损参数只能提出建议，不自动覆盖。

必须只返回以下 JSON，不要输出其他文字：
{{
    "key_findings": [
        "发现1（数据支撑）",
        "发现2",
        "发现3"
    ],
    "identified_flaws": "最关键的逻辑缺陷（指出根因）",
    "applied_rules": [
        {{
            "rule_id": "rule_{datetime.date.today().strftime('%Y%m%d')}_001",
            "type": "TECH_WEIGHT_ADJUST 或 SIGNAL_BOOST 或 STOPLOSS_ADJUST 或 HOLD_PERIOD_ADJUST 或 CONDITION_ADD 或 CONDITION_REMOVE",
            "description": "规则说明",
            "prompt_patch": "注入 scan.py AI prompt 的具体文字（可执行，如：'历史数据显示MACD金叉标的胜率达71%，当出现MACD金叉信号时，消息面评分可适当上浮5-8分'）",
            "evidence": "支撑数据",
            "expires_after_trades": 20
        }}
    ],
}}
"""

    try:
        response = client.messages.create(
            model=EVOLVE_MODEL,
            max_tokens=2000,
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

        audit = claude_red_team_audit(metrics, result)
        result["claude_red_team_audit"] = audit
        print(f"🛡️ Claude红队：approve={audit.get('approve')} risk={audit.get('risk_level')}")

        # 代码级参数：白名单 + OOS 门槛验证 + Claude 红队批准，避免 AI 随意改阈值。
        applied_parameter_updates = []
        tv = metrics.get("threshold_validation") or {}
        if tv.get("eligible") and tv.get("best") and audit.get("approve") is True and audit.get("risk_level") != "high":
            best_t = int(tv["best"]["threshold"])
            current_t = int(STRATEGY_PARAMS["scoring"].get("core_min_score",65))
            if best_t != current_t:
                STRATEGY_PARAMS["scoring"]["core_min_score"] = best_t
                applied_parameter_updates.append({"name":"core_min_score","old":current_t,"new":best_t,"reason":"time-ordered OOS EV >= baseline"})
        # Observation 门槛不单独自动降低；保持更保守的下限，避免用 Observation 扩大低质量样本。
        if applied_parameter_updates:
            with open(STRATEGY_PARAMS_FILE,"w",encoding="utf-8") as f:
                json.dump(STRATEGY_PARAMS,f,ensure_ascii=False,indent=2)
        result["applied_parameter_updates"] = applied_parameter_updates
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

        recent_limit = 4
        deduped = deduped[-recent_limit:]
        evolved_output = {
            "last_updated":            result["date"],
            "total_closed_at_update":  total_now,
            "overall_win_rate":        metrics["overall_win_rate"],
            "recent_win_rate":         metrics.get("since_last_evolution"),
            "active_rules":            deduped,
            "prompt_patches":          [r.get("prompt_patch","") for r in deduped],
            "applied_parameter_updates": result.get("applied_parameter_updates",[]),
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
    if metrics["generation_stats"]:
        print(f"  按进化世代拆分：{metrics['generation_stats']}")
    if metrics["since_last_evolution"]:
        print(f"  最近一次进化之后：{metrics['since_last_evolution']}")
    if metrics["tech_score_stats"]:
        print(f"  技术评分分层胜率: {metrics['tech_score_stats']}")
    if metrics["signal_stats"]:
        print(f"  信号有效性: {metrics['signal_stats']}")

    evolve_strategy(metrics)
