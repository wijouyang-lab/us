import pandas as pd, json, hashlib
from pathlib import Path
P=Path("data/research/unified_selection/unified_selection_v1.csv")
def test_rows_unique(): d=pd.read_csv(P); assert len(d)==5600 and d.ticker.nunique()==5600
def test_blocked_not_ranked(): d=pd.read_csv(P); assert d[d.research_group=="BLOCKED"].research_rank.isna().all()
def test_composite_ready_all_dims(): d=pd.read_csv(P); r=d[d.composite_ready]; assert (r.dimension_coverage==4).all()
def test_missing_not_zero(): d=pd.read_csv(P); assert d.composite_score.isna().sum()>0
def test_groups_sum(): d=pd.read_csv(P); assert d.research_group.value_counts().sum()==5600
def test_snapshot_hash():
 p=Path("dashboard/data/unified_selection_v1.json"); h=hashlib.sha256(p.read_bytes()).hexdigest(); assert h==Path("dashboard/data/unified_selection_v1.sha256").read_text().strip(); assert len(json.loads(p.read_text())["rows"])==5600
def test_page_assets(): assert Path("terminal/unified.html").exists() and Path("dashboard/data/unified_selection_v1.json").exists()
