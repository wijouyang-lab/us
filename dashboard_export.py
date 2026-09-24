#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dashboard_export.py
===================
Dashboard 真实数据导出层（第三阶段 A）

职责
----
只做一件事：读取现有系统已经产出的数据文件，生成 Dashboard 前端使用的
dashboard/data/dashboard_data.json。

输入（只读）
-----------
- us_stocks_pending_YYYYMMDD.csv   最新 pending 扫描结果（Core / Observation）
- trade_history.csv                推荐事件账本
- option_strategies.csv            期权策略账本
- review_history.csv               Review 每日快照（可选，用于价格兜底 + history）
- strategy_params.json             策略参数（可选，仅写入 meta）

输出
----
dashboard/data/dashboard_data.json

硬性约束（本阶段）
------------------
1. 不修改 scan.py / review.py / evolve.py / scan_us_option_engine.py / strategy_params.json
2. 不改变任何选股 / 评分 / 止损 / Review / Options 逻辑
3. 不执行 scan.py 主程序、不触发完整 Scan
4. 不调用任何 GPT / AI 接口（AI 六段文本留到下一阶段）
5. 数据取不到时输出 null 并明确记录原因，绝不伪造

为什么没有 import scan.py / review.py
-------------------------------------
scan.py 在模块顶层执行 `from clawsocket_compat import ClawSocketClient` 等副作用导入，
import 即可能触发网络/主流程风险，且 scan.py 依赖 pandas / yfinance / 自有配置。
因此本脚本 **不 import 任何现有交易模块**，而是把需要的纯计算逻辑按 review.py 原实现
逐行复制到本文件（见下方 indicator 注释，标注了来源行号），保证算法口径一致。

运行
----
    python dashboard_export.py                        # 默认：脚本所在目录读取/输出
    python dashboard_export.py --data-dir /path/repo  # 指定数据目录
    python dashboard_export.py --out /path/file.json  # 指定输出文件
    python dashboard_export.py --no-network           # 完全跳过行情抓取（只导出 CSV 派生数据）
    python dashboard_export.py --kline-bars 120       # K 线保留交易日数量（默认 180）
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ============================================================
# 0. 常量
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

PENDING_RE = re.compile(r"^us_stocks_pending_(\d{8})\.csv$")
TRADE_HISTORY_NAME = "trade_history.csv"
OPTION_CSV_NAME = "option_strategies.csv"
PARAMS_NAME = "strategy_params.json"
REVIEW_HISTORY_NAME = "review_history.csv"
VERSION_NAME = "scan_version.txt"

# AI 六段文本：CSV 列名 -> JSON 字段名
# 来源为 scan.py 的 enrich_verified_items_with_ai_details() 已生成内容，本脚本只做透传：
# 不调用 GPT、不改写、不摘要、不截断；列缺失或为空时输出空字符串。
AI_FIELD_MAP = [
    ("AI_industry_logic", "industry_logic"),
    ("AI_news_cn", "news_cn"),
    ("AI_premarket_conclusion", "premarket_conclusion"),
    ("AI_catalysts", "catalysts"),
    ("AI_risks", "risks"),
    ("AI_invalidation", "invalidation"),
]

# AI 六段历史回填：从这些历史 CSV 中按 Ticker 检索同名股票此前已生成的 AI 文本。
# 只做检索 + 复制，绝不生成、改写或补写任何文案；检索不到就保持空字符串。
AI_HISTORY_PATTERNS = (
    "us_stocks_pending_*.csv",
    "scan_results*.csv",
    "scan_result*.csv",
)

# AI 文本持久化缓存：scan.py 在本地生成六段后按 Ticker Upsert 到该文件并提交入库。
# 优先级高于历史 CSV——它是唯一保证"只要 GPT 生成过就永久可查"的来源。
AI_CACHE_NAME = "ai_text_cache.csv"

# 单位提示（只做说明，不改数值）
UNIT_HINT = {
    "roe": "ratio (0.177 = 17.7%)",
    "revenue_growth": "ratio (0.55 = 55%)",
    "earnings_growth": "ratio (0.59 = 59%)",
    "profit_margin": "ratio (0.177 = 17.7%)",
    "market_cap": "usd",
    "atr_pct": "percent",
    "price": "usd",
}

# 全球市场资产：(输出名, 主抓 symbol, 备用 symbol, 分组, 单位, CNBC 符号, 仅常规时段)
# 口径设计（与东方财富 / 同花顺 100% 对齐）：
# - 三大股指：现货指数 ^DJI / ^GSPC / ^IXIC（点位与国内终端一致）。
#   regular_hours_only=True —— 仅在美股常规时段（美东 09:30-16:00）实时更新，
#   盘前/盘后/周末/节假日保持“上一常规交易日收盘”静态不变（price_kind=daily_close）。
# - 美债收益率：优先 CNBC 现货接口（Tradeweb 实时，24h），失败回退 Yahoo 并手动重算涨跌幅。
# - 大宗商品 / 外汇：24h 高频跳动（期货/现货连续合约），不受常规时段限制。
MARKET_ASSETS = [
    ("Dow Jones",  "^DJI",     None,    "index",      "index point",   None,    True),
    ("S&P 500",    "^GSPC",    None,    "index",      "index point",   None,    True),
    ("Nasdaq",     "^IXIC",    None,    "index",      "index point",   None,    True),
    ("VIX",        "^VIX",     None,    "volatility", "index point",   None,    False),
    ("US10Y",      "^TNX",     None,    "rate",       "percent yield", "US10Y", False),
    ("US2Y",       "2YY=F",    None,    "rate",       "percent yield", "US2Y",  False),
    ("US5Y",       "^FVX",     None,    "rate",       "percent yield", "US5Y",  False),
    ("US30Y",      "^TYX",     None,    "rate",       "percent yield", "US30Y", False),
    ("DXY",        "DX-Y.NYB", None,    "fx",         "index point",   None,    False),
    ("Gold",       "XAUUSD=X", "GC=F",  "commodity",  "usd/oz",        None,    False),
    ("Silver",     "XAGUSD=X", "SI=F",  "commodity",  "usd/oz",        None,    False),
    ("Copper",     "HG=F",     None,    "commodity",  "usd/lb",        None,    False),
    ("WTI",        "CL=F",     None,    "energy",     "usd/bbl",       None,    False),
    ("Brent",      "BZ=F",     None,    "energy",     "usd/bbl",       None,    False),
    ("Natural Gas","NG=F",     None,    "energy",     "usd/mmbtu",     None,    False),
]

# review.py:2317 CLOSED_STOCK_STATUSES —— 原样复制，不改变口径
CLOSED_STOCK_STATUSES = {
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
}

# review.py:1554 active_list 允许的开放状态（trade_history 口径）
ACTIVE_STATUSES = {"", "Active", "pending"}
# review_history.csv 中对应的“仍在跟踪”状态
OPEN_TRACK_STATUSES = {"持仓中", "观察推荐", "", "Active", "pending"}

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

REQUEST_TIMEOUT = 10
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}


# ============================================================
# 1. 通用工具
# ============================================================

def log(msg: str) -> None:
    print(msg, flush=True)


