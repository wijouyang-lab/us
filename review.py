# -*- coding: utf-8 -*-
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

# 启动前置校验：AI 凭证（缺失则立即报错退出，避免跑完前面的复盘数据整理逻辑后才在AI调用阶段崩溃）
_missing_env = [k for k in ("CLAWSOCKET_API_KEY", "CLAWSOCKET_BASE_URL") if not os.environ.get(k)]
if _missing_env:
    print(f"致命错误：未检测到环境变量 {', '.join(_missing_env)}！请检查 GitHub Actions 仓库的 Secrets 配置（Settings → Secrets and variables → Actions），并确认 workflow yml 中已通过 env: 正确传递。")
    import sys; sys.exit(1)

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
print("启动美股盘后复盘与风控审查引擎 (全功能工程版)...")
print("=" * 50)

# ==========================================
# 1.5 补充美股成交记录（从盘前待确认文件）
# ==========================================
def _recalibrate_stop_loss_us(stop_loss_str, scan_ref_price, real_open_price):
    """
    止损位校准：Stop_Loss 的数字是 scan.py 在盘前用 Scan_Ref_Price（latest['Open']/['Close']，
    盘前参考价）算出来的兜底公式（参考价*(1+默认止损百分比)）。参考价和真实开盘价一旦有偏差，
    止损位这个"锚点"从一开始就偏了。这里按比例（真实开盘价/盘前参考价）平移止损位，保留原始
    "$XX.XX"格式，任何一步解析失败都原样返回。
    """
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
    except (ValueError, TypeError, ZeroDivisionError):
        return stop_loss_str


def get_live_quote_bootstrap(clean_ticker):
    """
    实时行情兜底（仅用于'今天'这份待确认文件、且当天全市场历史行情还没来得及发布的情况）。
    和下面第276行左右的 get_live_quote 是同一套逻辑，这里提前放一份是因为
    supplement_us_stocks_from_pending() 在文件最开头就会被调用，比原定义位置更早。
    """
    try:
        fi = yf.Ticker(clean_ticker).fast_info
        try:
            open_p = float(fi["open"])
        except Exception:
            open_p = None
        try:
            last_p = float(fi["last_price"])
        except Exception:
            last_p = None
        return open_p, last_p
    except Exception as e:
        print(f"实时行情兜底查询失败 [{clean_ticker}]: {e}")
        return None, None


def _migrate_trade_history_add_close_price(log_file):
    """
    trade_history.csv 表头升级：老数据没有 Close_Price 列，也没有 evolve.py 实际会读的
    5 个技术信号列（技术评分/MACD金叉/周线共振/KDJ_J回升/量能放大——这几个字段
    scan.py 早就算出来了，但从来没有接到 trade_history.csv 里，导致 evolve.py 里
    "技术信号有效性分析"和"技术评分分层胜率"这两部分一直是拿空值在跑），也没有
    ATR_Pct（新加的ATR动态止损用来算止损距离的波动率依据，不带上没法用evolve.py
    验证止损从固定-5%换成ATR动态算这件事到底有没有用）。
    全部加在表末尾，迁移很简单——每条老数据行末尾补齐对应数量的空字段即可。
    """
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
    print(f"⚠️ 检测到旧版trade_history.csv缺少 {missing_cols} 列，已自动升级表头并补齐 {len(migrated) - 1} 行历史数据（老数据这些列留空，不影响后续追踪）")


