# -*- coding: utf-8 -*-
import pandas as pd
import pandas_ta as ta  
import datetime
import os
import smtplib
import time
import re
import tushare as ts
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai 
from google.genai import types

today = datetime.datetime.now().weekday()
if today >= 5:
    print(f"[{datetime.datetime.now()}] 周末休市，脚本自动跳过。")
    exit()

TARGET_MODEL = 'gemini-3.1-pro-preview' 
TARGET_REGION = "美国市场 (纯 Tushare 引擎)"

# 🔑 读取关键环境变量
SUPER_ADMIN = os.environ.get("TARGET_EMAILS")
TS_TOKEN = os.environ.get("TUSHARE_TOKEN")

if not SUPER_ADMIN or not TS_TOKEN:
    print("🚨 致命错误：未检测到 TARGET_EMAILS 或 TUSHARE_TOKEN！请检查 GitHub Secrets！")
    exit(1)

print(f"🚀 启动：相对强度(Alpha)强制排序引擎 | 当前市场: {TARGET_REGION} | 引擎: {TARGET_MODEL}")

# ==========================================
# 📊 1. 获取标的池 (Tushare 驱动，筛选成交活跃 Top 100)
# ==========================================
ts.set_token(TS_TOKEN)
pro = ts.pro_api()

def get_scan_pool():
    tickers = {}
    print("📡 正在调用 Tushare 获取美股高活跃标的池...")
    try:
        for i in range(1, 10):
            trade_date = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime('%Y%m%d')
            df = pro.us_daily(trade_date=trade_date)
            
            if df is not None and not df.empty:
                print(f"✅ 成功获取 {trade_date} 美股行情，正在按成交量筛选 Top 100...")
                df_sorted = df.sort_values('vol', ascending=False).head(100)
                raw_tickers = df_sorted['ts_code'].tolist()
                
                try:
                    basic = pro.us_basic()
                    name_map = dict(zip(basic['ts_code'], basic['enname']))
                except:
                    name_map = {}
                    
                for t in raw_tickers:
                    clean_ticker = t.split('.')[0] if '.' in t else t
                    tickers[t] = name_map.get(t, clean_ticker) 
                break
                
        if not tickers:
            raise ValueError("Tushare 返回为空，触发备用池。")
            
    except Exception as e:
        print(f"⚠️ Tushare 数据拉取受限 ({e})，启用备用核心池...")
        tickers = {"NVDA": "NVIDIA", "AAPL": "Apple", "MSFT": "Microsoft", "TSLA": "Tesla"}
    return tickers

ACTIVE_STOCKS = get_scan_pool()

# ==========================================
# 📈 2. 深度 K 线拉取 (依然是 Tushare！绝不封IP)
# ==========================================
def get_kline_data(ts_code):
    end_dt = datetime.datetime.now().strftime('%Y%m%d')
    start_dt = (datetime.datetime.now() - datetime.timedelta(days=150)).strftime('%Y%m%d')
    
    for attempt in range(3):
        try:
            time.sleep(0.2) 
            df = pro.us_daily(ts_code=ts_code, start_date=start_dt, end_date=end_dt)
            if df is not None and not df.empty:
                df['Date'] = pd.to_datetime(df['trade_date'])
                df.set_index('Date', inplace=True)
                df.rename(columns={'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'vol':'Volume'}, inplace=True)
                
                # 🚨 极其关键：Tushare 数据默认是倒序，必须按时间升序重排，否则 MACD/RSI 全部算反！
                df.sort_index(ascending=True, inplace=True)
                return df
        except Exception:
            time.sleep(1)
    return pd.DataFrame()

# ==========================================
# 🧠 3. 全量相对打分引擎
# ==========================================
def run_quant_filter(tickers):
    scored_stocks = []
    print(f"🌊 启动纯血 Tushare 波段评分引擎，扫描 {len(tickers)} 只标的...")
    for ts_code, name in tickers.items():
        try:
            df = get_kline_data(ts_
