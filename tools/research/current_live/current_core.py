"""Pure helpers for current selection tests."""
import hashlib, json
import pandas as pd

def latest_session(df, date_col="Date"):
    return pd.to_datetime(df[date_col]).max()

def is_public(filed, signal_date):
    if pd.isna(filed): return False
    return pd.to_datetime(filed) <= pd.to_datetime(signal_date)

def quality_or_none(value):
    return None if pd.isna(value) else float(value)

def horizon_index(dates, signal_date, n):
    idx = pd.DatetimeIndex(pd.to_datetime(dates)).sort_values()
    if pd.to_datetime(signal_date) not in idx: return None
    i = idx.get_loc(pd.to_datetime(signal_date)); j = i + n
    return None if j >= len(idx) else idx[j]

def forward_return(close, dates, signal_date, n):
    idx = pd.DatetimeIndex(pd.to_datetime(dates)).sort_values()
    s = pd.Series(close, index=idx).sort_index()
    j = horizon_index(idx, signal_date, n)
    if j is None or pd.to_datetime(signal_date) not in s.index: return "PENDING", None
    return j.date().isoformat(), float(s.loc[j] / s.loc[pd.to_datetime(signal_date)] - 1)

def snapshot_name(date, payload):
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:10]
    return f"signal_{date}_{digest}.json"

def status_for_count(n):
    return "NO_CANDIDATE" if n == 0 else "WATCHLIST"
