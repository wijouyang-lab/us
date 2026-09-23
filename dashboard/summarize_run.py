"""把 dashboard_data.json 的关键指标抽成一份运行摘要 last_run.json。

用途：Workflow 每次运行后落盘，便于在 GitHub 上直接查看本次抓取结果
（全球市场成功数、K线与指标成功数、Review partial 情况），无需翻日志。
只读 JSON，不做任何计算推测。
"""
import json
import sys


def summarize(path):
    d = json.load(open(path, encoding="utf-8"))
    meta = d.get("meta", {})
    counts = meta.get("counts", {})
    market = d.get("market", {})
    review = d.get("review", {})

    stocks = d.get("stocks", [])
    tech_ok = sum(1 for s in stocks if (s.get("technical") or {}).get("status") == "ok")
    kline_ok = sum(1 for s in stocks if s.get("ohlcv"))
    price_src = {}
    for s in stocks:
        src = s.get("price_source") or "none"
        price_src[src] = price_src.get(src, 0) + 1

    partial = []
    for k in ("core_closed_count", "core_open_count", "observation_closed_count",
              "observation_open_count", "actual_active_count"):
        st = review.get(k + "_status")
        if st and st != "complete":
            partial.append({k: review.get(k), "status": st,
                            "unresolved": review.get(k.replace("_count", "_unresolved"))})

    return {
        "generated_at": d.get("generated_at"),
        "market_updated_at": meta.get("market_updated_at"),
        "technical_updated_at": meta.get("technical_updated_at"),
        "network_status": meta.get("network_status"),
        "quote_backends": meta.get("quote_backends"),
        "market": {
            "available": market.get("available_count"),
            "total": market.get("total_count"),
            "source_used": market.get("source_used"),
            "missing": [a["symbol"] for a in market.get("assets", []) if not a.get("available")],
        },
        "stocks": {
            "total": len(stocks),
            "core": sum(1 for s in stocks if s.get("bucket") == "Core"),
            "observation": sum(1 for s in stocks if s.get("bucket") == "Observation"),
            "kline_ok": kline_ok,
            "technical_ok": tech_ok,
            "price_source_breakdown": price_src,
        },
        "review": {
            "core_closed": review.get("core_closed_count"),
            "core_open": review.get("core_open_count"),
            "observation_closed": review.get("observation_closed_count"),
            "observation_open": review.get("observation_open_count"),
            "actual_active": review.get("actual_active_count"),
            "unresolved_pnl_events": review.get("unresolved_pnl_events"),
            "price_refreshed_count": review.get("price_refreshed_count"),
            "price_backfill_count": review.get("price_backfill_count"),
            "partial_items": partial,
        },
        "warnings": meta.get("warnings", []),
        "ai_status": meta.get("ai_status"),
        "ai_calls": 0,
    }


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "dashboard/data/dashboard_data.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "dashboard/data/last_run.json"
    out = summarize(src)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
