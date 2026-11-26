import json
import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.investment_research.fs2 import publish_snapshot as pub

BASE = Path("dashboard/data")
SRC = json.loads((BASE / "fs2/versions/fs2_v1.4.json").read_text(encoding="utf-8"))


def h(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def setup(tmp_path):
    (tmp_path / "data/versions").mkdir(parents=True)
    return tmp_path / "data/manifest.json", tmp_path / "data/versions"


def source(tmp_path, version, mutate=None):
    d = json.loads(json.dumps(SRC)); d["version"] = version
    if mutate: mutate(d)
    p = tmp_path / f"{version}.json"; p.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
    return p


def small_source(tmp_path, version):
    d = json.loads(json.dumps(SRC)); d['version'] = version; d['rows'] = d['rows'][:10]
    p = tmp_path / f'small_{version}.json'; p.write_text(json.dumps(d, separators=(',', ':')), encoding='utf-8'); return p


def publish(src, manifest, versions, version=None, keep=30):
    return pub.publish(SimpleNamespace(source=src, manifest=manifest, versions=versions, version=version, keep=keep))


def test_31_versions_retention_and_consistency(tmp_path, monkeypatch):
    monkeypatch.setattr(pub, "ROWS", 10)
    manifest, versions = setup(tmp_path)
    for i in range(31):
        publish(small_source(tmp_path, f"v{i}"), manifest, versions)
    m = json.loads(manifest.read_text())
    disk = sorted(p.name for p in versions.glob("fs2_v*.json"))
    assert len(disk) == 30
    assert m["retained"] == disk
    assert Path(m["current"]["path"]).name in disk
    assert Path(m["previous"]["path"]).name in disk


def test_pinned_not_deleted(tmp_path):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions)
    m = json.loads(manifest.read_text()); m["pinned"] = ["fs2_vvA.json"]; manifest.write_text(json.dumps(m))
    for i in range(5):
        publish(source(tmp_path, f"p{i}"), manifest, versions, keep=2)
    assert (versions / "fs2_vvA.json").exists()
    assert "fs2_vvA.json" in json.loads(manifest.read_text())["pinned"]


def test_rollback_dotdot_rejected(tmp_path):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions)
    before = h(manifest)
    with pytest.raises(ValueError): pub.cmd_rollback(SimpleNamespace(manifest=manifest, versions=versions, version="../vA", keep=30))
    assert h(manifest) == before


def test_rollback_backslash_rejected(tmp_path):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions)
    with pytest.raises(ValueError): pub.cmd_rollback(SimpleNamespace(manifest=manifest, versions=versions, version="a\\b", keep=30))
    assert h(manifest) == h(manifest)


def test_rollback_missing_rejected(tmp_path):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions)
    before = h(manifest)
    with pytest.raises(ValueError): pub.cmd_rollback(SimpleNamespace(manifest=manifest, versions=versions, version="nope", keep=30))
    assert h(manifest) == before


def test_rollback_bad_data_rejected(tmp_path):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions)
    bad = source(tmp_path, "bad", lambda d: d.update(rows=d["rows"][:5]))
    (versions / "fs2_vbad.json").write_text(bad.read_text())
    before = h(manifest)
    with pytest.raises(ValueError): pub.cmd_rollback(SimpleNamespace(manifest=manifest, versions=versions, version="bad", keep=30))
    assert h(manifest) == before


def test_current_corrupt_verify_fails(tmp_path):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions)
    m = json.loads(manifest.read_text()); p = manifest.parent / m["current"]["path"]
    p.write_text("{}")
    with pytest.raises(ValueError): pub.verify_manifest(manifest)


def test_previous_corrupt_verify_fails(tmp_path):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions); publish(source(tmp_path, "vB"), manifest, versions)
    m = json.loads(manifest.read_text()); p = manifest.parent / m["previous"]["path"]
    p.write_text("{}")
    with pytest.raises(ValueError): pub.verify_manifest(manifest)


def test_manifest_write_failure_keeps_old(tmp_path, monkeypatch):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions)
    before = h(manifest)
    real = pub.atomic_write
    def fail(path, payload):
        if Path(path) == manifest: raise OSError("inject manifest write")
        return real(path, payload)
    monkeypatch.setattr(pub, "atomic_write", fail)
    with pytest.raises(OSError): publish(source(tmp_path, "vB"), manifest, versions)
    assert h(manifest) == before
    pub.verify_manifest(manifest)


