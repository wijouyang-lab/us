# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf
import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic
import re

# ==========================================
# 1. 基础配置与时区初始化
# ==========================================
US_TZ = datetime.timezone(datetime.timedelta(hours=-4))

def get_us_time():
    """获取美东当前时间"""
    return datetime.datetime.now(US_TZ)

# 周末检查逻辑
current_time = get_us_time()
if current_time.weekday() >= 5:
    print(f"当前时间为周{current_time.weekday() + 1}，属于周末休市时间，退出盘后复盘程序。")
    import sys
    sys.exit(0)

TARGET_MODEL = 'claude-opus-4-8'
print("=" * 50)
print("🚀 启动美股盘后复盘与风控审查引擎 (全功能工程版)...")
print("=" * 50)

# ==========================================
# 2. 账本文件检查与加载
# ==========================================
log_file = "trade_history.csv"
if not os.path.exists(log_file):
    print(f"⚠️ 警告：未检测到交易账本文件 [{log_file}]，跳过本次复盘。")
    import sys
    sys.exit(0)

try:
    print(f"📂 正在加载交易账本: {log_file} ...")
    df = pd.read_csv(log_file)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # 筛选最近 30 天的记录
    cutoff_date = get_us_time() - datetime.timedelta(days=30)
    recent_picks = df[df['Date'] >= cutoff_date.replace(tzinfo=None)].copy()
    
    if recent_picks.empty:
        print("⚠️ 提示：最近 30 天内无任何操作记录，跳过复盘。")
        import sys
        sys.exit(0)
    print(f"✅ 成功加载最近 30 天交易记录，共计 {len(recent_picks)} 行原始数据。")
except Exception as e:
    print(f"❌ 错误：账本读取失败，异常原因: {e}")
    import sys
    sys.exit(1)

# ==========================================
# 5.5 期权策略联动与结算引擎
# ==========================================
# 设计原则：
# 1) scan 负责产生“期权推荐事件”，review 负责结算与统计；
# 2) 优先读取独立 option_trade_history.csv；
# 3) 同时兼容 scan 后续写入 trade_history.csv 的 Asset_Type=OPTION / Option_* 字段；
# 4) 股票胜率与期权胜率完全分开，不互相污染；
# 5) 胜负按“期权合约本身”的权利金 PnL 计算，而不是用正股涨跌代替。

OPTION_LEDGER = "option_trade_history.csv"
OPTION_REVIEW_LOG = "option_review_history.csv"
OPTION_ACTIVE_STATUS = {"ACTIVE", "持仓中", "OPEN"}
OPTION_CLOSED_STATUS = {
    "止损触发清仓", "周期到期清仓", "到期结算", "手动清仓",
    "突发清仓暂停", "已结算", "CLOSED", "EXPIRED"
}

OPTION_COLUMNS = [
    "Strategy_ID", "Scan_Date", "Ticker", "Name", "Option_Action",
    "Option_Position", "Option_Type", "Strike", "Expiration", "DTE",
    "Option_Contract", "Entry_Premium", "Stop_Premium", "Target_Premium",
    "Underlying_Stop", "Contracts", "Multiplier", "Score", "Tag", "Reason"
]

def _pick_col(row, names, default=""):
    """兼容不同 scan 版本的字段命名。"""
    for n in names:
        if n in row.index:
            v = row.get(n)
            if pd.notna(v) and str(v).strip() != "":
                return v
    return default

def _is_option_row(row):
    vals = []
    for col in [
        "Asset_Type", "Type", "Option_Type", "Option_Action",
        "Option_Contract", "Contract", "Strike", "Expiration",
        "Option_Premium", "Entry_Premium"
    ]:
        if col in row.index:
            vals.append(str(row.get(col, "")))
    blob = " ".join(vals).upper()
    return (
        "OPTION" in blob or "CALL" in blob or "PUT" in blob
        or "认购" in blob or "认沽" in blob or "期权" in blob
        or (str(row.get("Option_Type", "")).strip() != "")
    )

def _normalize_option_row(row):
    """把 scan 的推荐记录标准化成 review 内部统一结构。"""
    ticker = str(_pick_col(row, ["Ticker", "Underlying_Ticker"], "")).strip()
    ticker = ticker.lstrip("$").upper()

    opt_type = str(_pick_col(row, ["Option_Type", "Type", "Call_Put"], "")).strip().upper()
    if opt_type in {"认购", "C", "CALLS"}:
        opt_type = "CALL"
    elif opt_type in {"认沽", "P", "PUTS"}:
        opt_type = "PUT"

    position = str(_pick_col(row, ["Option_Position", "Position", "Side"], "LONG")).strip().upper()
    if position in {"买入", "BUY", "LONG CALL", "LONG PUT"}:
        position = "LONG"
    elif position in {"卖出", "SELL", "SHORT"}:
        position = "SHORT"

    strike_raw = _pick_col(row, ["Strike", "Strike_Price", "行权价"], "")
    try:
        strike = float(re.findall(r"-?\d+\.?\d*", str(strike_raw))[0])
    except Exception:
        strike = None

    expiry_raw = _pick_col(row, ["Expiration", "Expiry", "Expiration_Date", "到期日"], "")
    expiry = ""
    if str(expiry_raw).strip():
        try:
            expiry = pd.to_datetime(expiry_raw).strftime("%Y-%m-%d")
        except Exception:
            expiry = str(expiry_raw).strip()[:10]

    entry_raw = _pick_col(row, ["Entry_Premium", "Option_Premium", "Premium", "Option_Entry_Price", "权利金"], "")
    try:
        entry_premium = float(re.findall(r"-?\d+\.?\d*", str(entry_raw))[0])
    except Exception:
        entry_premium = None

    stop_raw = _pick_col(row, ["Stop_Premium", "Option_Stop_Premium", "Premium_Stop", "期权止损价"], "")
    try:
        stop_premium = float(re.findall(r"-?\d+\.?\d*", str(stop_raw))[0])
    except Exception:
        stop_premium = None

    target_raw = _pick_col(row, ["Target_Premium", "Option_Target_Premium", "Premium_Target", "期权目标价"], "")
    try:
        target_premium = float(re.findall(r"-?\d+\.?\d*", str(target_raw))[0])
    except Exception:
        target_premium = None

    under_stop_raw = _pick_col(row, ["Underlying_Stop", "Stop_Loss", "Underlying_Stop_Loss", "正股止损"], "")
    try:
        nums = re.findall(r"-?\d+\.?\d*", str(under_stop_raw))
        underlying_stop = float(nums[0]) if nums else None
    except Exception:
        underlying_stop = None

    dte_raw = _pick_col(row, ["DTE", "Days_To_Expiration", "到期剩余天数"], "")
    try:
        dte = int(float(re.findall(r"\d+\.?\d*", str(dte_raw))[0]))
    except Exception:
        dte = None

    contracts_raw = _pick_col(row, ["Contracts", "Quantity", "Contract_Count", "合约数"], 1)
    try:
        contracts = max(1, int(float(contracts_raw)))
    except Exception:
        contracts = 1

    multiplier_raw = _pick_col(row, ["Multiplier", "Contract_Multiplier", "乘数"], 100)
    try:
        multiplier = float(multiplier_raw)
    except Exception:
        multiplier = 100.0

    strategy_id = str(_pick_col(
        row, ["Strategy_ID", "Option_Strategy_ID", "Signal_ID", "Trade_ID"], ""
    )).strip()
    if not strategy_id:
        strategy_id = f"{str(row.get('Date', ''))[:10]}_{ticker}_{opt_type}_{strike}_{expiry}"

    return {
        "Strategy_ID": strategy_id,
        "Scan_Date": pd.to_datetime(row.get("Date")).strftime("%Y-%m-%d") if pd.notna(row.get("Date")) else "",
        "Ticker": ticker,
        "Name": str(_pick_col(row, ["Name", "Underlying_Name"], ticker)),
        "Option_Action": str(_pick_col(row, ["Option_Action", "Action"], "BUY")).strip().upper(),
        "Option_Position": position,
        "Option_Type": opt_type,
        "Strike": strike,
        "Expiration": expiry,
        "DTE": dte,
        "Option_Contract": str(_pick_col(
            row, ["Option_Contract", "Contract", "Option_Symbol", "Contract_Symbol"], ""
        )).strip(),
        "Entry_Premium": entry_premium,
        "Stop_Premium": stop_premium,
        "Target_Premium": target_premium,
        "Underlying_Stop": underlying_stop,
        "Contracts": contracts,
        "Multiplier": multiplier,
        "Score": str(_pick_col(row, ["Option_Score", "Score"], "N/A")),
        "Tag": str(_pick_col(row, ["Option_Tag", "Tag"], "Option_Strategy")),
        "Reason": str(_pick_col(row, ["Option_Reason", "Reason"], "")),
    }

