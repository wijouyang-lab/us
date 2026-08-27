# -*- coding: utf-8 -*-
"""
美股盘后复盘与风控审查引擎
- 硬止损（基于当日最低价，触及即止损）
- 期权持仓自动平仓（到期日≤今日）
- AI 生成风控报告（含股票 + 期权）
- 与 scan.py 的 pending 文件联动
- 今日新增标的纳入胜率统计
"""

import pandas as pd
import yfinance as yf
import datetime
import os
import glob
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic
import re
import sys
import json

# ==========================================
# 环境变量校验
# ==========================================
_missing_env = [k for k in ("CLAWSOCKET_API_KEY", "CLAWSOCKET_BASE_URL") if not os.environ.get(k)]
if _missing_env:
    print(f"致命错误：未检测到环境变量 {', '.join(_missing_env)}！请检查 GitHub Secrets 配置。")
    sys.exit(1)

# ==========================================
# 时区 & 周末检查
# ==========================================
US_TZ = datetime.timezone(datetime.timedelta(hours=-4))

def get_us_time():
    return datetime.datetime.now(US_TZ)

current_time = get_us_time()
if current_time.weekday() >= 5:
    print(f"当前为周末，休市，退出复盘。")
    sys.exit(0)

TARGET_MODEL = 'claude-opus-4-8'
print("=" * 50)
print("启动美股盘后复盘与风控审查引擎 (硬止损+期权联动版)")
print("=" * 50)

# ==========================================
# 0. 期权账本处理（与 scan.py 联动）
# ==========================================
OPTION_LOG_FILE = "option_strategies.csv"

def load_option_positions():
    if not os.path.exists(OPTION_LOG_FILE) or os.path.getsize(OPTION_LOG_FILE) == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(OPTION_LOG_FILE, keep_default_na=False)
        required = ['Ticker', 'OptionType', 'Strike', 'Expiry', 'EntryPrice', 'Status', 'EntryDate']
        for col in required:
            if col not in df.columns:
                df[col] = ''
        df = df[df['Status'] == 'Active'].copy()
        if not df.empty:
            df['Expiry'] = pd.to_datetime(df['Expiry'])
        return df
    except Exception as e:
        print(f"⚠️ 读取期权账本失败: {e}")
        return pd.DataFrame()

def close_option_position(row, close_price, close_date, reason):
    df = pd.read_csv(OPTION_LOG_FILE, keep_default_na=False)
    mask = (df['Ticker'] == row['Ticker']) & (df['Expiry'] == row['Expiry']) & (df['Status'] == 'Active')
    if mask.any():
        df.loc[mask, 'Status'] = 'Closed'
        df.loc[mask, 'Close_Date'] = close_date
        df.loc[mask, 'Close_Price'] = close_price
        qty = float(row.get('Quantity', 1)) * 100
        entry = float(row['EntryPrice'])
        if row['OptionType'] == 'CALL':
            pnl = (close_price - entry) * qty
        else:
            pnl = (entry - close_price) * qty
        df.loc[mask, 'PnL'] = round(pnl, 2)
        df.to_csv(OPTION_LOG_FILE, index=False, encoding='utf-8')
        print(f"🔒 [期权] {row['Ticker']} {row['OptionType']} {row['Strike']} 平仓，原因: {reason}，盈亏 ${pnl:.2f}")
        return pnl
    return 0.0

def process_options(price_map_today):
    df_opt = load_option_positions()
    if df_opt.empty:
        print("📋 无活跃期权持仓，跳过期权风控。")
        return []
    today = get_us_time().date()
    closed_records = []
    for _, row in df_opt.iterrows():
        expiry = row['Expiry'].date()
        if expiry <= today:
            underlying = row['Ticker']
            cur_price = price_map_today.get(underlying)
            if cur_price is None:
                try:
                    fi = yf.Ticker(underlying).fast_info
                    cur_price = fi.get("last_price") or fi.get("lastPrice")
                    if cur_price:
                        cur_price = float(cur_price)
                except:
                    cur_price = None
            if cur_price is None:
                print(f"⚠️ [期权] {underlying} 现价获取失败，跳过平仓")
                continue
            strike = float(row['Strike'])
            option_type = row['OptionType']
            if option_type == 'CALL':
                intrinsic = max(0, cur_price - strike)
            else:
                intrinsic = max(0, strike - cur_price)
            close_price = intrinsic
            reason = "价内行权" if intrinsic > 0 else "价外归零"
            pnl = close_option_position(row, close_price, today.strftime('%Y-%m-%d'), reason)
            closed_records.append({
                'ticker': underlying,
                'option_type': option_type,
                'strike': strike,
                'expiry': expiry.strftime('%Y-%m-%d'),
                'entry_price': float(row['EntryPrice']),
                'close_price': close_price,
                'pnl': pnl,
                'reason': reason
            })
    return closed_records