def test_manifest_replace_failure_keeps_old(tmp_path, monkeypatch):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions)
    before = h(manifest); real = pub.os.replace
    def fail(src, dst):
        if Path(dst) == manifest: raise OSError("inject replace")
        return real(src, dst)
    monkeypatch.setattr(pub.os, "replace", fail)
    with pytest.raises(OSError): publish(source(tmp_path, "vB"), manifest, versions)
    assert h(manifest) == before
    pub.verify_manifest(manifest)


def test_version_write_failure_keeps_old(tmp_path, monkeypatch):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions)
    before = h(manifest); real = pub.atomic_write
    def fail(path, payload):
        if Path(path).name.startswith("fs2_vvB"): raise OSError("inject version write")
        return real(path, payload)
    monkeypatch.setattr(pub, "atomic_write", fail)
    with pytest.raises(OSError): publish(source(tmp_path, "vB"), manifest, versions)
    assert h(manifest) == before
    pub.verify_manifest(manifest)


def test_cleanup_failure_keeps_current_previous(tmp_path, monkeypatch):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions); publish(source(tmp_path, "vB"), manifest, versions)
    before = h(manifest)
    def boom(*a, **k): raise RuntimeError("inject cleanup")
    monkeypatch.setattr(pub, "prune_versions", boom)
    with pytest.raises(RuntimeError): publish(source(tmp_path, "vC"), manifest, versions)
    assert h(manifest) == before
    pub.verify_manifest(manifest)


def test_rollback_success(tmp_path):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions); publish(source(tmp_path, "vB"), manifest, versions)
    pub.cmd_rollback(SimpleNamespace(manifest=manifest, versions=versions, version="vA", keep=30))
    m = pub.verify_manifest(manifest)
    assert m["current"]["version"] == "vA"
    assert m["previous"]["version"] == "vB"


def test_retained_equals_disk_after_cleanup(tmp_path):
    manifest, versions = setup(tmp_path)
    for i in range(5): publish(source(tmp_path, f"z{i}"), manifest, versions, keep=3)
    m = json.loads(manifest.read_text())
    assert m["retained"] == sorted(p.name for p in versions.glob("fs2_v*.json"))
def test_verify_entry_full_validation(tmp_path):
    manifest, versions = setup(tmp_path)
    publish(source(tmp_path, "vA"), manifest, versions)
    m = pub.verify_manifest(manifest)
    d = json.loads((manifest.parent / m["current"]["path"]).read_text()); d["rows"][0]["composite_tier"]="NOT_A_TIER"
    (manifest.parent / m["current"]["path"]).write_text(json.dumps(d))
    with pytest.raises(ValueError): pub.verify_manifest(manifest)
def test_rollback_over_30_protects_old_current(tmp_path, monkeypatch):
    monkeypatch.setattr(pub, "ROWS", 10)
    manifest, versions = setup(tmp_path)
    for i in range(32):
        publish(small_source(tmp_path, f"r{i}"), manifest, versions, keep=30)
    old = json.loads(manifest.read_text())
    old_current = Path(old["current"]["path"]).name
    old_previous = Path(old["previous"]["path"]).name
    pub.cmd_rollback(SimpleNamespace(manifest=manifest, versions=versions, version="r5", keep=30))
    m = pub.verify_manifest(manifest); disk = set(p.name for p in versions.glob("fs2_v*.json"))
    assert m["current"]["version"] == "r5"
    assert Path(m["previous"]["path"]).name == old_current
    assert old_current in disk and old_previous in disk
    assert m["retained"] == sorted(disk)
def test_durability_dir_fsync_true(tmp_path, monkeypatch):
    manifest, versions = setup(tmp_path); monkeypatch.setattr(pub, "fsync_dir", lambda path: True)
    publish(source(tmp_path, "dA"), manifest, versions)
    assert json.loads(manifest.read_text())["durability"]["dir_fsync"] is True
def test_durability_dir_fsync_false(tmp_path, monkeypatch):
    manifest, versions = setup(tmp_path); monkeypatch.setattr(pub, "fsync_dir", lambda path: False)
    publish(source(tmp_path, "dB"), manifest, versions)
    assert json.loads(manifest.read_text())["durability"]["dir_fsync"] is False
def test_durability_dir_fsync_failure_flag(tmp_path, monkeypatch):
    manifest, versions = setup(tmp_path)
    def boom(path): return False
    monkeypatch.setattr(pub, "fsync_dir", boom)
    publish(source(tmp_path, "dC"), manifest, versions)
    assert json.loads(manifest.read_text())["durability"] == {"file_fsync": True, "dir_fsync": False}