def clean_text(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def parse_num(v):
    """把 CSV 里的 '$76.33' / '3.43' / '' / 'None' / 'nan' 统一转成 float 或 None。"""
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() in {"none", "nan", "null", "n/a", "na", "-"}:
        return None
    s = s.replace(",", "").replace("$", "").replace("%", "")
    try:
        f = float(s)
    except ValueError:
        return None
    if f != f:  # NaN
        return None
    return f


def round_num(v, nd=4):
    if v is None:
        return None
    try:
        return round(float(v), nd)
    except Exception:
        return None


def parse_date(v):
    """接受 YYYY-MM-DD / YYYY-MM-DD HH:MM:SS / YYYYMMDD，返回 date 或 None。"""
    s = clean_text(v)
    if not s:
        return None
    s = s.split(" ")[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def read_csv_rows(path: Path):
    """读取 CSV，返回 DictReader 行列表；文件缺失抛 FileNotFoundError。"""
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.stat().st_size == 0:
        return []
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"无法解码 {path}")


# ---- 美东时间：优先 zoneinfo，Windows 无 tzdata 时手工 DST 兜底 ----
def _us_eastern_offset(d: dt.date) -> int:
    """返回美东相对 UTC 的分钟偏移（含夏令时判定）。"""
    # 3 月第二个周日 02:00 -> 11 月第一个周日 02:00 为夏令时
    dst_start = dt.date(d.year, 3, 1)
    dst_start += dt.timedelta(days=(6 - dst_start.weekday()) % 7)  # 第一个周日
    dst_start += dt.timedelta(days=7)                              # 第二个周日
    dst_end = dt.date(d.year, 11, 1)
    dst_end += dt.timedelta(days=(6 - dst_end.weekday()) % 7)      # 第一个周日
    return -240 if dst_start <= d < dst_end else -300


def now_us() -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo  # noqa
        return dt.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        utc = dt.datetime.now(dt.timezone.utc)
        off = _us_eastern_offset(utc.date())
        return (utc + dt.timedelta(minutes=off)).replace(tzinfo=None)


def last_completed_regular_date_us(asof=None) -> dt.date:
    """scan.py:703 _last_completed_regular_date_us —— 原样复制。"""
    now = asof or now_us()
    if now.time() < dt.time(16, 0):
        return now.date() - dt.timedelta(days=1)
    return now.date()


def us_regular_session_open(asof=None) -> bool:
    """判断当前是否处于美股常规交易时段（美东周一~周五 09:30-16:00）。

    用于股指：常规时段内实时更新；盘前/盘后/周末/节假日保持静态收盘价。
    严格按美东本地时间判定（含夏令时），不依赖行情源返回的市场状态。
    """
    now = asof or now_us()
    if now.weekday() >= 5:          # 周六/周日
        return False
    t = now.time()
    return dt.time(9, 30) <= t < dt.time(16, 0)


# ============================================================
# 2. 技术指标（纯计算）
#    来源：review.py:1151-1180 _calc_atr / _calc_macd / _calc_kdj
#    本文件用纯 python 复刻，算法与参数完全一致
# ============================================================

def sma(vals, n):
    if len(vals) < n:
        return None
    return sum(vals[-n:]) / n


def calc_atr(bars, length=14):
    """review.py:1151 _calc_atr —— TR 的 14 日简单移动平均（非 Wilder 平滑）。"""
    if len(bars) < length + 1:
        return None
    trs = []
    for i in range(1, len(bars)):
        h, l = bars[i]["high"], bars[i]["low"]
        pc = bars[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < length:
        return None
    return sum(trs[-length:]) / length


def _ema(vals, span):
    if not vals:
        return []
    a = 2.0 / (span + 1.0)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(a * v + (1 - a) * out[-1])
    return out


def calc_macd(closes, fast=12, slow=26, signal=9):
    """review.py:1157 _calc_macd —— EMA(adjust=False)。"""
    if len(closes) < slow + signal:
        return None
    ef = _ema(closes, fast)
    es = _ema(closes, slow)
    macd = [f - s for f, s in zip(ef, es)]
    sig = _ema(macd, signal)
    return {"macd": macd[-1], "signal": sig[-1], "hist": macd[-1] - sig[-1]}


def calc_kdj(bars, n=9):
    """review.py:1164 _calc_kdj —— K=D=50 起步，RSV 分母 +1e-9。"""
    if not bars:
        return {"k": None, "d": None, "j": None}
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    K = D = 50.0
    k = d = j = None
    for i in range(len(closes)):
        if i < n - 1:
            rsv = 50.0
        else:
            hn = max(highs[max(0, i - n + 1):i + 1])
            ln = min(lows[max(0, i - n + 1):i + 1])
            rsv = (closes[i] - ln) / (hn - ln + 1e-9) * 100 if hn != ln else 50.0
        K = 2 / 3 * K + 1 / 3 * rsv
        D = 2 / 3 * D + 1 / 3 * K
        k, d, j = K, D, 3 * K - 2 * D
    return {"k": k, "d": d, "j": j}


def calc_rsi_wilder(closes, length=14):
    """标准 Wilder RSI。仅当 CSV 未提供 RSI 时才用，避免与 scan.py 口径冲突。"""
    if len(closes) < length + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_g = sum(gains[:length]) / length
    avg_l = sum(losses[:length]) / length
    for i in range(length, len(gains)):
        avg_g = (avg_g * (length - 1) + gains[i]) / length
        avg_l = (avg_l * (length - 1) + losses[i]) / length
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - 100.0 / (1.0 + rs)


# ============================================================
# 3. 行情抓取
#    顺序：yfinance（与 scan.py 同源） -> Yahoo HTTP -> Stooq（备用源）
#    任一源成功即写入真实数值，并在 JSON 中记录 source；
#    全部失败则输出 null + 真实 error 文本，绝不伪造、绝不硬编码价格。
# ============================================================

# 备用源（Stooq）符号映射；只有前序源都失败时才用到，来源会如实写入 JSON
STOOQ_SYMBOL_MAP = {
    "^GSPC": "^spx", "^IXIC": "^ndq", "^DJI": "^dji", "^VIX": "^vix",
    "^TNX": "10usy.b", "^FVX": "5usy.b", "^TYX": "30usy.b", "DX-Y.NYB": "usdidx",
    "GC=F": "gc.f", "SI=F": "si.f", "HG=F": "hg.f",
    "CL=F": "cl.f", "BZ=F": "bz.f", "NG=F": "ng.f",
    "XAUUSD=X": "xauusd", "XAGUSD=X": "xagusd",
}

# CNBC 公开接口（quote-html-webservice）：美债现货收益率（Tradeweb 实时）。
# 多 symbol 逗号拼接会被当成单一非法 symbol，故逐个轻量请求。
CNBC_QUOTE_URL = ("https://quote.cnbc.com/quote-html-webservice/restQuote/"
                  "symbolType/symbol?symbols={sym}&requestMethod=itv&output=json")


def fetch_cnbc_rates(symbols, timeout=REQUEST_TIMEOUT):
    """从 CNBC 公开接口抓取美国国债现货收益率。

    返回 {symbol: {"price": float, "change_pct": float|None, "asof": str|None}}；
    每个 symbol 独立成败，失败的不出现在结果中（由调用方 fallback）。
    只解析真实返回的 last / change_pct，不做任何推算或编造。
    """
    out = {}
    for sym in symbols:
        try:
            url = CNBC_QUOTE_URL.format(sym=urllib.parse.quote(sym))
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                payload = json.load(r)
            quotes = (payload.get("FormattedQuoteResult") or {}).get("FormattedQuote") or []
            if isinstance(quotes, dict):
                quotes = [quotes]
            q = next((x for x in quotes
                      if x.get("symbol") == sym and str(x.get("code")) == "0"), None)
            if not q:
                continue
            last = parse_num(q.get("last"))            # "5.129%" -> 5.129
            chg = parse_num(q.get("change_pct"))       # "+0.2933%" -> 0.2933
            if last is None or last <= 0:
                continue
            out[sym] = {"price": last, "change_pct": chg,
                        "asof": q.get("last_time") or None}
        except Exception:
            continue
    return out

# Yahoo -> 备用源
def stooq_symbol(symbol: str) -> str:
    return STOOQ_SYMBOL_MAP.get(symbol, symbol.lower() + ".us")


class QuoteProvider:
    """多后端行情提供者。

    - backends：按优先级排列的可用数据源
    - last_source / last_error：最近一次请求的真实来源与错误（写入 JSON，便于排查）
    - error_log：{symbol: ["backend: 错误", ...]}，全部失败时原样落盘
    """

    def __init__(self, mode="auto", timeout=REQUEST_TIMEOUT, allow_stooq=True, retries=2):
        self.mode = mode            # auto | yf | yahoo | none
        self.timeout = timeout
        self.retries = max(1, retries)
        self.allow_stooq = allow_stooq
        self.name = "none"
        self.backends = []
        self.network_error = None
        self.last_source = None
        self.last_error = None
        self.error_log = {}
        self._yf = None
        self._init()

    # ---------- 初始化 / 探测 ----------
    def _init(self):
        if self.mode == "none":
            self.network_error = "--no-network 已禁用行情抓取"
            return

        yf_ok = False
        if self.mode in ("auto", "yf"):
            try:
                import yfinance as yf  # noqa
                self._yf = yf
                self.backends.append("yfinance")
                yf_ok = True
            except Exception as e:
                self._yf = None
                self._note("global", "yfinance", f"import 失败：{e}")
                if self.mode == "yf":
                    self.network_error = f"yfinance 不可用：{e}"
                    return

        if self.mode in ("auto", "yahoo") or not yf_ok:
            # 连通性预检：避免 20+ 次请求逐个超时
            if self._probe_yahoo():
                self.backends.append("yahoo_http")
            elif self.mode == "yahoo":
                self.network_error = self.network_error or "Yahoo 连通性预检失败"
                return

        if self.allow_stooq and self.mode in ("auto", "yahoo", "yf"):
            self.backends.append("stooq")

        if not self.backends:
            self.network_error = self.network_error or "无任何可用行情源"
            return
        self.name = self.backends[0]

    def _note(self, symbol, backend, err):
        self.error_log.setdefault(symbol, []).append(f"{backend}: {err}")

    def _probe_yahoo(self) -> bool:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=5d&interval=1d"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                r.read(64)
            return True
        except Exception as e:
            self.network_error = self.network_error or f"Yahoo 连通性预检失败：{type(e).__name__}: {e}"
            return False

    @property
    def available(self) -> bool:
        return bool(self.backends)

    # ---------- 日线 ----------
    def daily_bars(self, symbol: str, days: int = 260):
        """返回 [{'date','open','high','low','close','volume'}, ...]（升序），全部失败返回 []。"""
        self.last_source, self.last_error = None, None
        if not self.backends:
            return []
        for backend in self.backends:
            try:
                if backend == "yfinance":
                    bars = self._bars_yf(symbol, days)
                elif backend == "yahoo_http":
                    bars = self._bars_yahoo(symbol, days)
                else:
                    bars = self._bars_stooq(symbol, days)
            except Exception as e:
                bars = []
                self._note(symbol, backend, f"{type(e).__name__}: {e}")
            if bars:
                self.last_source = backend
                return bars
            self._note(symbol, backend, "无可用日线")
            self.last_error = f"{backend} 无可用日线"
        self.last_error = "; ".join(self.error_log.get(symbol, [])) or "全部行情源失败"
        return []

    # ---------- 实时报价 ----------
    def quote(self, symbol: str):
        """返回 {'price': float, 'ts': epoch|None, 'source': str} 或 None。"""
        for backend in self.backends:
            try:
                if backend == "yahoo_http":
                    q = self._quote_yahoo(symbol)
                elif backend == "yfinance":
                    q = self._quote_yf(symbol)
                else:
                    q = None
            except Exception as e:
                q = None
                self._note(symbol + "#quote", backend, f"{type(e).__name__}: {e}")
            if q:
                q["source"] = backend
                return q
        return None

    def _quote_yahoo(self, symbol):
        url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
               f"{urllib.parse.quote(symbol)}?range=1d&interval=1d&includePrePost=true")
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            payload = json.load(r)
        meta = payload["chart"]["result"][0]["meta"]
        price = parse_num(meta.get("regularMarketPrice"))
        # 盘前 / 盘后：常规时段价缺失或市场未开时，用 pre/postMarketPrice
        if price is None:
            price = parse_num(meta.get("postMarketPrice"))
        if price is None:
            price = parse_num(meta.get("preMarketPrice"))
        if price is None:
            return None
        ts = meta.get("regularMarketTime") or meta.get("postMarketTime") or meta.get("preMarketTime")
        return {"price": float(price), "ts": ts}

    def _quote_yf(self, symbol):
        if self._yf is None:
            return None
        t = self._yf.Ticker(symbol)

        # prepost=True：1m 粒度会包含盘前 / 盘后（Extended Hours）成交，
        # 这样美东 04:00-09:30 与 16:00-20:00 也能取到真实变动的价格。
        # （日线 interval="1d" 情况下 Yahoo 会忽略 prepost，故这里必须用 1m。）
        try:
            h = t.history(period="1d", interval="1m",
                          prepost=True, auto_adjust=False)
            if h is not None and not h.empty:
                price = parse_num(h["Close"].iloc[-1])
                ts_epoch = None
                try:
                    ts_epoch = int(h.index[-1].timestamp())
                except Exception:
                    ts_epoch = None
                if price is not None:
                    return {"price": float(price), "ts": ts_epoch, "prepost": True}
        except Exception as e:
            self._note(symbol + "#quote", "yfinance",
                       f"prepost 1m 报价失败：{type(e).__name__}: {e}")

        # 回退：fast_info（无时间戳，仅常规时段）
        price = parse_num(getattr(t.fast_info, "last_price", None))
        if price is None:
            price = parse_num(getattr(t.fast_info, "previous_close", None))
        if price is None:
            return None
        return {"price": float(price), "ts": None}

    # ---------- yfinance 日线 ----------
    def _bars_yf(self, symbol, days):
        period = "2y" if days > 250 else ("1y" if days > 130 else "6mo")
        df = self._yf.download(
            symbol, period=period, interval="1d",
            progress=False, auto_adjust=False, threads=False,
            prepost=True,   # 仅对 intraday 生效；1d 日线下 Yahoo 会忽略此参数
        )
        if df is None or df.empty:
            return []
        if hasattr(df.columns, "get_level_values"):
            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                pass
        out = []
        for idx, row in df.iterrows():
            d = parse_date(idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else idx)
            o = parse_num(row.get("Open"))
            h = parse_num(row.get("High"))
            l = parse_num(row.get("Low"))
            c = parse_num(row.get("Close"))
            v = parse_num(row.get("Volume"))
            if d is None or None in (o, h, l, c):
                continue
            out.append({"date": d, "open": o, "high": h, "low": l,
                        "close": c, "volume": int(v) if v else 0})
        return self._filter_completed(out)[-days:]

    # ---------- Yahoo HTTP 日线 ----------
    def _bars_yahoo(self, symbol, days):
        rng = "2y" if days > 250 else ("1y" if days > 130 else "6mo")
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{urllib.parse.quote(symbol)}?range={rng}&interval=1d&includePrePost=false"
        )
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    payload = json.load(r)
                res = payload["chart"]["result"][0]
                ts = res.get("timestamp") or []
                q = res["indicators"]["quote"][0]
                opens = q.get("open") or []
                highs = q.get("high") or []
                lows = q.get("low") or []
                closes = q.get("close") or []
                vols = q.get("volume") or []
                out = []
                for i, t in enumerate(ts):
                    try:
                        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
                    except IndexError:
                        break
                    if None in (o, h, l, c):
                        continue
                    d = dt.datetime.fromtimestamp(int(t), tz=dt.timezone.utc).date()
                    v = vols[i] if i < len(vols) else 0
                    out.append({"date": d, "open": float(o), "high": float(h),
                                "low": float(l), "close": float(c),
                                "volume": int(v) if v else 0})
                return self._filter_completed(out)[-days:]
            except Exception as e:
                self._note(symbol, "yahoo_http", f"第{attempt + 1}次：{type(e).__name__}: {e}")
                if attempt + 1 < self.retries:
                    time.sleep(1.0)
        return []

    # ---------- Stooq 备用源日线 ----------
    def _bars_stooq(self, symbol, days):
        sym = stooq_symbol(symbol)
        url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(sym)}&i=d"
        req = urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            text = r.read().decode("utf-8", "ignore")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) < 2 or not lines[0].lower().startswith("date,"):
            # 反爬页面 / 无此符号：明确拒绝，不解析成数据
            raise RuntimeError(f"Stooq 返回非 CSV（疑似反爬或无此符号 {sym}）")
        out = []
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) < 5:
                continue
            d = parse_date(parts[0])
            o, h, l, c = parse_num(parts[1]), parse_num(parts[2]), parse_num(parts[3]), parse_num(parts[4])
            v = parse_num(parts[5]) if len(parts) > 5 else 0
            if d is None or None in (o, h, l, c):
                continue
            out.append({"date": d, "open": o, "high": h, "low": l, "close": c,
                        "volume": int(v) if v else 0})
        return self._filter_completed(out)[-days:]

    @staticmethod
    def _filter_completed(bars):
        """scan.py:711 _filter_completed_daily_bars —— 剔除未完成/当天 K 棒。"""
        if not bars:
            return []
        cutoff = last_completed_regular_date_us()
        return [b for b in bars if b["date"] <= cutoff]