def _option_ticker_quote(contract, underlying, opt_type, strike, expiration):
    """
    获取当前期权权利金。
    yfinance 对当前/未来合约可直接查 option_chain；若 scan 已提供 OCC 合约代码，
    则优先尝试直接读取该合约历史最新价。
    """
    try:
        if contract:
            hist = yf.Ticker(contract).history(period="2d", auto_adjust=False)
            if hist is not None and not hist.empty and "Close" in hist.columns:
                v = hist["Close"].dropna()
                if not v.empty:
                    return float(v.iloc[-1]), {"source": "contract_history"}
    except Exception:
        pass

    try:
        t = yf.Ticker(underlying)
        expirations = list(getattr(t, "options", ()) or ())
        expiry = expiration
        if not expiry:
            return None, {"source": "none"}
        # yfinance 当前链可能只保留尚未到期的月份
        if expiry not in expirations:
            return None, {"source": "none"}
        chain = t.option_chain(expiry)
        table = chain.calls if opt_type == "CALL" else chain.puts
        if table is None or table.empty or strike is None:
            return None, {"source": "none"}

        table = table.copy()
        table["_dist"] = (pd.to_numeric(table["strike"], errors="coerce") - float(strike)).abs()
        r = table.sort_values("_dist").iloc[0]
        last = pd.to_numeric(pd.Series([r.get("lastPrice")]), errors="coerce").iloc[0]
        bid = pd.to_numeric(pd.Series([r.get("bid")]), errors="coerce").iloc[0]
        ask = pd.to_numeric(pd.Series([r.get("ask")]), errors="coerce").iloc[0]

        price = None
        if pd.notna(last) and float(last) > 0:
            price = float(last)
        elif pd.notna(bid) and pd.notna(ask) and float(bid) >= 0 and float(ask) > 0:
            price = round((float(bid) + float(ask)) / 2.0, 4)

        meta = {
            "source": "option_chain",
            "iv": float(r.get("impliedVolatility")) if pd.notna(r.get("impliedVolatility")) else None,
            "bid": float(bid) if pd.notna(bid) else None,
            "ask": float(ask) if pd.notna(ask) else None,
            "last": float(last) if pd.notna(last) else None,
        }
        return price, meta
    except Exception as e:
        print(f"⚠️ 期权行情获取失败 [{underlying} {opt_type} {strike} {expiration}]: {e}")
        return None, {"source": "error"}

def _underlying_price(ticker, price_map_today):
    t = ticker.lstrip("$").upper()
    if t in price_map_today:
        return float(price_map_today[t])
    try:
        hist = yf.Ticker(t).history(period="5d", auto_adjust=True)
        if hist is not None and not hist.empty:
            return float(hist["Close"].dropna().iloc[-1])
    except Exception:
        pass
    return None

def _intrinsic_value(underlying_price, strike, opt_type):
    if underlying_price is None or strike is None or opt_type not in {"CALL", "PUT"}:
        return None
    if opt_type == "CALL":
        return max(underlying_price - strike, 0.0)
    return max(strike - underlying_price, 0.0)

def _calc_option_pnl(entry, exit_price, position="LONG"):
    if entry is None or exit_price is None or entry <= 0:
        return None
    if position == "SHORT":
        return round((entry - exit_price) / entry * 100.0, 2)
    return round((exit_price - entry) / entry * 100.0, 2)

def _load_option_ledger():
    frames = []

    if os.path.exists(OPTION_LEDGER) and os.path.getsize(OPTION_LEDGER) > 0:
        try:
            x = pd.read_csv(OPTION_LEDGER, on_bad_lines="skip")
            if not x.empty:
                x["Date"] = pd.to_datetime(x["Date"], errors="coerce")
                x = x[_is_option_series(x)].copy()
                frames.append(x)
        except Exception as e:
            print(f"⚠️ 读取 {OPTION_LEDGER} 失败: {e}")

    if not recent_picks.empty:
        try:
            x = recent_picks.copy()
            if "Date" not in x.columns:
                x["Date"] = pd.NaT
            mask = x.apply(_is_option_row, axis=1)
            x = x[mask].copy()
            if not x.empty:
                frames.append(x)
        except Exception as e:
            print(f"⚠️ 从 trade_history.csv 读取期权记录失败: {e}")

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True, sort=False)

def _is_option_series(df):
    if df.empty:
        return pd.Series(dtype=bool, index=df.index)
    return df.apply(_is_option_row, axis=1)

