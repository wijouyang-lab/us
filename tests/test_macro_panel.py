"""美股宏观板块 —— 后端逻辑测试（flag 门控，默认关闭）。

覆盖：
  1) write_macro_data 构造正确（mock 输入 → 输出 JSON 结构）
  2) AI 判断批量调用（mock _model_stream_text，断言一次调用多条）
  3) AI 失败 → sentiment: null（不崩、文件仍落盘）
  4) flag 关闭 → macro_panel_enabled()=False（main 不会调用 write_macro_data）

前端 renderMacro 测试见 tests/test_macro_panel_frontend.py（随 dashboard 提交）。

注意：本仓库目标运行时为 Python 3.12（scan.py 含 3.12 才允许的 f-string 语法），
请用 `python3.12 -m pytest` 运行。
"""
import json
import os
import sys
import types

# scan.py 在导入时有两处守卫：(1) 校验 CLAWSOCKET 环境变量；(2) 周末直接 sys.exit(0)。
# 本测试不导入真实 scan 模块（会触发上述退出），而是读取 scan.py 源码、中性化周末守卫后
# exec 为内存模块。CI 在周一~周五运行本测试不受影响；本地周末亦可验证。
# 逻辑代码（write_macro_data 等）一字未改，仅绕过导入期守卫。
os.environ.setdefault("CLAWSOCKET_API_KEY", "test-key")
os.environ.setdefault("CLAWSOCKET_BASE_URL", "https://test.local")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_scan_for_test():
    src = open(os.path.join(_REPO_ROOT, "scan.py"), encoding="utf-8").read()
    # 中性化所有导入期/运行期 sys.exit(0) 守卫（周末/盘后/未知状态），
    # 使测试可加载模块、验证宏欢函数；磁盘 scan.py 一字未改。
    # env 守卫 sys.exit(1) 因已注入 dummy 环境变量不会触发，故保留。
    src = src.replace("sys.exit(0)", "pass  # 测试：守卫已中性化")
    # 强制进入有效会话分支（PREMARKET 会定义 SCAN_RUN_MODE_LABEL），
    # 避免周末/盘后/未知分支缺失变量导致 NameError。
    src = src.replace(
        "_scan_session_state = get_market_session_state(RUN_ASOF_US)",
        "_scan_session_state = 'PREMARKET'  # 测试：强制有效分支",
    )
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    mod = types.ModuleType("scan_under_test")
    mod.__file__ = os.path.join(_REPO_ROOT, "scan.py")
    exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    return mod


scan = _load_scan_for_test()

import pytest


# ---------------------------------------------------------------------------
# 1) write_macro_data 构造正确
# ---------------------------------------------------------------------------
def test_write_macro_data_structure(tmp_path):
    economic_structured = {
        "CPI指数": {"value": 312.5, "yoy": 3.2, "date": "2026-09", "source": "BLS", "prev": 311.0},
        "失业率": {"value": 4.1, "date": "2026-09", "source": "BLS"},
        "10Y国债": {"value": 4.25, "prev": 4.10, "date": "2026-10-09", "source": "Yahoo Finance"},
    }
    key_people_news = (
        "[Google News] 10-09 14:30 - Powell says rates may stay higher for longer\n"
        "Trump tariffs could spur inflation, Fed officials warn"
    )
    out = tmp_path / "macro_data.json"
    path = scan.write_macro_data(
        economic_structured, key_people_news, client=None, output_dir=str(tmp_path)
    )
    assert path == str(out)
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["schema_version"] == "macro.v1"
    assert data["error"] is None
    assert isinstance(data["generated_at"], str) and data["generated_at"].endswith("Z")

    econ = data["economic"]
    assert len(econ) == 3
    by_ind = {e["indicator"]: e for e in econ}
    # CPI：取 yoy 为头条；通胀类 prev 为上一期指数 → 不展示百分比（置 None）
    assert by_ind["CPI"]["value"] == "3.20%"
    assert by_ind["CPI"]["prev"] is None
    assert by_ind["CPI"]["source"] == "BLS"
    # 失业率：无 yoy，value=失业率本身（百分比），prev=None（输入未给）
    assert by_ind["失业率"]["value"] == "4.10%"
    # 10Y国债：利率类，value/prev 均为百分比
    assert by_ind["10Y国债"]["value"] == "4.25%"
    assert by_ind["10Y国债"]["prev"] == "4.10%"

    spk = data["speakers"]
    assert len(spk) == 2
    # 第一条：Google News 源 + 时间 + 抽中 Powell
    assert spk[0]["source"] == "Google News"
    assert spk[0]["time"] == "10-09 14:30"
    assert spk[0]["person"] == "Powell"
    assert "Powell" in spk[0]["content"]
    # 第二条：Trump 命中已知人物；source=未知（无 [source] 前缀）
    assert spk[1]["source"] == "未知"
    assert spk[1]["person"] == "Trump"
    # 默认无 AI 判断
    assert all(s["sentiment"] is None for s in spk)


def test_write_macro_data_empty_input(tmp_path):
    out = scan.write_macro_data({}, "", client=None, output_dir=str(tmp_path))
    data = json.loads(open(out, encoding="utf-8").read())
    assert data["economic"] == []
    assert data["speakers"] == []
    assert data["error"] is None


