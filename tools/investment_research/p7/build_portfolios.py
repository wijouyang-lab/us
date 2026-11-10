"""P7 portfolio construction: long-only, 5% cash, 10% issuer / 25% sector caps."""
from __future__ import annotations
import csv, json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SEL = Path("data/universe/selection")
OUT = Path("data/universe/p7")
OUT.mkdir(parents=True, exist_ok=True)
CASH = 0.05
MAX_POS = 0.10
MAX_SECTOR = 0.25
SLIPPAGE_BPS = 5.0   # existing scripts/paper_trading.py default
COMMISSION_BPS = 0.5
COST_BPS = SLIPPAGE_BPS + COMMISSION_BPS


def read(p):
    b = p.read_bytes()[:2]
    with p.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def cap(raw, sectors):
    # raw weights sum to invested capital; enforce issuer and sector caps by water filling.
    w = dict(raw)
    for _ in range(100):
        changed = False
        for t in list(w):
            if w[t] > MAX_POS + 1e-12:
                w[t] = MAX_POS; changed = True
        for sec in set(sectors.values()):
            ts = [t for t in w if sectors.get(t) == sec]
            total = sum(w[t] for t in ts)
            if total > MAX_SECTOR + 1e-12:
                scale = MAX_SECTOR / total
                for t in ts: w[t] *= scale
                changed = True
        total = sum(w.values())
        if total < 0.95 - 1e-9:
            diff = 0.95 - total
            eligible = [t for t in w if w[t] < MAX_POS - 1e-12]
            # respect sector caps when redistributing
            for t in eligible:
                sec = sectors.get(t, "UNKNOWN")
                sec_total = sum(w[x] for x in w if sectors.get(x) == sec)
                room = min(MAX_POS - w[t], MAX_SECTOR - sec_total)
                if room > 0:
                    add = min(diff, room)
                    w[t] += add; diff -= add
                    if diff <= 1e-12: break
        if not changed: break
    return w


def main():
    scores = {r["ticker"]: r for r in read(OUT / "strategy_scores.csv")}
    liq = {r["ticker"]: r for r in read(SEL / "tradability/value_tradable_candidates.csv")}
    for kind in ("quality", "garp"):
        for r in read(SEL / f"tradability/{kind}_tradable_candidates.csv"):
            liq.setdefault(r["ticker"], r)
    sessions = defaultdict(list)
    for r in read(Path("data/universe/selection_inputs/liquidity_sessions_p617.csv")):
        sessions[r["ticker"]].append((r["date"], float(r["close"])))
    vols = {}
    for t, xs in sessions.items():
        xs = sorted(xs); rets = []
        for i in range(1, len(xs)):
            if xs[i-1][1] > 0: rets.append(xs[i][1] / xs[i-1][1] - 1)
        if len(rets) >= 20:
            mean = sum(rets) / len(rets)
            var = sum((x-mean)**2 for x in rets) / (len(rets)-1)
            vols[t] = math.sqrt(var) * math.sqrt(252)
    candidates = defaultdict(list)
    for r in read(OUT / "strategy_candidates.csv"):
        if r["candidate_status"] == "ELIGIBLE": candidates[r["strategy"]].append(r)
    weights = []; summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "as_of": "2026-11-05",
                              "research_only": True, "initial_capital": 50000.0, "cash_policy": CASH,
                              "constraints": {"long_only": True, "leverage": 0, "target_positions": [10, 20],
                                              "max_position": MAX_POS, "max_sector": MAX_SECTOR,
                                              "cost_bps": COST_BPS, "cost_model": "scripts/paper_trading.py 5bps slippage + 0.5bps commission"},
                              "strategies": {}}
    for sid in ("VALUE_V1", "QUALITY_V1", "GARP_V1", "BLENDED_V1"):
        rows = candidates.get(sid, [])
        if len(rows) < 10:
            summary["strategies"][sid] = {"launchable": False, "status": "NOT_LAUNCHABLE",
                                          "candidate_count": len(rows), "reason": f"ONLY_{len(rows)}_ELIGIBLE_CANDIDATES_LT_10",
                                          "selected": 0, "cash": 1.0, "variants": {}}
            continue
        rows = sorted(rows, key=lambda x: -float(x["score"]))[:20]
        selected = [r["ticker"] for r in rows]
        sectors = {t: scores[t].get("model_family") or "UNKNOWN" for t in selected}
        # Equal weight variant.
        eq = cap({t: 0.95 / len(selected) for t in selected}, sectors)
        # Inverse-volatility variant; fall back equal when volatility is unavailable.
        inv = {t: (1.0 / vols[t] if vols.get(t, 0) > 0 else 1.0) for t in selected}
        risk_raw = {t: 0.95 * inv[t] / sum(inv.values()) for t in selected}
        risk = cap(risk_raw, sectors)
        for variant, w in (("equal_weight", eq), ("risk_adjusted", risk)):
            for t in sorted(w):
                adv20 = num(liq.get(t, {}).get("adv20_usd")); adv60 = num(liq.get(t, {}).get("adv60_usd"))
                notional = 50000.0 * w[t]
                weights.append({"strategy": sid, "variant": variant, "ticker": t,
                                "company_name": scores[t].get("company_name", ""),
                                "model_family": sectors[t], "weight": round(w[t], 8),
                                "target_notional_usd": round(notional, 2),
                                "adv20_usd": adv20 if adv20 is not None else "",
                                "adv60_usd": adv60 if adv60 is not None else "",
                                "adv20_participation_pct": round(notional / adv20 * 100, 6) if adv20 else "",
                                "score": scores[t].get("value_score") if sid == "VALUE_V1" else scores[t].get("quality_score") if sid == "QUALITY_V1" else scores[t].get("garp_score") if sid == "GARP_V1" else scores[t].get("blended_score"),
                                "factor_count": scores[t].get("factor_count"),
                                "factors_present": scores[t].get("factors_present")})
        sector_w = defaultdict(float)
        for t, x in risk.items(): sector_w[sectors[t]] += x
        summary["strategies"][sid] = {
            "launchable": True, "status": "LAUNCHABLE",
            "candidate_count": len(candidates[sid]), "selected": len(selected),
            "cash": round(1.0 - sum(risk.values()), 8), "variants": {"equal_weight": {"cash": 1 - sum(eq.values()), "max_position": max(eq.values())},
                                                                     "risk_adjusted": {"cash": 1 - sum(risk.values()), "max_position": max(risk.values())}},
            "sector_weights": {k: round(v, 8) for k, v in sorted(sector_w.items())},
            "turnover": {"initial_one_way": 1.0, "expected_annual_one_way": 0.25},
            "estimated_initial_cost_usd": round(50000.0 * 0.95 * COST_BPS / 10000.0, 2),
            "selected_tickers": selected,
        }
    with (OUT / "portfolio_weights.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(weights[0].keys())); w.writeheader(); w.writerows(weights)
    (OUT / "portfolio_risk_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
