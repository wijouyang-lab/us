"""Download the SEC CompanyFacts bulk ZIP once, streaming; no per-CIK requests."""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"


def status() -> str:
    ua = os.getenv("SEC_USER_AGENT", "").strip()
    if not ua: return "SEC_USER_AGENT_NOT_CONFIGURED"
    if "example.com" in ua or "your_" in ua or "@" not in ua or len(ua) < 12:
        return "SEC_USER_AGENT_INVALID"
    return "SEC_USER_AGENT_CONFIGURED"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/sec/companyfacts_p63.zip"))
    ap.add_argument("--metadata", type=Path, default=Path("data/sec/companyfacts_p63_meta.json"))
    a = ap.parse_args()
    if status() != "SEC_USER_AGENT_CONFIGURED":
        print("CONFIGURATION_BLOCKED: " + status())
        return 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    ua = os.getenv("SEC_USER_AGENT", "")
    headers = {"User-Agent": ua, "Accept": "*/*"}
    meta = {"url": URL, "configured_at": datetime.now(timezone.utc).isoformat()}
    try:
        req = urllib.request.Request(URL, method="HEAD", headers=headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            meta["head_status"] = r.status
            meta["content_length"] = r.headers.get("Content-Length")
            meta["last_modified"] = r.headers.get("Last-Modified")
        time.sleep(0.25)
        req = urllib.request.Request(URL, headers=headers)
        with urllib.request.urlopen(req, timeout=180) as r:
            meta["get_status"] = r.status
            meta["content_type"] = r.headers.get("Content-Type")
            total = int(r.headers.get("Content-Length") or 0)
            h = hashlib.sha256(); size = 0
            with a.out.open("wb") as f:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk: break
                    f.write(chunk); h.update(chunk); size += len(chunk)
        meta.update({"downloaded_bytes": size, "sha256": h.hexdigest(),
                     "downloaded_at": datetime.now(timezone.utc).isoformat()})
        if total and total != size:
            meta["status"] = "SIZE_MISMATCH"
        else:
            meta["status"] = "DOWNLOADED"
        a.metadata.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(json.dumps({k: meta.get(k) for k in ("status", "head_status", "get_status", "downloaded_bytes", "sha256")}))
        return 0 if meta["status"] == "DOWNLOADED" else 1
    except urllib.error.HTTPError as exc:
        meta.update({"status": f"HTTP_{exc.code}", "error": str(exc)[:300]})
    except Exception as exc:
        meta.update({"status": "DOWNLOAD_FAILED", "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
    a.metadata.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
