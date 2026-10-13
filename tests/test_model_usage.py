# -*- coding: utf-8 -*-
"""运行时模型使用记录（model_usage）测试。

对应 docs/MODEL_DISPLAY_TASK.md §三 的 4 个测试 —— 目标是让用户一眼看出
**中转站实际返回了什么模型**（upstream_model），而不是我们请求了什么模型：

  1. test_model_usage_record_and_write
     record + write → JSON 里有 scan.model / requested / fallback / updated_at
  2. test_model_usage_merged_across_contexts
     先写 scan 再写 review → 两个 key 都在，scan 的内容不被覆盖（合并语义）
  3. test_dashboard_export_injects_model_usage
     有文件 → payload 注入 model_usage；无文件 → 返回哨兵、**不注入键**（逐字节一致）
     并额外守住「读取路径必须是 <root>/dashboard/data/model_usage.json」这一回归点
  4. test_frontend_runtime_shows_model
     node 脚手架跑**真实 app.js** 的 renderRuntime：
     有记录 → 渲染 runtime-model 小字；fallback=true → warn + ⚠️；无记录 → 不渲染任何小字

注：clawsocket_compat 的 `_MODEL_USAGE` 是**模块级**累积器，各用例通过
importlib 重新加载一份干净模块实例，避免用例之间互相污染。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_clawsocket():
    """加载一份全新的 clawsocket_compat 模块实例（干净的模块级累积器）。"""
    p = REPO_ROOT / "clawsocket_compat.py"
    spec = importlib.util.spec_from_file_location("clawsocket_compat_model_usage_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _usage_path(root: Path) -> Path:
    return root / "dashboard" / "data" / "model_usage.json"


# --------------------------------------------------------------------------- #
# 1. 记录 + 落盘
# --------------------------------------------------------------------------- #
def test_model_usage_record_and_write(tmp_path):
    cs = _load_clawsocket()
    cs.set_context("scan")
    cs.record_model_usage("scan", "claude-fable-5-1", "claude-fable-5-1", False)
    cs.write_model_usage(tmp_path, "scan")

    p = _usage_path(tmp_path)
    assert p.exists(), f"未落盘 {p}"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert set(data.keys()) == {"scan"}
    rec = data["scan"]
    assert rec["model"] == "claude-fable-5-1"
    assert rec["requested"] == "claude-fable-5-1"
    assert rec["fallback"] is False
    assert isinstance(rec["updated_at"], str) and rec["updated_at"], "updated_at 必须是非空 ISO 时间"
    # 进程内累积器也能读到（供调试）
    assert cs.get_model_usage()["scan"]["model"] == "claude-fable-5-1"


def test_model_usage_skips_write_when_nothing_recorded(tmp_path):
    """本次进程一次真实调用都没有 → 不写文件，避免写出 {"scan": null} 污染数据。"""
    cs = _load_clawsocket()
    cs.set_context("scan")
    cs.write_model_usage(tmp_path, "scan")
    assert not _usage_path(tmp_path).exists()


# --------------------------------------------------------------------------- #
# 2. 跨 context 合并（核心保护：review 不能抹掉 scan）
# --------------------------------------------------------------------------- #
def test_model_usage_merged_across_contexts(tmp_path):
    cs = _load_clawsocket()

    cs.record_model_usage("scan", "claude-fable-5-1", "claude-fable-5-1", False)
    cs.write_model_usage(tmp_path, "scan")

    cs.record_model_usage("review", "claude-fable-5-1", "claude-fable-5-1", False)
    cs.write_model_usage(tmp_path, "review")

    data = json.loads(_usage_path(tmp_path).read_text(encoding="utf-8"))
    assert set(data.keys()) == {"scan", "review"}, "两个 context 必须都在（合并写入，不是覆盖）"
    assert data["scan"]["model"] == "claude-fable-5-1", "scan 的记录被 review 覆盖了"
    assert data["review"]["model"] == "claude-fable-5-1"

    # 再写一次 evolve，前面两个仍然保留
    cs.record_model_usage("evolve", "gpt-6-astra", "claude-fable-5-1", True)
    cs.write_model_usage(tmp_path, "evolve")
    data = json.loads(_usage_path(tmp_path).read_text(encoding="utf-8"))
    assert set(data.keys()) == {"scan", "review", "evolve"}
    assert data["evolve"]["fallback"] is True
    assert data["evolve"]["model"] == "gpt-6-astra"
    assert data["evolve"]["requested"] == "claude-fable-5-1"


# --------------------------------------------------------------------------- #
# 3. dashboard_export 注入（缺文件 → 哨兵 → 不注入键）
# --------------------------------------------------------------------------- #
def test_dashboard_export_injects_model_usage(tmp_path):
    from dashboard_export import _read_model_usage, _MODEL_USAGE_MISSING

    # (a) 无文件 → 哨兵（调用方据此不注入键 ⇒ dashboard_data.json 逐字节一致）
    assert _read_model_usage(tmp_path) is _MODEL_USAGE_MISSING

    # (b) 把文件放在**真实嵌套位置** → 正常读到
    payload_rec = {
        "scan": {"model": "claude-fable-5-1", "requested": "claude-fable-5-1",
                 "fallback": False, "updated_at": "2026-10-13T08:46:00+00:00"},
        "review": {"model": "claude-fable-5-1", "requested": "claude-opus-5-5",
                   "fallback": True, "updated_at": "2026-10-13T22:30:00+00:00"},
    }
    p = _usage_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload_rec, ensure_ascii=False), encoding="utf-8")

    got = _read_model_usage(tmp_path)
    assert got is not _MODEL_USAGE_MISSING
    assert got == payload_rec

    # (c) 回归守卫：读取路径必须是 <root>/dashboard/data/，根目录那份读不到
    wrong_root = tmp_path / "wrong"
    wrong_root.mkdir()
    (wrong_root / "model_usage.json").write_text(json.dumps(payload_rec), encoding="utf-8")
    assert _read_model_usage(wrong_root) is _MODEL_USAGE_MISSING, (
        "读取路径必须是 <data-dir>/dashboard/data/model_usage.json；"
        "放在根目录不应被读到（与 market_indicators 的路径回归同一类 bug）"
    )

    # (d) 文件存在但解析失败 → None（键存在这一事实保留，前端只是不显示小字）
    p.write_text("{ 这不是 JSON", encoding="utf-8")
    assert _read_model_usage(tmp_path) is None


# --------------------------------------------------------------------------- #
# 4. 前端 renderRuntime 显示模型名（node 跑真实 app.js）
# --------------------------------------------------------------------------- #
def _run_node(transformed, tail):
    harness = (
        "globalThis.document={\n"
        "  addEventListener(){},querySelectorAll(){return[]},getElementById(){return null;},\n"
        "  querySelector(sel){\n"
        "    globalThis.__els = globalThis.__els || {};\n"
        "    if(!globalThis.__els[sel]) globalThis.__els[sel] = {\n"
        "      textContent:'', innerHTML:'', className:'', title:'',\n"
        "      insertAdjacentHTML(pos, html){\n"
        "        globalThis.__adj = globalThis.__adj || {};\n"
        "        (globalThis.__adj[sel] = globalThis.__adj[sel] || []).push(html);\n"
        "      }\n"
        "    };\n"
        "    return globalThis.__els[sel];\n"
        "  }\n"
        "};\n"
        "globalThis.window={addEventListener(){},IT:null};\n"
        "globalThis.fetch=()=>Promise.resolve({json:()=>Promise.resolve({})});\n"
    )
    js = REPO_ROOT / "tests" / "_model_usage_harness.js"
    js.write_text(harness + transformed + tail, encoding="utf-8")
    try:
        proc = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, f"node 执行失败：{proc.stderr}"
        return json.loads(proc.stdout.strip().splitlines()[-1])
    finally:
        js.unlink(missing_ok=True)


def _expose(src):
    out = src.replace(
        "\n  boot();\n",
        "\n  globalThis.__setData = function(d){ DATA = d; };\n"
        "  globalThis.__renderRuntime = renderRuntime;\n")
    assert "__renderRuntime" in out, "未能注入 renderRuntime 暴露钩子"
    return out


def _tail(payload_json):
    return (
        "\nglobalThis.__setData(" + payload_json + ");\n"
        "globalThis.__renderRuntime();\n"
        "var adj = globalThis.__adj || {};\n"
        "console.log(JSON.stringify({\n"
        "  scan: (adj['#scanStatus'] || []).join(''),\n"
        "  review: (adj['#reviewStatus'] || []).join(''),\n"
        "  evolve: (adj['#evolveStatus'] || []).join('')\n"
        "}));\n"
    )


def _runtimes():
    return {"scan": {"latest": {"status": "completed", "conclusion": "success",
                                "updated_at": "2026-10-13T08:46:00Z",
                                "head_sha": "c35aa5d41f6103610d668366eefa657b0068a35c",
                                "run_number": 160}}}


def test_frontend_runtime_shows_model():
    src = _expose((REPO_ROOT / "app.js").read_text(encoding="utf-8"))

    # (a) 正常路径：requested == upstream_model == claude-fable-5-1、fallback=false
    normal = dict(_runtimes())
    normal["model_usage"] = {"scan": {"model": "claude-fable-5-1",
                                      "requested": "claude-fable-5-1",
                                      "fallback": False}}
    r = _run_node(src, _tail(json.dumps(normal)))
    assert 'class="runtime-model"' in r["scan"], f"应渲染模型小字：{r['scan']!r}"
    assert "fable-5-1" in r["scan"], "claude- 前缀应缩写掉，显示 fable-5-1"
    assert "claude-fable-5-1" in r["scan"], "title 里必须保留全名"
    assert "warn" not in r["scan"], "非 fallback 不应带 warn 样式"
    assert "⚠️" not in r["scan"], "非 fallback 不应显示 ⚠️"
    assert r["review"] == "" and r["evolve"] == "", "只有 scan 有记录时 review/evolve 不应渲染小字"

    # (b) fallback 分支（真实 API 造不出来，用 mock 数据）：warn 样式 + ⚠️ + 请求模型写进 title
    fb = dict(_runtimes())
    fb["model_usage"] = {"scan": {"model": "claude-fable-5-1",
                                  "requested": "claude-opus-5-5",
                                  "fallback": True}}
    r = _run_node(src, _tail(json.dumps(fb)))
    assert "runtime-model warn" in r["scan"], f"fallback 必须带 warn 样式：{r['scan']!r}"
    assert "⚠️" in r["scan"], "fallback 必须前置 ⚠️"
    assert "claude-opus-5-5" in r["scan"], "title 里应显示请求的模型"
    assert "运行时降级" in r["scan"], "title 里应说明走了运行时降级"

    # (c) 无记录 → 不渲染任何 model 小字（功能关闭时逐字节一致）
    r = _run_node(src, _tail(json.dumps(_runtimes())))
    assert "runtime-model" not in r["scan"] + r["review"] + r["evolve"], "无记录时不应渲染任何小字"

    # (d) model 为 None（upstream_model 可能为 None）→ 同样不渲染，且不能抛异常
    nullmodel = dict(_runtimes())
    nullmodel["model_usage"] = {"scan": {"model": None, "requested": "claude-fable-5-1",
                                         "fallback": False}}
    r = _run_node(src, _tail(json.dumps(nullmodel)))
    assert "runtime-model" not in r["scan"], "model 为空时不应渲染小字"
