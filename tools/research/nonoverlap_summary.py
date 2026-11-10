import json
from pathlib import Path
import pandas as pd

d = json.load(open("docs/research/nonoverlap_portfolios_phase274_2026-10-30.json"))
st = json.load(open("docs/research/nonoverlap_stability_2026-10-30.json"))
out = {"label": d["label"], "hold_sessions": d["hold_sessions"], "window": d["window"],
       "cost_bps_per_side": d["cost_bps_per_side"], "invalid_periods": len(d["invalid"]),
       "strategies": {}}
for name, ports in d["periods"].items():
    out["strategies"][name] = {c: ports[str(c)]["metrics"] for c in (10, 25, 50)}
    out["strategies"][name]["periods"] = len(ports["10"]["periods"])
out["equal_weight_10bps"] = d["equal_weight_10bps"]["metrics"]
out["spy_buyhold"] = d["spy_buyhold"]
out["annual"] = st["annual"]
out["regime"] = st["regime"]
Path("docs/research/nonoverlap_summary_2026-10-30.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print("ok", Path("docs/research/nonoverlap_summary_2026-10-30.json").stat().st_size)
