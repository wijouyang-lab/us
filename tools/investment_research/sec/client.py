"""SEC EDGAR client with required User-Agent, rate limit, retry and cache."""
from __future__ import annotations
import hashlib, json, os, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from tools.investment_research.sec.rate_limiter import get_rate_limiter

SEC_UA_ENV = "SEC_USER_AGENT"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


class SECError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message); self.status = status


class SECClient:
    def __init__(self, cache_dir: Path, user_agent: str | None = None,
                 min_interval: float = 0.25, timeout: float = 20.0,
                 sleep: Callable[[float], None] = time.sleep):
        ua = user_agent or os.getenv(SEC_UA_ENV, "").strip()
        if not ua:
            raise SECError(f"{SEC_UA_ENV} is required; set a real contact string, do not fabricate")
        if "@" not in ua and "http" not in ua:
            raise SECError("SEC_USER_AGENT must contain a contact email or URL")
        self.ua = ua; self.cache = Path(cache_dir); self.cache.mkdir(parents=True, exist_ok=True)
        self.min_interval = max(0.2, min_interval); self.timeout = timeout; self.sleep = sleep

    def _wait(self):
        get_rate_limiter().wait()

    def get_json(self, url: str, *, cache_key: str, max_age: int = 86400) -> dict:
        p = self.cache / f"{cache_key}.json"; meta = self.cache / f"{cache_key}.meta.json"
        if p.exists():
            try:
                m = json.loads(meta.read_text()); age = time.time() - m.get("fetched_epoch", 0)
                if age <= max_age:
                    return json.loads(p.read_text())
            except Exception:
                pass
        last = None
        for attempt in range(3):
            self._wait()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    raw = r.read(); status = r.status
                data = json.loads(raw)
                p.write_bytes(raw)
                meta.write_text(json.dumps({"url": url, "status": status,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "fetched_epoch": time.time(),
                    "sha256": hashlib.sha256(raw).hexdigest()}, indent=2))
                return data
            except urllib.error.HTTPError as e:
                last = e
                if e.code == 429 or 500 <= e.code < 600:
                    self.sleep(2 ** attempt); continue
                raise SECError(f"SEC HTTP {e.code}", e.code)
            except Exception as e:
                last = e; self.sleep(2 ** attempt)
        raise SECError(f"SEC request failed after retries: {last}")

    def ticker_map(self) -> dict[str, dict]:
        d = self.get_json(TICKERS_URL, cache_key="company_tickers", max_age=86400)
        out = {}
        for row in d.values():
            out[str(row["ticker"]).upper()] = {"ticker": row["ticker"], "cik": f"{int(row['cik_str']):010d}",
                                               "company_name": row["title"]}
        return out

    def submissions(self, cik: str, max_age: int = 86400) -> dict:
        return self.get_json(SUBMISSIONS.format(cik=cik), cache_key=f"submissions_{cik}", max_age=max_age)

    def companyfacts(self, cik: str, max_age: int = 86400) -> dict:
        return self.get_json(COMPANYFACTS.format(cik=cik), cache_key=f"companyfacts_{cik}", max_age=max_age)