# ==========================================
# 1. 股票账本补充（从 pending 文件）
# ==========================================
def _recalibrate_stop_loss_us(stop_loss_str, scan_ref_price, real_open_price):
    try:
        s = str(stop_loss_str).strip()
        if not s or s.lower() in ('n/a', 'nan', 'none', '观望'):
            return stop_loss_str
        has_dollar = s.startswith('$')
        body = s.lstrip('$')
        nums = re.findall(r'\d+\.?\d*', body)
        if not nums:
            return stop_loss_str
        old_val = float(nums[0])
        ref = float(scan_ref_price)
        new_open = float(real_open_price)
        if ref <= 0 or new_open <= 0 or old_val <= 0:
            return stop_loss_str
        new_val = round(old_val * (new_open / ref), 2)
        return f"${new_val}" if has_dollar else str(new_val)
    except:
        return stop_loss_str

def get_live_quote_bootstrap(clean_ticker):
    try:
        fi = yf.Ticker(clean_ticker).fast_info
        open_p = float(fi.get("open", 0)) if fi.get("open") else None
        last_p = float(fi.get("last_price", 0)) if fi.get("last_price") else None
        return open_p, last_p
    except:
        return None, None

def _migrate_trade_history_add_close_price(log_file):
    if not (os.path.exists(log_file) and os.path.getsize(log_file) > 0):
        return
    with open(log_file, "r", encoding="utf-8") as f:
        old_lines = f.readlines()
    if not old_lines:
        return
    trailing_cols = ["Close_Price", "技术评分", "MACD金叉", "周线共振", "KDJ_J回升", "量能放大", "ATR_Pct", "周期共振"]
    missing_cols = [c for c in trailing_cols if c not in old_lines[0]]
    if not missing_cols:
        return
    migrated = [old_lines[0].rstrip("\n") + "," + ",".join(missing_cols) + "\n"]
    for line in old_lines[1:]:
        if not line.strip():
            continue
        migrated.append(line.rstrip("\n") + "," * len(missing_cols) + "\n")
    with open(log_file, "w", encoding="utf-8") as f:
        f.writelines(migrated)
    print(f"⚠️ 账本升级：增加列 {missing_cols}")

