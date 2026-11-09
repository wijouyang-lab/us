import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_2_historical_pit"

def test_blocked_status():
    s=json.loads((P/"p10_5_2_status.json").read_text())
    assert s["status"]=="P10_5_2_DATA_BLOCKED"
    assert s["p10_6_allowed"] is False
    assert s["no_shadow"] is True
    assert s["preserved"]["p10_5_parser_validation_accessions"]==120