# ============================================================
# 4. 输入文件定位
# ============================================================

def find_latest_pending(data_dir: Path):
    """找到最新的 us_stocks_pending_YYYYMMDD.csv（忽略 *.processed）。"""
    candidates = []
    for p in glob.glob(str(data_dir / "us_stocks_pending_*.csv")):
        name = os.path.basename(p)
        m = PENDING_RE.match(name)
        if not m:
            continue
        try:
            d = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        candidates.append((d, os.path.getmtime(p), Path(p)))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[-1][2]


def require_file(path: Path, what: str) -> Path:
    if not path.exists():
        raise SystemExit(
            f"[ERROR] 缺少必需输入文件 {what}：{path}\n"
            f"        dashboard_export.py 不会静默跳过该文件，请先确认数据目录是否正确"
            f"（可用 --data-dir 指定），或确认该文件是否应由 scan.py / review.py 生成。"
        )
    return path


# ============================================================
# 5. STOCKS
# ============================================================

BUCKET_MAP = {"Core_Dragon": "Core", "Observation": "Observation"}


def load_ai_history(data_dir, skip_paths=()):
    """扫描 data_dir 下的历史 pending / scan_results CSV，建立 Ticker -> AI 六段 的索引。

    - 只收录 AI_HISTORY_PATTERNS 命中的文件，按名称倒序（新日期优先）
    - 已存在内容的字段不覆盖
    - 返回 {TICKER: {json_key: text}}；没有任何可用历史时返回 {}
    """
    files = []
    for pat in AI_HISTORY_PATTERNS:
        files.extend(glob.glob(os.path.join(str(data_dir), pat)))
    skip = {os.path.abspath(str(p)) for p in skip_paths}
    files = sorted({os.path.abspath(f) for f in files} - skip, reverse=True)

    index = {}
    for path in files:
        try:
            rows = read_csv_rows(Path(path))
        except Exception:
            continue
        for row in rows:
            ticker = clean_text(row.get("Ticker")).upper()
            if not ticker:
                continue
            entry = index.setdefault(ticker, {})
            for csv_col, json_key in AI_FIELD_MAP:
                if csv_col not in row:
                    continue
                text = clean_text(row.get(csv_col))
                if text and not entry.get(json_key):
                    entry[json_key] = text
    return index


def load_ai_cache(data_dir):
    """读取 ai_text_cache.csv（scan.py 本地生成 GPT 文本后按 Ticker Upsert 的持久化缓存）。

    返回 {TICKER: {"texts": {json_key: text}, "update_date": str}}；
    文件不存在或为空返回 {}。只搬运真实已生成文本，绝不生成/改写。
    """
    path = Path(data_dir) / AI_CACHE_NAME
    if not path.exists():
        return {}
    try:
        rows = read_csv_rows(path)
    except Exception:
        return {}
    index = {}
    for row in rows:
        ticker = clean_text(row.get("Ticker")).upper()
        if not ticker:
            continue
        texts = {}
        for csv_col, json_key in AI_FIELD_MAP:
            text = clean_text(row.get(csv_col))
            if text:
                texts[json_key] = text
        if texts:
            index[ticker] = {
                "texts": texts,
                "update_date": clean_text(row.get("Update_Date")) or None,
            }
    return index


def backfill_ai_fields(stocks, data_dir, current_pending=None, notes=None):
    """Core / Observation 股票的 AI 六段若为空，按优先级回填同名 Ticker 的真实文本。

    硬性约束：本函数**不生成、不改写、不补写任何文案**，只搬运已生成的真实文本。
    回填优先级与 stock['ai_source'] 取值：
      scan_pending_csv  本次 pending CSV 自带
      ai_text_cache     ai_text_cache.csv 持久化缓存（scan 生成后 Upsert 入库，永久可查）
      history_backfill  历史 pending / scan_results CSV
      none              三处都没有（前端显示 pending 是正确的）
    """
    skip = [str(current_pending)] if current_pending else []
    try:
        cache = load_ai_cache(data_dir)
    except Exception as e:
        cache = {}
        if notes is not None:
            notes.append(f"AI 文本缓存读取失败：{type(e).__name__}: {e}")
    try:
        history = load_ai_history(data_dir, skip_paths=skip)
    except Exception as e:
        history = {}
        if notes is not None:
            notes.append(f"AI 历史索引构建失败：{type(e).__name__}: {e}")

    backfilled = []
    for s in stocks:
        ai = s.get("ai") or {}
        if all(ai.get(k) for _c, k in AI_FIELD_MAP):
            s["ai_source"] = "scan_pending_csv"
            continue
        ticker = s.get("ticker")
        changed = False
        # 第一优先级：持久化缓存（scan.py 生成后 Upsert，永久保留）
        cached = cache.get(ticker)
        if cached:
            for _csv_col, key in AI_FIELD_MAP:
                if not ai.get(key) and cached["texts"].get(key):
                    ai[key] = cached["texts"][key]
                    changed = True
            if changed:
                if cached.get("update_date"):
                    s["ai_update_date"] = cached["update_date"]
                s["ai"] = ai
                s["ai_source"] = "ai_text_cache"
                backfilled.append(ticker)
                continue
        # 第二优先级：历史 pending / scan_results CSV
        src = history.get(ticker)
        if src:
            for _csv_col, key in AI_FIELD_MAP:
                if not ai.get(key) and src.get(key):
                    ai[key] = src[key]
                    changed = True
        s["ai"] = ai
        if changed:
            s["ai_source"] = "history_backfill"
            backfilled.append(ticker)
        elif any(ai.get(k) for _c, k in AI_FIELD_MAP):
            s["ai_source"] = "scan_pending_csv"
        else:
            s["ai_source"] = "none"

    if notes is not None:
        if cache:
            notes.append(f"AI 文本缓存索引：{AI_CACHE_NAME} 命中 {len(cache)} 个 Ticker")
        else:
            notes.append(f"未找到可用的 {AI_CACHE_NAME}（scan 尚未生成或尚未入库）。")
        if history:
            notes.append(f"AI 历史回填索引：命中 {len(history)} 个 Ticker 的历史 AI 文本")
        if backfilled:
            notes.append("AI 六段已回填：" + "、".join(sorted(set(backfilled))))
        elif stocks:
            notes.append("AI 六段无文本可回填（缓存与历史 CSV 中均未找到同名 Ticker）。")
    return backfilled


def load_fallback_stock_rows(data_dir):
    """无 pending CSV 时，从仓库已有的 dashboard_data.json 复原 Core / Observation 名单。

    把上一版导出 JSON 的 stocks[] 反向映射成 pending CSV 形态的 dict，供
    build_stocks 原样消费——分数 / 止损 / 基本面 / AI 文本全部原样保留，
    行情（价格 / K线 / 技术指标）仍由 build_stocks 重新抓取刷新。

    返回 (rows, source_path)；找不到文件或列表为空返回 ([], None)。
    """
    path = Path(data_dir) / "dashboard" / "data" / "dashboard_data.json"
    if not path.exists():
        return [], None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [], None
    stocks = data.get("stocks") or []

    rows = []
    for s in stocks:
        ticker = clean_text(s.get("ticker")).upper()
        if not ticker:
            continue
        ai = s.get("ai") or {}
        row = {
            "Ticker": ticker,
            "Name": s.get("name") or ticker,
            "Tag": s.get("tag_raw") or (
                "Core_Dragon" if s.get("bucket") == "Core" else "Observation"),
            "Prev_Close": s.get("prev_close") or "",
            "Price": s.get("price") or "",
            "Scan_Ref_Price": s.get("pending_price") or "",
            "RSI": s.get("rsi") or "", "ATR_Pct": s.get("atr_pct") or "",
            "Stop_Loss": s.get("stop_loss") or "",
            "Stop_Method": s.get("stop_method") or "",
            "Final_Score": s.get("final_score") or "",
            "Quant_Score": s.get("quant_score") or "",
            "AI_Score": s.get("ai_score") or "",
            "Fundamental_Score": s.get("fundamental_score") or "",
            "Technical_Score_25": s.get("technical_score") or "",
            "Risk_Liquidity_Score": s.get("risk_liquidity_score") or "",
            "PE_TTM": s.get("pe_ttm") or "", "PE_Forward": s.get("pe_forward") or "",
            "PB": s.get("pb") or "", "EPS_TTM": s.get("eps_ttm") or "",
            "ROE": s.get("roe") or "", "Revenue_Growth": s.get("revenue_growth") or "",
            "Earnings_Growth": s.get("earnings_growth") or "",
            "Profit_Margin": s.get("profit_margin") or "",
            "Market_Cap": s.get("market_cap") or "",
            "Market_Regime": s.get("market_regime") or "", "VIX": s.get("vix") or "",
            "Status": s.get("status") or "",
            "Technical_Date": s.get("technical_date") or "",
            "Date": s.get("scan_date") or "",
            "Avg_Dollar_Volume_20D": s.get("avg_dollar_volume_20d") or "",
            "Sector_RS_20D_Pct": s.get("sector_rs_20d_pct") or "",
            "Bias": s.get("bias") or "", "Event_Score": s.get("event_score") or "",
            "技术确认数": s.get("technical_confirmations") or "",
            "技术确认信号": s.get("technical_confirmation_signals") or "",
        }
        for csv_col, json_key in AI_FIELD_MAP:
            if ai.get(json_key):
                row[csv_col] = ai[json_key]
        rows.append(row)
    return rows, path