# ---------------------------------------------------------------------------
# 2) AI 判断批量调用：一次调用多条
# ---------------------------------------------------------------------------
def test_ai_judge_batch_single_call(monkeypatch, tmp_path):
    calls = []

    def fake_stream(client, **kwargs):
        calls.append(kwargs)
        # 返回与 combined 等长的数组：2 economic + 1 speaker = 3（对象包裹，复用 _extract_json_object）
        return json.dumps({"items": [
            {"sentiment": "bearish", "rationale": "通胀超预期施压"},
            {"sentiment": "neutral", "rationale": "符合预期"},
            {"sentiment": "bullish", "rationale": "鸽派表态利好"},
        ]})

    monkeypatch.setattr(scan, "_model_stream_text", fake_stream)

    economic_structured = {
        "CPI指数": {"value": 312.5, "yoy": 3.2, "date": "2026-09", "source": "BLS"},
        "10Y国债": {"value": 4.25, "prev": 4.10, "date": "2026-10-09", "source": "Yahoo Finance"},
    }
    key_people_news = "Powell hints rate cuts next year"
    path = scan.write_macro_data(
        economic_structured, key_people_news, client=object(), output_dir=str(tmp_path)
    )
    data = json.loads(open(path, encoding="utf-8").read())

    # 一次批量调用（无论多少条）
    assert len(calls) == 1
    # 组合条目数 = 2 economic + 1 speaker = 3，prompt 含全部
    assert "输入条目" in calls[0]["messages"][0]["content"]
    # sentiment 已回填
    econ = {e["indicator"]: e for e in data["economic"]}
    assert econ["CPI"]["sentiment"] == "bearish"
    assert econ["10Y国债"]["sentiment"] == "neutral"
    assert data["speakers"][0]["sentiment"] == "bullish"
    assert data["speakers"][0]["rationale"] == "鸽派表态利好"


def test_ai_judge_returns_non_list_safe(monkeypatch, tmp_path):
    """AI 返回非数组 → 所有 sentiment 保持 null（不崩）。"""
    monkeypatch.setattr(scan, "_model_stream_text", lambda client, **kw: "不是数组")
    economic_structured = {"失业率": {"value": 4.1, "date": "2026-09", "source": "BLS"}}
    path = scan.write_macro_data(
        economic_structured, "Powell spoke", client=object(), output_dir=str(tmp_path)
    )
    data = json.loads(open(path, encoding="utf-8").read())
    assert all(e["sentiment"] is None for e in data["economic"])
    assert all(s["sentiment"] is None for s in data["speakers"])
    assert data["error"] is None  # 未因 AI 异常写入 error


# ---------------------------------------------------------------------------
# 3) AI 失败 → sentiment: null（不崩）
# ---------------------------------------------------------------------------
def test_ai_judge_failure_null_and_no_crash(monkeypatch, tmp_path):
    def boom(client, **kwargs):
        raise RuntimeError("Claude 超时")

    monkeypatch.setattr(scan, "_model_stream_text", boom)
    economic_structured = {"CPI指数": {"value": 312.5, "yoy": 3.2, "date": "2026-09", "source": "BLS"}}
    key_people_news = "Waller says inflation cooling"
    # 不应抛异常
    path = scan.write_macro_data(
        economic_structured, key_people_news, client=object(), output_dir=str(tmp_path)
    )
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["economic"][0]["sentiment"] is None
    assert data["speakers"][0]["sentiment"] is None
    assert data["error"] is None


def test_parse_speakers_variants():
    raw = (
        "[Google News] 10-09 14:30 - Powell says rates may stay higher for longer\n"
        "Trump tariffs could spur inflation, Fed officials warn\n"
        "[CNBC] 10-08 09:15 - Markets rally on soft landing hopes"
    )
    spk = scan._parse_speakers(raw)
    assert len(spk) == 3
    assert spk[0]["source"] == "Google News" and spk[0]["time"] == "10-09 14:30"
    assert spk[0]["person"] == "Powell"
    # 第二条含 Trump（已知人物），person 应被提取；source=未知（无 [source] 前缀）
    assert spk[1]["source"] == "未知" and spk[1]["person"] == "Trump"
    assert spk[2]["source"] == "CNBC" and spk[2]["person"] is None


# ---------------------------------------------------------------------------
# 4) flag 关闭 → 不会调用 write_macro_data
# ---------------------------------------------------------------------------
def test_flag_default_off(monkeypatch):
    monkeypatch.delenv("ENABLE_MACRO_PANEL", raising=False)
    assert scan.macro_panel_enabled() is False


def test_flag_on(monkeypatch):
    monkeypatch.setenv("ENABLE_MACRO_PANEL", "1")
    assert scan.macro_panel_enabled() is True


def test_flag_off_does_not_write(monkeypatch, tmp_path):
    """gate=False 时 main 跳过落盘：直接验证 write_macro_data 未被调用。"""
    monkeypatch.delenv("ENABLE_MACRO_PANEL", raising=False)
    called = {"n": 0}

    def fake_write(*a, **k):
        called["n"] += 1
        return str(tmp_path / "macro_data.json")

    monkeypatch.setattr(scan, "write_macro_data", fake_write)
    # 模拟 main 中的 gate 逻辑
    if scan.macro_panel_enabled():
        scan.write_macro_data({}, "", client=None, output_dir=str(tmp_path))
    assert called["n"] == 0
