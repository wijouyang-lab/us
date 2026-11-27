import pandas as pd,json,hashlib
from pathlib import Path
P=Path("artifacts/full_universe_multi_style_v1")
def test_universe(): u=pd.read_csv(P/"universe_coverage.csv").set_index("metric").value; assert int(u["total_tickers"])==5600
def test_unique(): c=pd.read_csv(P/"all_style_candidates.csv"); assert c.duplicated(["ticker","style"]).sum()==0
def test_types(): c=pd.read_csv(P/"all_style_candidates.csv"); assert set(c.security_type).issubset({"COMMON","ADR"})
def test_no_composite(): c=pd.read_csv(P/"all_style_candidates.csv"); assert not any("composite" in x or x=="research_rank" for x in c.columns)
def test_peer_gate(): c=pd.read_csv(P/"all_style_candidates.csv"); assert (c.peer_n>=20).all()
def test_priority_cap(): p=pd.read_csv(P/"priority_research_candidates.csv"); assert len(p)==40 and p.groupby("style").size().le(10).all()
def test_style_counts(): c=pd.read_csv(P/"all_style_candidates.csv"); assert c.groupby("style").ticker.nunique().to_dict()=={"VALUE":115,"QUALITY":345,"GARP":341,"TREND":541}
def test_snapshot_hash():
 p=Path("dashboard/data/multi_style_candidates_v1.json"); assert hashlib.sha256(p.read_bytes()).hexdigest()==Path("dashboard/data/multi_style_candidates_v1.sha256").read_text().strip()
def test_page(): assert Path("terminal/multi_style.html").exists()
def test_source(): s=pd.read_csv(P/"source_register.csv"); assert len(s)>=3 and s.sha256.notna().all()
