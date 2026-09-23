from pathlib import Path
import re

review = Path('/mnt/data/v34/review.py')
s = review.read_text(encoding='utf-8')

# 1) Make the Wall wording precise: never imply a volume proxy is an OI Wall.
s = s.replace(
    'return f"{_price(value)}（成交量代理 {int(volume or 0)}；非OI Wall）"',
    'return f"{_price(value)}（成交量代理 {int(volume or 0)}；OI不可用）"'
)

# 2) Add Observation lifecycle configuration + helpers before stock classification.
marker = '# ============================================================\n# 9. 股票分类\n# ============================================================\n'
if marker not in s:
    raise SystemExit('classification marker not found')

insert = r'''# ============================================================
# 8.5 Observation 生命周期管理
# ============================================================
# Observation 是观察性推荐，不应无限期占用 Review 算力。
# 事件仍永久保留在 trade_history / review KPI 中，但“当前跟踪”会自动结束。
OBS_MAX_TRADING_SESSIONS = 10
OBS_TARGET_PCT = 10.0          # 达标即停止继续跟踪
OBS_INVALIDATION_PCT = -6.0    # 跌破即停止继续跟踪
OBS_CLOSE_STATUS = "Observation_Closed"
OBS_END_REASONS = {
    "TARGET_REACHED": "达到观察目标，停止继续跟踪",
    "THESIS_INVALIDATED": "观察期价格表现跌破失效阈值，停止继续跟踪",
    "MAX_TRACKING_SESSIONS": "达到最大观察交易日，停止继续跟踪",
    "SUPERSEDED_BY_NEW_OBSERVATION": "同一标的出现新的 Observation，结束旧事件",
    "SUPERSEDED_BY_CORE": "同一标的升级为 Core，结束旧 Observation",
}


def _observation_sessions_held(rec_date_str, review_date_str):
    try:
        a = pd.Timestamp(rec_date_str).normalize()
        b = pd.Timestamp(review_date_str).normalize()
        if b <= a:
            return 0
        return max(0, len(pd.bdate_range(a, b)) - 1)
    except Exception:
        return 0


def _historical_close_for_review_event(ticker, date_str):
    """尽量取指定推荐/替换交易日收盘价，给 Observation 事件做干净的结束结算。"""
    try:
        if 'df_hist_all' not in globals() or df_hist_all is None or df_hist_all.empty:
            return None
        d = df_hist_all.copy()
        d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
        target = pd.Timestamp(date_str).normalize()
        sub = d[
            d["Ticker"].astype(str).str.upper().eq(str(ticker).upper())
            & d["Date"].dt.normalize().eq(target)
        ]
        if sub.empty:
            return None
        return safe_float(sub.iloc[-1].get("close"))
    except Exception:
        return None


def manage_observation_lifecycle():
    """
    自动结束过老/已失效/被新推荐替代的 Observation。
    只结束当前仍 Active/pending 的 Observation；历史事件不反复修改。
    """
    if not os.path.exists(TRADE_HISTORY) or os.path.getsize(TRADE_HISTORY) == 0:
        return 0
    try:
        d = pd.read_csv(TRADE_HISTORY, dtype=str, keep_default_na=False, on_bad_lines='warn')
    except Exception as e:
        print(f"⚠️ Observation 生命周期读取失败：{e}")
        return 0

    for col in ["Status", "Exit_Date", "Exit_Price", "Observation_Status", "Observation_End_Reason"]:
        if col not in d.columns:
            d[col] = ""
        d[col] = d[col].astype(object)

    if "Date" not in d.columns or "Ticker" not in d.columns or "Tag" not in d.columns:
        return 0

    tmp = d.copy()
    tmp["_date"] = pd.to_datetime(tmp["Date"], errors="coerce")
    tmp["_ticker"] = tmp["Ticker"].astype(str).str.upper().str.strip()
    tmp["_tag"] = tmp["Tag"].astype(str).str.strip()
    tmp["_status"] = tmp["Status"].astype(str).str.strip()

    active_obs = tmp[
        (tmp["_tag"] == "Observation")
        & tmp["_status"].isin(["", "Active", "pending"])
        & tmp["_date"].notna()
    ].copy()
    if active_obs.empty:
        return 0

    # 仅比较同 ticker 的后续 Scan 事件。旧 Observation 被新的 Observation/Core 替代后关闭。
    closes = []
    for idx, row in active_obs.sort_values(["_ticker", "_date"]).iterrows():
        ticker = str(row["_ticker"]).strip()
        rec_date = row["_date"].strftime("%Y-%m-%d")
        rec_price = safe_record_price(row)
        if rec_price is None or rec_price <= 0:
            # 推荐价缺失时仍允许超期关闭，但无法形成收益数字。
            rec_price = None

        later = tmp[
            (tmp["_ticker"] == ticker)
            & tmp["_date"].notna()
            & (tmp["_date"] > row["_date"])
        ].copy()
        later = later.sort_values("_date")

        replacement = None
        if not later.empty:
            core_later = later[later["_tag"].isin(["Core_Dragon", "Core_Double_Dragon", "Sub_Pioneer"])]
            obs_later = later[later["_tag"] == "Observation"]
            if not core_later.empty:
                replacement = ("SUPERSEDED_BY_CORE", core_later.iloc[0])
            elif not obs_later.empty:
                replacement = ("SUPERSEDED_BY_NEW_OBSERVATION", obs_later.iloc[0])

        reason_code = None
        close_date = pd.Timestamp(REVIEW_SESSION_DATE).strftime("%Y-%m-%d")
        close_price = safe_float(price_map_today.get(ticker))

        # 新事件替代：尽量在“新事件的推荐日收盘”结束旧观察，而不是等到今天。
        if replacement is not None:
            reason_code, repl = replacement
            close_date = repl["_date"].strftime("%Y-%m-%d")
            close_price = _historical_close_for_review_event(ticker, close_date) or close_price
        else:
            if rec_price and close_price:
                pnl = (close_price - rec_price) / rec_price * 100.0
                if pnl >= OBS_TARGET_PCT:
                    reason_code = "TARGET_REACHED"
                elif pnl <= OBS_INVALIDATION_PCT:
                    reason_code = "THESIS_INVALIDATED"
            if reason_code is None:
                sessions = _observation_sessions_held(rec_date, REVIEW_SESSION_DATE)
                if sessions >= OBS_MAX_TRADING_SESSIONS:
                    reason_code = "MAX_TRACKING_SESSIONS"

        if reason_code is None:
            continue

        label = OBS_END_REASONS.get(reason_code, reason_code)
        mask = (
            tmp.index.eq(idx)
        )
        d.loc[mask, "Status"] = OBS_CLOSE_STATUS
        d.loc[mask, "Exit_Date"] = close_date
        if close_price is not None:
            d.loc[mask, "Exit_Price"] = str(round(float(close_price), 4))
        d.loc[mask, "Observation_Status"] = "Closed"
        d.loc[mask, "Observation_End_Reason"] = label
        closes.append((ticker, rec_date, reason_code, close_price))

    if closes:
        try:
            d.to_csv(TRADE_HISTORY, index=False, encoding="utf-8")
        except Exception as e:
            print(f"⚠️ Observation 生命周期写回失败：{e}")
            return 0

        reason_counts = {}
        for ticker, rec_date, code, close_price in closes:
            reason_counts[code] = reason_counts.get(code, 0) + 1
        detail = "；".join(f"{OBS_END_REASONS.get(k,k)} {v}笔" for k, v in reason_counts.items())
        print(f"📌 [Observation跟踪管理] 本次结束 {len(closes)} 笔，原因：{detail}")

    return len(closes)


# 事件生命周期管理必须先于分类和 KPI。
manage_observation_lifecycle()

'''
s = s.replace(marker, insert + marker)