def _fetch_open_close(tickers_clean, target_date_str):
    """
    用 yfinance 拉取一批标的在 target_date_str（YYYY-MM-DD）当天的开盘价+收盘价。
    找不到当天数据（节假日/刚上市等）时会自动往前多取几天窗口兜底。
    返回 (open_map, close_map)，key 是去掉 $ 前缀的干净代码。
    """
    open_map, close_map = {}, {}
    if not tickers_clean:
        return open_map, close_map

    target_dt = datetime.datetime.strptime(target_date_str, '%Y-%m-%d')
    start = (target_dt - datetime.timedelta(days=6)).strftime('%Y-%m-%d')
    end = (target_dt + datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    try:
        hist_data = yf.download(tickers_clean, start=start, end=end, progress=False,
                                 auto_adjust=True, group_by='ticker')
    except Exception as e:
        print(f"⚠️ yfinance 批量拉取失败: {e}")
        return open_map, close_map

    if hist_data is None or hist_data.empty:
        return open_map, close_map

    for t in tickers_clean:
        try:
            sub = hist_data[t] if len(tickers_clean) > 1 else hist_data
            sub = sub.dropna(subset=['Open', 'Close'])
            if sub.empty:
                continue
            sub = sub[sub.index <= pd.Timestamp(target_date_str)]
            if sub.empty:
                continue
            last_row = sub.iloc[-1]
            open_map[t] = float(last_row['Open'])
            close_map[t] = float(last_row['Close'])
        except Exception:
            continue

    return open_map, close_map


def supplement_us_stocks_from_pending():
    """
    ✅ 【根因修复】原来的版本只找"今天"日期的待确认文件——一旦某天处理失败
    （比如 yfinance 临时抽风、网络问题等），那份文件就会永远留在原地、不会被
    后续任何一次运行重试。这里改成扫描所有还没带 .processed 后缀的待确认文件。

    ✅ 【根因修复二 · 更重要】原来这个函数写入 trade_history.csv 用的表头是
    "Date,Ticker,Name,Tag,Industry,Close_Price,Amount,Daily_Pct,Hold_Period,Stop_Loss,Score"
    （11列，是从A股版本照搬过来的），但 trade_history.csv 实际的表头早就是
    "Date,Ticker,Name,Tag,Score,Price,RSI,Bias,Hold_Period,Stop_Loss,Exit_Date,Exit_Price,Status"
    （13列，Active/Dropped 生命周期模型）。两边列名对不上，之前用旧函数追加的
    那几行（可以在 trade_history.csv 里看到 Score 显示成"科技"、Status 是空的）
    实际上是把 11 个值硬塞进 13 列表头，从第5列开始全部错位——Industry 的值
    "科技"顶替了 Score，Status 因为多出的2列直接空着，导致这些标的从未被
    识别为"持仓中"（下游所有逻辑都是按 Status=='Active' 来找持仓的）。

    这里改成按 trade_history.csv 真实的列结构来写，新增标的 Status 正确写成
    'Active'，Price 用盘后真实开盘价（而不是盘前的参考价），并新增一列
    Close_Price 记录当天真实收盘价。
    """
    log_file = "trade_history.csv"

    pending_files = sorted(
        f for f in glob.glob("us_stocks_pending_*.csv")
        if not f.endswith(".processed")
    )

    if not pending_files:
        print(f"[盘后补充] 未发现任何美股待确认文件，跳过美股补充。")
        return

    print(f"[盘后补充] 发现 {len(pending_files)} 份美股待确认文件（含历史遗留未处理的）：{pending_files}")

    _migrate_trade_history_add_close_price(log_file)
    new_header_cols = ["Date", "Ticker", "Name", "Tag", "Score", "Price", "RSI", "Bias",
                        "Hold_Period", "Stop_Loss", "Exit_Date", "Exit_Price", "Status", "Close_Price",
                        "技术评分", "MACD金叉", "周线共振", "KDJ_J回升", "量能放大", "ATR_Pct", "周期共振"]
    new_header = ",".join(new_header_cols) + "\n"

    for pending_file in pending_files:
        m = re.search(r"us_stocks_pending_(\d{8})\.csv", pending_file)
        if not m:
            print(f"⚠️ 无法从文件名解析交易日期，跳过: {pending_file}")
            continue
        file_date_str = m.group(1)
        target_date_str = f"{file_date_str[:4]}-{file_date_str[4:6]}-{file_date_str[6:]}"
        is_today = (target_date_str == get_us_time().strftime('%Y-%m-%d'))

        print(f"[盘后补充] 正在处理 {pending_file}（交易日 {target_date_str}）...")

        try:
            df_pending = pd.read_csv(pending_file)

            if df_pending.empty:
                print(f"{pending_file} 为空，直接标记为已处理。")
                os.rename(pending_file, f"{pending_file}.processed")
                continue

            us_tickers = df_pending['Ticker'].astype(str).unique().tolist()
            us_tickers_clean = [t.lstrip('$') for t in us_tickers]

            open_map, close_map = _fetch_open_close(us_tickers_clean, target_date_str)

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
                        print(f"{ticker} 已在账本中，跳过重复")
                        continue

                open_price = open_map.get(ticker_clean)
                close_price = close_map.get(ticker_clean)

                # 批量快照没有的话（新上市/停牌/数据延迟等），只有处理"今天"这份文件时
                # 用实时行情接口兜底（历史遗留文件对应的是过去的交易日，实时行情帮不上忙）
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
                print(f"⚠️ 以下标的未取到开盘价/收盘价，已按空值写入账本，建议后续手动核对: {missing_price_tickers}")

            if new_records:
                need_header = not os.path.exists(log_file) or os.path.getsize(log_file) == 0
                with open(log_file, "a", encoding="utf-8") as f:
                    if need_header:
                        f.write(new_header)
                    for record in new_records:
                        f.write(",".join(str(record[c]) for c in new_header_cols) + "\n")

                print(f"[盘后补充] {pending_file} 成功补充 {len(new_records)} 条美股成交记录（含开盘价+收盘价，Status=Active）")
            else:
                print(f"{pending_file} 中的美股都已在账本，无新增")

            processed_file = f"{pending_file}.processed"
            os.rename(pending_file, processed_file)
            print(f"{pending_file} 已处理，备份为 {processed_file}")

        except Exception as e:
            print(f"❌ 处理 {pending_file} 出错，保留原文件以便下次自动重试: {e}")


supplement_us_stocks_from_pending()

# ==========================================
# 2. 账本文件检查与加载
# ==========================================
log_file = "trade_history.csv"
if not os.path.exists(log_file):
    print(f"警告：未检测到交易账本文件 [{log_file}]，跳过本次复盘。")
    import sys
    sys.exit(0)

try:
    print(f"正在加载交易账本: {log_file} ...")
    df = pd.read_csv(log_file)
    df['Date'] = pd.to_datetime(df['Date'])

    cutoff_date = get_us_time() - datetime.timedelta(days=30)
    recent_picks = df[df['Date'] >= cutoff_date.replace(tzinfo=None)].copy()

    if recent_picks.empty:
        print("提示：最近 30 天内无任何操作记录，跳过复盘。")
        import sys
        sys.exit(0)
    print(f"成功加载最近 30 天交易记录，共计 {len(recent_picks)} 行原始数据。")
except Exception as e:
    print(f"错误：账本读取失败，异常原因: {e}")
    import sys
    sys.exit(1)

# ==========================================
# 3. 版本过滤与字段清洗校验
# ==========================================
print("正在进行版本过滤与字段合法性校验...")
_INVALID = {'', 'n/a', 'nan', 'none'}
for _col in ['Hold_Period', 'Stop_Loss', 'Score']:
    if _col not in recent_picks.columns:
        recent_picks[_col] = ''

_schema_valid = recent_picks['Hold_Period'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID)
_dropped = (~_schema_valid).sum()
if _dropped > 0:
    print(f"版本过滤提示：成功剔除 {_dropped} 条 Hold_Period 缺失的旧版本/不完整记录，不纳入本次复盘。")
recent_picks = recent_picks[_schema_valid].copy()

_no_score = recent_picks['Score'].astype(str).str.strip().str.lower().isin(_INVALID)
if _no_score.sum() > 0:
    tickers_no_score = recent_picks.loc[_no_score, 'Ticker'].tolist()
    print(f"提示：以下 {_no_score.sum()} 条记录 Score=N/A（可能是历史评分bug所致），仍会继续追踪：{tickers_no_score[:10]}")

_no_stoploss = recent_picks['Stop_Loss'].astype(str).str.strip().str.lower().isin(_INVALID)
if _no_stoploss.sum() > 0:
    tickers_no_sl = recent_picks.loc[_no_stoploss, 'Ticker'].tolist()
    print(f"警告：以下 {_no_stoploss.sum()} 条记录的 Stop_Loss 属性为 N/A，将继续追踪但无法进行精确止损价核查。涉及标的: {tickers_no_sl[:10]}")

if recent_picks.empty:
    print("警告：经过版本过滤后，无有效的新版本记录可供复盘，程序退出。")
    import sys
    sys.exit(0)

# ==========================================
# 4. 行情数据拉取与价格映射准备
# ==========================================
all_tickers_raw = recent_picks['Ticker'].unique().tolist()
clean_map = {t: t.lstrip('$') for t in all_tickers_raw}
clean_tickers = list(set(clean_map.values()))

print(f"正在通过 yfinance 批量拉取美股历史行情数据，标的列表: {clean_tickers}")
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
                    print(f"解析标的 {t} 历史行情出错: {sub_e}")
            df_hist_all = pd.DataFrame(records)
        print(f"行情数据拉取完毕，成功获取最新收盘价的标的数: {len(price_map_today)}")
    except Exception as e:
        print(f"严重错误：调用 yfinance 历史价格拉取失败: {e}")

# ==========================================
# 5. 核心辅助函数定义
# ==========================================
def parse_hold_days(hold_period_str):
    if not hold_period_str or str(hold_period_str).strip().lower() in ['n/a', 'nan', '坚决空仓', '观望']:
        return None
    nums = re.findall(r'\d+', str(hold_period_str))
    if nums:
        return int(nums[-1])
    return None

def get_price_on_date(clean_ticker, target_date_str):
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

def get_live_quote(clean_ticker):
    try:
        fi = yf.Ticker(clean_ticker).fast_info
        try:
            open_p = float(fi["open"])
        except Exception:
            open_p = None
        try:
            last_p = float(fi["last_price"])
        except Exception:
            last_p = None
        return open_p, last_p
    except Exception as e:
        print(f"实时行情兜底查询失败 [{clean_ticker}]: {e}")
        return None, None

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
            print(f"已加载历史归档去重库，共包含 {len(already_archived)} 笔已处理记录。")
    except Exception as e:
        print(f"读取历史归档记录出错，将跳过部分去重校验: {e}")

# ==========================================
# 7. 遍历分组持仓并分类处理（活跃 vs 超期）
# ==========================================
active_list = []
expired_list = []
skipped_duplicate = 0

print("开始逐个标的进行持仓状态与期满归档判定...")
for orig_ticker, group in recent_picks.groupby('Ticker'):
    group = group.sort_values('Date')
    first_row = group.iloc[0]
    latest_row = group.iloc[-1]
    days_held = (get_us_time().replace(tzinfo=None) - first_row['Date']).days

    latest_tag = str(latest_row.get('Tag', '')).strip()

    if latest_tag in ['Trap_Warning', 'Forced_Exit', 'Stop_Loss_Hit', 'Period_Matured']:
        print(f"标的 [{orig_ticker}] 已被防守端标签处理（{latest_tag}），跳过常规追踪。")
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
        print(f"标的 [{orig_ticker}] 持股周期为 N/A，按要求从复盘列表中剔除。")
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
        is_new_today = (rec_date_str == get_us_time().strftime('%Y-%m-%d'))
        today_open_price = None

        cur_price = price_map_today.get(clean_t)

        if not cur_price:
            cur_price = get_price_on_date(clean_t, get_us_time().strftime('%Y-%m-%d'))

        if not cur_price or is_new_today:
            live_open, live_last = get_live_quote(clean_t)
            today_open_price = live_open
            if not cur_price:
                cur_price = live_last or live_open

        if is_new_today and today_open_price:
            rec_price = today_open_price

        if not cur_price:
            print(f"标的 [{orig_ticker}] 现价/开盘价均获取失败，暂用推荐价代替显示，盈亏将显示为 0%。")
            cur_price = rec_price

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
            "今日开盘价": round(today_open_price, 2) if today_open_price else ("N/A" if not is_new_today else round(cur_price, 2)),
            "现价": cur_price,
            "持仓天数": days_held,
            "剩余天数": remaining,
            "当前盈亏(%)": cur_pnl,
            "系统连续推荐次数": len(group),
            "今日新增": "是" if is_new_today else "否",
        })

