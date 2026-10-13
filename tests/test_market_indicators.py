# -*- coding: utf-8 -*-
"""市场情绪指标（F&G + FedWatch）测试。

覆盖：
  1) 两数据源都成功 → 正确解析（score / rating / 概率归一化）
  2) F&G 失败 + FedWatch 成功 → fear_greed=null，fedwatch 正常，error 记录失败源
  3) 两源都失败 → 不写文件（R1）
  4) flag 关：yml 步骤被 if: 跳过；且 export 在文件缺失时返回哨兵（payload 不注入键，逐字节一致）
  5) 前端：market_indicators 为 null → 整块隐藏
  6) 前端：有数据 → 正确渲染 F&G 环形图 + FedWatch 概率条

注：fear_greed / cme_fedwatch 在沙箱 / 默认 CI 可能未安装，测试通过 monkeypatch
sys.modules 注入 fake 包，不依赖真实网络与真实包，纯验证解析 / 容错 / 渲染逻辑。
"""
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_fetcher():
    p = REPO_ROOT / "dashboard" / "fetch_market_indicators.py"
    spec = importlib.util.spec_from_file_location("fetch_market_indicators", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_fear_greed():
    mod = types.SimpleNamespace()

    class _Pt:
        def __init__(self, date, score, rating):
            self.date = date
            self.score = score
            self.rating = rating

        def to_dict(self):
            return {"date": self.date, "score": self.score, "rating": self.rating}

    def get():
        return {
            "score": 69,
            "rating": "Greed",
            "timestamp": "2026-10-12T13:00:00+00:00",
            "history": {"1w": 60.0, "1m": 55.0},
            "indicators": {
                "stock_price_momentum": {"score": 70.0, "rating": "Greed"},
                "put_call_ratio": {"score": 40.0, "rating": "Fear"},
            },
        }

    def get_history(last=None, start=None, end=None):
        return [_Pt("2026-10-12", 69.0, "Greed"), _Pt("2026-10-11", 68.0, "Fear")]

    mod.get = get
    mod.get_history = get_history
    return mod


def _fake_cme_fedwatch():
    mod = types.SimpleNamespace()

    def get_probabilities(meeting=None, trade_date=None, current_rate=None):
        return {
            "effr": 4.33,
            "current_target": "4.25%-4.50%",
            "trade_date": "2026-10-10",
            "schedule_status": {},
            "meetings": [{
                "date": "2026-11-05",
                "contract": "ZQX6",
                "probabilities": {
                    "4.25%-4.50%": 55.0,
                    "4.00%-4.25%": 45.0,
                    "4.50%-4.75%": 0.0,
                },
            }],
        }

    mod.get_probabilities = get_probabilities
    return mod


@pytest.fixture(autouse=True)
def _clean_fg_fw_modules():
    saved = {}
    for name in ("fear_greed", "cme_fedwatch"):
        if name in sys.modules:
            saved[name] = sys.modules[name]
            del sys.modules[name]
    yield
    for name, mod in saved.items():
        sys.modules[name] = mod


def test_both_sources_success(tmp_path):
    """两数据源都成功 → 正确解析 score/rating + FedWatch 概率归一化。"""
    fetcher = _load_fetcher()
    sys.modules["fear_greed"] = _fake_fear_greed()
    sys.modules["cme_fedwatch"] = _fake_cme_fedwatch()

    out = tmp_path / "market_indicators.json"
    rc = fetcher.main(["--out", str(out)])
    assert rc == 0, "两源成功应写文件"
    assert out.exists()

    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["schema_version"] == "market_indicators.v1"
    assert d["error"] is None
    # F&G
    fg = d["fear_greed"]
    assert fg["score"] == 69
    assert fg["rating"] == "Greed"
    assert fg["subindicators"]["stock_price_momentum"]["score"] == 70.0
    assert isinstance(fg["history_30d"], list) and len(fg["history_30d"]) == 2
    # FedWatch 概率归一化：相对当前目标 4.25%-4.50%
    fw = d["fedwatch"]
    assert fw["next_meeting"] == "2026-11-05"
    assert fw["source"] == "cme"
    assert fw["probabilities"]["hold"] == 55.0       # 等于当前目标区间
    assert fw["probabilities"]["cut_25bp"] == 45.0    # 低 25bp → 降息
    assert fw["probabilities"]["hike_25bp"] == 0.0   # 高 25bp → 加息


def _block_imports(monkeypatch, *names):
    """强制指定顶层包 import 抛 ImportError，模拟"包未安装"。

    为什么需要：本文件有两个用例靠"包恰好没装"来构造失败分支
    （`import fear_greed` / `import cme_fedwatch` 失败 → None）。
    一旦这些包被装进环境（例如 `requirements-production.txt` 声明了它们），
    用例就会去访问真实网络并把断言打穿 —— 即"环境脆弱"。

    这里用 monkeypatch 覆盖 `builtins.__import__`，只拦白名单里的包，
    其余 import 一律委托真实实现，因此不依赖环境、不打网络。
    必须在 `_load_fetcher()` 之后调用（该函数自身还要 import importlib）。
    """
    import builtins

    real_import = builtins.__import__
    blocked = set(names)

    def fake_import(name, *args, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError(f"simulated missing module: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_fg_fails_fw_ok(tmp_path, monkeypatch):
    """F&G 失败 + FedWatch 成功 → fear_greed=null，fedwatch 正常，error 记录 F&G 失败。

    hermetic：用 `_block_imports` 强制 F&G import 失败，不再依赖"环境里恰好没装
    fear-greed"。否则一旦装了这个包，本用例会去访问真实 CNN 接口并返回真数据。
    """
    fetcher = _load_fetcher()
    sys.modules["cme_fedwatch"] = _fake_cme_fedwatch()
    _block_imports(monkeypatch, "fear_greed")

    out = tmp_path / "market_indicators.json"
    rc = fetcher.main(["--out", str(out)])
    assert rc == 0  # 至少一源成功 → 写文件
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["fear_greed"] is None
    assert d["fedwatch"]["next_meeting"] == "2026-11-05"
    assert "fear_greed" in (d["error"] or {})


def test_both_sources_fail_no_file(tmp_path, monkeypatch):
    """两源都失败（包均不可用）→ 不写文件（R1），返回 1。

    hermetic：两个包都强制 import 失败，不依赖环境里是否安装。
    """
    fetcher = _load_fetcher()
    _block_imports(monkeypatch, "fear_greed", "cme_fedwatch")

    out = tmp_path / "market_indicators.json"
    rc = fetcher.main(["--out", str(out)])
    assert rc == 1
    assert not out.exists(), "R1：两源失败不应写文件"


def test_flag_off_guard_and_export_no_key(tmp_path):
    """flag 关：yml 步骤被 if: 跳过；且 export 在文件缺失时返回哨兵（payload 不注入键）。"""
    # 1) dashboard-data.yml 含 flag-gated 步骤（步骤被 if: 跳过 → flag 关时根本不调用脚本）
    yml = (REPO_ROOT / ".github" / "workflows" / "dashboard-data.yml").read_text(encoding="utf-8")
    assert "Fetch market indicators (flag-gated)" in yml
    step_region = yml.split("Fetch market indicators (flag-gated)")[1].split("Run dashboard_export.py")[0]
    assert "if: env.ENABLE_MARKET_INDICATORS == '1'" in step_region, "步骤必须被 if: 包裹"
    assert "continue-on-error: true" in step_region
    assert "ENABLE_MARKET_INDICATORS: ${{ vars.ENABLE_MARKET_INDICATORS }}" in yml
    # commit guard 已放行 market_indicators.json
    assert "dashboard/data/market_indicators.json" in yml

    # 2) export：文件缺失 → 哨兵（调用方不注入键 → 与现在逐字节一致）
    from dashboard_export import _read_market_indicators, _MARKET_INDICATORS_MISSING
    d = _read_market_indicators(tmp_path)  # tmp_path 无该文件
    assert d is _MARKET_INDICATORS_MISSING
    # 对称验证：文件存在 → 返回其 dict（flag 开时才会写文件，此时 payload 才注入键）
    # 注意：必须放在**真实嵌套位置** dashboard/data/ 下；读取函数只认
    # <root>/dashboard/data/market_indicators.json（见下方回归测试）。
    nested = tmp_path / "dashboard" / "data"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "market_indicators.json").write_text(
        json.dumps({"schema_version": "market_indicators.v1", "fear_greed": None,
                    "fedwatch": None, "error": "test"}), encoding="utf-8")
    d2 = _read_market_indicators(tmp_path)
    assert d2 is not _MARKET_INDICATORS_MISSING
    assert d2["schema_version"] == "market_indicators.v1"
    assert d2["error"] == "test"


def test_read_path_must_be_dashboard_data_regression(tmp_path):
    """回归（2026-10-13）：读取路径必须是 <root>/dashboard/data/market_indicators.json。

    历史 bug（已修）：
      · 写入侧 `dashboard/fetch_market_indicators.py:140` 默认写
        `dashboard/data/market_indicators.json`；
      · 读取侧 `dashboard_export.py` 却读 `<root>/market_indicators.json`
        —— 少了 `dashboard/data/` 这一段；
      · 结果：文件已生成并入库，但 `dashboard_data.json` **从不注入**
        `market_indicators` 键 → 前端「市场情绪指标」面板永不出现。

    旧测试为什么抓不到：它们把文件直接放在 `tmp_path` 根下，正好等于**错误路径**，
    与 bug 自洽。本测试把文件放在**真实嵌套位置**，并把「直接放根」显式断言为
    **读不到**，从而把契约钉死，防止未来退回旧路径。
    """
    from dashboard_export import _read_market_indicators, _MARKET_INDICATORS_MISSING

    payload = {
        "schema_version": "market_indicators.v1",
        "fear_greed": {"score": 45.4, "rating": "neutral"},
        "fedwatch": None,
        "error": None,
    }

    # 1) 正确位置：<root>/dashboard/data/market_indicators.json → 必须读到
    nested = tmp_path / "dashboard" / "data"
    nested.mkdir(parents=True)
    (nested / "market_indicators.json").write_text(json.dumps(payload), encoding="utf-8")
    got = _read_market_indicators(tmp_path)
    assert got is not _MARKET_INDICATORS_MISSING, (
        "路径回归：读取函数没有去 <root>/dashboard/data/ 找 market_indicators.json"
    )
    assert got["fear_greed"]["score"] == 45.4

    # 2) 错误位置：<root>/market_indicators.json → 不应被读取（钉死契约）
    wrong_root = tmp_path / "wrong_root"
    wrong_root.mkdir()
    (wrong_root / "market_indicators.json").write_text(json.dumps(payload), encoding="utf-8")
    assert _read_market_indicators(wrong_root) is _MARKET_INDICATORS_MISSING, (
        "路径回归：<root>/market_indicators.json 不应被读取（那是历史错误路径）"
    )


# --------------------------------------------------------------------------- #
# 前端 node harness（复用 test_macro_panel_frontend.py 思路：内存注入 DOM 钩子）
# --------------------------------------------------------------------------- #
def _run_node(transformed, tail):
    harness = (
        "globalThis.document={\n"
        "  addEventListener(){},querySelectorAll(){return[]},getElementById(){return null},\n"
        "  querySelector(sel){\n"
        "    globalThis.__els = globalThis.__els || {};\n"
        "    if(!globalThis.__els[sel]) globalThis.__els[sel] = {innerHTML:'',textContent:'',style:{}};\n"
        "    return globalThis.__els[sel];\n"
        "  }\n"
        "};\n"
        "globalThis.window={addEventListener(){},IT:null};\n"
        "globalThis.fetch=()=>Promise.resolve({json:()=>Promise.resolve({})});\n"
    )
    js = REPO_ROOT / "tests" / "_mi_harness.js"
    js.write_text(harness + transformed + tail, encoding="utf-8")
    try:
        proc = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, f"node 执行失败：{proc.stderr}"
        return json.loads(proc.stdout.strip().splitlines()[-1])
    finally:
        js.unlink(missing_ok=True)


def _expose(app_js):
    out = app_js.replace(
        "\n  boot();\n",
        "\n  globalThis.__setMI = function(m){ if(!DATA) DATA={}; DATA.market_indicators = m; };\n"
        "  globalThis.__renderMI = renderMarketIndicators;\n")
    assert "__renderMI" in out, "未能注入 renderMarketIndicators 暴露钩子"
    return out


def test_frontend_null_hidden():
    """market_indicators 为 null → 整块隐藏（style.display='none'），不渲染。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)
    tail = (
        "\nglobalThis.__setMI(null);\n"
        "globalThis.__renderMI();\n"
        "var els = globalThis.__els || {};\n"
        "console.log(JSON.stringify({\n"
        "  card_display: els['#marketIndicatorsCard'] ? els['#marketIndicatorsCard'].style.display : null,\n"
        "  body: els['#marketIndicatorsBody'] ? els['#marketIndicatorsBody'].innerHTML : null\n"
        "}));\n"
    )
    r = _run_node(exposed, tail)
    assert r["card_display"] == "none", r
    assert not (r["body"] or ""), r


def test_frontend_render_with_data():
    """有数据 → 正确渲染 F&G 环形图 + 5 档标签 + FedWatch 概率条；整块显示。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)
    mi = {
        "schema_version": "market_indicators.v1",
        "fear_greed": {
            "score": 69, "rating": "Greed",
            "timestamp": "2026-10-12T13:00:00+00:00",
            "subindicators": {
                # 非 7 个真实 key 之一 → 应原样回退显示原 key
                "stock_price_momentum": {"score": 70.0, "rating": "Greed"},
                # 真实 key → 应显示中文；rating 用大写测大小写无关
                "market_volatility_vix": {"score": 50.0, "rating": "Neutral"},
                # 真实 key + 小写 rating（真实数据就是小写）→ 同样要命中
                "put_call_options": {"score": 35.0, "rating": "extreme fear"},
            },
            "history_30d": [{"date": "2026-10-12", "score": 69.0, "rating": "Greed"}],
        },
        "fedwatch": {
            "next_meeting": "2026-11-05", "current_target": "4.25%-4.50%",
            "probabilities": {"hold": 55.0, "cut_25bp": 45.0, "hike_25bp": 0.0},
            "source": "cme",
        },
        "error": None,
    }
    tail = (
        "\nglobalThis.__setMI(" + json.dumps(mi) + ");\n"
        "globalThis.__renderMI();\n"
        "var els = globalThis.__els || {};\n"
        "console.log(JSON.stringify({\n"
        "  card_display: els['#marketIndicatorsCard'] ? els['#marketIndicatorsCard'].style.display : null,\n"
        "  body: els['#marketIndicatorsBody'] ? els['#marketIndicatorsBody'].innerHTML : null\n"
        "}));\n"
    )
    r = _run_node(exposed, tail)
    body = r["body"] or ""
    assert r["card_display"] == "block", r
    # F&G
    assert "CNN 恐惧贪婪指数" in body, body
    assert "69.0" in body, body  # ring 中心分数
    assert "mi-greed" in body, body  # 5 档配色（score 69 → greed；⚠️ 类名不翻译）
    # --- F&G 中文映射（大小写无关：fake 给的是大写 "Greed" / "Neutral"）---
    assert "贪婪" in body, body            # rating → 中文
    assert "中性" in body, body            # 子指标 rating → 中文
    assert "Greed" not in body, body       # 英文原值不应残留
    assert "市场波动(VIX)" in body, body   # 真实子指标 key → 中文
    assert "看跌/看涨期权" in body, body    # 真实子指标 key → 中文
    assert "极度恐惧" in body, body         # 小写 "extreme fear" 也要命中（真实数据即小写）
    assert "stock_price_momentum" in body, body  # 非映射 key → fallback 原样
    # FedWatch
    assert "CME FedWatch" in body, body
    assert "下次 FOMC：" in body, body  # 日期被 <b> 包裹，分段断言
    assert "2026-11-05" in body, body
    assert "降息 25bp" in body, body  # cut_25bp 归一化标签
    assert "55.0%" in body, body     # hold 概率


# --------------------------------------------------------------------------- #
# FedWatch 多会议（最近 3 次）
# --------------------------------------------------------------------------- #
_FW_DATES = ["2026-11-05", "2026-12-16", "2027-01-27", "2027-03-17", "2027-04-28"]


def _fake_cme_fedwatch_n(n, calls=None):
    """返回含 n 场会议的 fake；`calls` 非 None 时记录每次调用的 meeting 实参。"""
    mod = types.SimpleNamespace()

    def get_probabilities(meeting=None, trade_date=None, current_rate=None):
        if calls is not None:
            calls.append(meeting)
        return {
            "effr": 4.33,
            "current_target": "4.25%-4.50%",
            "trade_date": "2026-10-10",
            "schedule_status": {},
            "meetings": [
                {"date": d, "contract": f"ZQ{i}",
                 "probabilities": {"4.25%-4.50%": 55.0, "4.00%-4.25%": 45.0}}
                for i, d in enumerate(_FW_DATES[:n])
            ],
        }

    mod.get_probabilities = get_probabilities
    return mod


def test_fedwatch_takes_three_meetings_and_keeps_backcompat():
    """取最近 3 场；旧字段 next_meeting / probabilities 必须保留 = meetings[0]。"""
    fetcher = _load_fetcher()
    calls = []
    sys.modules["cme_fedwatch"] = _fake_cme_fedwatch_n(5, calls)

    fw, err = fetcher.fetch_fedwatch()
    assert err is None, err
    assert len(fw["meetings"]) == 3, f"应只取 3 场，实得 {len(fw['meetings'])}"
    assert [m["date"] for m in fw["meetings"]] == _FW_DATES[:3]

    # 关键：必须【不传】meeting（传 "next" 只会给 1 场）
    assert calls == [None], f"应以无参调用 get_probabilities()，实际 calls={calls}"

    # 向后兼容：旧字段 = 第一场
    assert fw["next_meeting"] == fw["meetings"][0]["date"]
    assert fw["probabilities"] == fw["meetings"][0]["probabilities"]
    assert fw["probabilities"]["hold"] == 55.0     # 归一化仍生效

    # 每场都必须有 date + 归一化后的 probabilities
    for m in fw["meetings"]:
        assert m["date"], m
        assert m["probabilities"], m
        assert "hold" in m["probabilities"], m


def test_fedwatch_fewer_than_max_is_ok():
    """只有 1 场可用时不应补空、不应报错。"""
    fetcher = _load_fetcher()
    sys.modules["cme_fedwatch"] = _fake_cme_fedwatch_n(1)
    fw, err = fetcher.fetch_fedwatch()
    assert err is None, err
    assert len(fw["meetings"]) == 1
    assert fw["next_meeting"] == _FW_DATES[0]


def _mi_payload(fedwatch):
    return {
        "schema_version": "market_indicators.v1",
        "fear_greed": {"score": 45.4, "rating": "neutral"},
        "fedwatch": fedwatch,
        "error": None,
    }


def _render_mi(mi):
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)
    tail = (
        "\nglobalThis.__setMI(" + json.dumps(mi) + ");\n"
        "globalThis.__renderMI();\n"
        "var els = globalThis.__els || {};\n"
        "console.log(JSON.stringify({"
        " body: els['#marketIndicatorsBody'] ? els['#marketIndicatorsBody'].innerHTML : null }));\n"
    )
    return _run_node(exposed, tail)["body"] or ""