# 3) Ensure Observation_Closed is treated as a completed Scan recommendation event.
old = '''                    closed_statuses = {
                        "Stop_Loss_Hit",
                        "移动止损清仓",
                        "止损触发清仓",
                        "已超期归档",
                        "突发清仓暂停",
                        "周期到期清仓",
                    }'''
new = '''                    closed_statuses = {
                        "Stop_Loss_Hit",
                        "移动止损清仓",
                        "止损触发清仓",
                        "已超期归档",
                        "突发清仓暂停",
                        "周期到期清仓",
                        "Observation_Closed",
                    }'''
if old not in s:
    raise SystemExit('review_history closed_statuses not found')
s = s.replace(old, new, 1)

# 4) There is another closed-status set for trade_history supplement; add Observation_Closed there too.
old2 = '''                    if status in {
                        "Stop_Loss_Hit", "移动止损清仓", "止损触发清仓",
                        "已超期归档", "突发清仓暂停", "周期到期清仓"
                    } and exit_price is not None:'''
new2 = '''                    if status in {
                        "Stop_Loss_Hit", "移动止损清仓", "止损触发清仓",
                        "已超期归档", "突发清仓暂停", "周期到期清仓", "Observation_Closed"
                    } and exit_price is not None:'''
if old2 not in s:
    raise SystemExit('trade_history closed_statuses not found')