if skipped_duplicate > 0:
    print(f"去重机制生效：本次成功跳过 {skipped_duplicate} 条已归档的历史到期交易。")

print(f"分类统计结果 -> 持仓中: {len(active_list)} 只 | 已超期(本次新归档): {len(expired_list)} 只")

if not active_list and not expired_list:
    print("提示：当前没有需要复盘的有效标的，程序安全退出。")
    import sys
    sys.exit(0)

# ==========================================
# 8. 调用大模型生成风控报告内容
# ==========================================
print("正在调用 Claude 客户端生成美股盘后风控审查与策略复盘报告...")
client = anthropic.Anthropic(
    api_key=os.environ.get("CLAWSOCKET_API_KEY"),
    base_url=os.environ.get("CLAWSOCKET_BASE_URL")
)

prompt = (
    "你是顶级量化风控总监。以下是今日需要复盘的美股标的数据：\n\n"
    "【持仓中（周期内，需要给出风控指令）】：\n"
    + str(active_list) + "\n\n"
    "【已超期（本次新归档，只做策略复盘评价，不需要风控指令）】：\n"
    + str(expired_list) + "\n\n"
    "在风控判断或策略复盘时，请结合推荐评分进行验证：高分票（80分以上）如果出现明显亏损，"
    "需要特别指出高信心预期未兑现；低分票（60分以下）如果反而盈利良好，也需要指出评分体系可能过于保守。\n\n"
    "【今日新增标的特别说明】持仓列表中今日新增=是的标的是当天刚生成的全新推荐，"
    "现价为当天的开盘价/实时价，尚未经历完整交易日，几乎不会有真实盈亏。"
    "这类标的请勿按亏损/止损逻辑给风控指令，只需确认开盘价已正确入账，"
    "风控动作指令统一给新建仓，持有观察，明日起纳入正常止损监控，"
    "摘要中也不要把它们的 0% 波动算作高信心预期未兑现。\n\n"
    "请严格按以下 HTML 骨架输出复盘报告（直出HTML，禁加markdown框，盈利标红，亏损标绿）：\n\n"
    '<div style="background: #eceff1; border-left: 6px solid #455a64; padding: 20px; margin-bottom: 25px; border-radius: 8px;">\n'
    '    <h3 style="margin-top: 0; color: #263238;">盘后总体风控审查</h3>\n'
    '    <p>(总结持仓中标的整体盈亏状况，以及本次新归档标的的策略胜率评估，'
    '特别指出评分与实际表现是否存在明显反差；若有今日新增标的，在此提一句今日共新增几只)</p>\n'
    '</div>\n\n'
    '<h2 style="color: #1565c0; border-bottom: 2px solid #1565c0; padding-bottom: 5px;">持仓中 - 风控纪律核对单</h2>\n'
    '<div style="background: #fff; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">\n'
    '    <h3 style="margin: 0 0 10px 0;">'
    '[若今日新增=是则在最前面加一个 今日新增 徽章] [首次推荐日] | [股票名称] ([代码]) | '
    '评分[推荐评分]/100 | 系统连续推荐[N]次 | 还剩[剩余天数]天到期</h3>\n'
    '    <p><b>持股周期建议:</b> [持股周期建议] | <b>止损位:</b> [止损价]</p>\n'
    '    <p><b>买入成本:</b> $[首次推荐价] -> <b>现价:</b> $[现价]（今日开盘价 $[今日开盘价]） | '
    '<b>当前盈亏:</b> <span style="font-weight:bold; color:[盈利#d32f2f/亏损#388e3c];">[当前盈亏(%)]%</span></p>\n'
    '    <p><span style="background: #607d8b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 12px;">风控动作指令</span>\n'
    '    (今日新增标的：给新建仓，持有观察；其余标的：判断现价是否跌破止损位，给出持有/止损/减仓指令)</p>\n'
    '</div>\n\n'
    '<h2 style="color: #37474f; border-bottom: 2px solid #cfd8dc; padding-bottom: 5px; margin-top: 40px;">已超期归档 - 策略复盘评价</h2>\n'
    '<div style="background: #f5f5f5; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #e0e0e0;">\n'
    '    <h3 style="margin: 0 0 10px 0;">[首次推荐日] | [股票名称] ([代码]) | 评分[推荐评分]/100 | 期满日:[期满日]</h3>\n'
    '    <p><b>持股周期建议:</b> [持股周期建议] | <b>止损位:</b> [止损价]</p>\n'
    '    <p><b>买入成本:</b> $[首次推荐价] -> <b>期满日价格:</b> $[期满日价格] | '
    '<b>策略实际盈亏:</b> <span style="font-weight:bold; color:[盈利#d32f2f/亏损#388e3c];">[期满日盈亏(%)]%</span></p>\n'
    '    <p><span style="background: #455a64; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 12px;">策略复盘</span>\n'
    '    (评价这次策略是否成功，归因分析盈亏原因)</p>\n'
    '</div>\n\n'
    "【极其重要】直接输出HTML代码，第一个字符必须是 < 符号，绝对不要输出任何思考过程。"
)

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
    print(f"警告：检测到 AI 输出前置了 {html_start} 字符的非 HTML 内容，已自动切片丢弃。")
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
        print("历史复盘日志表头已自动升级更新。")

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

    print("成功将本次复盘状态写入 review_history.csv 文件。")