def _fetch_ohlc(tickers_clean, target_date_str):
    """返回 open_map, high_map, low_map, close_map"""
    open_map, high_map, low_map, close_map = {}, {}, {}, {}
    if not tickers_clean:
        return open_map, high_map, low_map, close_map
    target_dt = datetime.datetime.strptime(target_date_str, '%Y-%m-%d')
    start = (target_dt - datetime.timedelta(days=6)).strftime('%Y-%m-%d')
    end = (target_dt + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    try:
        hist_data = yf.download(tickers_clean, start=start, end=end, progress=False, auto_adjust=True, group_by='ticker')
    except:
        return open_map, high_map, low_map, close_map
    if hist_data is None or hist_data.empty:
        return open_map, high_map, low_map, close_map
    for t in tickers_clean:
        try:
            sub = hist_data[t] if len(tickers_clean) > 1 else hist_data
            sub = sub.dropna(subset=['Open', 'High', 'Low', 'Close'])
            if sub.empty:
                continue
            sub = sub[sub.index <= pd.Timestamp(target_date_str)]
            if sub.empty:
                continue
            last_row = sub.iloc[-1]
            open_map[t] = float(last_row['Open'])
            high_map[t] = float(last_row['High'])
            low_map[t]  = float(last_row['Low'])
            close_map[t] = float(last_row['Close'])
        except:
            continue
    return open_map, high_map, low_map, close_map

def supplement_us_stocks_from_pending():
    log_file = "trade_history.csv"
    pending_files = sorted(f for f in glob.glob("us_stocks_pending_*.csv") if not f.endswith(".processed"))
    if not pending_files:
        print("无待确认美股文件，跳过补充。")
        return
    print(f"发现 {len(pending_files)} 份待确认文件。")
    _migrate_trade_history_add_close_price(log_file)
    new_header_cols = ["Date", "Ticker", "Name", "Tag", "Score", "Price", "RSI", "Bias",
                       "Hold_Period", "Stop_Loss", "Exit_Date", "Exit_Price", "Status", "Close_Price",
                       "技术评分", "MACD金叉", "周线共振", "KDJ_J回升", "量能放大", "ATR_Pct", "周期共振"]
    new_header = ",".join(new_header_cols) + "\n"
    for pending_file in pending_files:
        m = re.search(r"us_stocks_pending_(\d{8})\.csv", pending_file)
        if not m:
            continue
        file_date_str = m.group(1)
        target_date_str = f"{file_date_str[:4]}-{file_date_str[4:6]}-{file_date_str[6:]}"
        is_today = (target_date_str == get_us_time().strftime('%Y-%m-%d'))
        print(f"处理 {pending_file}（交易日 {target_date_str}）")
        try:
            df_pending = pd.read_csv(pending_file)
            if df_pending.empty:
                os.rename(pending_file, f"{pending_file}.processed")
                continue
            us_tickers = df_pending['Ticker'].astype(str).unique().tolist()
            us_tickers_clean = [t.lstrip('$') for t in us_tickers]
            open_map, high_map, low_map, close_map = _fetch_ohlc(us_tickers_clean, target_date_str)
            df_existing = pd.DataFrame()
            if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
                df_existing = pd.read_csv(log_file, on_bad_lines='skip')
                df_existing['Date'] = pd.to_datetime(df_existing['Date'])
            new_records = []
            missing_price_tickers = []
            for _, row in df_pending.iterrows():
                ticker = str(row['Ticker'])
                ticker_clean = ticker.lstrip('$')
                if not df_existing.empty:
                    existing = df_existing[
                        (df_existing['Date'] == pd.to_datetime(target_date_str)) &
                        (df_existing['Ticker'] == ticker)
                    ]
                    if not existing.empty:
                        print(f"{ticker} 已在账本，跳过")
                        continue
                open_price = open_map.get(ticker_clean)
                close_price = close_map.get(ticker_clean)
                if (open_price is None or close_price is None) and is_today:
                    live_open, live_last = get_live_quote_bootstrap(ticker_clean)
                    if open_price is None:
                        open_price = live_open
                    if close_price is None:
                        close_price = live_last or live_open
                if open_price is None or close_price is None:
                    missing_price_tickers.append(ticker)
                calibrated_stop_loss = row.get('Stop_Loss', 'N/A')
                if open_price is not None:
                    calibrated_stop_loss = _recalibrate_stop_loss_us(
                        row.get('Stop_Loss', 'N/A'), row.get('Scan_Ref_Price'), open_price
                    )
                new_records.append({
                    'Date': target_date_str,
                    'Ticker': ticker,
                    'Name': row.get('Name', ''),
                    'Tag': row.get('Tag', ''),
                    'Score': row.get('Score', 'N/A'),
                    'Price': '' if open_price is None else open_price,
                    'RSI': row.get('RSI', ''),
                    'Bias': row.get('Bias', ''),
                    'Hold_Period': row.get('Hold_Period', 'N/A'),
                    'Stop_Loss': calibrated_stop_loss,
                    'Exit_Date': '',
                    'Exit_Price': '',
                    'Status': 'Active',
                    'Close_Price': '' if close_price is None else close_price,
                    '技术评分': row.get('技术评分', ''),
                    'MACD金叉': row.get('MACD金叉', ''),
                    '周线共振': row.get('周线共振', ''),
                    'KDJ_J回升': row.get('KDJ_J回升', ''),
                    '量能放大': row.get('量能放大', ''),
                    'ATR_Pct': row.get('ATR_Pct', ''),
                    '周期共振': row.get('周期共振', ''),
                })
            if missing_price_tickers:
                print(f"⚠️ 以下标的无价格: {missing_price_tickers}")
            if new_records:
                need_header = not os.path.exists(log_file) or os.path.getsize(log_file) == 0
                with open(log_file, "a", encoding="utf-8") as f:
                    if need_header:
                        f.write(new_header)
                    for record in new_records:
                        f.write(",".join(str(record[c]) for c in new_header_cols) + "\n")
                print(f"新增 {len(new_records)} 条记录")
            os.rename(pending_file, f"{pending_file}.processed")
        except Exception as e:
            print(f"❌ 处理 {pending_file} 出错: {e}")

supplement_us_stocks_from_pending()

# ==========================================
# 2. 加载股票账本
# ==========================================
log_file = "trade_history.csv"
if not os.path.exists(log_file):
    print("无交易账本，退出。")
    sys.exit(0)

try:
    df = pd.read_csv(log_file, keep_default_na=False)
    df['Date'] = pd.to_datetime(df['Date'])
    cutoff_date = get_us_time() - datetime.timedelta(days=30)
    recent_picks = df[df['Date'] >= cutoff_date.replace(tzinfo=None)].copy()
    if recent_picks.empty:
        print("最近30天无记录，退出。")
        sys.exit(0)
    print(f"加载最近30天记录 {len(recent_picks)} 行。")
except Exception as e:
    print(f"读取账本失败: {e}")
    sys.exit(1)

# ==========================================
# 3. 版本过滤
# ==========================================
_INVALID = {'', 'n/a', 'nan', 'none'}
for col in ['Hold_Period', 'Stop_Loss', 'Score']:
    if col not in recent_picks.columns:
        recent_picks[col] = ''
valid_mask = recent_picks['Hold_Period'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID)
recent_picks = recent_picks[valid_mask].copy()
if recent_picks.empty:
    print("无有效持仓，退出。")
    sys.exit(0)

# ==========================================
# 4. 行情数据（需获取 OHLC）
# ==========================================
all_tickers_raw = recent_picks['Ticker'].unique().tolist()
clean_map = {t: t.lstrip('$') for t in all_tickers_raw}
clean_tickers = list(set(clean_map.values()))
print(f"获取 {len(clean_tickers)} 只标的价格与OHLC...")
price_map_today = {}
ohlc_map_today = {}

try:
    hist_data = yf.download(clean_tickers, period="60d", progress=False, auto_adjust=True, group_by='ticker')
    df_hist_all = pd.DataFrame()
    if len(clean_tickers) == 1:
        t = clean_tickers[0]
        if not hist_data.empty:
            temp = hist_data.copy()
            temp['ts_code'] = t
            temp['trade_date'] = temp.index
            df_hist_all = temp[['ts_code', 'trade_date', 'Open', 'High', 'Low', 'Close']]
            if not df_hist_all.empty:
                last = df_hist_all.iloc[-1]
                price_map_today[t] = float(last['Close'])
                ohlc_map_today[t] = {
                    'open': float(last['Open']),
                    'high': float(last['High']),
                    'low': float(last['Low']),
                    'close': float(last['Close'])
                }
    else:
        records = []
        for t in clean_tickers:
            try:
                sub = hist_data[t].dropna(subset=['Open', 'High', 'Low', 'Close'])
                if sub.empty:
                    continue
                for date, row in sub.iterrows():
                    records.append({
                        'ts_code': t,
                        'trade_date': date,
                        'open': float(row['Open']),
                        'high': float(row['High']),
                        'low': float(row['Low']),
                        'close': float(row['Close'])
                    })
                last = sub.iloc[-1]
                price_map_today[t] = float(last['Close'])
                ohlc_map_today[t] = {
                    'open': float(last['Open']),
                    'high': float(last['High']),
                    'low': float(last['Low']),
                    'close': float(last['Close'])
                }
            except:
                pass
        df_hist_all = pd.DataFrame(records)
    print(f"获取到 {len(price_map_today)} 只完整OHLC。")
except Exception as e:
    print(f"行情拉取失败: {e}")
    df_hist_all = pd.DataFrame()

# 补全缺失价格
for t in clean_tickers:
    if t not in price_map_today or price_map_today[t] is None:
        _, last = get_live_quote_bootstrap(t)
        if last:
            price_map_today[t] = last
            ohlc_map_today[t] = {'open': last, 'high': last, 'low': last, 'close': last}
        else:
            match_row = recent_picks[recent_picks['Ticker'] == t].iloc[-1]
            price_map_today[t] = float(match_row.get('Price', 0))
            ohlc_map_today[t] = {'open': price_map_today[t], 'high': price_map_today[t], 'low': price_map_today[t], 'close': price_map_today[t]}

# ==========================================
# 5. 处理期权平仓（依赖 price_map_today）
# ==========================================
option_closed_records = process_options(price_map_today)
if option_closed_records:
    print(f"✅ 期权平仓 {len(option_closed_records)} 笔。")

# ==========================================
# 6. 股票硬止损 & 分类
# ==========================================
def parse_hold_days(s):
    if not s or str(s).strip().lower() in ['n/a', 'nan', '坚决空仓', '观望']:
        return None
    nums = re.findall(r'\d+', str(s))
    return int(nums[-1]) if nums else None

def parse_stop_loss_price(s):
    s = str(s).strip().lstrip('$')
    if not s or s.lower() in ('', 'n/a', 'nan', 'none', '观望', '坚决空仓'):
        return None
    nums = re.findall(r'\d+\.?\d*', s)
    return float(nums[0]) if nums else None

def update_trade_history_status(ticker, buy_date_str, new_status, exit_price):
    if not os.path.exists(log_file):
        return
    df_orig = pd.read_csv(log_file, keep_default_na=False)
    # 【修复】确保 Exit_Date 和 Exit_Price 列为 object 类型，允许混合类型
    for col in ['Exit_Date', 'Exit_Price']:
        if col in df_orig.columns:
            df_orig[col] = df_orig[col].astype(object)
    mask = (df_orig['Ticker'] == ticker) & (df_orig['Date'] == buy_date_str) & (df_orig['Status'] == 'Active')
    if mask.any():
        df_orig.loc[mask, 'Status'] = new_status
        df_orig.loc[mask, 'Exit_Date'] = get_us_time().strftime('%Y-%m-%d')
        df_orig.loc[mask, 'Exit_Price'] = exit_price
        df_orig.to_csv(log_file, index=False, encoding='utf-8')
        print(f"✅ 更新 {ticker} 状态为 {new_status}，退出价 {exit_price}")

# 加载历史归档去重
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
            print(f"历史归档 {len(already_archived)} 条。")
    except:
        pass

active_list = []
expired_list = []
stopped_list = []
skipped_duplicate = 0

print("开始股票风控检查（触及即止损，基于当日最低价）...")
for orig_ticker, group in recent_picks.groupby('Ticker'):
    group = group.sort_values('Date')
    first_row = group.iloc[0]
    latest_row = group.iloc[-1]
    days_held = (get_us_time().replace(tzinfo=None) - first_row['Date']).days
    latest_tag = str(latest_row.get('Tag', '')).strip()
    if latest_tag in ['Trap_Warning', 'Forced_Exit', 'Stop_Loss_Hit', 'Period_Matured']:
        continue

    hold_period_str = 'N/A'
    stop_loss_str = 'N/A'
    score_str = 'N/A'
    for _, r in group.iterrows():
        val = str(r.get('Hold_Period', 'N/A')).strip()
        if val not in ['N/A', 'nan', '', '坚决空仓']:
            hold_period_str = r['Hold_Period']
            break
    for _, r in group.iterrows():
        val = str(r.get('Stop_Loss', 'N/A')).strip()
        if val not in ['N/A', 'nan', '', '坚决空仓', '绝对规避', '观望']:
            stop_loss_str = r['Stop_Loss']
            break
    for _, r in group.iterrows():
        val = str(r.get('Score', 'N/A')).strip()
        if val not in ['N/A', 'nan', '']:
            score_str = r['Score']
            break

    hold_days = parse_hold_days(hold_period_str)
    if hold_days is None:
        continue

    clean_t = clean_map.get(orig_ticker, orig_ticker)
    rec_price = float(first_row.get('Price', first_row.get('Close_Price', 0)))
    rec_date_str = first_row['Date'].strftime('%Y-%m-%d')

    # 获取今日 OHLC
    ohlc = ohlc_map_today.get(clean_t)
    if ohlc is None:
        cur_price = price_map_today.get(clean_t, rec_price)
        ohlc = {'open': cur_price, 'high': cur_price, 'low': cur_price, 'close': cur_price}
    today_low = ohlc['low']
    cur_price = ohlc['close']

    # === 硬止损检查（触及即止损，基于最低价） ===
    stop_loss_num = parse_stop_loss_price(stop_loss_str)
    if stop_loss_num is not None and today_low <= stop_loss_num:
        exit_price = stop_loss_num
        pnl_pct = round(((exit_price - rec_price) / rec_price) * 100, 2) if rec_price > 0 else 0
        stopped_list.append({
            "代码": orig_ticker,
            "名称": first_row.get('Name', orig_ticker),
            "标签": latest_tag,
            "推荐评分": score_str,
            "持股周期建议": hold_period_str,
            "止损价": stop_loss_str,
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "止损触发日": get_us_time().strftime('%Y-%m-%d'),
            "止损结算价": exit_price,
            "止损盈亏(%)": pnl_pct,
            "持仓天数": days_held,
            "系统连续推荐次数": len(group),
            "触发方式": "盘中最低价触及止损"
        })
        update_trade_history_status(orig_ticker, rec_date_str, 'Stop_Loss_Hit', exit_price)
        continue

    # === 到期检查 ===
    maturity_date_dt = first_row['Date'] + datetime.timedelta(days=hold_days)
    if maturity_date_dt.replace(tzinfo=None) <= get_us_time().replace(tzinfo=None):
        if (str(orig_ticker), rec_date_str) in already_archived:
            skipped_duplicate += 1
            continue
        if not df_hist_all.empty:
            ticker_hist = df_hist_all[df_hist_all['ts_code'] == clean_t].copy()
            if not ticker_hist.empty:
                ticker_hist['trade_date'] = pd.to_datetime(ticker_hist['trade_date']).dt.tz_localize(None)
                target_dt = pd.to_datetime(maturity_date_dt.strftime('%Y-%m-%d'))
                valid = ticker_hist[ticker_hist['trade_date'] <= target_dt]
                if not valid.empty:
                    maturity_price = float(valid.iloc[-1]['close'])
                else:
                    maturity_price = None
            else:
                maturity_price = None
        else:
            maturity_price = None
        maturity_pnl = round(((maturity_price - rec_price) / rec_price) * 100, 2) if maturity_price and rec_price > 0 else None
        expired_list.append({
            "代码": orig_ticker,
            "名称": first_row.get('Name', orig_ticker),
            "标签": latest_tag,
            "推荐评分": score_str,
            "持股周期建议": hold_period_str,
            "止损价": stop_loss_str,
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "期满日": maturity_date_dt.strftime('%Y-%m-%d'),
            "期满日价格": maturity_price if maturity_price else "无数据",
            "期满日盈亏(%)": maturity_pnl if maturity_pnl is not None else "无数据",
            "持仓天数": days_held,
            "系统连续推荐次数": len(group),
        })
    else:
        # 活跃
        is_new_today = (rec_date_str == get_us_time().strftime('%Y-%m-%d'))
        today_open_price = ohlc['open'] if is_new_today else None
        if is_new_today and today_open_price:
            rec_price = today_open_price
        remaining = (maturity_date_dt.replace(tzinfo=None) - get_us_time().replace(tzinfo=None)).days
        cur_pnl = round(((cur_price - rec_price) / rec_price) * 100, 2) if rec_price > 0 else 0
        active_list.append({
            "代码": orig_ticker,
            "名称": first_row.get('Name', orig_ticker),
            "标签": latest_tag,
            "推荐评分": score_str,
            "持股周期建议": hold_period_str,
            "止损价": stop_loss_str,
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "今日开盘价": round(today_open_price, 2) if today_open_price else ("N/A" if not is_new_today else round(cur_price, 2)),
            "现价": cur_price,
            "持仓天数": days_held,
            "剩余天数": remaining,
            "当前盈亏(%)": cur_pnl,
            "系统连续推荐次数": len(group),
            "今日新增": "是" if is_new_today else "否",
        })

print(f"股票分类：持仓 {len(active_list)}，超期 {len(expired_list)}，止损 {len(stopped_list)}，去重跳过 {skipped_duplicate}")

if not any([active_list, expired_list, stopped_list, option_closed_records]):
    print("无任何复盘数据，退出。")
    sys.exit(0)

# ==========================================
# 7. 写入归档（股票 + 期权）
# ==========================================
review_log = "review_history.csv"
new_header = "Review_Date,Ticker,Name,Tag,Rec_Date,Rec_Price,Cur_Price,Days_Held,PnL_Pct,Maturity_PnL,Hold_Period,Stop_Loss,Rec_Count,Status,Score,Option_Type,Strike,Expiry\n"
review_need_header = not (os.path.exists(review_log) and os.path.getsize(review_log) > 0)

if os.path.exists(review_log) and os.path.getsize(review_log) > 0:
    with open(review_log, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if lines and "Score" not in lines[0]:
        lines[0] = new_header
        with open(review_log, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print("review_history.csv 表头升级。")

try:
    with open(review_log, "a", encoding="utf-8") as f:
        if review_need_header:
            f.write(new_header)
        review_date = get_us_time().strftime('%Y-%m-%d')

        for item in active_list:
            f.write(f"{review_date},{item['代码']},{item['名称']},{item['标签']},{item['首次推荐日']},{item['首次推荐价']},{item['现价']},{item['持仓天数']},{item['当前盈亏(%)']},,{item['持股周期建议']},{item['止损价']},{item['系统连续推荐次数']},持仓中,{item['推荐评分']},,,,\n")
        for item in stopped_list:
            pnl = item['止损盈亏(%)']
            f.write(f"{review_date},{item['代码']},{item['名称']},{item['标签']},{item['首次推荐日']},{item['首次推荐价']},{item['止损结算价']},{item['持仓天数']},{pnl},{pnl},{item['持股周期建议']},{item['止损价']},{item['系统连续推荐次数']},止损触发清仓,{item['推荐评分']},,,,\n")
        for item in expired_list:
            pnl = item['期满日盈亏(%)'] if item['期满日盈亏(%)'] != "无数据" else ""
            f.write(f"{review_date},{item['代码']},{item['名称']},{item['标签']},{item['首次推荐日']},{item['首次推荐价']},{item['期满日价格']},{item['持仓天数']},{pnl},{pnl},{item['持股周期建议']},{item['止损价']},{item['系统连续推荐次数']},已超期归档,{item['推荐评分']},,,,\n")
        for opt in option_closed_records:
            name = opt['ticker']
            f.write(f"{review_date},{opt['ticker']},{name},期权平仓,{opt['expiry']},{opt['entry_price']},{opt['close_price']},,{opt['pnl']},{opt['pnl']},,{opt['strike']},,期权平仓,{opt['reason']},{opt['option_type']},{opt['strike']},{opt['expiry']}\n")
    print("归档记录写入成功。")
except Exception as e:
    print(f"归档写入失败: {e}")

# ==========================================
# 8. AI 报告生成
# ==========================================
print("调用 Claude 生成风控报告...")
client = anthropic.Anthropic(
    api_key=os.environ.get("CLAWSOCKET_API_KEY"),
    base_url=os.environ.get("CLAWSOCKET_BASE_URL")
)

prompt = f"""
你是顶级量化风控总监。以下是今日需要复盘的美股标的数据：

【股票持仓中（周期内，需给风控指令）】：
{str(active_list)}

【股票止损触发清仓（本次新归档，含触及即止损）】：
{str(stopped_list)}

【股票已超期（本次新归档）】：
{str(expired_list)}

【期权平仓记录（今日自动平仓）】：
{str(option_closed_records)}

在分析时注意：
- 高分票（80以上）若亏损需指出高预期未兑现；低分票（60以下）若盈利需指出评分可能保守。
- 今日新增标的（今日新增=是）已有完整交易日数据，应计入正常盈亏分析。
- 止损触发标的已按止损价结算，请评价止损纪律执行情况（尤其触及即止损）。
- 期权平仓记录包含行权/归零结果，请点评期权策略的有效性。

请严格按以下 HTML 骨架输出报告（直出 HTML，不加 markdown 框，盈利红字，亏损绿字）：

<div style="background: #eceff1; border-left: 6px solid #455a64; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #263238;">盘后总体风控审查</h3>
    <p>（总结今日整体表现，包括股票止损/超期数量、期权平仓盈亏，并点评评分体系有效性，尤其提及触及即止损的执行情况）</p>
</div>

<h2 style="color: #1565c0; border-bottom: 2px solid #1565c0;">持仓中 - 风控纪律核对单</h2>
（按原模板循环输出 active_list 卡片，包含风控动作指令）

<h2 style="color: #c62828; border-bottom: 2px solid #c62828;">止损触发清仓 - 策略复盘</h2>
（循环输出 stopped_list 卡片，注明触发方式）

<h2 style="color: #37474f; border-bottom: 2px solid #cfd8dc;">已超期归档 - 策略复盘评价</h2>
（循环输出 expired_list 卡片）

<h2 style="color: #6a1b9a; border-bottom: 2px solid #6a1b9a;">期权持仓风控 - 平仓复盘</h2>
（循环输出 option_closed_records 卡片）

【输出纪律】直接输出 HTML，第一个字符必须是 <，不要输出任何思考过程。
"""

ai_html = ""
with client.messages.stream(
    model=TARGET_MODEL,
    max_tokens=30000,
    messages=[{"role": "user", "content": prompt}]
) as stream:
    for text in stream.text_stream:
        ai_html += text

ai_html = ai_html.replace("```html", "").replace("```", "").strip()
html_start = ai_html.find("<div")
if html_start > 0:
    print(f"⚠️ AI输出前置非HTML，截断")
    ai_html = ai_html[html_start:]

# ==========================================
# 9. KPI 计算
# ==========================================
print("计算 KPI...")
historical_closed = []
_INVALID_H = {'', 'n/a', 'nan', 'none'}
if os.path.exists(review_log) and os.path.getsize(review_log) > 0:
    try:
        existing_review = pd.read_csv(review_log, on_bad_lines='skip')
        closed_rows = existing_review[existing_review['Status'].isin(['已超期归档', '突发清仓暂停', '止损触发清仓', '周期到期清仓', '期权平仓'])]
        for _, r in closed_rows.iterrows():
            try:
                pnl = float(r['PnL_Pct']) if r['PnL_Pct'] not in _INVALID_H else float(r['Maturity_PnL'])
            except:
                continue
            historical_closed.append({
                'ticker': r.get('Ticker', ''),
                'name': r.get('Name', ''),
                'pnl': pnl,
                'status': r.get('Status', '已超期归档')
            })
    except:
        pass

# 合并本次
for item in stopped_list:
    historical_closed.append({'ticker': item['代码'], 'name': item['名称'], 'pnl': item['止损盈亏(%)'], 'status': '止损触发清仓'})
for item in expired_list:
    pnl = float(item['期满日盈亏(%)']) if item['期满日盈亏(%)'] != "无数据" else 0.0
    historical_closed.append({'ticker': item['代码'], 'name': item['名称'], 'pnl': pnl, 'status': '已超期归档'})
for opt in option_closed_records:
    historical_closed.append({'ticker': opt['ticker'], 'name': opt['ticker'] + ' OPT', 'pnl': opt['pnl'], 'status': '期权平仓'})

closed_count = len(historical_closed)
active_count = len(active_list)
total_count = active_count + closed_count
new_today_count = sum(1 for x in active_list if x.get('今日新增') == '是')

# 【修复】今日新增的标的已有完整交易日数据，应纳入胜率统计
_win_rate_pool = [x for x in active_list if isinstance(x['当前盈亏(%)'], (int, float))]
active_wins = sum(1 for x in _win_rate_pool if x['当前盈亏(%)'] > 0)
active_win_rate = (active_wins / len(_win_rate_pool) * 100) if _win_rate_pool else 0.0

closed_wins = sum(1 for x in historical_closed if x['pnl'] > 0)
closed_win_rate = (closed_wins / closed_count * 100) if closed_count > 0 else 0.0

all_pnl = [x['当前盈亏(%)'] for x in active_list if isinstance(x['当前盈亏(%)'], (int, float))] + [x['pnl'] for x in historical_closed]
super_threshold = 50.0
super_winners = [p for p in all_pnl if p >= super_threshold]
super_contribution = sum(super_winners)
other_winners = [p for p in all_pnl if 0.0 < p < super_threshold]
other_avg = sum(other_winners) / len(other_winners) if other_winners else 0.0
losers = [p for p in all_pnl if p < 0.0]
loser_avg = sum(losers) / len(losers) if losers else 0.0

kpi_html = f"""
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
    <div style="background: #fff; border:1px solid #eef2f5; border-radius:10px; padding:15px; border-top:4px solid #1565c0;">
        <div style="font-size:13px; color:#7f8c8d;">总推荐笔数</div>
        <div style="font-size:24px; font-weight:bold;">{total_count}</div>
        <div style="font-size:12px;">持仓 {active_count}（含今日新增 {new_today_count}） · 了结 {closed_count}</div>
    </div>
    <div style="background: #fff; border:1px solid #eef2f5; border-radius:10px; padding:15px; border-top:4px solid #2ecc71;">
        <div style="font-size:13px; color:#7f8c8d;">持仓胜率</div>
        <div style="font-size:24px; font-weight:bold; color:#2ecc71;">{active_win_rate:.2f}%</div>
        <div style="font-size:12px;">{active_wins} 赢 / {len(_win_rate_pool)-active_wins} 亏（含今日新增 {new_today_count} 笔）</div>
    </div>
    <div style="background: #fff; border:1px solid #eef2f5; border-radius:10px; padding:15px; border-top:4px solid #e67e22;">
        <div style="font-size:13px; color:#7f8c8d;">已了结胜率</div>
        <div style="font-size:24px; font-weight:bold; color:#e67e22;">{closed_win_rate:.2f}%</div>
        <div style="font-size:12px;">{closed_wins} 赢 / {closed_count-closed_wins} 亏（含期权）</div>
    </div>
    <div style="background: #fff; border:1px solid #eef2f5; border-radius:10px; padding:15px; border-top:4px solid #9b59b6;">
        <div style="font-size:13px; color:#7f8c8d;">超级赢家贡献</div>
        <div style="font-size:24px; font-weight:bold; color:#9b59b6;">+{super_contribution:.2f}%</div>
        <div style="font-size:12px;">超级赢家(>{super_threshold}%)累计涨幅</div>
    </div>
    <div style="background: #fff; border:1px solid #eef2f5; border-radius:10px; padding:15px; border-top:4px solid #1abc9c;">
        <div style="font-size:13px; color:#7f8c8d;">其余盈利平均</div>
        <div style="font-size:24px; font-weight:bold; color:#1abc9c;">+{other_avg:.2f}%</div>
        <div style="font-size:12px;">除超级赢家外盈利均值</div>
    </div>
    <div style="background: #fff; border:1px solid #eef2f5; border-radius:10px; padding:15px; border-top:4px solid #e74c3c;">
        <div style="font-size:13px; color:#7f8c8d;">亏损平均</div>
        <div style="font-size:24px; font-weight:bold; color:#e74c3c;">{loser_avg:.2f}%</div>
        <div style="font-size:12px;">所有亏损标的平均跌幅</div>
    </div>
</div>
"""

full_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background: #f4f6f8; padding: 20px; }}
    .card {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); max-width: 1200px; margin: 0 auto; }}
</style></head><body>
    <div class='card'>
        <h2 style='color:#2c3e50; margin-bottom:20px; border-bottom:3px solid #1565c0; padding-bottom:10px;'>美股盘后复盘与风控审查报告（含期权）</h2>
        {kpi_html}
        {ai_html}
    </div>
</body></html>"""

# ==========================================
# 10. 邮件发送
# ==========================================
def send_mail():
    acc = os.environ.get("EMAIL_ACCOUNT")
    pwd = os.environ.get("EMAIL_PASSWORD")
    owner_email = os.environ.get("TARGET_EMAILS") or os.environ.get("OWNER_EMAIL")
    if not acc or not pwd or not owner_email:
        print("邮件配置缺失，报告已保存本地。")
        return
    msg = MIMEMultipart()
    msg['From'] = acc
    msg['To'] = owner_email
    msg['Subject'] = f"盘后清算 美股风控纪律与复盘 ({get_us_time().strftime('%Y-%m-%d')})"
    msg.attach(MIMEText(full_html, 'html', 'utf-8'))
    to_list = [e.strip() for e in owner_email.split(',')]
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(acc, pwd)
            s.sendmail(acc, to_list, msg.as_string())
            print(f"邮件发送成功至 {owner_email}")
    except Exception as e:
        print(f"邮件发送失败: {e}")

send_mail()
print("美股盘后复盘（含触及即止损 + 期权联动）执行完毕。")