def test_frontend_fedwatch_renders_three_meetings():
    """fw.meetings[] 有 3 场 → 全部渲染（下次 + 随后×2），各自独立概率条。"""
    body = _render_mi(_mi_payload({
        "next_meeting": "2026-10-28",
        "current_target": "3.75%-4.00%",
        "probabilities": {"hold": 79.0, "hike_25bp": 21.0},
        "meetings": [
            {"date": "2026-10-28", "probabilities": {"hold": 79.0, "hike_25bp": 21.0}},
            {"date": "2026-12-09", "probabilities": {"hold": 60.0, "cut_25bp": 40.0}},
            {"date": "2027-01-27", "probabilities": {"hold": 50.0, "cut_25bp": 50.0}},
        ],
        "source": "cme",
    }))
    for d in ("2026-10-28", "2026-12-09", "2027-01-27"):
        assert d in body, f"{d} 未渲染：{body}"
    assert body.count("下次 FOMC：") == 1, body
    assert body.count("随后 FOMC：") == 2, body
    assert body.count('class="mi-fw-meet') == 3, body
    assert body.count('class="mi-bars"') == 3, body
    assert "79.0%" in body and "40.0%" in body and "50.0%" in body, body


def test_frontend_fedwatch_backward_compat_single_meeting():
    """旧后端 payload（**无** meetings 字段）→ 仍按单会议渲染，不白屏。"""
    body = _render_mi(_mi_payload({
        "next_meeting": "2026-11-05",
        "current_target": "4.25%-4.50%",
        "probabilities": {"hold": 55.0, "cut_25bp": 45.0},
        "source": "cme",
    }))
    assert "2026-11-05" in body, body
    assert body.count("下次 FOMC：") == 1, body
    assert "随后 FOMC：" not in body, body
    assert body.count('class="mi-bars"') == 1, body
    assert "55.0%" in body and "降息 25bp" in body, body