def _option_already_closed(strategy_id):
    if not os.path.exists(OPTION_REVIEW_LOG) or os.path.getsize(OPTION_REVIEW_LOG) == 0:
        return False
    try:
        h = pd.read_csv(OPTION_REVIEW_LOG, on_bad_lines="skip")
        if "Strategy_ID" not in h.columns or "Status" not in h.columns:
            return False
        return bool(((h["Strategy_ID"].astype(str) == str(strategy_id)) &
                     h["Status"].isin(OPTION_CLOSED_STATUS)).any())
    except Exception:
        return False

def evaluate_option_strategies(option_rows, price_map_today):
    active = []
    closed = []

    if option_rows is None or option_rows.empty:
        return active, closed

    normalized = [_normalize_option_row(r) for _, r in option_rows.iterrows()]
    # 同一 Strategy_ID 只保留最后一条 scan 记录
    latest = {}
    for item in normalized:
        latest[item["Strategy_ID"]] = item

    now = get_us_time().replace(tzinfo=None)

    for item in latest.values():
        if _option_already_closed(item["Strategy_ID"]):
            continue

        ticker = item["Ticker"]
        spot = _underlying_price(ticker, price_map_today)
        entry = item["Entry_Premium"]
        opt_type = item["Option_Type"]
        position = item["Option_Position"]
        strike = item["Strike"]
        expiry = item["Expiration"]

        # 如果 scan 没写 entry premium，无法形成可验证的期权胜率记录
        if entry is None or entry <= 0 or opt_type not in {"CALL", "PUT"} or not expiry:
            print(f"⚠️ 期权策略 [{item['Strategy_ID']}] 缺少 Entry_Premium/Type/Expiration，跳过胜率计算。")
            continue

        try:
            expiry_dt = pd.to_datetime(expiry).to_pydatetime()
        except Exception:
            expiry_dt = None

        current_premium, meta = _option_ticker_quote(
            item["Option_Contract"], ticker, opt_type, strike, expiry
        )

        status = "ACTIVE"
        close_reason = ""
        exit_premium = current_premium
        exit_date = now.strftime("%Y-%m-%d")

        # 1) 期权自身权利金止损
        if item["Stop_Premium"] is not None and current_premium is not None:
            if position == "SHORT":
                premium_stop_hit = current_premium >= item["Stop_Premium"]
            else:
                premium_stop_hit = current_premium <= item["Stop_Premium"]
            if premium_stop_hit:
                status = "止损触发清仓"
                close_reason = f"期权权利金触及止损价 {item['Stop_Premium']}"
                exit_premium = current_premium

        # 2) 正股止损：由 scan 推荐的正股风控底线触发
        if status == "ACTIVE" and item["Underlying_Stop"] is not None and spot is not None:
            under_hit = (
                (opt_type == "CALL" and spot <= item["Underlying_Stop"]) or
                (opt_type == "PUT" and spot >= item["Underlying_Stop"])
            )
            if under_hit:
                status = "止损触发清仓"
                close_reason = f"正股价格 {spot:.2f} 触发 scan 正股止损位 {item['Underlying_Stop']:.2f}"
                exit_date = now.strftime("%Y-%m-%d")

        # 3) 持有到期/策略期限
        scan_date_dt = pd.to_datetime(item["Scan_Date"]).to_pydatetime() if item["Scan_Date"] else None
        hold_days = item["DTE"]
        if status == "ACTIVE" and scan_date_dt is not None and hold_days is not None:
            if now >= scan_date_dt + datetime.timedelta(days=int(hold_days)):
                status = "周期到期清仓"
                close_reason = f"达到 scan 建议策略期限 {hold_days} 天"
                exit_date = now.strftime("%Y-%m-%d")

        # 4) 合约到期：优先按到期日内在价值结算
        if status == "ACTIVE" and expiry_dt is not None and now.date() >= expiry_dt.date():
            intrinsic = _intrinsic_value(spot, strike, opt_type)
            if intrinsic is not None:
                status = "到期结算"
                close_reason = "期权合约到期，按到期内在价值结算"
                exit_premium = intrinsic
                exit_date = expiry_dt.strftime("%Y-%m-%d")

        if status == "ACTIVE":
            pnl = _calc_option_pnl(entry, current_premium, position)
            active.append({
                **item,
                "Current_Premium": current_premium,
                "Current_IV": meta.get("iv"),
                "Underlying_Price": spot,
                "PnL_Pct": pnl,
                "Status": "持仓中"
            })
            continue

        pnl = _calc_option_pnl(entry, exit_premium, position)
        if pnl is None:
            print(f"⚠️ 期权策略 [{item['Strategy_ID']}] 已触发 {status}，但缺少可验证 Exit_Premium，暂不计入胜率。")
            continue

        contracts = item["Contracts"]
        multiplier = item["Multiplier"]
        if position == "SHORT":
            pnl_dollars = round((entry - exit_premium) * multiplier * contracts, 2)
        else:
            pnl_dollars = round((exit_premium - entry) * multiplier * contracts, 2)

        closed.append({
            **item,
            "Exit_Premium": round(float(exit_premium), 4),
            "Exit_Date": exit_date,
            "Underlying_Price": spot,
            "PnL_Pct": pnl,
            "PnL_Dollars": pnl_dollars,
            "Status": status,
            "Close_Reason": close_reason
        })

    return active, closed

def append_option_review_history(option_closed):
    if not option_closed:
        return

    columns = [
        "Review_Date", "Strategy_ID", "Ticker", "Name", "Option_Type",
        "Option_Position", "Strike", "Expiration", "DTE", "Option_Contract",
        "Entry_Premium", "Exit_Premium", "Underlying_Price",
        "PnL_Pct", "PnL_Dollars", "Contracts", "Multiplier",
        "Stop_Premium", "Underlying_Stop", "Score", "Tag", "Status",
        "Rec_Date", "Exit_Date", "Close_Reason"
    ]

    exists = os.path.exists(OPTION_REVIEW_LOG) and os.path.getsize(OPTION_REVIEW_LOG) > 0
    try:
        with open(OPTION_REVIEW_LOG, "a", encoding="utf-8", newline="") as f:
            if not exists:
                f.write(",".join(columns) + "\n")
            for x in option_closed:
                vals = [
                    get_us_time().strftime("%Y-%m-%d"),
                    x["Strategy_ID"], x["Ticker"], x["Name"], x["Option_Type"],
                    x["Option_Position"], x["Strike"], x["Expiration"], x["DTE"],
                    x["Option_Contract"], x["Entry_Premium"], x["Exit_Premium"],
                    x["Underlying_Price"], x["PnL_Pct"], x["PnL_Dollars"],
                    x["Contracts"], x["Multiplier"], x["Stop_Premium"],
                    x["Underlying_Stop"], x["Score"], x["Tag"], x["Status"],
                    x["Scan_Date"], x["Exit_Date"], x["Close_Reason"].replace(",", "，")
                ]
                f.write(",".join("" if v is None else str(v) for v in vals) + "\n")
        print(f"✅ 已归档 {len(option_closed)} 笔期权结算记录到 {OPTION_REVIEW_LOG}")
    except Exception as e:
        print(f"⚠️ 期权复盘归档失败: {e}")