s = s.replace(old2, new2, 1)

# 5) Closed KPI status set should include Observation_Closed.
old3 = '''CLOSED_STOCK_STATUSES = {
    "Stop_Loss_Hit",
    "Dropped",
    "Period_Matured",
    "Forced_Exit",
    "移动止损清仓",
    "止损触发清仓",
    "已超期归档",
    "周期到期清仓",
    "突发清仓暂停",
}'''
new3 = '''CLOSED_STOCK_STATUSES = {
    "Stop_Loss_Hit",
    "Dropped",
    "Period_Matured",
    "Forced_Exit",
    "移动止损清仓",
    "止损触发清仓",
    "已超期归档",
    "周期到期清仓",
    "突发清仓暂停",
    "Observation_Closed",
}'''
if old3 not in s:
    raise SystemExit('KPI CLOSED_STOCK_STATUSES not found')
s = s.replace(old3, new3, 1)

# 6) Make the Observation section explicitly state lifecycle rules and active scope.
old_html = 'return \'<h2 style="color:#e65100;border-bottom:2px solid #e65100;padding-bottom:5px;">👀 最近30天 Observation 推荐</h2>\' + "".join(blocks)'
new_html = 'return \'<h2 style="color:#e65100;border-bottom:2px solid #e65100;padding-bottom:5px;">👀 当前 Observation 跟踪</h2><div style="background:#fff7e6;border:1px solid #ffd59a;padding:12px;margin-bottom:15px;border-radius:8px;color:#7a4b00;">当前只保留仍在跟踪的 Observation。自动取消跟踪条件：达到 +10% 目标、跌幅达到 -6% 失效、满 10 个交易日、被新的 Observation 替代、或升级为 Core。已结束事件仍保留在 KPI 历史统计中，不再持续占用当前跟踪资源。</div>\' + "".join(blocks)'
if old_html not in s:
    raise SystemExit('Observation html return not found')
s = s.replace(old_html, new_html, 1)

# 7) Update the note in each observation card.
s = s.replace(
    '<div style="color:#607d8b;">Observation 不计入实际持仓，但属于有效 Scan 推荐，按首次推荐价持续追踪并计入 Scan 推荐绩效。</div>',
    '<div style="color:#607d8b;">Observation 不计入实际持仓。当前跟踪有明确结束条件；结束后的事件仍保留在历史绩效统计中。</div>'
)

review.write_text(s, encoding='utf-8')

# 8) Add the same wording to option strategy engine output by keeping source precise.
opt = Path('/mnt/data/v34/scan_us_option_engine.py')
o = opt.read_text(encoding='utf-8')
o = o.replace('"source":"volume_proxy"', '"source":"volume_proxy"')
opt.write_text(o, encoding='utf-8')

# 9) Change log
Path('/mnt/data/v34/REVIEW_V34_OBSERVATION_LIFECYCLE_WALL.md').write_text('''# V34 Observation 生命周期 + Wall 标识修复\n\n## Wall\n- OI 可用：Call/Put Wall = 最大 Open Interest 执行价。\n- OI 不可用：只显示成交量代理，不再标成“非OI Wall”这种容易误解的表述；邮件显示为“成交量代理；OI不可用”。\n\n## Observation\n当前 Observation 不再无限期跟踪。自动结束条件：\n- +10%：TARGET_REACHED\n- -6%：THESIS_INVALIDATED\n- 满 10 个交易日：MAX_TRACKING_SESSIONS\n- 同一标的出现新的 Observation：SUPERSEDED_BY_NEW_OBSERVATION\n- 同一标的升级为 Core：SUPERSEDED_BY_CORE\n\n结束事件：\n- trade_history.csv 写入 Status=Observation_Closed、Exit_Date、Exit_Price、Observation_End_Reason\n- 仍参与历史 KPI 完成样本\n- 不再进入当前 Observation 跟踪列表\n''', encoding='utf-8')