except Exception as e:
    print(f"错误：复盘历史数据写入失败: {e}")

# ==========================================
# 10. 程序化 KPI 指标计算与 HTML 仪表盘渲染
# ==========================================
print("正在计算核心 KPI 指标并组装 HTML 仪表盘...")
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
        print(f"读取历史归档用于 KPI 计算时出错: {e}")

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

new_today_count = sum(1 for x in active_list if x.get('今日新增') == '是')
_win_rate_pool = [x for x in active_list if x.get('今日新增') != '是']
active_wins = sum(1 for x in _win_rate_pool if isinstance(x['当前盈亏(%)'], (int, float)) and x['当前盈亏(%)'] > 0)
active_win_rate = (active_wins / len(_win_rate_pool) * 100) if _win_rate_pool else 0.0

closed_wins = sum(1 for x in all_closed_trades if x['pnl'] > 0)
closed_win_rate = (closed_wins / closed_count * 100) if closed_count > 0 else 0.0

effective_risk = sum(1 for x in all_closed_trades if x['prevented'] >= -2.0)
risk_rate = (effective_risk / closed_count * 100) if closed_count > 0 else 0.0

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
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">总推荐笔数</div>
        <div style="font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 5px;">{total_count}</div>
        <div style="font-size: 12px; color: #95a5a6;">活跃持仓 {active_count} 笔（含今日新增 {new_today_count} 笔） · 历史归档 {closed_count} 笔</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #2ecc71;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">活跃持仓胜率</div>
        <div style="font-size: 24px; font-weight: bold; color: #2ecc71; margin-bottom: 5px;">{active_win_rate:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">{active_wins} 赢 / {len(_win_rate_pool) - active_wins} 亏（不含今日新增 {new_today_count} 笔）</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #e67e22;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">已归档实现胜率</div>
        <div style="font-size: 24px; font-weight: bold; color: #e67e22; margin-bottom: 5px;">{closed_win_rate:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">{closed_wins} 赢 / {closed_count - closed_wins} 亏</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #95a5a6;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">风控拦截率</div>
        <div style="font-size: 24px; font-weight: bold; color: #95a5a6; margin-bottom: 5px;">{risk_rate:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">{effective_risk}/{closed_count} 次避险离场有效防范深度回撤</div>
    </div>
</div>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-bottom: 25px;">
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #9b59b6;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">超级赢家贡献</div>
        <div style="font-size: 24px; font-weight: bold; color: #9b59b6; margin-bottom: 5px;">+{super_winner_contribution:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">超级赢家(>{super_threshold}%)累计涨幅</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #1abc9c;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">其余盈利平均</div>
        <div style="font-size: 24px; font-weight: bold; color: #1abc9c; margin-bottom: 5px;">+{other_winner_avg:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">扣除超级赢家后的盈利均值</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #e74c3c;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">亏损标的平均</div>
        <div style="font-size: 24px; font-weight: bold; color: #e74c3c; margin-bottom: 5px;">{loser_avg:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">所有亏损标的的平均跌幅</div>
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
            <span>美股盘后复盘与风控审查报告</span>
        </h2>
        {kpi_html}
        {ai_html}
    </div>
</body></html>"""

# ==========================================
# 11. 邮件发送模块
# ==========================================
def send_mail():
    acc = os.environ.get("EMAIL_ACCOUNT")
    pwd = os.environ.get("EMAIL_PASSWORD")
    owner_email = os.environ.get("TARGET_EMAILS") or os.environ.get("OWNER_EMAIL")

    if not acc or not pwd or not owner_email:
        print("邮件发送配置缺失（缺少 ACCOUNT/PASSWORD/TARGET_EMAILS），跳过邮件发送。报告已安全保存在本地。")
        return

    msg = MIMEMultipart()
    msg['From'] = acc
    msg['To'] = owner_email
    msg['Subject'] = f"盘后清算 美股风控纪律与复盘 ({get_us_time().strftime('%Y-%m-%d')})"
    msg.attach(MIMEText(full_html, 'html', 'utf-8'))

    to_list = [e.strip() for e in owner_email.split(',')]

    try:
        print(f"正在通过 SSL 连接发送邮件至: {owner_email} ...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(acc, pwd)
            s.sendmail(acc, to_list, msg.as_string())
            print(f"邮件发送成功！收件人: {owner_email}")
    except Exception as e:
        print(f"错误：邮件发送失败，异常原因: {e}")

send_mail()
print("美股盘后复盘与风控审查程序顺利执行完毕。")