def build_stocks(pending_rows, provider, kline_bars, anomalies, warnings=None):
    stocks = []
    kline_ok, kline_fail = 0, 0
    realtime_count, last_close_count = 0, 0
    warnings = warnings if warnings is not None else []

    for row in pending_rows:
        ticker = clean_text(row.get("Ticker")).upper()
        name = clean_text(row.get("Name")) or ticker
        raw_tag = clean_text(row.get("Tag"))
        bucket = BUCKET_MAP.get(raw_tag, raw_tag or "Unknown")

        if not TICKER_RE.match(ticker or ""):
            anomalies.append(f"pending 中出现异常 Ticker：{ticker!r}（Tag={raw_tag!r}）")
        if raw_tag not in BUCKET_MAP:
            anomalies.append(f"Ticker {ticker} 的 Tag 未识别：{raw_tag!r}（已原样写入 bucket）")

        prev_close = parse_num(row.get("Prev_Close"))
        ref_price = parse_num(row.get("Scan_Ref_Price"))
        pre_price = parse_num(row.get("Premarket_Price"))

        # 价格优先级与 scan.py 一致：盘前价 > 扫描参考价 > 前收
        if pre_price and pre_price > 0:
            price, price_src = pre_price, "Premarket_Price"
        elif ref_price and ref_price > 0:
            price, price_src = ref_price, "Scan_Ref_Price"
        elif prev_close and prev_close > 0:
            price, price_src = prev_close, "Prev_Close"
        else:
            price, price_src = None, None

        pre_chg = parse_num(row.get("Premarket_Change_Pct"))
        if pre_chg is not None:
            pending_change, pending_chg_src = pre_chg, "Premarket_Change_Pct"
        elif price and prev_close and prev_close > 0:
            pending_change = (price - prev_close) / prev_close * 100
            pending_chg_src = "computed(price vs Prev_Close)"
        else:
            pending_change, pending_chg_src = None, None

        stop = parse_num(row.get("Stop_Loss"))  # 兼容 "$76.33" / "观望"

        stock = {
            "ticker": ticker,
            "name": name,
            "bucket": bucket,
            "tag_raw": raw_tag,

            # price / price_source 在下面按「实时 > 最新完整收盘 > pending CSV」覆盖
            "price": None,
            "price_source": None,
            "current_price": None,
            "current_price_updated_at": None,
            "pending_price": round_num(price),
            "pending_price_source": price_src,
            "prev_close": round_num(prev_close),
            "change_1d": None,
            "change_1d_source": None,
            "pending_change_1d": round_num(pending_change, 4),
            "pending_change_1d_source": pending_chg_src,

            "final_score": round_num(parse_num(row.get("Final_Score")), 2),
            "quant_score": round_num(parse_num(row.get("Quant_Score")), 2),
            "ai_score": round_num(parse_num(row.get("AI_Score")), 2),

            "fundamental_score": round_num(parse_num(row.get("Fundamental_Score")), 2),
            "technical_score": round_num(parse_num(row.get("Technical_Score_25")), 2),
            "risk_liquidity_score": round_num(parse_num(row.get("Risk_Liquidity_Score")), 2),

            "rsi": round_num(parse_num(row.get("RSI")), 2),
            "atr_pct": round_num(parse_num(row.get("ATR_Pct")), 4),
            "stop_loss": round_num(stop),
            "stop_method": clean_text(row.get("Stop_Method")) or None,

            "pe_ttm": round_num(parse_num(row.get("PE_TTM"))),
            "pe_forward": round_num(parse_num(row.get("PE_Forward"))),
            "pb": round_num(parse_num(row.get("PB"))),
            "eps_ttm": round_num(parse_num(row.get("EPS_TTM"))),
            "roe": round_num(parse_num(row.get("ROE"))),
            "revenue_growth": round_num(parse_num(row.get("Revenue_Growth"))),
            "earnings_growth": round_num(parse_num(row.get("Earnings_Growth"))),
            "profit_margin": round_num(parse_num(row.get("Profit_Margin"))),
            "market_cap": round_num(parse_num(row.get("Market_Cap")), 2),

            "market_regime": clean_text(row.get("Market_Regime")) or None,
            "vix": round_num(parse_num(row.get("VIX")), 4),

            "status": clean_text(row.get("Status")) or None,
            "technical_date": clean_text(row.get("Technical_Date")) or None,
            "scan_date": clean_text(row.get("Date")) or None,
            "avg_dollar_volume_20d": round_num(parse_num(row.get("Avg_Dollar_Volume_20D")), 2),
            "sector_rs_20d_pct": round_num(parse_num(row.get("Sector_RS_20D_Pct")), 4),
            "bias": round_num(parse_num(row.get("Bias")), 4),
            "event_score": round_num(parse_num(row.get("Event_Score")), 2),
            "technical_confirmations": clean_text(row.get("技术确认数")) or None,
            "technical_confirmation_signals": clean_text(row.get("技术确认信号")) or None,

            # AI 六段：直接透传 pending CSV 中 Scan 已生成的文本（本脚本不生成任何文案）
            "ai": {
                json_key: clean_text(row.get(csv_col))
                for csv_col, json_key in AI_FIELD_MAP
            },
        }

        # ---------- K 线 + 技术指标（先取，供当前价与涨跌幅使用） ----------
        bars = provider.daily_bars(ticker, days=max(kline_bars * 2, 260)) if provider.available else []
        # 二次防御：无论上游是否已过滤，这里再剔除未完成/未来 K 棒
        bars = QuoteProvider._filter_completed(bars)
        bars = bars[-kline_bars:] if bars else []
        if bars:
            kline_ok += 1
            if len(bars) < 60:
                warnings.append(
                    f"{ticker}: 仅取得 {len(bars)} 个完整交易日（目标 {kline_bars}，下限 60），"
                    f"MA50 等技术指标可靠性下降"
                )
        else:
            kline_fail += 1

        # ---------- 当前价补齐：实时报价 > 最新完整交易日 close > pending CSV ----------
        current_price, cur_src, cur_ts = None, None, None
        if provider.available:
            q = provider.quote(ticker)
            if q and q.get("price"):
                q_day = None
                if q.get("ts"):
                    try:
                        q_day = dt.datetime.fromtimestamp(
                            int(q["ts"]), tz=dt.timezone.utc
                        ).astimezone(dt.timezone(dt.timedelta(hours=-4))).date()
                    except Exception:
                        q_day = None
                if q.get("ts") is None:
                    cur_src = "realtime_unverified"   # yfinance fast_info 未返回时间戳
                    cur_ts = None
                elif q_day == now_us().date():
                    cur_src = "realtime"
                    cur_ts = dt.datetime.fromtimestamp(
                        int(q["ts"]), tz=dt.timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    cur_src = None                    # 报价已过期 -> 退回完整收盘价
                if cur_src in ("realtime", "realtime_unverified"):
                    current_price = q["price"]
                    if cur_src == "realtime":
                        realtime_count += 1
        if current_price is None and bars:
            current_price = bars[-1]["close"]
            cur_src = "last_close"
            cur_ts = bars[-1]["date"].strftime("%Y-%m-%d")
            last_close_count += 1

        live_change, live_chg_src = None, None
        if current_price and bars:
            if cur_src in ("realtime", "realtime_unverified"):
                base = bars[-1]["close"]          # 最近一个完整交易日收盘
                live_chg_src = "computed(current vs last completed close)"
            else:
                base = bars[-2]["close"] if len(bars) >= 2 else None
                live_chg_src = "computed(last close vs previous close)"
            if base:
                live_change = (current_price - base) / base * 100

        if live_change is not None:
            change_1d, chg_src = live_change, live_chg_src
        else:
            change_1d, chg_src = pending_change, pending_chg_src

        if current_price:
            display_price, display_price_src = current_price, cur_src
        else:
            display_price, display_price_src = price, "pending_csv"

        stock["price"] = round_num(display_price)
        stock["price_source"] = display_price_src
        stock["current_price"] = round_num(current_price)
        stock["current_price_updated_at"] = cur_ts
        stock["change_1d"] = round_num(change_1d, 4)
        stock["change_1d_source"] = chg_src

        if bars:
            closes = [b["close"] for b in bars]
            macd = calc_macd(closes)
            kdj = calc_kdj(bars)
            atr = calc_atr(bars)
            csv_rsi = parse_num(row.get("RSI"))
            stock["ohlcv"] = [
                {
                    "date": b["date"].strftime("%Y-%m-%d"),
                    "open": round_num(b["open"]),
                    "high": round_num(b["high"]),
                    "low": round_num(b["low"]),
                    "close": round_num(b["close"]),
                    "volume": b["volume"],
                }
                for b in bars
            ]
            stock["technical"] = {
                "ma20": round_num(sma(closes, 20)),
                "ma50": round_num(sma(closes, 50)),
                "kdj_j": round_num(kdj["j"], 2),
                "kdj_k": round_num(kdj["k"], 2),
                "kdj_d": round_num(kdj["d"], 2),
                "macd_hist": round_num(macd["hist"], 4) if macd else None,
                "macd": round_num(macd["macd"], 4) if macd else None,
                "macd_signal": round_num(macd["signal"], 4) if macd else None,
                "atr_abs": round_num(atr, 4),
                "atr_pct_computed": round_num((atr / closes[-1] * 100) if atr else None, 4),
                "rsi": round_num(csv_rsi if csv_rsi is not None else calc_rsi_wilder(closes), 2),
                "rsi_source": "pending_csv" if csv_rsi is not None else "computed_wilder_14",
                "bars_used": len(bars),
                "last_bar_date": bars[-1]["date"].strftime("%Y-%m-%d"),
                "bars_source": provider.last_source,
                "computed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "ok" if len(bars) >= 60 else "insufficient",
            }
            stock["ohlcv_status"] = "ok" if len(bars) >= 60 else f"insufficient({len(bars)} bars)"
        else:
            stock["ohlcv"] = []
            stock["technical"] = {
                "ma20": None, "ma50": None, "kdj_j": None, "kdj_k": None, "kdj_d": None,
                "macd_hist": None, "macd": None, "macd_signal": None,
                "atr_abs": None, "atr_pct_computed": None,
                "rsi": round_num(parse_num(row.get("RSI")), 2),
                "rsi_source": "pending_csv" if parse_num(row.get("RSI")) is not None else None,
                "bars_used": 0, "last_bar_date": None,
                "bars_source": None,
                "status": "unavailable",
                "reason": provider.network_error or "行情不可用",
                "error_log": provider.error_log.get(ticker),
            }
            stock["ohlcv_status"] = "unavailable"

        stocks.append(stock)

    stats = {
        "kline_ok": kline_ok,
        "kline_fail": kline_fail,
        "price_realtime": realtime_count,
        "price_last_close": last_close_count,
    }
    return stocks, stats


# ============================================================
# 6. GLOBAL MARKET
# ============================================================

def build_market(provider, regular_open=None):
    """全球市场资产：无论正常导出还是兜底降级流程，都必须实时抓取。

    数据口径（与东方财富 / Bloomberg 终端对齐）：
    - 美债收益率（US10Y/US2Y/US30Y）：优先 CNBC 现货收益率（Tradeweb 实时），
      直接采用其 last / change_pct；CNBC 失败回退 Yahoo 收益率指数实时报价，
      涨跌幅一律用 (现价 - 前收) / 前收 手动重算，不采用 yfinance 异常涨跌幅。
    - 三大股指：主抓 CME E-mini 期货（ES=F/NQ=F/YM=F，~23h 连续），
      盘外时段真实跳动；期货不可用回退现货指数。
    - 金 / 银：主抓伦敦现货（XAUUSD=X/XAGUSD=X），回退 COMEX 期货。
    - 实时报价不可用时回退最近一根已完成日线收盘价（明确标记 price_kind）；
      任何情况下都不读取、不复用旧 dashboard_data.json 里的宏观缓存。
    - JSON 记录 symbol_used：实际提供数据的 symbol（主抓 / 备用 / CNBC），
      主备切换全程透明可查。
    """
    updated_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assets = []
    ok = 0
    regular_open = us_regular_session_open() if regular_open is None else regular_open

    # CNBC 现货收益率：每次运行批量抓一次（逐 symbol 轻量请求，独立成败）
    cnbc_wanted = [c for *_rest, c in MARKET_ASSETS if c]
    cnbc_rates = {}
    if provider.available and cnbc_wanted:
        try:
            cnbc_rates = fetch_cnbc_rates(cnbc_wanted)
        except Exception:
            cnbc_rates = {}

    for label, primary, fallback, group, unit, cnbc_sym, regular_only in MARKET_ASSETS:
        item = {
            "symbol": primary,
            "symbol_used": None,
            "name": label,
            "group": group,
            "unit": unit,
            "price": None,
            "change_1d": None,
            "change_5d": None,
            "change_20d": None,
            "updated_at": updated_at if provider.available else None,
            "available": False,
            "source": None,
            "price_kind": None,
            "error": provider.network_error,
        }
        if provider.available:
            # ---- 日线（5d/20d 基准与前收）：主抓 -> 备用 ----
            bars = provider.daily_bars(primary, days=40)
            bars_used = primary
            if not bars and fallback:
                bars = provider.daily_bars(fallback, days=40)
                bars_used = fallback if bars else primary
            closes = [b["close"] for b in bars] if bars else []

            # ---- 实时报价：主抓 -> 备用 ----
            quote = provider.quote(primary)
            quote_used = primary
            if not quote and fallback:
                quote = provider.quote(fallback)
                quote_used = fallback if quote else primary
            live_price = parse_num(quote.get("price")) if quote else None

            # ---- CNBC 现货收益率优先（美债）----
            rate = cnbc_rates.get(cnbc_sym) if cnbc_sym else None

            def chg_from(base_price, n):
                if len(closes) > n and closes[-(n + 1)]:
                    return (base_price / closes[-(n + 1)] - 1) * 100
                return None

            if rate:
                # CNBC：last 与 change_pct 直接采用（Tradeweb 实时口径）
                item.update({
                    "price": round_num(rate["price"]),
                    "change_1d": round_num(rate["change_pct"], 4),
                    "price_kind": "live",
                    "source": "cnbc",
                    "symbol_used": f"CNBC:{cnbc_sym}",
                    "quote_ts": rate.get("asof"),
                })
            elif regular_only and not regular_open:
                # 股指盘外：保持“上一常规交易日收盘”静态不变，绝不取盘前/盘后跳动
                if closes:
                    item.update({
                        "price": round_num(closes[-1]),
                        "change_1d": round_num(chg_from(closes[-1], 1), 4),
                        "price_kind": "daily_close_frozen",
                        "source": provider.last_source,
                        "symbol_used": bars_used,
                        "frozen_outside_session": True,
                    })
                else:
                    errs = provider.error_log.get(primary) or []
                    item["error"] = " | ".join(errs[-3:]) if errs else (provider.network_error or "无可用日线")
            elif live_price and live_price > 0:
                # 实时报价：涨跌幅手动重算 = (现价 - 前收) / 前收，不用 yfinance 异常涨跌幅
                # 前收 = 最近一根已完成日线收盘（closes[-1]），避免相对前前日
                prev_close = closes[-1] if closes else None
                chg1 = ((live_price / prev_close - 1) * 100) if prev_close else None
                item.update({
                    "price": round_num(live_price),
                    "change_1d": round_num(chg1, 4),
                    "price_kind": "live",
                    "source": quote.get("source") or provider.last_source,
                    "symbol_used": quote_used,
                    "quote_ts": quote.get("ts"),
                })
            elif closes:
                item.update({
                    "price": round_num(closes[-1]),
                    "change_1d": round_num(chg_from(closes[-1], 1), 4),
                    "price_kind": "daily_close",
                    "source": provider.last_source,
                    "symbol_used": bars_used,
                })

            if item["price"] is not None:
                item.update({
                    "change_5d": round_num(chg_from(item["price"], 5), 4),
                    "change_20d": round_num(chg_from(item["price"], 20), 4),
                    "available": True,
                    "error": None,
                })
                if bars:
                    item["last_bar_date"] = bars[-1]["date"].strftime("%Y-%m-%d")
                ok += 1
            else:
                # 记录该 symbol 在每个后端的真实失败原因，不编造价格
                errs = provider.error_log.get(primary) or []
                item["error"] = " | ".join(errs[-3:]) if errs else (provider.network_error or "无可用行情")
        assets.append(item)
    return assets, ok


# ============================================================
# 7. OPTIONS
# ============================================================

def classify_wall(value, source, oi):
    """
    严格区分真实 OI Wall / 成交量代理 Wall / OI 不可用。
    返回 (value, source, is_true_oi, note)
    """
    src = clean_text(source).upper()
    v = parse_num(value)
    oi_v = parse_num(oi)
    if v is None:
        if src and "INVALID" in src:
            return None, clean_text(source) or None, False, "源数据标记为无效 Wall，不可作为 OI 使用"
        if src:
            return None, clean_text(source), False, f"Wall 数值为空（源={clean_text(source)}）"
        return None, None, False, "无 Wall 数据"
    if "INVALID" in src:
        return v, clean_text(source), False, "源数据标记为无效 Wall，数值不可信"
    if "VOLUME" in src or "PROXY" in src:
        return v, clean_text(source), False, "成交量代理 Wall，不是真实 OI"
    if "OI" in src:
        return v, clean_text(source), True, "真实 OI Wall" + (f"（OI={oi_v}）" if oi_v else "")
    return v, clean_text(source) or None, False, "Wall 来源未知，无法确认是否为真实 OI"


def build_options(option_rows, anomalies):
    out = []
    for row in option_rows:
        ticker = clean_text(row.get("Ticker")).upper()
        if not ticker:
            anomalies.append("option_strategies.csv 存在空 Ticker 行，已跳过")
            continue
        if not TICKER_RE.match(ticker):
            anomalies.append(f"option_strategies.csv 异常 Ticker：{ticker!r}")

        # premium 字段按优先级取，并记录来源，避免张冠李戴
        premium, premium_field = None, None
        for col in ("NetDebit", "EntryPrice", "PremiumCollected"):
            v = parse_num(row.get(col))
            if v is not None:
                premium, premium_field = v, col
                break

        call_wall, call_src, call_true, call_note = classify_wall(
            row.get("CallWall"), row.get("CallWallSource"), row.get("CallWallOI"))
        put_wall, put_src, put_true, put_note = classify_wall(
            row.get("PutWall"), row.get("PutWallSource"), row.get("PutWallOI"))

        out.append({
            "ticker": ticker,
            "name": clean_text(row.get("Name")) or ticker,
            "strategy": clean_text(row.get("Strategy")) or None,
            "option_type": clean_text(row.get("OptionType")) or None,
            "strategy_side": clean_text(row.get("StrategySide")) or None,
            "direction": clean_text(row.get("Direction")) or None,

            "strike": round_num(parse_num(row.get("Strike"))),
            "long_strike": round_num(parse_num(row.get("LongStrike"))),
            "short_strike": round_num(parse_num(row.get("ShortStrike"))),
            "expiry": clean_text(row.get("Expiry")) or None,
            "dte": int(parse_num(row.get("DTE"))) if parse_num(row.get("DTE")) is not None else None,

            "premium": round_num(premium),
            "premium_field": premium_field,
            "delta": round_num(parse_num(row.get("Delta")), 4),
            "put_delta": round_num(parse_num(row.get("PutDelta")), 4),
            "iv": round_num(parse_num(row.get("IV")), 4),
            "iv_regime": clean_text(row.get("IV_Regime")) or None,

            "break_even": round_num(parse_num(row.get("BreakEven"))),
            "max_loss": round_num(parse_num(row.get("MaxLoss"))),
            "max_profit": round_num(parse_num(row.get("MaxProfit"))),

            "entry_date": clean_text(row.get("EntryDate")) or None,
            "underlying_price": round_num(parse_num(row.get("UnderlyingPrice"))),
            "status": clean_text(row.get("Status")) or None,
            "quantity": int(parse_num(row.get("Quantity"))) if parse_num(row.get("Quantity")) is not None else None,
            "stop_loss": clean_text(row.get("StopLoss")) or None,
            "reason": clean_text(row.get("Reason")) or None,
            "earnings_date": clean_text(row.get("EarningsDate")) or None,
            "earnings_days": int(parse_num(row.get("EarningsDays"))) if parse_num(row.get("EarningsDays")) is not None else None,
            "scan_score": round_num(parse_num(row.get("ScanScore")), 2),

            "call_wall": call_wall,
            "put_wall": put_wall,
            "wall_source": call_src or put_src,
            "call_wall_source": call_src,
            "put_wall_source": put_src,
            "call_wall_oi": round_num(parse_num(row.get("CallWallOI")), 2),
            "put_wall_oi": round_num(parse_num(row.get("PutWallOI")), 2),
            "call_wall_unavailable": False,
            "put_wall_unavailable": False,
            "wall_is_true_oi": bool(call_true and put_true),
            "wall_note": " | ".join([x for x in (f"CALL: {call_note}", f"PUT: {put_note}") if x]),
        })
    return out


def _max_oi_strike(df):
    """返回 (strike, openInterest)：期权链中未平仓量最大的那一行；无效/全 0 返回 (None, None)。

    关键修复：OI 全为 0 或合计为 0 时，idxmax 会返回“第一行”从而给出任意 strike（如 100.0），
    造成“Call Wall 100.00 / OI 0”的异常显示。此处显式判定 sum(OI) <= 0 视为无效，
    绝不返回任何数值，交由上层标记为 N/A。
    """
    if df is None or getattr(df, "empty", True):
        return None, None
    col = None
    for c in ("openInterest", "open_interest", "OI"):
        if c in df.columns:
            col = c
            break
    if col is None or "strike" not in df.columns:
        return None, None
    d = df[["strike", col]].dropna()
    if d.empty:
        return None, None
    try:
        oi_sum = float(d[col].sum())
    except Exception:
        return None, None
    # 关键修复：OI 合计 <= 0（含全 0）一律视为无效数据，不返回任何 strike
    if oi_sum <= 0:
        return None, None
    try:
        row = d.loc[d[col].idxmax()]
    except Exception:
        return None, None
    return parse_num(row.get("strike")), parse_num(row.get(col))


def _fetch_option_chain(yf, symbol, expiry, tries=3, sleep_base=1.0):
    """带重试地抓取期权链；任何失败都抛异常由上层捕获，绝不伪造。

    - 请求到期日不在可用列表时，回退到“最近的可用的 >= 该日”的到期日，仍取不到则抛错。
    - 网络/限流等瞬时错误重试最多 tries 次，指数退避。
    """
    last = None
    for attempt in range(1, tries + 1):
        try:
            tk = yf.Ticker(symbol)
            avail = list(getattr(tk, "options", None) or [])
            use_expiry = expiry
            if expiry and expiry not in avail:
                cand = sorted([e for e in avail if e >= expiry]) if avail else []
                use_expiry = cand[0] if cand else (avail[0] if avail else None)
            if not use_expiry:
                raise ValueError(f"无可用到期日（请求 {expiry or 'N/A'}）")
            chain = tk.option_chain(use_expiry)
            return chain, use_expiry
        except Exception as e:  # noqa: BLE001 - yfinance 异常类型不可枚举，统一重试/上报
            last = e
            if attempt < tries:
                time.sleep(sleep_base * attempt)
    raise last or RuntimeError("期权链获取失败")


def _is_monthly_expiry(date_str):
    """标准月度期权到期日 = 当月第 3 个星期五（weekday==4 且 15<=day<=21）。

    月度合约通常是持仓量最集中的“主力量化墙”，作为特定到期日 OI 为空时的回退参考。
    """
    try:
        d = dt.datetime.strptime(str(date_str), "%Y-%m-%d").date()
    except Exception:
        return False
    return d.weekday() == 4 and 15 <= d.day <= 21


def _find_primary_monthly_wall(yf, symbol, preferred_expiry, tries=3, max_scan=12):
    """特定到期日 OI 为空时的主力月度合约回退。

    流程：
      1. 取该标的全部可用到期日，筛出月度合约（第 3 周五），按离 preferred_expiry 由近到远排序。
      2. 先试最近的 1-2 个；若仍无 OI，再扫描其余月度（上限 max_scan 个）找任一有 OI 的。
      3. 返回 (call_strike, call_oi, put_strike, put_oi, used_expiry)；仅当所有月度合约 OI 全为空才返回 None。

    绝不伪造数值：所有到期日都无有效 OI 时返回 None，交由上层标记 N/A。
    """
    try:
        tk = yf.Ticker(symbol)
        avail = list(getattr(tk, "options", None) or [])
    except Exception:
        return None
    if not avail:
        return None
    monthlies = sorted([e for e in avail if _is_monthly_expiry(e)])
    if not monthlies:  # 无法识别月度时用全部到期日兜底
        monthlies = sorted(avail)

    def _dist(e):
        try:
            ed = dt.datetime.strptime(e, "%Y-%m-%d").date()
        except Exception:
            return 1 << 30
        ref = preferred_expiry
        if ref:
            try:
                return abs((ed - dt.datetime.strptime(ref, "%Y-%m-%d").date()).days)
            except Exception:
                pass
        return abs((ed - dt.date.today()).days)

    ordered = sorted(monthlies, key=_dist)
    ordered = [e for e in ordered if e != preferred_expiry]  # 排除已尝试过的请求到期日

    scanned = 0
    for e in ordered:
        if scanned >= max_scan:
            break
        scanned += 1
        try:
            chain, _ = _fetch_option_chain(yf, symbol, e, tries=tries)
        except Exception:
            continue
        cs, co = _max_oi_strike(getattr(chain, "calls", None))
        ps, po = _max_oi_strike(getattr(chain, "puts", None))
        if cs is not None and ps is not None:
            return cs, co, ps, po, e
    return None


def _is_real_oi_source(src):
    """判断 wall 来源是否为“真实 OI”（期权链最大 OI 或主力月度合约回退）。"""
    return bool(src) and ("max_oi" in src or "near_month_primary" in src)


def enrich_option_walls(options, provider, anomalies, notes=None):
    """用 yfinance 真实期权链补齐缺失 / LEGACY_INVALID_WALL 的 Call Wall / Put Wall。

    口径（严格按 Open Interest，不用成交量代理）：
      Call Wall = 该到期日 Call 链中 openInterest 最大的 strike
      Put  Wall = 该到期日 Put  链中 openInterest 最大的 strike

    特定到期日 OI 为空（远期/薄合约常态）时的回退：
      自动取该标的全部到期日，筛选月度合约（第 3 周五），回退到离请求到期日最近的
      1-2 个主力月度合约作为参考 Wall，wall_source 标 "yfinance_near_month_primary"。
      仅当所有到期日 OI 全为空才标记 N/A，**绝不伪造数值**。

    只处理 wall 为空或来源标记含 INVALID 的条目；已有真实 OI 的不动。
    取不到期权链时保留原标记并记入 anomalies，**绝不伪造数值**。
    """
    yf = getattr(provider, "_yf", None)
    if yf is None:
        if notes is not None:
            notes.append("yfinance 不可用，跳过期权 Wall 计算，保留源数据原标记（不伪造）。")
        return []

    def _needs(o, key, src_key):
        return o.get(key) is None or "INVALID" in ((o.get(src_key) or "").upper())

    fixed = []
    for o in options:
        need_call = _needs(o, "call_wall", "call_wall_source")
        need_put = _needs(o, "put_wall", "put_wall_source")
        if not (need_call or need_put):
            continue

        symbol = o.get("ticker")
        expiry = o.get("expiry")
        try:
            chain, used_expiry = _fetch_option_chain(yf, symbol, expiry, tries=3)
        except Exception as e:
            anomalies.append(
                f"{symbol}: 期权链获取失败（{type(e).__name__}: {e}），保留原 Wall 标记，不伪造数值")
            continue

        call_strike, call_oi = (None, None)
        put_strike, put_oi = (None, None)
        if need_call:
            call_strike, call_oi = _max_oi_strike(getattr(chain, "calls", None))
        if need_put:
            put_strike, put_oi = _max_oi_strike(getattr(chain, "puts", None))

        # ---- 主力月度合约回退：特定到期日 OI 为空时不直接放弃 ----
        primary_used = None
        primary_note = None
        if (need_call and call_strike is None) or (need_put and put_strike is None):
            primary = _find_primary_monthly_wall(yf, symbol, expiry, tries=3)
            if primary:
                pcs, pco, pps, ppo, pexp = primary
                if need_call and call_strike is None:
                    call_strike, call_oi = pcs, pco
                if need_put and put_strike is None:
                    put_strike, put_oi = pps, ppo
                primary_used = pexp
                primary_note = (
                    f"原始到期日 {expiry or 'N/A'} OI 为空，已自动回退主力月度合约 "
                    f"{pexp}（NEAR_MONTH_PRIMARY）")

        changed = False
        parts = []
        if primary_note:
            parts.append(primary_note)
        # ---- Call Wall：仅在拿到真实 OI 时赋值；否则显式标记 N/A，绝不给默认数值 ----
        if need_call:
            if call_strike is not None:
                o["call_wall"] = round_num(call_strike)
                o["call_wall_oi"] = round_num(call_oi)
                o["call_wall_source"] = ("yfinance_near_month_primary" if primary_used
                                         else "yfinance_option_chain_max_oi")
                parts.append(f"CALL: 真实期权链 OI 最大 strike={call_strike}（OI={call_oi}）")
                changed = True
            else:
                o["call_wall"] = None
                o["call_wall_oi"] = None
                o["call_wall_unavailable"] = True
                parts.append("CALL: 所有到期日期权链均无有效 OI，Call Wall = N/A，不伪造数值")
        # ---- Put Wall：同上 ----
        if need_put:
            if put_strike is not None:
                o["put_wall"] = round_num(put_strike)
                o["put_wall_oi"] = round_num(put_oi)
                o["put_wall_source"] = ("yfinance_near_month_primary" if primary_used
                                        else "yfinance_option_chain_max_oi")
                parts.append(f"PUT: 真实期权链 OI 最大 strike={put_strike}（OI={put_oi}）")
                changed = True
            else:
                o["put_wall"] = None
                o["put_wall_oi"] = None
                o["put_wall_unavailable"] = True
                parts.append("PUT: 所有到期日期权链均无有效 OI，Put Wall = N/A，不伪造数值")

        if changed:
            o["wall_source"] = ("yfinance_near_month_primary" if primary_used
                                else "yfinance_option_chain_max_oi")
            o["wall_is_true_oi"] = bool(
                _is_real_oi_source(o.get("call_wall_source"))
                and _is_real_oi_source(o.get("put_wall_source")))
            o["wall_expiry_used"] = primary_used or used_expiry
        if parts:
            o["wall_note"] = " | ".join(parts)
        if changed or parts:
            fixed.append(symbol)

    if notes is not None:
        if fixed:
            notes.append("期权 Wall 已按真实期权链 OI 重算：" + "、".join(sorted(set(fixed))))
        else:
            notes.append("期权 Wall 本次未重算（无缺失项或期权链不可用）。")
    return fixed


# ============================================================
# 8. REVIEW
# ============================================================

def _event_key(ticker, rec_date, tag):
    return (str(ticker).upper(), str(rec_date), str(tag))


def build_events(trade_rows, review_rows, anomalies):
    """
    复刻 review.py 的推荐事件账本（review.py:2100-2248）：
    - 主键 = (Ticker, Rec_Date, Tag)
    - 来源优先级：review_history.csv（含 Cur_Price 兜底） > trade_history.csv 补充
    同时返回 price_lookup：key -> 该推荐最近一次有价格的 Review 快照价
    """
    events = {}
    price_lookup = {}
    # 价格兜底：最新一条的 Cur_Price 为空时，回退到该推荐最近一次「有 Cur_Price」的快照
    # （trade_history.Close_Price 是建仓快照价，不能当现价用，故不采用）
    groups = {}
    for r in review_rows:
        ticker = clean_text(r.get("Ticker")).upper()
        rec_date = parse_date(r.get("Rec_Date"))
        tag = clean_text(r.get("Tag"))
        if not ticker or rec_date is None:
            continue
        key = _event_key(ticker, rec_date.strftime("%Y-%m-%d"), tag)
        rv_date = parse_date(r.get("Review_Date")) or dt.date.min
        groups.setdefault(key, []).append((rv_date, r))

    for key, items in groups.items():
        items.sort(key=lambda x: x[0])
        latest_row = items[-1][1]
        priced = [r for _, r in items if parse_num(r.get("Cur_Price")) is not None]
        row = priced[-1] if priced else latest_row
        ticker, rec_date_str, tag = key
        rec_price = parse_num(row.get("Rec_Price"))
        cur = parse_num(row.get("Cur_Price"))
        pnl = parse_num(row.get("PnL_Pct"))
        if pnl is None and cur is not None and rec_price and rec_price > 0:
            pnl = round((cur - rec_price) / rec_price * 100, 2)
        status = clean_text(row.get("Status"))
        events[key] = {
            "ticker": ticker,
            "name": clean_text(row.get("Name")) or ticker,
            "rec_date": rec_date_str,
            "tag": tag,
            "status": status,
            "rec_price": rec_price,
            "cur_price": cur,
            "pnl": pnl,
            "source": "review_history",
        }
        if cur is not None:
            price_lookup[key] = cur

    # 来源 2：trade_history.csv 补充（不覆盖来源 1）
    for r in trade_rows:
        ticker = clean_text(r.get("Ticker")).upper()
        rec_date = parse_date(r.get("Date"))
        tag = clean_text(r.get("Tag"))
        if not ticker or rec_date is None:
            continue
        if not TICKER_RE.match(ticker):
            anomalies.append(f"trade_history.csv 异常 Ticker：{ticker!r}")
        key = _event_key(ticker, rec_date.strftime("%Y-%m-%d"), tag)
        if key in events:
            continue
        rec_price = None
        for col in ("Price", "Scan_Ref_Price", "Close_Price", "Prev_Close"):  # review.py:426
            v = parse_num(r.get(col))
            if v and v > 0:
                rec_price = v
                break
        status = clean_text(r.get("Status"))
        exit_price = parse_num(r.get("Exit_Price"))
        cur = exit_price if (status in CLOSED_STOCK_STATUSES and exit_price is not None) else None
        pnl = ((cur - rec_price) / rec_price * 100) if (cur and rec_price and rec_price > 0) else None
        events[key] = {
            "ticker": ticker,
            "name": clean_text(r.get("Name")) or ticker,
            "rec_date": rec_date.strftime("%Y-%m-%d"),
            "tag": tag,
            "status": status,
            "rec_price": rec_price,
            "cur_price": cur,
            "pnl": round(pnl, 2) if pnl is not None else None,
            "source": "trade_history",
        }
    return list(events.values()), price_lookup


def build_active_positions(trade_rows, cutoff, price_lookup, stock_price_map):
    """
    实际持仓候选：完全按 review.py:1542-1557 的口径 ——
    只认 trade_history 中 status ∈ {"", "Active", "pending"} 的非 Observation 推荐事件，
    （trade_history.Close_Price 是建仓快照价，不能当现价，故不作为价格来源）
    """
    out = []
    for r in trade_rows:
        ticker = clean_text(r.get("Ticker")).upper()
        rec_date = parse_date(r.get("Date"))
        tag = clean_text(r.get("Tag"))
        if not ticker or rec_date is None or rec_date < cutoff:
            continue
        if tag == "Observation":
            continue
        status = clean_text(r.get("Status"))
        if status not in ACTIVE_STATUSES:
            continue
        rec_price = None
        for col in ("Price", "Scan_Ref_Price", "Close_Price", "Prev_Close"):  # review.py:426
            v = parse_num(r.get(col))
            if v and v > 0:
                rec_price = v
                break
        if not rec_price:
            continue
        key = _event_key(ticker, rec_date.strftime("%Y-%m-%d"), tag)
        cur = stock_price_map.get(ticker)
        if cur is None:
            cur = price_lookup.get(key)
        pnl = round((cur - rec_price) / rec_price * 100, 2) if (cur and rec_price > 0) else None
        out.append({"ticker": ticker, "tag": tag, "status": status, "rec_date": key[1],
                    "rec_price": rec_price, "cur_price": cur, "pnl": pnl})
    return out


def backfill_event_prices(events, provider, price_map, notes=None, max_symbols=80):
    """为缺少当前价的推荐事件补价（Review 口径不变，只补价格这一项输入）。

    事件记账里有很多历史推荐标的，它们不在当期 pending 池内，只补当期 8 只
    并不能解决 partial。因此这里按事件 ticker 单独取价：
    实时报价优先，其次最新完整交易日 close。取不到就不补（保持 null）。
    """
    if not provider.available:
        return {"fetched": 0, "attempted": 0, "sources": {}}

    need = sorted({e["ticker"] for e in events
                   if e["pnl"] is None and e["ticker"] not in price_map
                   and TICKER_RE.match(e["ticker"] or "")})
    if not need:
        return {"fetched": 0, "attempted": 0, "sources": {}}

    if len(need) > max_symbols:
        if notes is not None:
            notes.append(f"需要补价的历史标的 {len(need)} 个，本次按上限只处理前 {max_symbols} 个")
        need = need[:max_symbols]

    sources = {}
    for t in need:
        q = provider.quote(t)
        if q and q.get("price"):
            price_map[t] = q["price"]
            sources[t] = "realtime"
            continue
        bars = provider.daily_bars(t, days=5)
        if bars:
            price_map[t] = bars[-1]["close"]
            sources[t] = "last_close"
    return {"fetched": len(sources), "attempted": len(need), "sources": sources}


def build_review(events, price_lookup, trade_rows, stock_price_map, notes, missing):
    asof = now_us()
    cutoff = asof.date() - dt.timedelta(days=30)   # review.py:2267 近 30 天窗口

    def in_window(e):
        d = parse_date(e["rec_date"])
        return d is not None and d >= cutoff

    # 用本次 K 线抓到的最后收盘价刷新当前价（与 review.py price_map_today 作用一致）
    refreshed = 0
    for e in events:
        if e["cur_price"] is None and e["ticker"] in stock_price_map:
            e["cur_price"] = stock_price_map[e["ticker"]]
            refreshed += 1
        if e["pnl"] is None and e["cur_price"] is not None and e["rec_price"]:
            e["pnl"] = round((e["cur_price"] - e["rec_price"]) / e["rec_price"] * 100, 2)

    win = [e for e in events if in_window(e)]
    core_events = [e for e in win if e["tag"] != "Observation"]      # review.py:2302
    obs_events = [e for e in win if e["tag"] == "Observation"]       # review.py:2307

    def split(events_):
        closed_all = [e for e in events_ if e["status"] in CLOSED_STOCK_STATUSES]
        open_all = [e for e in events_ if e["status"] not in CLOSED_STOCK_STATUSES]
        closed = [e for e in closed_all if e["pnl"] is not None]
        opened = [e for e in open_all if e["pnl"] is not None]
        return closed, opened, closed_all, open_all

    core_closed, core_open, core_closed_all, core_open_all = split(core_events)
    obs_closed, obs_open, obs_closed_all, obs_open_all = split(obs_events)

    # 实际持仓：review.py:1542-1557 口径（见 build_active_positions）
    active_candidates = build_active_positions(trade_rows, cutoff, price_lookup, stock_price_map)
    active = [e for e in active_candidates if e["pnl"] is not None]

    def kpi(resolved, total_all):
        """
        返回 (value, status, unresolved)。
        缺当前价导致一条都算不出来时输出 null —— 绝不把「没数据」伪装成 0。
        """
        unresolved = max(0, total_all - len(resolved))
        if len(resolved) > 0:
            return len(resolved), ("complete" if unresolved == 0 else "partial"), unresolved
        if unresolved > 0:
            return None, f"unavailable：{unresolved} 条事件缺当前价，未计入", unresolved
        return 0, "complete", 0

    core_closed_v, core_closed_s, core_closed_u = kpi(core_closed, len(core_closed_all))
    core_open_v, core_open_s, core_open_u = kpi(core_open, len(core_open_all))
    obs_closed_v, obs_closed_s, obs_closed_u = kpi(obs_closed, len(obs_closed_all))
    obs_open_v, obs_open_s, obs_open_u = kpi(obs_open, len(obs_open_all))
    active_v, active_s, active_u = kpi(active, len(active_candidates))

    def win_rate(items):
        if not items:
            return None
        w = sum(1 for e in items if (e["pnl"] or 0) > 0)
        return round(w / len(items) * 100, 2)

    unresolved = sum(1 for e in win if e["pnl"] is None)
    if unresolved:
        notes.append(
            f"近30天 {len(win)} 条推荐事件中有 {unresolved} 条无法取得当前价"
            f"（未平仓且无 Cur_Price 兜底、本次也未抓到行情），这些事件不计入 Completed/Current 计数；"
            f"受影响的 KPI 已标记 partial / unavailable。"
        )
    for name, st in (("core_closed_count", core_closed_s), ("core_open_count", core_open_s),
                     ("observation_closed_count", obs_closed_s), ("observation_open_count", obs_open_s),
                     ("actual_active_count", active_s)):
        if st != "complete":
            missing.append(f"review.{name} ({st})")

    review = {
        "window_days": 30,
        "as_of_us": asof.strftime("%Y-%m-%d %H:%M:%S"),
        "window_start": cutoff.strftime("%Y-%m-%d"),

        "core_closed_count": core_closed_v,
        "core_open_count": core_open_v,
        "observation_closed_count": obs_closed_v,
        "observation_open_count": obs_open_v,
        "actual_active_count": active_v,

        "core_closed_count_status": core_closed_s,
        "core_open_count_status": core_open_s,
        "observation_closed_count_status": obs_closed_s,
        "observation_open_count_status": obs_open_s,
        "actual_active_count_status": active_s,
        "core_closed_unresolved": core_closed_u,
        "core_open_unresolved": core_open_u,
        "observation_closed_unresolved": obs_closed_u,
        "observation_open_unresolved": obs_open_u,
        "actual_active_unresolved": active_u,

        "core_event_count": len(core_events),
        "observation_event_count": len(obs_events),
        "actual_active_candidate_count": len(active_candidates),

        "core_closed_win_rate": win_rate(core_closed),
        "core_open_win_rate": win_rate(core_open),
        "observation_closed_win_rate": win_rate(obs_closed),
        "observation_open_win_rate": win_rate(obs_open),
        "actual_active_win_rate": win_rate(active),

        "stop_loss_hit_count": sum(
            1 for e in win
            if e["status"] in {"Stop_Loss_Hit", "移动止损清仓", "止损触发清仓"}
        ),
        "price_source": "ohlcv_last_close" if stock_price_map else "review_history_Cur_Price / Exit_Price",
        "price_refreshed_count": refreshed,
        "unresolved_pnl_events": unresolved,
        "notes": notes,
        "missing_fields": missing,
    }
    return review


# ============================================================
# 9. HISTORY
# ============================================================

def build_history(review_rows, notes):
    """以 review_history.csv 的每日快照构造基础 history。"""
    if not review_rows:
        notes.append("history：缺少 review_history.csv，无法构造历史序列（留空，不伪造）。")
        return []

    by_date = {}
    for r in review_rows:
        d = parse_date(r.get("Review_Date"))
        ticker = clean_text(r.get("Ticker")).upper()
        rec_date = parse_date(r.get("Rec_Date"))
        tag = clean_text(r.get("Tag"))
        status = clean_text(r.get("Status"))
        if d is None or not ticker:
            continue
        slot = by_date.setdefault(d, {"Core_Dragon": set(), "Observation": set()})
        if tag in ("Core_Dragon", "Observation") and status in OPEN_TRACK_STATUSES:
            slot[tag].add((ticker, rec_date.strftime("%Y-%m-%d") if rec_date else ""))

    hist = []
    for d in sorted(by_date.keys()):
        slot = by_date[d]
        hist.append({
            "date": d.strftime("%Y-%m-%d"),
            "core_count": len(slot["Core_Dragon"]),
            "observation_count": len(slot["Observation"]),
        })
    notes.append(
        "history：基于 review_history.csv 的每日快照，统计口径=当日仍在跟踪(持仓中/观察推荐)"
        "的去重推荐事件数（Ticker+Rec_Date），非当日新增数。"
    )
    return hist


# ============================================================
# 10. 主流程
# ============================================================

def count_nulls(stocks, keys):
    """统计指定字段为 null 的股票数量。"""
    res = {}
    for k in keys:
        res[k] = sum(1 for s in stocks if s.get(k) is None)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成 Dashboard 使用的 dashboard_data.json（只读导出层）")
    ap.add_argument("--data-dir", default=str(SCRIPT_DIR),
                    help="数据目录（默认脚本所在目录），需包含 us_stocks_pending_*.csv / trade_history.csv")
    ap.add_argument("--out", default=None,
                    help="输出 JSON 路径（默认优先写入 us-market-terminal/dashboard/data/，"
                         "否则 <data-dir>/dashboard/data/dashboard_data.json）")
    ap.add_argument("--kline-bars", type=int, default=180, help="K 线保留的完整交易日数量（默认 180）")
    ap.add_argument("--no-network", action="store_true", help="完全跳过行情抓取")
    ap.add_argument("--provider", default="auto", choices=["auto", "yf", "yahoo", "stooq", "none"],
                    help="行情提供者：auto=yfinance -> Yahoo HTTP -> Stooq 依次降级")
    ap.add_argument("--no-stooq", action="store_true",
                    help="禁用 Stooq 备用源（默认在前两个源都失败时启用）")
    ap.add_argument("--timeout", type=int, default=REQUEST_TIMEOUT, help="单次行情请求超时秒数")
    ap.add_argument("--retries", type=int, default=2, help="单个 symbol 的 HTTP 重试次数")
    ap.add_argument("--no-mirror", action="store_true",
                    help="不把 JSON 同步写入 us-market-terminal/dashboard/data/")
    args = ap.parse_args(argv)

    data_dir = Path(args.data_dir).resolve()
    if args.out:
        out_path = Path(args.out).resolve()
    else:
        # 阶段 B：前端通过相对路径 dashboard/data/dashboard_data.json 读取，
        # 默认直接写到前端目录，避免导出后忘记拷贝导致页面读旧数据。
        frontend_out = SCRIPT_DIR / "us-market-terminal" / "dashboard" / "data" / "dashboard_data.json"
        out_path = frontend_out if (SCRIPT_DIR / "us-market-terminal").is_dir() \
            else data_dir / "dashboard" / "data" / "dashboard_data.json"

    log("=" * 62)
    log("dashboard_export.py —— Dashboard 真实数据导出（只读）")
    log("=" * 62)
    log(f"数据目录：{data_dir}")

    # ---- 采集容器（提前初始化，输入文件阶段的降级提示也要记录）----
    anomalies = []
    notes = []
    missing = []
    warnings = []

    # ---- 输入文件 ----
    pending_path = find_latest_pending(data_dir)
    stocks_source = None
    if pending_path is None:
        # 盘后复盘流程会消费掉当日 pending CSV。此时绝不能把持仓清空：
        # 先复用上一版 dashboard_data.json 的 Core / Observation 名单，
        # 行情 / K线 / 技术指标照常重新抓取刷新。
        log("[WARN] 未找到任何 us_stocks_pending_YYYYMMDD.csv"
            "（通常是盘后复盘已消费当日文件，或当日尚未扫描）。")
        fallback_rows, fallback_src = load_fallback_stock_rows(data_dir)
        if fallback_rows:
            log(f"       已复用上一版 dashboard_data.json 的股票名单：{len(fallback_rows)} 只，"
                f"行情 / 技术指标照常刷新。")
            log("       兜底模式下全球市场（商品/外汇/股指等）同样强制实时抓取，"
                "绝不复用旧 JSON 的宏观缓存。")
            notes.append(
                "未找到新的 pending CSV，已复用上一版 dashboard_data.json 中的 "
                f"Core/Observation 名单（{len(fallback_rows)} 只）并刷新行情与技术指标；"
                "名单未发生清空。"
            )
            notes.append(
                "兜底保护模式：旧 JSON 仅用于复原股票名单与基本面快照；"
                "全球市场宏观指标在后续 MARKET 阶段通过行情源强制重新实时抓取"
                "（含盘前盘后报价），未复用旧 JSON 中的任何宏观价格。"
            )
            pending_rows = fallback_rows
            stocks_source = "existing_dashboard_json"
        else:
            log("       上一版 dashboard_data.json 也不存在或无股票，stocks 输出空数组。")
            notes.append(
                "未找到新的 pending CSV，且上一版 dashboard_data.json 不可用，"
                "Core / Observation 为空数组；全球市场与期权数据照常刷新。"
            )
            pending_rows = []
    else:
        log(f"pending CSV：{pending_path.name}")
        pending_rows = read_csv_rows(pending_path)
        stocks_source = "scan_pending_csv"

    trade_path = require_file(data_dir / TRADE_HISTORY_NAME, "推荐事件账本")
    option_path = data_dir / OPTION_CSV_NAME
    params_path = data_dir / PARAMS_NAME
    review_hist_path = data_dir / REVIEW_HISTORY_NAME
    version_path = data_dir / VERSION_NAME

    trade_rows = read_csv_rows(trade_path)
    option_rows = read_csv_rows(option_path) if option_path.exists() else None
    review_rows = read_csv_rows(review_hist_path) if review_hist_path.exists() else []

    if option_rows is None:
        log(f"[WARN] 未找到 {OPTION_CSV_NAME}，options 输出为空数组（不会伪造期权数据）")
        option_rows = []
    if not review_rows:
        log(f"[WARN] 未找到或为空：{REVIEW_HISTORY_NAME}（history 将为空，Review 仅用 trade_history 口径）")

    params = None
    if params_path.exists():
        try:
            params = json.loads(params_path.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"[WARN] 读取 {PARAMS_NAME} 失败：{e}")
    else:
        log(f"[WARN] 未找到 {PARAMS_NAME}（仅影响 meta，不影响主数据）")

    # ---- 行情 ----
    provider = QuoteProvider(
        mode=("none" if args.no_network else args.provider),
        timeout=args.timeout,
        allow_stooq=(not args.no_stooq),
        retries=args.retries,
    )
    if provider.available:
        log(f"行情提供者优先级    ： {' -> '.join(provider.backends)}")
    else:
        log(f"[WARN] 行情不可用：{provider.network_error or '未知原因'}。"
            f"K线/技术指标与全球市场行情将输出 null（不伪造、不硬编码）。")

    # ---- STOCKS ----
    stocks, kstats = build_stocks(pending_rows, provider, args.kline_bars, anomalies, warnings)
    if not stocks:
        # 自愈守卫：本次构建为空（无 pending / pending 为空）时，
        # 回退复用上一版 dashboard_data.json 的名单，杜绝把持仓清空成 []。
        fb_rows, _ = load_fallback_stock_rows(data_dir)
        if fb_rows:
            log(f"[WARN] 本次构建结果为空，回退复用上一版 JSON 名单（{len(fb_rows)} 只），"
                f"行情 / 技术指标照常刷新。")
            notes.append(
                f"本次 pending 来源未产出任何股票，已回退复用上一版 dashboard_data.json 的 "
                f"名单（{len(fb_rows)} 只）并刷新行情；stocks 未写空。"
            )
            stocks, kstats = build_stocks(
                fb_rows, provider, args.kline_bars, anomalies, warnings)
            stocks_source = "existing_dashboard_json"
    kline_ok, kline_fail = kstats["kline_ok"], kstats["kline_fail"]
    technical_ok = sum(1 for s in stocks if s["technical"]["status"] == "ok")
    price_live = sum(1 for s in stocks if s["price_source"] in ("realtime", "realtime_unverified", "last_close"))
    core_count = sum(1 for s in stocks if s["bucket"] == "Core")
    obs_count = sum(1 for s in stocks if s["bucket"] == "Observation")

    # ---- AI 六段：本次为空时，从历史 pending / scan_results CSV 回填同名 Ticker 文本 ----
    # 只搬运历史已生成的真实文本；本脚本不调用任何 AI 接口、不生成文案。
    ai_backfilled = backfill_ai_fields(
        stocks, data_dir, current_pending=pending_path, notes=notes)

    # ---- AI 六段状态（只统计，不生成内容）----
    first_row = pending_rows[0] if pending_rows else {}
    ai_cols_present = [c for c, _ in AI_FIELD_MAP if c in first_row]
    ai_cols_missing = [c for c, _ in AI_FIELD_MAP if c not in first_row]
    ai_filled = sum(1 for s in stocks if any((s.get("ai") or {}).values()))
    ai_scan_date = clean_text(first_row.get("Date")) or None
    if ai_filled == 0:
        ai_status = "pending"          # 本次与历史都没有可用的 AI 文本
    elif ai_filled < len(stocks):
        ai_status = "partial"
    else:
        ai_status = "complete"

    # ---- MARKET ----
    # 无论正常导出还是兜底降级（stocks_source == existing_dashboard_json），
    # 宏观指标都走到这里通过行情源强制实时抓取，绝不复用旧 JSON 的宏观缓存。
    market_assets, market_ok = build_market(provider)
    live_count = sum(1 for a in market_assets if a.get("price_kind") == "live")
    frozen_count = sum(1 for a in market_assets if a.get("price_kind") == "daily_close_frozen")
    cnbc_count = sum(1 for a in market_assets if a.get("source") == "cnbc")
    log(f"全球市场：{market_ok}/{len(market_assets)} 可用，实时 {live_count} 只"
        f"（CNBC 现货收益率 {cnbc_count} 只；盘外静态收盘 {frozen_count} 只；"
        f"绝不使用旧 JSON 宏观缓存）")
    regime_market = None
    regime_vix = None
    for s in stocks:
        if s.get("market_regime") and regime_market is None:
            regime_market = s["market_regime"]
        if s.get("vix") is not None and regime_vix is None:
            regime_vix = s["vix"]
    if regime_market is None:
        missing.append("regime.market")
        notes.append("Market_Regime 在 pending CSV 中为空，regime.market 输出 null。")
    if regime_vix is None:
        missing.append("regime.vix")

    market = {
        "regime": {"market": regime_market, "vix": regime_vix,
                   "source": "pending CSV Market_Regime / VIX 列（不重新设计 Regime 规则）"},
        "assets": market_assets,
        "available_count": market_ok,
        "total_count": len(market_assets),
        "live_quote_count": live_count,
        "frozen_outside_session_count": frozen_count,
        "provider": provider.name,
        "source_used": sorted({a["source"] for a in market_assets if a.get("source")}),
        "refresh_policy": "indices_frozen_outside_session; rates_cnbc_24h; commodities_forex_24h（禁止复用旧 JSON 宏观缓存）",
        "updated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # ---- OPTIONS ----
    options = build_options(option_rows, anomalies)
    # Wall 为空或标记为 LEGACY_INVALID_WALL 时，用 yfinance 真实期权链 OI 重算
    wall_fixed = enrich_option_walls(options, provider, anomalies, notes)
    active_options = sum(1 for o in options if (o.get("status") or "").lower() == "active")

    # ---- REVIEW ----
    # 用本次抓到的行情补齐当前价（实时价优先，其次最新完整交易日收盘），
    # 与 review.py price_map_today 的作用一致，不改变 Review 的任何口径。
    events, price_lookup = build_events(trade_rows, review_rows, anomalies)
    stock_price_map = {}
    for s in stocks:
        if s.get("current_price"):
            stock_price_map[s["ticker"]] = s["current_price"]
        elif s.get("ohlcv"):
            stock_price_map[s["ticker"]] = s["ohlcv"][-1]["close"]
    # 历史推荐标的（不在当期池内）也要补价，否则 Review 一直是 partial
    backfill = backfill_event_prices(events, provider, stock_price_map, notes)
    review = build_review(events, price_lookup, trade_rows, stock_price_map, notes, missing)
    review["price_backfill_count"] = backfill["fetched"]
    review["price_backfill_attempted"] = backfill["attempted"]
    review["price_backfill_sources"] = backfill["sources"]
    review["active_options_count"] = active_options

    # ---- HISTORY ----
    history = build_history(review_rows, notes)

    # ---- 组装 ----
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stocks": stocks,
        "market": market,
        "options": options,
        "review": review,
        "history": history,
        "meta": {
            "data_source": (
                f"{(pending_path.name + ' + ') if pending_path else ''}"
                f"{TRADE_HISTORY_NAME} + {OPTION_CSV_NAME}"
                + (f" + {REVIEW_HISTORY_NAME}" if review_rows else "")
            ),
            "ai_generated_at": (ai_scan_date if ai_status in ("partial", "complete") else None),
            "ai_status": ai_status,
            "ai_stocks_filled": ai_filled,
            "ai_fields_present": ai_cols_present,
            "ai_fields_pending": ai_cols_missing,
            "ai_backfilled": sorted(set(ai_backfilled)),
            "ai_backfilled_count": len(set(ai_backfilled)),
            "ai_calls": 0,
            "pending_csv": (pending_path.name if pending_path else None),
            "stocks_source": stocks_source,
            "pending_scan_date": (clean_text(pending_rows[0].get("Date")) if pending_rows else None),
            "quote_provider": provider.name,
            "quote_backends": provider.backends,
            "network_status": "ok" if provider.available else f"unavailable: {provider.network_error}",
            "kline_bars_target": args.kline_bars,
            "market_updated_at": market["updated_at"] if market_ok else None,
            "technical_updated_at": (
                dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if technical_ok else None
            ),
            "counts": {
                "core": core_count,
                "observation": obs_count,
                "market_available": market_ok,
                "market_total": len(market_assets),
                "kline_ok": kline_ok,
                "kline_fail": kline_fail,
                "technical_ok": technical_ok,
                "price_live": price_live,
                "price_realtime": kstats["price_realtime"],
                "price_last_close": kstats["price_last_close"],
                "wall_recomputed": len(set(wall_fixed)),
                "wall_true_oi": sum(1 for o in options if o.get("wall_is_true_oi")),
            },
            "warnings": warnings,
            "unit_hints": UNIT_HINT,
            "strategy_params": params,
            "scan_version": (version_path.read_text(encoding="utf-8").strip()
                             if version_path.exists() else None),
            "anomalies": anomalies,
            "notes": notes,
            "missing_fields": missing,
            "schema_hint": {
                "stocks[]": "pending CSV 派生；technical 为 OHLCV 计算值；ohlcv 为完整日线（已剔除未完成 K 棒）",
                "market.assets[]": "13 项全球市场资产；price/change_* 未取到时为 null",
                "options[]": "option_strategies.csv 原样字段；Wall 缺失或 LEGACY_INVALID_WALL 时用 yfinance 期权链 OI 最大值重算（wall_source=yfinance_option_chain_max_oi）",
                "review": "口径与 review.py 一致（近30天，closed 需 CLOSED_STOCK_STATUSES 且有 pnl）",
                "history[]": "review_history.csv 每日快照的仍在跟踪事件数",
                "stocks[].ai": "pending CSV 中 Scan 已生成的 AI 六段文本；本次为空时会从历史 pending/scan_results CSV 按 Ticker 回填（ai_source=history_backfill）。空字符串表示本次与历史都没有，前端显示 AI analysis pending",
            },
        },
    }

    if ai_status == "pending":
        notes.append(
            "AI 六段：pending CSV "
            + ("尚无这 6 列（旧版文件，未破坏）" if not ai_cols_present else "本次 Scan 未产出内容")
            + "，且历史 pending / scan_results CSV 中未检索到同名 Ticker 的历史文本，"
            + "前端显示 AI analysis pending；本脚本未调用任何 AI 接口，也未生成替代文案。"
        )

    # ---- 写出 ----
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    out_path.write_text(text, encoding="utf-8")
    mirror_path = None
    if not args.no_mirror:
        # 前端 us-market-terminal/ 若存在，同步写一份，避免两边读到不同版本
        mirror_path = SCRIPT_DIR / "us-market-terminal" / "dashboard" / "data" / "dashboard_data.json"
        if mirror_path.resolve() != out_path.resolve() and (SCRIPT_DIR / "us-market-terminal").is_dir():
            mirror_path.parent.mkdir(parents=True, exist_ok=True)
            mirror_path.write_text(text, encoding="utf-8")

    # ---- 日志 ----
    log("-" * 62)
    log(f"pending CSV          : {pending_path.name if pending_path else '（无）'}   股票名单来源：{stocks_source}")
    log(f"Core 数量            : {core_count}")
    log(f"Observation 数量     : {obs_count}")
    log(f"Options 数量         : {len(options)}（Active {active_options}）")
    log(f"Market 数据数量      : {market_ok}/{len(market_assets)} 可用"
        + (f"（来源 {market['source_used']}）" if market_ok else ""))
    log(f"K线成功 / 失败       : {kline_ok} / {kline_fail}"
        + (f"   技术指标成功 {technical_ok}/{len(stocks)}" if len(stocks) else ""))
    log(f"当前价来源           : 实时 {kstats['price_realtime']} · "
        f"最新收盘 {kstats['price_last_close']} · 合计可取 {price_live}/{len(stocks)}")
    if warnings:
        log(f"[WARN] 行情告警       : {len(warnings)} 条")
        for w in warnings[:10]:
            log(f"   ! {w}")
    log("Review 数据状态      :")
    for k in ("core_closed_count", "core_open_count", "observation_closed_count",
              "observation_open_count", "actual_active_count"):
        log(f"   · {k:<28} = {review[k]}  [{review[k + '_status']}]"
            + (f"  未计入 {review[k.replace('_count', '_unresolved')]} 条" if review[k + '_status'] != "complete" else ""))
    log(f"history 条数         : {len(history)}")
    log(f"AI 六段状态          : {ai_status}（{ai_filled}/{len(stocks)} 只股票有内容"
        + (f"，CSV 缺失列 {len(ai_cols_missing)} 个" if ai_cols_missing else "")
        + f"，来源 Scan {ai_scan_date or '未知'}）")
    log("AI / GPT             : 未调用（本脚本只透传 Scan 已落盘的 AI 文本）")
    log(f"输出 JSON 路径       : {out_path}"
        + (f"\n同步副本             : {mirror_path}" if mirror_path else ""))

    null_stats = count_nulls(stocks, [
        "price", "change_1d", "final_score", "quant_score", "ai_score",
        "fundamental_score", "technical_score", "risk_liquidity_score",
        "rsi", "atr_pct", "stop_loss", "pe_ttm", "pe_forward", "pb",
        "eps_ttm", "roe", "revenue_growth", "earnings_growth",
        "profit_margin", "market_cap", "market_regime", "vix",
    ])
    heavy = {k: v for k, v in null_stats.items() if v}
    log(f"字段 null 统计       : {heavy if heavy else '无 null'}")
    for s in stocks:
        if s["technical"]["status"] != "ok":
            log(f"   · {s['ticker']} 技术指标不可用：{s['technical'].get('reason')}")
            break
    if anomalies:
        log(f"异常记录             : {len(anomalies)} 条")
        for a in anomalies[:10]:
            log(f"   ! {a}")
    if missing:
        log(f"缺失字段             : {missing}")
    log("GPT / LLM            : 全程 0 次调用（AI 文本来自 Scan 已落盘内容，本脚本只透传）")
    log("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
