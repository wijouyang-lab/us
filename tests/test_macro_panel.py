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
    # 中性化版本标记写入（收尾 2）：scan.py 在导入期调用 update_version_marker()，
    # 它会重写被跟踪文件 scan_version.txt → 跑测试会污染工作区。
    # 在定义处插入提前 return，使该函数成为空实现（无论被谁调用都不写盘）。
    src = src.replace(
        "def update_version_marker():\n",
        "def update_version_marker():\n    return None  # 测试：禁止改写 scan_version.txt\n",
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
# 2b) content_cn 中文翻译（改动 2）
# ---------------------------------------------------------------------------
def test_parse_speakers_content_cn_defaults_none():
    """改动 2：_parse_speakers 必须初始化 content_cn（字段恒存在，值为 null）。"""
    spk = scan._parse_speakers("[CNBC] 10-12 09:00 - Powell speaks on rates")
    assert "content_cn" in spk[0]
    assert spk[0]["content_cn"] is None


def test_ai_judge_fills_content_cn_for_speaker_only(monkeypatch, tmp_path):
    """改动 2：AI 返回的 content_cn 落到 speaker；economic 不写该字段。"""
    def fake_stream(client, **kwargs):
        return json.dumps({"items": [
            {"sentiment": "bearish", "rationale": "通胀超预期施压", "content_cn": ""},
            {"sentiment": "neutral", "rationale": "无明确方向",
             "content_cn": "债券交易员等待 CPI，关注沃什对美联储利率路径的看法"},
        ]})

    monkeypatch.setattr(scan, "_model_stream_text", fake_stream)
    economic_structured = {"CPI指数": {"value": 312.5, "yoy": 3.2, "date": "2026-09", "source": "BLS"}}
    key_people_news = ("[📄昨日-中等权重][Google News] 10-11 10:23 - "
                       "US bond traders await CPI - Yahoo Finance Singapore")
    path = scan.write_macro_data(
        economic_structured, key_people_news, client=object(), output_dir=str(tmp_path)
    )
    data = json.loads(open(path, encoding="utf-8").read())

    spk = data["speakers"][0]
    assert spk["content_cn"] == "债券交易员等待 CPI，关注沃什对美联储利率路径的看法"
    assert spk["age_tag"] == "📄昨日-中等权重"
    assert spk["source"] == "Yahoo Finance Singapore"
    # economic 条目不写 content_cn
    assert "content_cn" not in data["economic"][0]


def test_ai_judge_content_cn_null_on_failure(monkeypatch, tmp_path):
    """改动 2：AI 失败 → content_cn 保持 None（字段在、值为 null，前端回退英文）。"""
    def boom(client, **kwargs):
        raise RuntimeError("Claude 超时")

    monkeypatch.setattr(scan, "_model_stream_text", boom)
    path = scan.write_macro_data(
        {"CPI指数": {"value": 312.5, "yoy": 3.2, "date": "2026-09", "source": "BLS"}},
        "[CNBC] 10-12 09:00 - Powell speaks on rates",
        client=object(), output_dir=str(tmp_path),
    )
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["speakers"][0]["content_cn"] is None
    assert data["error"] is None


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
# 3b) source 解析：年龄标签 vs 真实来源（修 source 误显示为权重标签的 bug）
# ---------------------------------------------------------------------------
def test_parse_speakers_two_bracket_age_tag_and_tail_outlet():
    """生产格式 [年龄标签][Google News] 时间 - 正文 - 媒体名：
    年龄标签进 age_tag，来源取尾部媒体名（这正是原 bug 的修复点）。"""
    raw = (
        "[📄昨日-中等权重][Google News] 10-11 10:23 - "
        "US bond traders await CPI, Warsh for insight on Fed's rate path - Yahoo Finance Singapore"
    )
    spk = scan._parse_speakers(raw)
    assert len(spk) == 1
    s = spk[0]
    assert s["age_tag"] == "📄昨日-中等权重"
    assert s["source"] == "Yahoo Finance Singapore"
    assert s["time"] == "10-11 10:23"
    assert s["person"] == "Warsh"
    assert "US bond traders await CPI" in s["content"]


def test_parse_speakers_two_bracket_real_source():
    """[年龄标签][真实来源] 时间 - 正文：来源取第二个方括号，不触发尾部兜底。"""
    raw = "[📰今日-高权重][CNBC] 10-12 20:00 - Waller flags cooling inflation"
    spk = scan._parse_speakers(raw)
    assert spk[0]["age_tag"] == "📰今日-高权重"
    assert spk[0]["source"] == "CNBC"
    assert spk[0]["time"] == "10-12 20:00"
    assert spk[0]["person"] == "Waller"


def test_parse_speakers_single_bracket_is_source():
    """[来源] 时间 - 正文（无年龄标签）：source=来源，age_tag 为空。"""
    raw = "[Reuters] 10-12 09:00 - Powell speaks on the rate path"
    spk = scan._parse_speakers(raw)
    assert spk[0]["source"] == "Reuters"
    assert spk[0]["age_tag"] is None
    assert spk[0]["time"] == "10-12 09:00"


def test_parse_speakers_no_timestamp_and_age_tag_only():
    """无时间戳可解析；且只有单个方括号、而它就是年龄标签时，不得把它当来源。"""
    raw = (
        "[📄昨日-中等权重][CNBC] - Waller flags cooling inflation\n"
        "[📑前日-低权重] - Bowman comments on policy"
    )
    spk = scan._parse_speakers(raw)
    assert spk[0]["age_tag"] == "📄昨日-中等权重"
    assert spk[0]["source"] == "CNBC"
    assert spk[0]["time"] is None
    assert spk[0]["content"] == "Waller flags cooling inflation"
    assert spk[1]["age_tag"] == "📑前日-低权重"
    assert spk[1]["source"] == "未知"


def test_parse_speakers_time_unknown_tag():
    """[时间未知]（_news_age_tag(None) 的产出）同样被识别为年龄标签，不是来源。"""
    raw = "[时间未知][CNBC] - Powell speaks"
    spk = scan._parse_speakers(raw)
    assert spk[0]["age_tag"] == "时间未知"
    assert spk[0]["source"] == "CNBC"


def test_parse_speakers_tail_heuristic_guard():
    """护栏：来源是真实媒体时，正文里的 ' - ' 不得被误当来源。"""
    raw = "[CNBC] 10-12 09:00 - Fed cuts rates - what it means for stocks"
    spk = scan._parse_speakers(raw)
    assert spk[0]["source"] == "CNBC"


def test_parse_speakers_degradation_no_brackets():
    """无方括号 / 空行 → 降级为 source=未知、age_tag 为空，不崩溃。"""
    raw = "\nTrump tariffs could spur inflation, Fed officials warn\n   \n"
    spk = scan._parse_speakers(raw)
    assert len(spk) == 1
    assert spk[0]["source"] == "未知"
    assert spk[0]["age_tag"] is None
    assert spk[0]["time"] is None
    assert spk[0]["person"] == "Trump"
    assert scan._parse_speakers("") == []


# ---------------------------------------------------------------------------
# 3c/3a) 稳定 ≥5 条：兜底补足 + 去重 + 查询词覆盖
# ---------------------------------------------------------------------------
_GN_3 = [
    "[📄昨日-中等权重][Google News] 10-11 10:23 - US bond traders await CPI - Yahoo Finance Singapore",
    "[📰今日-高权重][Google News] 10-12 21:08 - Trump tariffs spook markets - SMH.com.au",
    "[📄昨日-中等权重][Google News] 10-11 09:13 - Kevin Warsh speech preview - TradingView",
]


def _patch_rss(monkeypatch, google_news_rows, recorder=None):
    """把 _rss_search_google 替换为：仅第一条查询返回给定行，其余返回空；并停掉 sleep。"""
    def fake_rss(query, max_items=6):
        if recorder is not None:
            recorder.append(query)
        return list(google_news_rows) if query.startswith("Kevin Warsh") else []
    monkeypatch.setattr(scan, "_rss_search_google", fake_rss)
    monkeypatch.setattr(scan.time, "sleep", lambda *_: None)  # 免去 11 × 1s 等待


def test_fallback_tops_up_when_google_news_below_5(monkeypatch):
    """改动 3c：Google News 只有 3 条时必须兜底补足（原条件 `not rows` 不会触发）。"""
    _patch_rss(monkeypatch, _GN_3)
    macro_news = "\n".join([
        "[CNBC] 10-13 08:00 - Powell says the Fed is in no rush to cut rates",       # powell/rate
        "[Reuters] 10-13 07:30 - Waller flags cooling inflation",                    # waller/inflation
        "[MarketWatch] 10-12 20:00 - Federal Reserve minutes show hawkish tilt",     # federal reserve/hawkish
        "[CNBC] 10-12 16:00 - Oil rises on supply concerns",                         # 无 priority term → 应被排除
    ])
    out = scan.get_key_people_policy_news(macro_news)
    lines = [l for l in out.split("\n") if l.strip()]
    assert len(lines) == 6, lines                      # 3 条 Google News + 3 条兜底
    assert any("Powell says the Fed" in l for l in lines)
    assert any("Waller flags cooling" in l for l in lines)
    assert any("Federal Reserve minutes" in l for l in lines)
    assert not any("Oil rises" in l for l in lines)
    # 注：兜底与查询词已对齐（priority_terms 含 yellen/bessent，见收尾 1）。


def test_fallback_selects_yellen_and_bessent(monkeypatch):
    """收尾 1：兜底 priority_terms 已含 yellen/bessent，与新增查询词保持一致。"""
    _patch_rss(monkeypatch, [])          # Google News 无产出 → 触发兜底
    macro_news = "\n".join([
        "[CNBC] 10-13 08:30 - Yellen warns on Treasury yields",
        "[Reuters] 10-13 08:10 - Bessent comments on the dollar and deficit",
        "[CNBC] 10-13 07:00 - Oil rises on supply concerns",      # 无 priority term → 应排除
    ])
    out = scan.get_key_people_policy_news(macro_news)
    lines = [l for l in out.split("\n") if l.strip()]
    assert any("Yellen warns" in l for l in lines), lines
    assert any("Bessent comments" in l for l in lines), lines
    assert not any("Oil rises" in l for l in lines), lines
    # 解析后 person 应能识别 Yellen（_KNOWN_SPEAKERS 已含）
    spk = scan._parse_speakers(out)
    assert any(s["person"] == "Yellen" for s in spk), spk


def test_fallback_dedups_against_google_news(monkeypatch):
    """改动 3c：兜底结果与 Google News 结果按同一 key 去重，不重复追加。"""
    one = [_GN_3[0]]
    _patch_rss(monkeypatch, one)
    macro_news = "\n".join(one + ["[CNBC] 10-13 08:00 - Waller flags cooling inflation"])
    out = scan.get_key_people_policy_news(macro_news)
    lines = [l for l in out.split("\n") if l.strip()]
    assert len(lines) == 2, lines
    assert sum(1 for l in lines if "US bond traders await CPI" in l) == 1
    assert any("Waller flags cooling" in l for l in lines)


def test_fallback_skipped_when_already_5_or_more(monkeypatch):
    """改动 3c 边界：Google News 已 ≥5 条时不再兜底（不做多余选择）。"""
    five = [
        f"[📄昨日-中等权重][Google News] 10-11 10:0{i} - Powell story {i} - Outlet{i}"
        for i in range(5)
    ]
    _patch_rss(monkeypatch, five)
    out = scan.get_key_people_policy_news("[CNBC] 10-13 08:00 - Waller flags cooling inflation")
    lines = [l for l in out.split("\n") if l.strip()]
    assert len(lines) == 5, lines
    assert not any("Waller flags cooling" in l for l in lines)


def test_key_people_queries_cover_original_and_new(monkeypatch):
    """改动 3a：6 条原查询 + 5 条新增查询，共 11 条全部被调用。"""
    seen_queries = []
    _patch_rss(monkeypatch, [], recorder=seen_queries)
    out = scan.get_key_people_policy_news("")           # 无宏观新闻 → 不兜底
    assert len(seen_queries) == 11, seen_queries
    for q in (
        "Kevin Warsh Federal Reserve rate inflation speech",
        "Jerome Powell Federal Reserve speech rates inflation",
        "Christopher Waller Federal Reserve rate speech",
        "Michelle Bowman Federal Reserve rate speech",
        "Trump tariffs inflation Federal Reserve interest rates",
        "Federal Reserve officials hawkish dovish September rate decision",
        "Janet Yellen Federal Reserve speech",
        "Scott Bessent Treasury speech",
        "Fed minutes release",
        "Treasury yields forecast",
        "rate cut odds futures",
    ):
        assert q in seen_queries, q
    # 全部无产出且无兜底料 → 占位串，不崩
    assert out.startswith("暂无重要人物")


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