def build_option_kpis(option_active, option_closed):
    historical = []
    if os.path.exists(OPTION_REVIEW_LOG) and os.path.getsize(OPTION_REVIEW_LOG) > 0:
        try:
            h = pd.read_csv(OPTION_REVIEW_LOG, on_bad_lines="skip")
            for _, r in h.iterrows():
                try:
                    pnl = float(r["PnL_Pct"])
                except Exception:
                    continue
                historical.append({
                    "Ticker": str(r.get("Ticker", "")),
                    "Option_Type": str(r.get("Option_Type", "")),
                    "PnL_Pct": pnl,
                    "Status": str(r.get("Status", "")),
                })
        except Exception as e:
            print(f"⚠️ 读取历史期权 KPI 失败: {e}")

    # 防止本次刚归档的记录与历史文件重复计入
    existing_ids = set()
    if os.path.exists(OPTION_REVIEW_LOG) and os.path.getsize(OPTION_REVIEW_LOG) > 0:
        try:
            hh = pd.read_csv(OPTION_REVIEW_LOG, on_bad_lines="skip")
            if "Strategy_ID" in hh.columns:
                existing_ids = set(hh["Strategy_ID"].astype(str))
        except Exception:
            pass

    closed_rows = historical
    total = len(closed_rows)
    wins = sum(1 for x in closed_rows if x["PnL_Pct"] > 0)
    losses = sum(1 for x in closed_rows if x["PnL_Pct"] < 0)
    win_rate = wins / total * 100 if total else 0.0

    calls = [x for x in closed_rows if x["Option_Type"] == "CALL"]
    puts = [x for x in closed_rows if x["Option_Type"] == "PUT"]
    call_wr = (sum(1 for x in calls if x["PnL_Pct"] > 0) / len(calls) * 100) if calls else 0.0
    put_wr = (sum(1 for x in puts if x["PnL_Pct"] > 0) / len(puts) * 100) if puts else 0.0

    pos = [x["PnL_Pct"] for x in closed_rows if x["PnL_Pct"] > 0]
    neg = [x["PnL_Pct"] for x in closed_rows if x["PnL_Pct"] < 0]
    avg_win = sum(pos) / len(pos) if pos else 0.0
    avg_loss = sum(neg) / len(neg) if neg else 0.0
    profit_factor = (sum(pos) / abs(sum(neg))) if neg and sum(neg) != 0 else (float("inf") if pos else 0.0)
    expectancy = sum(x["PnL_Pct"] for x in closed_rows) / total if total else 0.0
    stop_count = sum(1 for x in closed_rows if x["Status"] == "止损触发清仓")
    expiry_count = sum(1 for x in closed_rows if x["Status"] in {"到期结算", "周期到期清仓"})
    stop_rate = stop_count / total * 100 if total else 0.0

    active_valid = [x for x in option_active if isinstance(x.get("PnL_Pct"), (int, float))]
    active_wins = sum(1 for x in active_valid if x["PnL_Pct"] > 0)
    active_wr = active_wins / len(active_valid) * 100 if active_valid else 0.0

    return {
        "total": total, "wins": wins, "losses": losses, "win_rate": win_rate,
        "call_count": len(calls), "put_count": len(puts),
        "call_wr": call_wr, "put_wr": put_wr,
        "avg_win": avg_win, "avg_loss": avg_loss,
        "profit_factor": profit_factor, "expectancy": expectancy,
        "stop_count": stop_count, "expiry_count": expiry_count,
        "stop_rate": stop_rate, "active_count": len(option_active),
        "active_wr": active_wr
    }



# ==========================================
# 3. 版本过滤与字段清洗校验
# ==========================================
print("🔍 正在进行版本过滤与字段合法性校验...")
_INVALID = {'', 'n/a', 'nan', 'none'}
for _col in ['Hold_Period', 'Stop_Loss', 'Score']:
    if _col not in recent_picks.columns:
        recent_picks[_col] = ''

# ──────────────────────────────────────────
# 期权/股票先分流：期权不受股票 Score 版本过滤影响
# ──────────────────────────────────────────
try:
    _option_mask_pre = recent_picks.apply(_is_option_row, axis=1)
except Exception:
    _option_mask_pre = pd.Series(False, index=recent_picks.index)

option_picks = recent_picks[_option_mask_pre].copy()
stock_picks = recent_picks[~_option_mask_pre].copy()

# 股票记录才执行原有 Score 版本过滤
_score_valid = stock_picks['Score'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID)
_dropped = (~_score_valid).sum()
if _dropped > 0:
    print(f"🗂️ 版本过滤提示：成功剔除 {_dropped} 条无评分的旧版股票记录，不纳入本次股票复盘。")
recent_picks = stock_picks[_score_valid].copy()

if not option_picks.empty:
    print(f"📦 检测到 {len(option_picks)} 条 scan 生成的期权策略记录，转入独立期权结算引擎。")

# 检查 Stop_Loss 是否为 N/A
_no_stoploss = recent_picks['Stop_Loss'].astype(str).str.strip().str.lower().isin(_INVALID)
if _no_stoploss.sum() > 0:
    tickers_no_sl = recent_picks.loc[_no_stoploss, 'Ticker'].tolist()
    print(f"⚠️ 警告：以下 {_no_stoploss.sum()} 条记录的 Stop_Loss 属性为 N/A，将继续追踪但无法进行精确止损价核查。涉及标的: {tickers_no_sl[:10]}")

if recent_picks.empty and option_picks.empty:
    print("⚠️ 警告：股票与期权均无有效记录，程序退出。")
    import sys
    sys.exit(0)

# ==========================================
# 4. 行情数据拉取与价格映射准备
# ==========================================
all_tickers_raw = recent_picks['Ticker'].unique().tolist()
# 美股特有：清洗带 $ 符号的 Ticker
clean_map = {t: t.lstrip('$') for t in all_tickers_raw}
clean_tickers = list(set(clean_map.values()))

print(f"📡 正在通过 yfinance 批量拉取美股历史行情数据，标的列表: {clean_tickers}")
df_hist_all = pd.DataFrame()
price_map_today = {}

