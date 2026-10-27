import json
from datetime import date, datetime, timezone
import pytest
from tools.research.capture_event_response_prices import capture_prices, fetch_chart_history, select_universe


def payload():
    stamps=[int(datetime(2026,10,23,16,tzinfo=timezone.utc).timestamp()),int(datetime(2026,10,26,16,tzinfo=timezone.utc).timestamp())]
    return {"chart":{"result":[{"timestamp":stamps,"indicators":{"quote":[{"open":[98,101],"high":[101,103],"low":[97,100],"close":[100,102],"volume":[1000,1200]}],"adjclose":[{"adjclose":[50,51]}]}}],"error":None}}


class Response:
    def __init__(self, data, status=200): self.data,self.status=data,status
    def raise_for_status(self):
        if self.status>=400: raise RuntimeError(f"HTTP {self.status}")
    def json(self): return self.data


def test_universe_filters_old_events_and_adds_spy():
    events=[
      {"first_seen_at_utc":"2026-10-26T12:00:00Z","availability_status":"available","event_type":"company_news","queried_ticker":"AAPL"},
      {"first_seen_at_utc":"2026-09-01T12:00:00Z","availability_status":"available","event_type":"company_news","tickers":["OLD"]},
      {"first_seen_at_utc":"2026-10-26T12:00:00Z","availability_status":"available","event_type":"macro_release"},
    ]
    symbols,start,end,stats=select_universe(events,as_of_utc=datetime(2026,10,27,12,tzinfo=timezone.utc))
    assert symbols==["SPY","AAPL"] and start==date(2026,10,19) and end==date(2026,10,26)
    assert stats=={"recent_event_count":2,"unmapped_event_count":0}


def test_chart_prices_keep_raw_and_derive_adjusted_ohlc():
    def get(url,**kwargs):
        assert url.endswith("/AAPL") and kwargs["params"]["interval"]=="1d"
        return Response(payload())
    rows=fetch_chart_history("AAPL",date(2026,10,23),date(2026,10,26),get=get)
    assert len(rows)==2 and rows[0]["Open"]==98 and rows[0]["Adj Close"]==50 and rows[0]["Adj Open"]==49
    assert rows[1]["Adj Open"]==50.5


def test_chart_handles_http_failure_and_empty_payload():
    def failed(*args,**kwargs): return Response({},403)
    with pytest.raises(RuntimeError,match="HTTP 403"): fetch_chart_history("SPY",date(2026,10,23),date(2026,10,26),get=failed)
    def empty(*args,**kwargs): return Response({"chart":{"result":None,"error":None}})
    assert fetch_chart_history("SPY",date(2026,10,23),date(2026,10,26),get=empty)==[]


def test_capture_records_partial_failures_and_refuses_overwrite(tmp_path):
    archive=tmp_path/"archive.json"
    archive.write_text(json.dumps([{"first_seen_at_utc":"2026-10-26T12:00:00Z","availability_status":"available","event_type":"company_news","tickers":["AAPL","MSFT"]}]),encoding="utf-8")
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        return Response({},403) if url.endswith("/MSFT") else Response(payload())
    csv_path,report_path=tmp_path/"prices.csv",tmp_path/"report.json"
    report=capture_prices(archive,csv_path,report_path,as_of_utc=datetime(2026,10,27,12,tzinfo=timezone.utc),get=get,delay_seconds=0)
    assert report["status"]=="partial" and report["price_row_count"]==4 and report["failed_symbol_count"]==1 and len(calls)==3
    assert json.loads(report_path.read_text())["price_csv_sha256"]==report["price_csv_sha256"]
    with pytest.raises(ValueError,match="refusing to overwrite"):
        capture_prices(archive,csv_path,report_path,as_of_utc=datetime(2026,10,27,12,tzinfo=timezone.utc),get=get,delay_seconds=0)
