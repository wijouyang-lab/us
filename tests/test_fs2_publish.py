import json, copy
from pathlib import Path
from tools.investment_research.fs2.publish_snapshot import validate, verify_manifest, sha_bytes
BASE=Path("dashboard/data")
def test_validate_real(): assert validate(json.loads((BASE/"fs2/versions/fs2_v1.4.json").read_text()))==5600
def test_reject_short(): d=json.loads((BASE/"fs2/versions/fs2_v1.4.json").read_text()); d["rows"]=d["rows"][:10]
# negative helper
def test_short_rejected():
 d=json.loads((BASE/"fs2/versions/fs2_v1.4.json").read_text()); d["rows"]=d["rows"][:10]
 try: validate(d); assert False
 except ValueError: pass
def test_duplicate_rejected():
 d=json.loads((BASE/"fs2/versions/fs2_v1.4.json").read_text()); d["rows"]=d["rows"]+[d["rows"][0]]
 try: validate(d); assert False
 except ValueError: pass
def test_formal_manifest_verify(): assert verify_manifest(BASE/"fs2_candidates_manifest.json")["current"]["version"]=="fs2.v1.4"
def test_manifest_current_sha():
 m=json.loads((BASE/"fs2_candidates_manifest.json").read_text()); p=BASE/m["current"]["path"]; assert sha_bytes(p.read_bytes())==m["current"]["sha256"]
def test_manifest_previous_sha():
 m=json.loads((BASE/"fs2_candidates_manifest.json").read_text()); p=BASE/m["previous"]["path"]; assert sha_bytes(p.read_bytes())==m["previous"]["sha256"]