if clean_tickers:
    try:
        hist_data = yf.download(clean_tickers, period="60d", progress=False, auto_adjust=True, group_by='ticker')
        if len(clean_tickers) == 1:
            t = clean_tickers[0]
            temp_df = hist_data.copy()
            temp_df['ts_code'] = t
            temp_df['trade_date'] = temp_df.index
            df_hist_all = temp_df[['ts_code', 'trade_date', 'Close']].rename(columns={'Close': 'close'})
            if not df_hist_all.empty:
                price_map_today[t] = float(df_hist_all['close'].iloc[-1])
        else:
            records = []
            for t in clean_tickers:
                try:
                    s = hist_data[t]['Close'].dropna()
                    for date, val in s.items():
                        records.append({'ts_code': t, 'trade_date': date, 'close': float(val)})
                    if not s.empty:
                        price_map_today[t] = float(s.iloc[-1])
                except Exception as sub_e:
                    print(f"⚠️ 解析标的 {t} 历史行情出错: {sub_e}")
            df_hist_all = pd.DataFrame(records)
        print(f"✅ 行情数据拉取完毕，成功获取最新收盘价的标的数: {len(price_map_today)}")
    except Exception as e:
        print(f"❌ 严重错误：调用 yfinance 历史价格拉取失败: {e}")

# ==========================================
# 5. 核心辅助函数定义
# ==========================================
def parse_hold_days(hold_period_str):
    """从持股周期字符串中提取天数"""
    if not hold_period_str or str(hold_period_str).strip().lower() in ['n/a', 'nan', '坚决空仓', '观望']:
        return None
    nums = re.findall(r'\d+', str(hold_period_str))
    if nums:
        return int(nums[-1])
    return None

def get_price_on_date(clean_ticker, target_date_str):
    """获取指定历史日期的收盘价"""
    if df_hist_all.empty:
        return None
    ticker_data = df_hist_all[df_hist_all['ts_code'] == clean_ticker].copy()
    if ticker_data.empty:
        return None
    ticker_data['trade_date'] = pd.to_datetime(ticker_data['trade_date']).dt.tz_localize(None)
    target_date = pd.to_datetime(target_date_str)
    valid = ticker_data[ticker_data['trade_date'] <= target_date]
    if valid.empty:
        return None
    return float(valid.iloc[-1]['close'])


# ==========================================
# 6. 读取历史归档记录以实现去重
# ==========================================
already_archived = set()
review_log_path = "review_history.csv"

if os.path.exists(review_log_path) and os.path.getsize(review_log_path) > 0:
    try:
        existing_review = pd.read_csv(review_log_path, on_bad_lines='skip')
        if {'Status', 'Ticker', 'Rec_Date'}.issubset(existing_review.columns):
            archived_rows = existing_review[existing_review['Status'].isin(
                ['已超期归档', '突发清仓暂停', '止损触发清仓', '周期到期清仓']
            )]
            already_archived = set(zip(archived_rows['Ticker'].astype(str), archived_rows['Rec_Date'].astype(str)))
            print(f"📌 已加载历史归档去重库，共包含 {len(already_archived)} 笔已处理记录。")
    except Exception as e:
        print(f"⚠️ 读取历史归档记录出错，将跳过部分去重校验: {e}")


# ==========================================
# 6.5 期权策略：读取 scan 独立期权账本并先行结算
# ==========================================
# option_picks 来自 trade_history.csv；若 scan 使用独立 option_trade_history.csv，则合并读取。
try:
    if os.path.exists(OPTION_LEDGER) and os.path.getsize(OPTION_LEDGER) > 0:
        option_external = pd.read_csv(OPTION_LEDGER, on_bad_lines="skip")
        if not option_external.empty:
            if "Date" not in option_external.columns:
                option_external["Date"] = option_external.get("Scan_Date", pd.NaT)
            option_external["Date"] = pd.to_datetime(option_external["Date"], errors="coerce")
            option_external = option_external[option_external.apply(_is_option_row, axis=1)]
            option_picks = pd.concat([option_picks, option_external], ignore_index=True, sort=False)
except Exception as e:
    print(f"⚠️ 独立期权账本加载失败: {e}")

option_active_list, option_closed_list = evaluate_option_strategies(option_picks, price_map_today)
append_option_review_history(option_closed_list)
option_kpis = build_option_kpis(option_active_list, option_closed_list)

# ==========================================
# 7. 遍历分组持仓并分类处理（活跃 vs 超期）
# ==========================================
active_list = []
expired_list = []
skipped_duplicate = 0

