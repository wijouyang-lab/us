from __future__ import annotations
import pandas as pd, yfinance as yf

def fetch(tickers, period="1y"):
    yf.set_tz_cache_location(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_yf_tmp")
    d=yf.download(list(tickers),period=period,interval="1d",group_by="ticker",progress=False,threads=False,auto_adjust=False,actions=False)
    return d