print("🔄 开始逐个标的进行持仓状态与期满归档判定...")
for orig_ticker, group in recent_picks.groupby('Ticker'):
    group = group.sort_values('Date')
    first_row = group.iloc[0]
    latest_row = group.iloc[-1]
    days_held = (get_us_time().replace(tzinfo=None) - first_row['Date']).days

    latest_tag = str(latest_row.get('Tag', '')).strip()
    
    if latest_tag in ['Trap_Warning', 'Forced_Exit', 'Stop_Loss_Hit', 'Period_Matured']:
        print(f"⏸️ 标的 [{orig_ticker}] 已被防守端标签处理（{latest_tag}），跳过常规追踪。")
        continue

    hold_period_str = 'N/A'
    stop_loss = 'N/A'
    score_str = 'N/A'
    
    for _, r in group.iterrows():
        val = str(r.get('Hold_Period', 'N/A')).strip()
        if val not in ['N/A', 'nan', '', '坚决空仓']:
            hold_period_str = r['Hold_Period']
            break
            
    for _, r in group.iterrows():
        val = str(r.get('Stop_Loss', 'N/A')).strip()
        if val not in ['N/A', 'nan', '', '坚决空仓', '绝对规避', '观望']:
            stop_loss = r['Stop_Loss']
            break
            
    for _, r in group.iterrows():
        val = str(r.get('Score', 'N/A')).strip()
        if val not in ['N/A', 'nan', '']:
            score_str = r['Score']
            break

    hold_days = parse_hold_days(hold_period_str)
    clean_t = clean_map.get(orig_ticker, orig_ticker)
    
    try:
        rec_price = float(first_row.get('Price', first_row.get('Close_Price', 0)))
    except:
        rec_price = 0.0

    if hold_days is None:
        print(f"⚠️ 标的 [{orig_ticker}] 持股周期为 N/A，仅加入活跃列表追踪，不触发到期归档。")
        rec_date_str = first_row['Date'].strftime('%Y-%m-%d')
        cur_price = price_map_today.get(clean_t) or get_price_on_date(clean_t, get_us_time().strftime('%Y-%m-%d')) or rec_price
        pnl = round((cur_price - rec_price) / rec_price * 100, 2) if rec_price > 0 else 0
        active_list.append({
            "代码": orig_ticker,
            "名称": first_row.get('Name', orig_ticker),
            "标签": latest_tag,
            "推荐评分": score_str,
            "持股周期建议": "待定(N/A)",
            "止损价": stop_loss,
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "现价": cur_price,
            "持仓天数": days_held,
            "剩余天数": "N/A",
            "当前盈亏(%)": pnl,
            "系统连续推荐次数": len(group),
        })
        continue

    rec_date_str = first_row['Date'].strftime('%Y-%m-%d')
    maturity_date_dt = first_row['Date'] + datetime.timedelta(days=hold_days)
    maturity_date = maturity_date_dt.strftime('%Y-%m-%d')

    if maturity_date_dt.replace(tzinfo=None) <= get_us_time().replace(tzinfo=None):
        if (str(orig_ticker), rec_date_str) in already_archived:
            skipped_duplicate += 1
            continue

        maturity_price = get_price_on_date(clean_t, maturity_date)
        maturity_pnl = round(((maturity_price - rec_price) / rec_price) * 100, 2) if maturity_price and rec_price > 0 else None

        expired_list.append({
            "代码": orig_ticker,
            "名称": first_row.get('Name', orig_ticker),
            "标签": latest_tag,
            "推荐评分": score_str,
            "持股周期建议": hold_period_str,
            "止损价": stop_loss,
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "期满日": maturity_date,
            "期满日价格": maturity_price if maturity_price else "无数据",
            "期满日盈亏(%)": maturity_pnl if maturity_pnl is not None else "无数据",
            "持仓天数": days_held,
            "系统连续推荐次数": len(group),
        })
    else:
        cur_price = price_map_today.get(clean_t)
        if not cur_price:
            continue

        cur_pnl = round(((cur_price - rec_price) / rec_price) * 100, 2) if rec_price > 0 else 0
        remaining = (maturity_date_dt.replace(tzinfo=None) - get_us_time().replace(tzinfo=None)).days

        active_list.append({
            "代码": orig_ticker,
            "名称": first_row.get('Name', orig_ticker),
            "标签": latest_tag,
            "推荐评分": score_str,
            "持股周期建议": hold_period_str,
            "止损价": stop_loss,
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "现价": cur_price,
            "持仓天数": days_held,
            "剩余天数": remaining,
            "当前盈亏(%)": cur_pnl,
            "系统连续推荐次数": len(group),
        })

if skipped_duplicate > 0:
    print(f"📌 去重机制生效：本次成功跳过 {skipped_duplicate} 条已归档的历史到期交易。")

print(f"📊 分类统计结果 -> 持仓中: {len(active_list)} 只 | 已超期(本次新归档): {len(expired_list)} 只")

if not active_list and not expired_list and not option_active_list and not option_closed_list and option_kpis["total"] == 0:
    print("⚠️ 提示：当前没有需要复盘的有效股票或期权策略，程序安全退出。")
    import sys
    sys.exit(0)

# ==========================================
# 8. 调用大模型生成风控报告内容
# ==========================================
print("🤖 正在调用 Claude 客户端生成美股盘后风控审查与策略复盘报告...")
client = anthropic.Anthropic(
    api_key=os.environ.get("CLAWSOCKET_API_KEY"),
    base_url=os.environ.get("CLAWSOCKET_BASE_URL")
)

prompt = f'''
你是顶级量化风控总监。以下是今日需要复盘的美股标的数据：

【持仓中（周期内，需要给出风控指令）】：
{active_list}

【已超期（本次新归档，只做策略复盘评价，不需要风控指令）】：
{expired_list}

【期权策略（scan→review 独立结算）】：
- 持仓中：{option_active_list}
- 本次新结算：{option_closed_list}
- 历史期权胜率：{option_kpis["win_rate"]:.2f}%
- Call胜率：{option_kpis["call_wr"]:.2f}%（{option_kpis["call_count"]}笔）
- Put胜率：{option_kpis["put_wr"]:.2f}%（{option_kpis["put_count"]}笔）
- 平均盈利：{option_kpis["avg_win"]:.2f}%
- 平均亏损：{option_kpis["avg_loss"]:.2f}%
- Profit Factor：{option_kpis["profit_factor"] if option_kpis["profit_factor"] != float("inf") else "∞"}
- 单笔期望收益：{option_kpis["expectancy"]:.2f}%
- 止损率：{option_kpis["stop_rate"]:.2f}%

在风控判断或策略复盘时，请结合推荐评分进行验证：高分票（80分以上）如果出现明显亏损，需要特别指出"高信心预期未兑现"；低分票（60分以下）如果反而盈利良好，也需要指出"评分体系可能过于保守"。

请严格按以下 HTML 骨架输出复盘报告（直出HTML，禁加markdown框，盈利标红，亏损标绿）：

<div style="background: #eceff1; border-left: 6px solid #455a64; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #263238;">⚖️ 盘后总体风控审查</h3>
    <p>(总结持仓中标的整体盈亏状况，以及本次新归档标的的策略胜率评估，特别指出评分与实际表现是否存在明显反差)</p>
</div>

<h2 style="color: #1565c0; border-bottom: 2px solid #1565c0; padding-bottom: 5px;">📊 持仓中 - 风控纪律核对单</h2>
<div style="background: #fff; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
    <h3 style="margin: 0 0 10px 0;">[首次推荐日] | [股票名称] ([代码]) | 评分[推荐评分]/100 | 系统连续推荐[N]次 | 还剩[剩余天数]天到期</h3>
    <p><b>持股周期建议:</b> [持股周期建议] | <b>止损位:</b> [止损价]</p>
    <p><b>买入成本:</b> $[首次推荐价] ➔ <b>现价:</b> $[现价] | <b>当前盈亏:</b> <span style="font-weight:bold; color:[盈利#d32f2f/亏损#388e3c];">[当前盈亏(%)]%</span></p>
    <p><span style="background: #607d8b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 12px;">风控动作指令</span>
    (判断：现价是否跌破止损位？给出持有/止损/减仓指令)</p>
</div>

<h2 style="color: #37474f; border-bottom: 2px solid #cfd8dc; padding-bottom: 5px; margin-top: 40px;">📁 已超期归档 - 策略复盘评价</h2>
<div style="background: #f5f5f5; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #e0e0e0;">
    <h3 style="margin: 0 0 10px 0;">[首次推荐日] | [股票名称] ([代码]) | 评分[推荐评分]/100 | 期满日:[期满日]</h3>
    <p><b>持股周期建议:</b> [持股周期建议] | <b>止损位:</b> [止损价]</p>
    <p><b>买入成本:</b> $[首次推荐价] → <b>期满日价格:</b> $[期满日价格] | <b>策略实际盈亏:</b> <span style="font-weight:bold; color:[盈利#d32f2f/亏损#388e3c];">[期满日盈亏(%)]%</span></p>
    <p><span style="background: #455a64; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 12px;">策略复盘</span>
    (评价这次策略是否成功，归因分析盈亏原因)</p>
</div>

【极其重要】直接输出HTML代码，第一个字符必须是 < 符号，绝对不要输出任何思考过程。
'''

ai_html = ""
with client.messages.stream(
    model=TARGET_MODEL,
    max_tokens=30000,
    temperature=0.1,
    messages=[{"role": "user", "content": prompt}]
) as stream:
    for text in stream.text_stream:
        ai_html += text

ai_html = ai_html.replace("```html", "").replace("```", "").strip()

html_start = ai_html.find("<div")
if html_start > 0:
    print(f"⚠️ 警告：检测到 AI 输出前置了 {html_start} 字符的非 HTML 内容，已自动切片丢弃。")
    ai_html = ai_html[html_start:]

# ==========================================
# 9. 写入归档记录至 review_history.csv
# ==========================================
review_log = "review_history.csv"
new_header = "Review_Date,Ticker,Name,Tag,Rec_Date,Rec_Price,Cur_Price,Days_Held,PnL_Pct,Maturity_PnL,Hold_Period,Stop_Loss,Rec_Count,Status,Score\n"
review_file_exists = os.path.exists(review_log) and os.path.getsize(review_log) > 0
review_need_header = not review_file_exists

if review_file_exists:
    with open(review_log, "r", encoding="utf-8") as f:
        review_lines = f.readlines()
    if review_lines and "Score" not in review_lines[0]:
        review_lines[0] = new_header
        with open(review_log, "w", encoding="utf-8") as f:
            f.writelines(review_lines)
        print("📌 历史复盘日志表头已自动升级更新。")

try:
    with open(review_log, "a", encoding="utf-8") as f:
        if review_need_header:
            f.write(new_header)
        review_date = get_us_time().strftime('%Y-%m-%d')

        for item in active_list:
            f.write(f"{review_date},{item['代码']},{item['名称']},{item['标签']},{item['首次推荐日']},{item['首次推荐价']},{item['现价']},{item['持仓天数']},{item['当前盈亏(%)']},,{item['持股周期建议']},{item['止损价']},{item['系统连续推荐次数']},持仓中,{item['推荐评分']}\n")

        for item in expired_list:
            maturity_pnl = item['期满日盈亏(%)'] if item['期满日盈亏(%)'] != "无数据" else ""
            f.write(f"{review_date},{item['代码']},{item['名称']},{item['标签']},{item['首次推荐日']},{item['首次推荐价']},{item['期满日价格']},{item['持仓天数']},{maturity_pnl},{maturity_pnl},{item['持股周期建议']},{item['止损价']},{item['系统连续推荐次数']},已超期归档,{item['推荐评分']}\n")

    print("✅ 成功将本次复盘状态写入 review_history.csv 文件。")
except Exception as e:
    print(f"❌ 错误：复盘历史数据写入失败: {e}")

# ==========================================
# 10. 程序化 KPI 指标计算与 HTML 仪表盘渲染
# ==========================================
print("📈 正在计算核心 KPI 指标并组装 HTML 仪表盘...")
historical_closed = []
_INVALID_H = {'', 'n/a', 'nan', 'none'}

if os.path.exists(review_log) and os.path.getsize(review_log) > 0:
    try:
        existing_review = pd.read_csv(review_log, on_bad_lines='skip')
        closed_rows = existing_review[existing_review['Status'].isin(['已超期归档', '突发清仓暂停', '止损触发清仓', '周期到期清仓'])]
        for _, r in closed_rows.iterrows():
            try:
                pnl_val = r['PnL_Pct']
                if pd.notna(pnl_val) and str(pnl_val).strip().lower() not in _INVALID_H:
                    pnl = float(pnl_val)
                else:
                    pnl_mat = r['Maturity_PnL']
                    if pd.notna(pnl_mat) and str(pnl_mat).strip().lower() not in _INVALID_H:
                        pnl = float(pnl_mat)
                    else:
                        continue
            except:
                continue
                
            prevented = 0.0
            try:
                sl_val = str(r.get('Stop_Loss', 'N/A')).strip()
                cur_val = str(r.get('Cur_Price', 'N/A')).strip()
                if sl_val not in _INVALID_H and cur_val not in _INVALID_H:
                    sl_price = float(sl_val)
                    cur_price = float(cur_val)
                    prevented = round((sl_price - cur_price) / sl_price * 100, 2) if sl_price > 0 else 0.0
            except:
                pass
                
            historical_closed.append({
                'ticker': r.get('Ticker', ''),
                'name': r.get('Name', ''),
                'pnl': pnl,
                'prevented': prevented,
                'status': r.get('Status', '已超期归档')
            })
    except Exception as e:
        print(f"⚠️ 读取历史归档用于 KPI 计算时出错: {e}")

all_closed_trades = []
for h in historical_closed:
    all_closed_trades.append(h)
for item in expired_list:
    try:
        pnl = float(item['期满日盈亏(%)']) if item['期满日盈亏(%)'] != "无数据" else 0.0
    except:
        pnl = 0.0
    all_closed_trades.append({
        'ticker': item['代码'], 'name': item['名称'], 'pnl': pnl,
        'prevented': 0.0, 'status': '已超期归档'
    })

active_count = len(active_list)
closed_count = len(all_closed_trades)
total_count = active_count + closed_count

active_wins = sum(1 for x in active_list if isinstance(x['当前盈亏(%)'], (int, float)) and x['当前盈亏(%)'] > 0)
active_win_rate = (active_wins / active_count * 100) if active_count > 0 else 0.0

closed_wins = sum(1 for x in all_closed_trades if x['pnl'] > 0)
closed_win_rate = (closed_wins / closed_count * 100) if closed_count > 0 else 0.0

effective_risk = sum(1 for x in all_closed_trades if x['prevented'] >= -2.0)
risk_rate = (effective_risk / closed_count * 100) if closed_count > 0 else 0.0

# 美股超级赢家阈值设定为 50%
super_threshold = 50.0
all_pnl_list = [x['当前盈亏(%)'] for x in active_list if isinstance(x['当前盈亏(%)'], (int, float))] + [x['pnl'] for x in all_closed_trades]
super_winners = [p for p in all_pnl_list if p >= super_threshold]
super_winner_contribution = sum(super_winners)

other_winners = [p for p in all_pnl_list if 0.0 < p < super_threshold]
other_winner_avg = (sum(other_winners) / len(other_winners)) if other_winners else 0.0

losers = [p for p in all_pnl_list if p < 0.0]
loser_avg = (sum(losers) / len(losers)) if losers else 0.0

kpi_html = f"""
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-bottom: 20px;">
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #1565c0;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">📊 总推荐笔数</div>
        <div style="font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 5px;">{total_count}</div>
        <div style="font-size: 12px; color: #95a5a6;">活跃持仓 {active_count} 笔 · 历史归档 {closed_count} 笔</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #2ecc71;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">📈 活跃持仓胜率</div>
        <div style="font-size: 24px; font-weight: bold; color: #2ecc71; margin-bottom: 5px;">{active_win_rate:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">{active_wins} 赢 / {active_count - active_wins} 亏</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #e67e22;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">📉 已归档实现胜率</div>
        <div style="font-size: 24px; font-weight: bold; color: #e67e22; margin-bottom: 5px;">{closed_win_rate:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">{closed_wins} 赢 / {closed_count - closed_wins} 亏</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #95a5a6;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">🛡️ 风控拦截率</div>
        <div style="font-size: 24px; font-weight: bold; color: #95a5a6; margin-bottom: 5px;">{risk_rate:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">{effective_risk}/{closed_count} 次避险离场有效防范深度回撤</div>
    </div>
</div>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-bottom: 25px;">
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #9b59b6;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">🏆 超级赢家贡献</div>
        <div style="font-size: 24px; font-weight: bold; color: #9b59b6; margin-bottom: 5px;">+{super_winner_contribution:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">超级赢家(>{super_threshold}%)累计涨幅</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #1abc9c;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">💰 其余盈利平均</div>
        <div style="font-size: 24px; font-weight: bold; color: #1abc9c; margin-bottom: 5px;">+{other_winner_avg:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">扣除超级赢家后的盈利均值</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #e74c3c;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">⚠️ 亏损标的平均</div>
        <div style="font-size: 24px; font-weight: bold; color: #e74c3c; margin-bottom: 5px;">{loser_avg:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">所有亏损标的的平均跌幅</div>
    </div>
</div>
"""


option_pf_display = "∞" if option_kpis["profit_factor"] == float("inf") else f"{option_kpis['profit_factor']:.2f}"
option_kpi_html = f"""
<h2 style="color:#6a1b9a;border-bottom:2px solid #6a1b9a;padding-bottom:5px;margin-top:30px;">🎯 期权策略胜率与结算表现（scan → review）</h2>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:15px;margin-bottom:20px;">
  <div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:15px;border-top:4px solid #6a1b9a;">
    <div style="font-size:13px;color:#777;">📈 期权已结算胜率</div>
    <div style="font-size:24px;font-weight:bold;">{option_kpis["win_rate"]:.2f}%</div>
    <div style="font-size:12px;color:#999;">{option_kpis["wins"]} 赢 / {option_kpis["losses"]} 亏 / {option_kpis["total"]} 笔</div>
  </div>
  <div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:15px;border-top:4px solid #1976d2;">
    <div style="font-size:13px;color:#777;">☎ CALL 胜率</div>
    <div style="font-size:24px;font-weight:bold;">{option_kpis["call_wr"]:.2f}%</div>
    <div style="font-size:12px;color:#999;">样本 {option_kpis["call_count"]} 笔</div>
  </div>
  <div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:15px;border-top:4px solid #ef6c00;">
    <div style="font-size:13px;color:#777;">🛡 PUT 胜率</div>
    <div style="font-size:24px;font-weight:bold;">{option_kpis["put_wr"]:.2f}%</div>
    <div style="font-size:12px;color:#999;">样本 {option_kpis["put_count"]} 笔</div>
  </div>
  <div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:15px;border-top:4px solid #2e7d32;">
    <div style="font-size:13px;color:#777;">💰 Profit Factor</div>
    <div style="font-size:24px;font-weight:bold;">{option_pf_display}</div>
    <div style="font-size:12px;color:#999;">单笔期望 {option_kpis["expectancy"]:+.2f}%</div>
  </div>
  <div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:15px;border-top:4px solid #c62828;">
    <div style="font-size:13px;color:#777;">🛑 期权止损率</div>
    <div style="font-size:24px;font-weight:bold;">{option_kpis["stop_rate"]:.2f}%</div>
    <div style="font-size:12px;color:#999;">止损 {option_kpis["stop_count"]} 笔</div>
  </div>
  <div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:15px;border-top:4px solid #455a64;">
    <div style="font-size:13px;color:#777;">📦 当前期权策略</div>
    <div style="font-size:24px;font-weight:bold;">{option_kpis["active_count"]}</div>
    <div style="font-size:12px;color:#999;">当前浮盈胜率 {option_kpis["active_wr"]:.2f}%</div>
  </div>
</div>
"""

full_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f4f6f8; padding: 20px; }}
    .card {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); max-width: 1200px; margin: 0 auto; }}
</style></head>
<body>
    <div class='card'>
        <h2 style='color: #2c3e50; margin-top: 0; margin-bottom: 20px; font-size: 26px; border-bottom: 3px solid #1565c0; padding-bottom: 10px; display: flex; align-items: center; gap: 10px;'>
            <span>📊 美股盘后复盘与风控审查报告</span>
        </h2>
        {kpi_html}
        {option_kpi_html}
        {ai_html}
    </div>
</body></html>"""

# ==========================================
# 11. 邮件发送模块
# ==========================================
def send_mail():
    """发送复盘报告邮件"""
    acc = os.environ.get("EMAIL_ACCOUNT")
    pwd = os.environ.get("EMAIL_PASSWORD")
    owner_email = os.environ.get("TARGET_EMAILS") or os.environ.get("OWNER_EMAIL")
    
    if not acc or not pwd or not owner_email:
        print("⚠️ 邮件发送配置缺失（缺少 ACCOUNT/PASSWORD/TARGET_EMAILS），跳过邮件发送。报告已安全保存在本地。")
        return

    msg = MIMEMultipart()
    msg['From'] = acc
    msg['To'] = owner_email
    msg['Subject'] = f"【盘后清算】美股风控纪律与复盘 ({get_us_time().strftime('%Y-%m-%d')})"
    msg.attach(MIMEText(full_html, 'html', 'utf-8'))
    
    to_list = [e.strip() for e in owner_email.split(',')]
    
    try:
        print(f"📧 正在通过 SSL 连接发送邮件至: {owner_email} ...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(acc, pwd)
            s.sendmail(acc, to_list, msg.as_string())
            print(f"✅ 邮件发送成功！收件人: {owner_email}")
    except Exception as e:
        print(f"❌ 错误：邮件发送失败，异常原因: {e}")

# 执行邮件分发
send_mail()
print("🎉 美股盘后复盘与风控审查程序顺利执行完毕。")
