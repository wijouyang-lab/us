/* =========================================================
   Invest Terminal · UI v3 —— 真实数据版（阶段 B）

   数据源：dashboard/data/dashboard_data.json
   由 dashboard_export.py 生成（读取 pending CSV / trade_history /
   option_strategies / strategy_params），前端只做 JSON → UI。

   铁律：
   - 不调用 GPT / 不生成评分 / 不生成行情
   - null 一律显示 — 或「暂无行情数据」，绝不显示 0 / NaN
   - 无 K 线序列时不画假 K 线
   ========================================================= */
(function () {
  'use strict';

  var DATA_URL = 'dashboard/data/dashboard_data.json';

  // iOS Safari / WKWebView 会忽略 cache:'no-store' 并沿用磁盘缓存，
  // 导致手机端一直显示旧数据。请求时追加一次性时间戳参数强制绕过缓存。
  function dataUrl() {
    return DATA_URL + (DATA_URL.indexOf('?') >= 0 ? '&' : '?') + 't=' + Date.now();
  }

  var NA = '—';
  var TECH_NA = '暂无行情数据';
  var MARKET_NA = '暂无行情';
  var INSUFF = '数据不足';
  var AI_PENDING = 'AI analysis pending';
  var AI_EMPTY = '暂无 AI 分析';

  /* ---------------- 全局状态 ---------------- */
  var DATA = null;
  var META = {}, MARKET = { assets: [], regime: {} }, REVIEW = {};
  var OPTIONS = [], HISTORY = [], STOCKS = [], OPT_BY_TK = {};
  var REVIEWS = [];                         /* review.records[] —— 历史推荐明细（只读，不重算） */
  var MAX_F = 35, MAX_T = 25, MAX_R = 20;   /* 来自 strategy_params.json 的评分权重 */
  var NET_DOWN = false;                      /* meta.network_status 是否 unavailable */
  var cur = null, curRange = 126;

  /* ---------------- utils ---------------- */
  var $ = function (s, r) { return (r || document).querySelector(s); };

  /* AI 六段：非字符串一律归一成空字符串，杜绝 null / undefined / NaN 出现在页面上 */
  function aiStr(v) { return (typeof v === 'string' && v.trim()) ? v.trim() : ''; }
  function normAi(ai) {
    ai = (ai && typeof ai === 'object') ? ai : {};
    return {
      chain: aiStr(ai.industry_logic),
      news: aiStr(ai.news_cn),
      conclusion: aiStr(ai.premarket_conclusion),
      catalysts: aiStr(ai.catalysts),
      risks: aiStr(ai.risks),
      invalidation: aiStr(ai.invalidation)
    };
  }

  function num(v) {
    if (v === null || v === undefined || v === '') return null;
    var n = Number(v);
    return (typeof n === 'number' && isFinite(n)) ? n : null;
  }
  function fmt(n, d) {
    d = d == null ? 2 : d;
    return Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function signed(v, d) { return (v > 0 ? '+' : '') + fmt(v, d == null ? 2 : d); }
  function dirCls(v) { return v > 0 ? 'up' : (v < 0 ? 'down' : 'flat'); }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }

  /* 普通数值 → 文本（null 显示 —） */
  function nv(v, d) { var n = num(v); return n === null ? NA : fmt(n, d == null ? 2 : d); }
  // 期权 Wall 显示：无效/无有效 OI 时显式标 N/A，绝不显示捏造的默认数值（如 100.00）
  function wallVal(v, unavailable, d) {
    if (v === null || v === undefined) return unavailable ? 'N/A' : NA;
    return fmt(num(v), d == null ? 2 : d);
  }
  /* 技术类数值 → 文本（行情不可用时显示「暂无行情数据」） */
  function tnv(v, d) {
    var n = num(v);
    if (n !== null) return fmt(n, d == null ? 2 : d);
    return NET_DOWN ? TECH_NA : NA;
  }
  /* 比率 → 百分比文本（0.3811 → +38.1%） */
  function pctTxt(v, d) {
    var n = num(v);
    return n === null ? NA : signed(n * 100, d == null ? 1 : d) + '%';
  }
  function usdTxt(v, d) { var n = num(v); return n === null ? NA : '$' + fmt(n, d == null ? 2 : d); }
  function capTxt(v) {
    var n = num(v);
    if (n === null) return NA;
    if (Math.abs(n) >= 1e12) return fmt(n / 1e12, 2) + 'T';
    if (Math.abs(n) >= 1e9) return fmt(n / 1e9, 2) + 'B';
    if (Math.abs(n) >= 1e6) return fmt(n / 1e6, 1) + 'M';
    return fmt(n, 0);
  }
  function naIf(txt) { return txt === NA || txt === TECH_NA || txt === INSUFF; }
  function cell(k, txt, cls) {
    return '<div class="mx"><div class="k">' + k + '</div><div class="v ' +
      (naIf(txt) ? 'na' : '') + ' ' + (cls || '') + '">' + txt + '</div></div>';
  }
  function pctCls(v) { return v > 0 ? 'up' : (v < 0 ? 'down' : ''); }

  /* 评分配色（蓝色系，避免与涨跌红绿混淆） */
  function scoreColor(v) {
    if (v >= 85) return '#2b5cf0';
    if (v >= 75) return '#4a7bf0';
    if (v >= 65) return '#5b8def';
    if (v >= 55) return '#93a7c4';
    return '#b6bdc9';
  }
  function barCls(p) {
    if (p >= 85) return '';
    if (p >= 75) return 'lv2';
    if (p >= 65) return 'lv3';
    return 'warn';
  }

  /* Final Score 环形（null → 中心显示 —，不画进度） */
  function ring(score, size, label) {
    var v = num(score);
    var val = v === null ? 0 : Math.max(0, Math.min(100, v));
    var st = size >= 54 ? 5 : 4;
    var r = (size - st) / 2, c = 2 * Math.PI * r, off = c * (1 - val / 100);
    var fs = Math.round(size * (v === null ? 0.28 : (size >= 54 ? 0.30 : 0.33)));
    var txt = v === null ? NA : fmt(v, 1);
    return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '" style="display:block">' +
      '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="#eaedf3" stroke-width="' + st + '"/>' +
      (v === null ? '' :
        '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="' + scoreColor(v) + '" stroke-width="' + st + '" stroke-linecap="round" stroke-dasharray="' + c.toFixed(1) + '" stroke-dashoffset="' + off.toFixed(1) + '" transform="rotate(-90 ' + size / 2 + ' ' + size / 2 + ')"/>') +
      '<text x="50%" y="50%" text-anchor="middle" dy="0.34em" font-size="' + fs + '" font-weight="700" fill="' + (v === null ? '#b6bdc9' : '#14171d') + '" font-family="-apple-system,Segoe UI,Roboto,sans-serif">' + txt + '</text>' +
      '</svg>' + (label ? '<span class="rl">' + label + '</span>' : '');
  }
  /* 子项评分条（按各自满分归一化，如 Fundamental 满分 35） */
  function scoreRow(label, v, max) {
    var n = num(v);
    var p = (n === null || !max) ? 0 : Math.max(0, Math.min(100, n / max * 100));
    return '<div class="brow"><span class="bk">' + label + '</span>' +
      '<span class="bar"><i class="' + barCls(p) + '" style="width:' + p.toFixed(1) + '%"></i></span>' +
      '<span class="bv' + (n === null ? ' na' : '') + '">' + nv(n, 1) + '</span></div>';
  }

  /* =========================================================
     数据规范化：JSON → 内部视图模型
     ========================================================= */
  function normalize(data) {
    DATA = data;
    META = data.meta || {};
    MARKET = data.market || { assets: [], regime: {} };
    OPTIONS = data.options || [];
    REVIEW = data.review || {};
    HISTORY = data.history || [];
    REVIEWS = (REVIEW && Array.isArray(REVIEW.records)) ? REVIEW.records.slice() : [];

    var sc = (META.strategy_params && META.strategy_params.scoring) || {};
    MAX_F = num(sc.fundamental_weight) || 35;
    MAX_T = num(sc.technical_weight) || 25;
    MAX_R = num(sc.risk_weight) || 20;

    var ns = String(META.network_status || '').toLowerCase();
    NET_DOWN = ns.indexOf('unavailable') === 0 || ns.indexOf('error') >= 0;

    STOCKS = (data.stocks || []).map(function (s) {
      var tech = s.technical || {};
      var ohlcv = (s.ohlcv || []).map(function (b) {
        return {
          d: b.date || '', o: num(b.open), h: num(b.high),
          l: num(b.low), c: num(b.close), v: num(b.volume) || 0
        };
      }).filter(function (b) { return b.o !== null && b.h !== null && b.l !== null && b.c !== null; });

      return {
        raw: s,
        t: s.ticker || NA,
        n: s.name || s.ticker || NA,
        bucket: s.bucket === 'Core' ? 'core' : 'obs',
        bucketLabel: s.bucket || NA,
        status: s.status || '',
        px: num(s.price),
        pct: num(s.change_1d),
        prevClose: num(s.prev_close),
        s: {
          final: num(s.final_score), quant: num(s.quant_score), ai: num(s.ai_score),
          fund: num(s.fundamental_score), tech: num(s.technical_score), risk: num(s.risk_liquidity_score)
        },
        f: {
          peTTM: num(s.pe_ttm), peFwd: num(s.pe_forward), pb: num(s.pb), eps: num(s.eps_ttm),
          roe: num(s.roe), revGrowth: num(s.revenue_growth),
          earnGrowth: num(s.earnings_growth), margin: num(s.profit_margin),
          mcap: num(s.market_cap)
        },
        m: {
          rsi: num(tech.rsi), ma20: num(tech.ma20), ma50: num(tech.ma50),
          atr: num(tech.atr_abs), atrPct: num(s.atr_pct),
          k: num(tech.kdj_k), d: num(tech.kdj_d), j: num(tech.kdj_j),
          dif: num(tech.macd), dea: num(tech.macd_signal), hist: num(tech.macd_hist)
        },
        stop: num(s.stop_loss),
        stopMethod: s.stop_method || '',
        regime: s.market_regime || '',
        vix: num(s.vix),
        techStatus: tech.status || (ohlcv.length ? 'ok' : 'unavailable'),
        techReason: tech.reason || '',
        lastBar: tech.last_bar_date || null,
        ohlcv: ohlcv,
        ohlcvStatus: s.ohlcv_status || (ohlcv.length ? 'ok' : 'unavailable'),
        confCount: s.technical_confirmations || '',
        conf: s.technical_confirmation_signals || '',
        eventScore: num(s.event_score),
        bias: num(s.bias),
        adv: num(s.avg_dollar_volume_20d),
        rs: num(s.sector_rs_20d_pct),
        scanDate: s.scan_date || '',
        /* AI 六段：只透传 Scan 已落盘的原始文本，前端不生成、不补充任何文案 */
        ai: normAi(s.ai)
      };
    });

    OPT_BY_TK = {};
    OPTIONS.forEach(function (o) {
      var tk = o.ticker || NA;
      (OPT_BY_TK[tk] = OPT_BY_TK[tk] || []).push(o);
    });
  }

  /* =========================================================
     加载状态 / 错误处理（绝不白屏）
     ========================================================= */
  function setBoot(state, title, detail) {
    var el = $('#boot');
    if (!el) return;
    el.classList.remove('hidden');
    if (state === 'loading') {
      el.className = 'boot';
      el.innerHTML = '<div class="boot-row"><span class="spinner"></span><span>Loading market data…</span></div>';
      return;
    }
    el.className = 'boot err';
    el.innerHTML = '<div class="bt">' + title + '</div>' +
      '<div class="bd">' + detail + '</div>' +
      '<div class="bd" style="margin-top:6px">读取路径：<code>' + DATA_URL + '</code></div>' +
      '<div class="bmsg">详细错误已输出到浏览器 Console（console.error）。</div>';
  }
  function hideBoot() { var el = $('#boot'); if (el) el.classList.add('hidden'); }

  function fail(kind, title, detail, err) {
    console.error('[Dashboard] ' + kind + ' — ' + title, detail || '', err || '');
    setBoot('error', title, detail);
  }

  function boot() {
    setBoot('loading');
    if (typeof window.fetch !== 'function') {
      fail('unavailable', 'Dashboard data unavailable',
        '当前浏览器不支持 fetch，无法读取 JSON。请升级浏览器或改用本地 HTTP 服务打开。');
      return;
    }
    if (window.location && window.location.protocol === 'file:') {
      fail('unavailable', 'Dashboard data unavailable',
        '检测到通过 <code>file://</code> 直接打开，浏览器安全策略会拦截 fetch 读取本地 JSON。' +
        '请在项目根目录启动本地服务，例如 <code>python -m http.server 8000</code>，' +
        '然后访问 <code>http://127.0.0.1:8000/</code>。');
      return;
    }
    window.fetch(dataUrl(), { cache: 'no-store' })
      .then(function (res) {
        if (!res.ok) {
          var e1 = new Error('HTTP ' + res.status + ' ' + res.statusText);
          e1.kind = 'unavailable';
          throw e1;
        }
        return res.text();
      })
      .then(function (text) {
        var d;
        try { d = JSON.parse(text); }
        catch (err) {
          var e2 = new Error('JSON.parse 失败：' + err.message + '（响应长度 ' + text.length + ' 字节）');
          e2.kind = 'invalid';
          throw e2;
        }
        if (!d || typeof d !== 'object' || !Array.isArray(d.stocks)) {
          var e3 = new Error('顶层结构不正确，缺少 stocks 数组（实际 keys: ' + Object.keys(d || {}).join(', ') + '）');
          e3.kind = 'invalid';
          throw e3;
        }
        return d;
      })
      .then(function (d) {
        try { renderDashboard(d); }
        catch (err) {
          console.error('[Dashboard] render failed:', err);
          var e4 = new Error((err && err.message) || String(err));
          e4.kind = 'invalid';
          throw e4;
        }
      })
      .catch(function (err) {
        var kind = err && err.kind || 'unavailable';
        if (kind === 'invalid') {
          fail('invalid', 'Invalid dashboard data',
            'JSON 已取回但无法解析为 Dashboard 数据结构：' + esc(String(err && err.message || err)), err);
        } else {
          fail('unavailable', 'Dashboard data unavailable',
            '无法读取 <code>' + DATA_URL + '</code>：' + esc(String(err && err.message || err)) +
            '。请先运行 <code>python dashboard_export.py</code> 生成该文件，并确认通过 HTTP 打开本页面。', err);
        }
      });
  }

  /* =========================================================
     渲染入口
     ========================================================= */
  function renderDashboard(data) {
    normalize(data);
    hideBoot();

    var core = STOCKS.filter(function (s) { return s.bucket === 'core'; });
    var obs = STOCKS.filter(function (s) { return s.bucket === 'obs'; });

    renderHeader();
    renderGmBar();
    renderPools(core, obs);
    renderGlobal();
    renderReview();
    renderReviewHistory();
    bindReviewHistory();
    renderOptions(OPTIONS, $('#optHomeList'), true);
    renderHistory();
    drawAllSparks();

    console.info('[Dashboard] loaded ' + DATA_URL +
      ' · Core ' + core.length + ' · Observation ' + obs.length +
      ' · Options ' + OPTIONS.length + ' · Market ' + MARKET.assets.length +
      ' · History ' + HISTORY.length + ' · ReviewRecords ' + REVIEWS.length +
      ' · network=' + (META.network_status || 'n/a'));

    window.IT = {
      data: DATA, stocks: STOCKS, market: MARKET, options: OPTIONS,
      review: REVIEW, reviews: REVIEWS, history: HISTORY, reload: boot, open: openDetail
    };
  }

  /* ---------------- 顶部：数据源与更新时间 ---------------- */
  function renderHeader() {
    var tag = $('#dataTag');
    if (tag) {
      tag.className = 'tag tag-real';
      tag.textContent = 'REAL · dashboard_data.json';
      tag.title = '数据源：' + (META.data_source || 'n/a');
    }
    var up = $('#updatedTag');
    if (up) {
      var g = DATA.generated_at || '';
      up.textContent = 'Data updated: ' + (g ? g.replace('T', ' ').replace('Z', ' UTC') : NA);
    }
    var se = $('#sessionTag');
    if (se) se.textContent = META.pending_scan_date ? 'Scan ' + META.pending_scan_date : '—';
    var fi = $('#footInfo');
    if (fi) {
      fi.textContent = 'Data Source: dashboard_data.json' +
        (META.pending_csv ? ' · 源 CSV ' + META.pending_csv : '') +
        ' · 本页不含任何模拟数据';
    }
    var df = $('#dFoot');
    if (df) df.textContent = 'Data Source: dashboard_data.json · 本页不含任何模拟数据';
  }

  /* ---------------- 1. Global Market 状态栏 ---------------- */
  var TOP_KEYS = ['S&P 500', 'Nasdaq', 'Dow Jones', 'VIX', 'US10Y', 'DXY', 'Gold', 'WTI'];
  function assetByName(name) {
    var list = MARKET.assets || [], i;
    for (i = 0; i < list.length; i++) if (list[i].name === name) return list[i];
    return null;
  }
  function assetPriceTxt(a) {
    if (!a) return NA;
    var p = num(a.price);
    if (p === null) return MARKET_NA;
    var d = (a.unit === 'percent yield') ? 3 : 2;
    return fmt(p, d);
  }
  function assetChgTxt(a, key) {
    if (!a) return NA;
    var v = num(a[key]);
    return v === null ? NA : signed(v, 2) + '%';
  }

  function renderGmBar() {
    var rg = MARKET.regime || {};
    var core = STOCKS.filter(function (s) { return s.bucket === 'core'; }).length;
    var obs = STOCKS.filter(function (s) { return s.bucket === 'obs'; }).length;
    var date = META.pending_scan_date || (DATA && DATA.generated_at ? DATA.generated_at.slice(0, 10) : NA);

    var html = '<div class="gm-grid"><div class="gm-cell hero">' +
      '<div class="gm-date">' + date + ' <small>Scan 日期 · 真实数据（非模拟）</small></div>' +
      '<span class="regime"><i></i>' + (rg.market || NA) + '</span>' +
      '<div class="regime-meta">VIX <b>' + nv(rg.vix, 2) + '</b> · Core <b>' + core + '</b> · Observation <b>' + obs +
      '</b> · Options <b>' + OPTIONS.length + '</b></div>' +
      '</div>';

    TOP_KEYS.forEach(function (k) {
      var a = assetByName(k);
      var pTxt = assetPriceTxt(a);
      var cTxt = assetChgTxt(a, 'change_1d');
      var cVal = num(a && a.change_1d);
      html += '<div class="gm-cell" title="' + esc((a && a.symbol) || k) + '">' +
        '<div class="gm-k">' + k + '</div>' +
        '<div class="gm-v' + (naIf(pTxt) ? ' na' : '') + '">' + pTxt + '</div>' +
        '<div class="gm-c ' + (cVal === null ? 'na' : dirCls(cVal)) + '">' + cTxt + '</div></div>';
    });
    html += '</div>';
    $('#gmBar').innerHTML = html;
  }

  /* ---------------- 2/3. Core / Observation 卡片 ---------------- */
  function sparkHtml(s, small) {
    if (s.ohlcv.length > 1) {
      return '<canvas class="spark' + (small ? ' spark-sm' : '') + '" data-spark="' + esc(s.t) + '"></canvas>';
    }
    return '<div class="spark-na' + (small ? ' sm' : '') + '">K线数据暂不可用</div>';
  }

  function coreCard(s) {
    var m = s.m;
    var stopPct = (s.stop !== null && s.px) ? (s.stop / s.px - 1) * 100 : null;
    var devMA20 = (m.ma20 && s.px) ? (s.px / m.ma20 - 1) * 100 : null;

    var bars = scoreRow('Fundamental', s.s.fund, MAX_F) +
      scoreRow('Technical', s.s.tech, MAX_T) +
      scoreRow('Risk', s.s.risk, MAX_R);

    var foot = [
      ['RSI', nv(m.rsi, 1), false],
      ['MA20', tnv(m.ma20, 2), true],
      ['MA50', tnv(m.ma50, 2), true],
      ['ATR%', nv(m.atrPct, 2), false],
      ['STOP', nv(s.stop, 2), false],
      ['距止损', stopPct === null ? NA : fmt(stopPct, 1) + '%', false],
      ['偏离MA20', devMA20 === null ? (NET_DOWN ? TECH_NA : NA) : fmt(devMA20, 1) + '%', true],
      ['MA20/50', (m.ma20 !== null && m.ma50 !== null) ? (m.ma20 >= m.ma50 ? '多头' : '空头') : (NET_DOWN ? TECH_NA : NA), true]
    ].map(function (x) {
      return '<div><div class="fk">' + x[0] + '</div><div class="fv' + (naIf(x[1]) ? ' na' : '') + '">' + x[1] + '</div></div>';
    }).join('');

    return '<article class="pcard" data-tk="' + esc(s.t) + '">' +
      '<div class="p-top">' +
      '<div class="p-id"><div class="p-tk">' + esc(s.t) + '</div><div class="p-nm">' + esc(s.n) + '</div>' +
      '<div class="p-px">' + nv(s.px, 2) + ' <span class="p-ch ' + (s.pct === null ? 'na' : dirCls(s.pct)) + '">' +
      (s.pct === null ? NA : signed(s.pct) + '%') + '</span></div></div>' +
      '<div class="p-ring">' + ring(s.s.final, 54, 'Final') + '</div>' +
      '</div>' +
      '<div class="p-quick">' +
      '<span class="qb">Quant ' + nv(s.s.quant, 1) + '</span>' +
      '<span class="qb">AI ' + nv(s.s.ai, 1) + '</span>' +
      '<span class="qb g">' + esc(s.bucketLabel) + '</span>' +
      '<span class="qb ' + (s.status === 'pending' ? 'dim' : 'ok') + '">' + esc(s.status || NA) + '</span>' +
      '<span class="qb g">' + esc(s.regime || NA) + '</span>' +
      '</div>' +
      sparkHtml(s, false) +
      '<div class="bars">' + bars + '</div>' +
      '<div class="p-foot">' + foot + '</div>' +
      '</article>';
  }

  function obsCard(s) {
    var m = s.m;
    var mini = [['F', s.s.fund, MAX_F], ['T', s.s.tech, MAX_T], ['R', s.s.risk, MAX_R]].map(function (x) {
      var n = num(x[1]);
      var p = (n === null || !x[2]) ? 0 : Math.max(0, Math.min(100, n / x[2] * 100));
      return '<span class="ob">' + x[0] + '<i><b style="width:' + p.toFixed(1) + '%"></b></i>' +
        '<b class="n">' + nv(n, 0) + '</b></span>';
    }).join('');

    var foot = [
      ['RSI', nv(m.rsi, 1)],
      ['MA20', tnv(m.ma20, 2)],
      ['ATR%', nv(m.atrPct, 2)],
      ['STOP', nv(s.stop, 2)]
    ].map(function (x) {
      return '<div><div class="fk">' + x[0] + '</div><div class="fv' + (naIf(x[1]) ? ' na' : '') + '">' + x[1] + '</div></div>';
    }).join('');

    return '<article class="ocard" data-tk="' + esc(s.t) + '">' +
      '<div class="o-top">' +
      '<div class="o-id"><div class="o-tk">' + esc(s.t) + '</div><div class="o-nm">' + esc(s.n) + '</div></div>' +
      '<div class="o-p"><div class="o-px">' + nv(s.px, 2) + '</div>' +
      '<div class="o-ch ' + (s.pct === null ? 'na' : dirCls(s.pct)) + '">' + (s.pct === null ? NA : signed(s.pct) + '%') + '</div></div>' +
      '</div>' +
      sparkHtml(s, true) +
      '<div class="o-mini"><div class="o-bars">' + mini + '</div>' + ring(s.s.final, 34) + '</div>' +
      '<div class="o-foot">' + foot + '</div>' +
      '</article>';
  }

  function renderPools(core, obs) {
    $('#coreList').innerHTML = core.map(coreCard).join('') ||
      '<div class="chart-na">当前 JSON 中没有 Core 标的</div>';
    $('#obsList').innerHTML = obs.map(obsCard).join('') ||
      '<div class="chart-na">当前 JSON 中没有 Observation 标的</div>';
    $('#coreSub').textContent = '核心池 · ' + core.length + ' 只 · 点击卡片查看详情';
    $('#obsSub').textContent = '待升级标的 · ' + obs.length + ' 只';
  }

  /* ---------------- 4. Global Markets ---------------- */
  var GM_GROUPS = [
    { name: '股指与波动', keys: ['index', 'volatility'] },
    { name: '利率与汇率', keys: ['rate', 'fx'] },
    { name: '商品与能源', keys: ['commodity', 'energy'] }
  ];
  function renderGlobal() {
    var assets = MARKET.assets || [];
    var avail = num(MARKET.available_count) || assets.filter(function (a) { return a.available; }).length;

    var notice = $('#gmNotice');
    if (notice) {
      if (NET_DOWN) {
        notice.innerHTML = '<div class="notice"><b>Market data temporarily unavailable</b> · ' +
          'meta.network_status = <b>' + esc(String(META.network_status)) + '</b>' +
          '（' + avail + '/' + assets.length + ' 项有价）。行情恢复后由 dashboard_export.py 重新导出即可自动显示，本页不会用任何数字占位。</div>';
      } else {
        notice.innerHTML = '';
      }
    }
    var sub = $('#gmSub');
    if (sub) sub.textContent = '全球市场 · ' + assets.length + ' 项 · 有价 ' + avail;

    $('#globalWrap').innerHTML = GM_GROUPS.map(function (g) {
      var items = assets.filter(function (a) { return g.keys.indexOf(a.group) >= 0; });
      if (!items.length) return '';
      return '<div class="ggroup"><div class="gg-h">' + g.name + '</div><div class="gg-grid">' +
        items.map(function (a) {
          var pTxt = assetPriceTxt(a);
          var c1 = num(a.change_1d), c5 = num(a.change_5d), c20 = num(a.change_20d);
          var x5 = c5 === null ? '—' : signed(c5, 2) + '%';
          var x20 = c20 === null ? '—' : signed(c20, 2) + '%';
          var upd = a.updated_at ? 'updated ' + a.updated_at : '';
          return '<div class="gcard" title="' + esc(a.symbol + (upd ? ' · ' + upd : '')) + '">' +
            '<div class="gc-top"><span class="gc-k">' + esc(a.name) + '</span>' +
            '<span class="gc-c ' + (c1 === null ? 'na' : dirCls(c1)) + '">' + assetChgTxt(a, 'change_1d') + '</span></div>' +
            '<div class="gc-v' + (naIf(pTxt) ? ' na' : '') + '">' + pTxt + '</div>' +
            '<div class="gc-x">5D ' + x5 + ' · 20D ' + x20 + '</div>' +
            '</div>';
        }).join('') + '</div></div>';
    }).join('');
  }

  /* ---------------- 12. Review ---------------- */
  function reviewTile(label, v, status, unresolved) {
    var st = status || 'unavailable';
    var cls = st === 'complete' ? 'ok' : (st === 'partial' ? 'partial' : 'unavailable');
    var val = num(v);
    return '<div class="rcard">' +
      '<div class="rv' + (val === null ? ' na' : '') + '">' + (val === null ? INSUFF : fmt(val, 0)) + '</div>' +
      '<div class="rk">' + label + '</div>' +
      '<span class="rst ' + cls + '">' + st + '</span>' +
      (unresolved ? '<div class="rk" style="color:var(--warn)">' + unresolved + ' 条未计入</div>' : '') +
      '</div>';
  }
  function renderReview() {
    var r = REVIEW || {};
    $('#revSubHome').textContent = '近 ' + (r.window_days || 30) + ' 天 · as of ' + (r.as_of_us || NA);
    $('#reviewTiles').innerHTML =
      reviewTile('Core Closed', r.core_closed_count, r.core_closed_count_status, r.core_closed_unresolved) +
      reviewTile('Core Open', r.core_open_count, r.core_open_count_status, r.core_open_unresolved) +
      reviewTile('Obs Closed', r.observation_closed_count, r.observation_closed_count_status, r.observation_closed_unresolved) +
      reviewTile('Obs Open', r.observation_open_count, r.observation_open_count_status, r.observation_open_unresolved) +
      reviewTile('Actual Active', r.actual_active_count, r.actual_active_count_status, r.actual_active_unresolved) +
      reviewTile('Stop Loss 触发', r.stop_loss_hit_count, 'complete', 0) +
      reviewTile('Core 胜率', r.core_closed_win_rate === null ? null : r.core_closed_win_rate, r.core_closed_win_rate === null ? 'unavailable' : 'complete', 0) +
      reviewTile('Active Options', r.active_options_count, 'complete', 0);

    var notes = [];
    (r.notes || []).forEach(function (n) { if (notes.indexOf(n) < 0) notes.push(n); });
    (META.notes || []).forEach(function (n) { if (notes.indexOf(n) < 0) notes.push(n); });
    var miss = [];
    (r.missing_fields || []).forEach(function (n) { if (miss.indexOf(n) < 0) miss.push(n); });
    (META.missing_fields || []).forEach(function (n) { if (miss.indexOf(n) < 0) miss.push(n); });

    var html = notes.map(function (n) { return '<div class="note">' + esc(n) + '</div>'; }).join('');
    if (miss.length) {
      html += '<div class="note warn"><b>标记为 partial / unavailable 的字段：</b>' + miss.map(esc).join('；') +
        '。partial 表示统计不完整，不等同于完整口径。</div>';
    }
    html += '<div class="note">统计口径与 review.py 保持一致（近 ' + (r.window_days || 30) +
      ' 天，Closed 需命中 CLOSED_STOCK_STATUSES 且能取到 PnL）。价格来源：' + esc(r.price_source || NA) + '</div>';
    $('#reviewNotes').innerHTML = html;
  }

  /* ---------------- 12b. Review 历史推荐明细（review.records[]） ----------------
     只读 dashboard_data.json 的 review.records[]：
     - 不在前端重算 PnL / Days Held（后端已给出真实值）
     - 不读 CSV、不调用任何 API、0 次 GPT
     - 不显示任何 AI 文本（AI Snapshot 阶段另行处理）
     - null 一律显示 N/A，绝不补 0
  */
  var REV_PAGE = 20;                        /* 每次「加载更多」的增量 */
  var RNA = 'N/A';
  var revFilter = 'all', revQuery = '', revShown = REV_PAGE, revExp = {}, revAiExp = {};

  /* 与 dashboard_export.py CLOSED_STOCK_STATUSES 保持一致（仅用于筛选，不产生新口径） */
  var REV_CLOSED = {
    'Stop_Loss_Hit': 1, 'Dropped': 1, 'Period_Matured': 1, 'Forced_Exit': 1,
    'Observation_Closed': 1,
    '移动止损清仓': 1, '止损触发清仓': 1, '已超期归档': 1,
    '周期到期清仓': 1, '突发清仓暂停': 1
  };

  function recMoney(v) { var n = num(v); return n === null ? RNA : '$' + fmt(n, 2); }
  function recPnl(v) {
    var n = num(v);
    return n === null ? RNA : (n > 0 ? '+' : '') + fmt(n, 2) + '%';
  }
  function recScore(v) {
    if (v === null || v === undefined) return RNA;
    var s = String(v).trim();
    if (!s || s === 'N/A' || s.toLowerCase() === 'nan') return RNA;
    var n = Number(s);
    if (!isFinite(n)) return esc(s);
    return fmt(n, Math.abs(n % 1) < 1e-9 ? 0 : 1);
  }
  function recDays(v) { var n = num(v); return n === null ? RNA : fmt(n, 0) + ' 天'; }
  function recTxt(v) { return (v === null || v === undefined || v === '') ? RNA : String(v); }

  function recTagLabel(t) {
    if (t === 'Core_Dragon') return 'Core';
    if (t === 'Trap_Warning') return 'Trap';
    return t || RNA;
  }
  function recTagCls(t) {
    if (t === 'Core_Dragon') return 't-core';
    if (t === 'Observation') return 't-obs';
    if (t === 'Trap_Warning') return 't-trap';
    return 't-other';
  }
  function recStatusCls(s) {
    if (!s) return 's-na';
    if (s === '持仓中' || s === '观察推荐' || s === 'Active' || s === 'pending') return 's-open';
    if (s === '止损触发清仓' || s === '移动止损清仓' || s === 'Stop_Loss_Hit') return 's-stop';
    if (REV_CLOSED[s]) return 's-closed';
    return 's-other';
  }
  function recIsClosed(r) { return !!(r.status && REV_CLOSED[r.status]); }
  function recIsCore(r) { return String(r.tag || '').indexOf('Core') === 0; }

  function recMatch(r) {
    if (revFilter === 'core' && !recIsCore(r)) return false;
    if (revFilter === 'observation' && r.tag !== 'Observation') return false;
    if (revFilter === 'closed' && !recIsClosed(r)) return false;
    if (revFilter === 'open' && recIsClosed(r)) return false;
    if (revQuery) {
      var hay = String(r.ticker || '') + ' ' + String(r.name || '');
      if (hay.toLowerCase().indexOf(revQuery.toLowerCase()) < 0) return false;
    }
    return true;
  }

  /* 单个 label/value 单元；raw 为空 → 加 na 样式（灰） */
  function gi(k, v, raw, cls) {
    var na = (raw === null || raw === undefined || raw === '' || v === RNA);
    return '<div class="gi"><span class="k">' + k + '</span><span class="v' +
      (na ? ' na' : '') + (cls && !na ? ' ' + cls : '') + '">' + v + '</span></div>';
  }

  /* ---- Review Milestone（review.records[].price_5d / pnl_5d / ... / review_stage，只透传不重算） ----
     后端 review.py 已按 OHLCV 交易日历算出 5D/10D/20D 客观收盘价与 PnL、Review_Stage；
     dashboard_export.py 只透传 review_history.csv 原值。前端只读，绝不重算、绝不推算日期。
     null 一律显示 N/A，绝不补 0 / 当前收益 / 最近价。 */
  function recMsItem(label, price, pnl) {
    var p = num(price);
    var pnlN = num(pnl);
    var pnlCls = pnlN === null ? '' : dirCls(pnlN);
    return '<div class="rh-ms-item">' +
      '<div class="rh-ms-label">' + label + '</div>' +
      '<div class="rh-ms-price' + (p === null ? ' na' : '') + '">' + recMoney(price) + '</div>' +
      '<div class="rh-ms-pnl ' + (pnlCls || 'na') + '">' + recPnl(pnl) + '</div>' +
    '</div>';
  }
  function recStageCls(s) {
    if (s === null || s === undefined || s === '') return 'stg-na';
    var u = String(s).toUpperCase();
    if (u === 'FINAL') return 'stg-final';
    if (u === 'OPEN') return 'stg-open';
    if (u === '5D' || u === '10D' || u === '20D') return 'stg-ms';
    return 'stg-other';
  }
  function recMsHtml(r) {
    return '<div class="rh-ms">' +
      '<div class="rh-ms-head">' +
        '<span class="rh-ms-title">Review Progress</span>' +
        '<span class="rh-ms-stage ' + recStageCls(r.review_stage) + '">' + esc(recTxt(r.review_stage)) + '</span>' +
      '</div>' +
      '<div class="rh-ms-grid">' +
        recMsItem('5D', r.price_5d, r.pnl_5d) +
        recMsItem('10D', r.price_10d, r.pnl_10d) +
        recMsItem('20D', r.price_20d, r.pnl_20d) +
      '</div>' +
    '</div>';
  }

  /* ---- AI Snapshot（review.records[].ai_snapshot，仅精确匹配，绝不回退 stocks[].ai / CSV） ----
     后端已按 (Ticker, Rec_Date, Tag) 精确匹配；前端只读 record.ai_snapshot，
     不建立任何 Ticker→AI 映射、不读 ai_snapshot.csv / ai_text_cache.csv、不调用 GPT。 */
  function recAiPara(v) { return v ? esc(v) : '<span class="na">' + RNA + '</span>'; }
  function recAiList(v) {
    if (!v) return '<li class="na">' + RNA + '</li>';
    var parts = String(v).split(/；|;|\|/).map(function (x) { return x.trim(); }).filter(Boolean);
    if (!parts.length) parts = [String(v)];
    return parts.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('');
  }

  function recAiHtml(r) {
    var snap = r.ai_snapshot;
    var id = r.event_id || '';
    var aiOpen = !!revAiExp[id];
    var none = '<div class="rh-ai rh-ai-none">' +
      '<div class="rh-ai-title">AI 分析 Snapshot</div>' +
      '<div class="rh-ai-na">AI Snapshot 尚未建立</div></div>';

    if (!snap || typeof snap !== 'object') return none;

    var n = normAi(snap);
    var hasAny = !!(n.chain || n.news || n.conclusion || n.catalysts || n.risks || n.invalidation);
    if (!hasAny) return none;

    var meta = [r.rec_date, r.tag].filter(function (x) { return x; }).join(' · ');
    var body =
      '<div class="rh-ai-block"><div class="rh-ai-k">产业链逻辑</div><p class="rh-ai-p">' + recAiPara(n.chain) + '</p></div>' +
      '<div class="rh-ai-block"><div class="rh-ai-k">新闻核查</div><p class="rh-ai-p">' + recAiPara(n.news) + '</p></div>' +
      '<div class="rh-ai-block"><div class="rh-ai-k">盘前结论</div><p class="rh-ai-p">' + recAiPara(n.conclusion) + '</p></div>' +
      '<div class="rh-ai-block"><div class="rh-ai-k">催化剂</div><ul class="rh-ai-ul">' + recAiList(n.catalysts) + '</ul></div>' +
      '<div class="rh-ai-block"><div class="rh-ai-k">风险</div><ul class="rh-ai-ul">' + recAiList(n.risks) + '</ul></div>' +
      '<div class="rh-ai-block"><div class="rh-ai-k">失效条件</div><p class="rh-ai-p">' + recAiPara(n.invalidation) + '</p></div>';

    return '<div class="rh-ai' + (aiOpen ? ' ai-open' : '') + '">' +
      '<button type="button" class="rh-ai-head">' +
        '<span class="rh-ai-title">AI 分析 Snapshot</span>' +
        '<span class="rh-ai-meta">' + esc(meta || RNA) + '</span>' +
        '<span class="rh-ai-arrow">' + (aiOpen ? '▲' : '▼') + '</span>' +
      '</button>' +
      '<div class="rh-ai-body">' + body + '</div>' +
    '</div>';
  }

  function recCard(r) {
    var id = r.event_id || '';
    var pnl = num(r.pnl_pct);
    var pnlCls = pnl === null ? '' : dirCls(pnl);
    var open = !!revExp[id];
    return '<div class="rh-card' + (open ? ' open' : '') + '" data-id="' + esc(id) + '">' +
      '<div class="rh-top">' +
        '<div class="rh-id"><div class="rh-tk">' + esc(r.ticker || RNA) + '</div>' +
          '<div class="rh-nm" title="' + esc(r.name || '') + '">' + esc(r.name || r.ticker || RNA) + '</div></div>' +
        '<div class="rh-right">' +
          '<span class="rh-tag ' + recTagCls(r.tag) + '">' + esc(recTagLabel(r.tag)) + '</span>' +
          '<div class="rh-pnl ' + (pnlCls || 'na') + '">' + recPnl(r.pnl_pct) + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="rh-meta"><span class="rh-date">' + esc(r.rec_date || RNA) + '</span>' +
        '<span class="rh-days">持有 ' + recDays(r.days_held) + '</span></div>' +
      '<div class="rh-g">' +
        gi('推荐价', recMoney(r.rec_price), r.rec_price) +
        gi('当前价', recMoney(r.cur_price), r.cur_price) +
        gi('当前收益', recPnl(r.pnl_pct), r.pnl_pct, pnlCls) +
        gi('止损', recMoney(r.stop_loss), r.stop_loss) +
        gi('评分', recScore(r.score), r.score) +
      '</div>' +
      recMsHtml(r) +
      '<div class="rh-st ' + recStatusCls(r.status) + '">状态：' + esc(recTxt(r.status)) + '</div>' +
      '<div class="rh-hint">点击展开详情</div>' +
      '<div class="rh-det"><div class="rh-g">' +
        gi('Event ID', esc(id), id) +
        gi('Ticker', esc(r.ticker || RNA), r.ticker) +
        gi('推荐日期', esc(r.rec_date || RNA), r.rec_date) +
        gi('Tag', esc(r.tag || RNA), r.tag) +
        gi('Status', esc(recTxt(r.status)), r.status) +
        gi('推荐价', recMoney(r.rec_price), r.rec_price) +
        gi('当前价', recMoney(r.cur_price), r.cur_price) +
        gi('PnL', recPnl(r.pnl_pct), r.pnl_pct, pnlCls) +
        gi('持有天数', recDays(r.days_held), r.days_held) +
        gi('止损', recMoney(r.stop_loss), r.stop_loss) +
        gi('评分', recScore(r.score), r.score) +
      '</div>' +
      recAiHtml(r) +
      '</div>' +
    '</div>';
  }

  var REV_FILTER_TXT = { all: '全部', core: 'Core', observation: 'Observation', closed: '已结束', open: '进行中' };

  function renderReviewHistory() {
    var listEl = $('#revHistList');
    if (!listEl) return;
    var all = REVIEWS || [];

    if (!all.length) {
      var s0 = $('#revHistSub');
      if (s0) s0.textContent = 'review.records[] · 暂无数据';
      listEl.innerHTML = '<div class="chart-na">当前 dashboard_data.json 尚无 review.records[]。' +
        '该字段由 dashboard_export.py 导出；此处不伪造、不用其它数据顶替。</div>';
      var m0 = $('#revHistMore'); if (m0) m0.hidden = true;
      var c0 = $('#revHistCount'); if (c0) c0.textContent = '';
      return;
    }

    var rows = all.filter(recMatch);
    var total = rows.length;
    var show = rows.slice(0, Math.max(REV_PAGE, revShown));

    var html = '', lastDate = '';
    show.forEach(function (r) {
      var d = String(r.rec_date || '');
      if (d !== lastDate) {
        lastDate = d;
        html += '<div class="rh-dayhead">' + esc(d || RNA) + '</div>';
      }
      html += recCard(r);
    });
    listEl.innerHTML = html;

    var more = $('#revHistMore');
    if (more) {
      if (total > show.length) {
        more.hidden = false;
        more.textContent = '加载更多（+' + Math.min(REV_PAGE, total - show.length) + '）';
      } else {
        more.hidden = true;
      }
    }
    var cnt = $('#revHistCount');
    if (cnt) {
      cnt.textContent = '显示 ' + show.length + ' / ' + total + ' 条' +
        (total !== all.length ? '（全部 ' + all.length + ' 条）' : '') +
        (revFilter !== 'all' ? ' · 筛选：' + REV_FILTER_TXT[revFilter] : '') +
        (revQuery ? ' · 搜索：' + revQuery : '');
    }
    var sub = $('#revHistSub');
    if (sub) {
      sub.textContent = 'review.records[] · 共 ' + all.length + ' 条 · 最新 ' + (all[0] && all[0].rec_date || NA);
    }
  }

  function closestByClass(node, cls, root) {
    while (node && node !== root) {
      if (node.classList && node.classList.contains(cls)) return node;
      node = node.parentNode;
    }
    return null;
  }

  var revBound = false;
  function bindReviewHistory() {
    if (revBound) return;
    var chips = $('#revHistChips'), list = $('#revHistList'),
        more = $('#revHistMore'), search = $('#revHistSearch');
    if (!chips || !list || !more || !search) return;

    chips.addEventListener('click', function (e) {
      var b = closestByClass(e.target, 'chip', chips);
      if (!b) return;
      var f = b.getAttribute('data-f') || 'all';
      if (f === revFilter) return;
      revFilter = f;
      revShown = REV_PAGE;
      Array.prototype.forEach.call(chips.querySelectorAll('.chip'), function (x) {
        if (x.getAttribute('data-f') === f) x.classList.add('on'); else x.classList.remove('on');
      });
      renderReviewHistory();
    });

    search.addEventListener('input', function () {
      revQuery = String(search.value || '').trim();
      revShown = REV_PAGE;
      renderReviewHistory();
    });

    more.addEventListener('click', function () {
      revShown += REV_PAGE;
      renderReviewHistory();
    });

    /* 展开 / 收起详情：纯前端交互，不请求任何接口、不调用 GPT */
    list.addEventListener('click', function (e) {
      /* AI Snapshot 六段的折叠开关：独立于卡片整体展开，点击不联动收起卡片 */
      var aiHead = closestByClass(e.target, 'rh-ai-head', list);
      if (aiHead) {
        var aiCard = closestByClass(aiHead, 'rh-card', list);
        var aiId = aiCard ? aiCard.getAttribute('data-id') || '' : '';
        if (aiId) { if (revAiExp[aiId]) delete revAiExp[aiId]; else revAiExp[aiId] = 1; }
        var aiWrap = aiHead.parentNode;
        var aiOpen = !!revAiExp[aiId];
        if (aiWrap && aiWrap.classList) aiWrap.classList.toggle('ai-open', aiOpen);
        var aiArrow = aiHead.querySelector('.rh-ai-arrow');
        if (aiArrow) aiArrow.textContent = aiOpen ? '▲' : '▼';
        return;
      }
      var card = closestByClass(e.target, 'rh-card', list);
      if (!card) return;
      var id = card.getAttribute('data-id') || '';
      if (revExp[id]) delete revExp[id]; else revExp[id] = 1;
      card.classList.toggle('open', !!revExp[id]);
    });

    revBound = true;
  }

  /* ---------------- Options ---------------- */
  var STRAT_TXT = {
    'CALL_DEBIT_SPREAD': 'CALL Debit Spread',
    'LONG_CALL': 'LONG CALL',
    'SHORT_PUT': 'SHORT PUT'
  };
  function dirTxt(d) {
    if (!d) return NA;
    return String(d).charAt(0).toUpperCase() + String(d).slice(1).toLowerCase();
  }
  function optCard(o) {
    var strat = STRAT_TXT[o.strategy] || o.strategy || NA;
    var longK = num(o.long_strike), shortK = num(o.short_strike), k = num(o.strike);
    var strikeTxt = (longK !== null && shortK !== null && longK !== shortK)
      ? fmt(longK, 0) + ' / ' + fmt(shortK, 0)
      : nv(k, 0);

    var trueOi = o.wall_is_true_oi === true;
    var wallBadge = trueOi
      ? '<span class="wb true">真实 OI Wall</span>'
      : ((o.call_wall_unavailable || o.put_wall_unavailable)
          ? '<span class="wb false">N/A · 期权链无有效 OI</span>'
          : '<span class="wb false">Proxy / Invalid Wall</span>');

    return '<div class="opt">' +
      '<div class="opt-h"><span class="opt-type">' + esc((o.ticker || NA) + ' · ' + strat) + '</span>' +
      '<span class="opt-dir ' + (String(o.direction || '').toLowerCase() === 'bullish' ? '' : 'neutral') + '">' +
      dirTxt(o.direction) + '</span></div>' +
      '<div class="opt-m">' +
      cell('Strike', strikeTxt) +
      cell('Expiry', o.expiry || NA) +
      cell('DTE', nv(o.dte, 0)) +
      cell('Premium', usdTxt(o.premium)) +
      cell('Delta', nv(o.delta, 3)) +
      cell('IV', pctTxt(o.iv, 1)) +
      cell('Break Even', usdTxt(o.break_even)) +
      cell('Max Loss', usdTxt(o.max_loss), 'down') +
      cell('Max Profit', usdTxt(o.max_profit), 'up') +
      '</div>' +
      '<div class="opt-wall">' +
      '<div class="wl">' + wallBadge +
      '<span class="wnote">wall_source: <b>' + esc(o.wall_source || NA) + '</b></span></div>' +
      '<div class="wl"><span class="wnote">Call Wall <b>' + wallVal(o.call_wall, o.call_wall_unavailable) + '</b> · Put Wall <b>' + wallVal(o.put_wall, o.put_wall_unavailable) + '</b>' +
      ' · OI <b>' + wallVal(o.call_wall_oi, o.call_wall_unavailable, 0) + ' / ' + wallVal(o.put_wall_oi, o.put_wall_unavailable, 0) + '</b></span></div>' +
      (o.wall_note ? '<div class="wnote">' + esc(o.wall_note) + '</div>' : '') +
      '</div>' +
      '<div class="opt-wall">' +
      '<div class="wl"><span class="wnote">Status <b>' + esc(o.status || NA) + '</b> · Qty <b>' + nv(o.quantity, 0) +
      '</b> · 标的价 <b>' + usdTxt(o.underlying_price) + '</b> · Entry <b>' + esc(o.entry_date || NA) + '</b></span></div>' +
      (o.iv_regime ? '<div class="wnote">IV 分位：<b>' + esc(o.iv_regime) + '</b></div>' : '') +
      (o.reason ? '<div class="wnote">' + esc(o.reason) + '</div>' : '') +
      '</div></div>';
  }
  function renderOptions(list, el, isHome) {
    if (!el) return;
    if (!list || !list.length) {
      el.innerHTML = '<div class="chart-na">' +
        (isHome ? 'option_strategies.csv 中暂无期权策略记录' : '该标的当前无 option_strategies.csv 记录') + '</div>';
      return;
    }
    el.innerHTML = list.map(optCard).join('');
    if (isHome) {
      $('#optSubHome').textContent = '来自 option_strategies.csv · ' + list.length + ' 条';
    }
  }

  /* ---------------- History ---------------- */
  function renderHistory() {
    var el = $('#histList');
    if (!el) return;
    if (!HISTORY.length) {
      el.innerHTML = '<div class="chart-na">history 为空：现有 CSV 不足以生成历史序列（不伪造）</div>';
      return;
    }
    var rows = HISTORY.slice().sort(function (a, b) { return String(a.date) < String(b.date) ? 1 : -1; });
    var show = rows.slice(0, 12);
    var maxC = 1;
    rows.forEach(function (h) { maxC = Math.max(maxC, num(h.core_count) || 0); });

    var html = '<div class="hist"><div class="hrow head"><span class="hd">Date</span>' +
      '<span class="hn">Core</span><span class="hn">Obs</span></div>' +
      show.map(function (h) {
        var c = num(h.core_count), o = num(h.observation_count);
        var w = (c === null ? 0 : Math.max(2, c / maxC * 100));
        return '<div class="hrow"><span class="hd">' + esc(h.date) + '</span>' +
          '<span class="hn' + (c === null ? ' na' : '') + '">' + nv(c, 0) + '</span>' +
          '<span class="hn' + (o === null ? ' na' : '') + '">' + nv(o, 0) + '</span>' +
          '<span class="hbar"><i style="width:' + w.toFixed(1) + '%"></i></span></div>';
      }).join('') + '</div>';
    html += '<div class="wnote" style="margin-top:7px">共 ' + rows.length + ' 条 · 显示最近 ' + show.length +
      ' 条 · 口径：当日仍在跟踪的去重推荐事件数（Ticker + Rec_Date），非当日新增数。</div>';
    el.innerHTML = html;
    $('#histSub').textContent = 'review_history.csv · ' + rows.length + ' 个交易日快照';
  }

  /* =========================================================
     详情页
     ========================================================= */
  var RANGES = [{ k: '1M', n: 21 }, { k: '3M', n: 63 }, { k: '6M', n: 126 }, { k: '1Y', n: 252 }];
  function slice(a, n) { return a.slice(Math.max(0, a.length - n)); }
  function mx(k, v, cls) { return cell(k, v, cls); }

  function indTile(id, title, value, status, statusCls, hasSeries) {
    return '<div class="ind"><div class="ind-h">' +
      '<span class="ind-t">' + title + '</span>' +
      '<span class="ind-r"><span class="ind-v' + (naIf(value) ? ' na' : '') + '">' + value + '</span>' +
      '<span class="ind-s ' + (statusCls || '') + '">' + status + '</span></span></div>' +
      (hasSeries ? '<canvas id="' + id + '" style="height:62px"></canvas>' : '') +
      '</div>';
  }

  function openDetail(tk) {
    var s = null, i;
    for (i = 0; i < STOCKS.length; i++) if (STOCKS[i].t === tk) s = STOCKS[i];
    if (!s) return;
    cur = s;
    var m = s.m;

    /* 头部 */
    $('#dTicker').textContent = s.t;
    $('#dName').textContent = s.n;
    $('#dPrice').textContent = nv(s.px, 2);
    var ce = $('#dChange');
    ce.textContent = s.pct === null ? NA : signed(s.pct) + '%';
    ce.className = 'db-ch ' + (s.pct === null ? 'na' : dirCls(s.pct));
    $('#dRing').innerHTML = ring(s.s.final, 44, 'Final');
    $('#dBadges').innerHTML =
      '<span class="qb">Quant ' + nv(s.s.quant, 1) + '</span>' +
      '<span class="qb">AI ' + nv(s.s.ai, 1) + '</span>' +
      '<span class="qb g">' + esc(s.bucketLabel) + '</span>' +
      '<span class="qb ' + (s.status === 'pending' ? 'dim' : 'ok') + '">' + esc(s.status || NA) + '</span>' +
      '<span class="qb g">' + esc(s.regime || NA) + '</span>';

    /* K 线区：无 ohlcv 一律不画假图 */
    var hasBars = s.ohlcv.length > 1;
    $('#rangeChips').innerHTML = hasBars ? RANGES.map(function (r) {
      return '<button class="chip' + (r.n === curRange ? ' on' : '') + '" data-n="' + r.n + '">' + r.k + '</button>';
    }).join('') : '';
    $('#chartPriceWrap').innerHTML = hasBars
      ? '<canvas id="chartPrice" style="height:320px"></canvas>'
      : '<div class="chart-na">K线数据暂不可用<br><span style="font-size:11px">ohlcv_status = ' +
      esc(s.ohlcvStatus) + (s.techReason ? ' · ' + esc(s.techReason) : '') + '</span></div>';
    var volWrap = $('#chartVolWrap');
    if (volWrap) volWrap.classList.toggle('hidden', !hasBars);
    $('#legendPrice').innerHTML =
      '<span><i style="background:#f0a020"></i>MA20 ' + tnv(m.ma20, 2) + '</span>' +
      '<span><i style="background:#7b5cf0"></i>MA50 ' + tnv(m.ma50, 2) + '</span>' +
      (hasBars ? '<span><i style="background:#d6372c"></i>涨</span><span><i style="background:#0f9d58"></i>跌</span>' : '');

    /* 8. 指标矩阵（值全部来自 JSON，不自行计算） */
    function cmpStatus(a, b, upTxt, downTxt) {
      if (a === null || b === null) return { t: NET_DOWN ? TECH_NA : NA, c: '' };
      return a >= b ? { t: upTxt, c: 'up' } : { t: downTxt, c: 'down' };
    }
    var stMa20 = cmpStatus(s.px, m.ma20, '价格在上方', '价格在下方');
    var stMa50 = cmpStatus(s.px, m.ma50, '价格在上方', '价格在下方');
    var stMacd = cmpStatus(m.dif, m.dea, '金叉 · 多头', '死叉 · 空头');
    var stKdj = cmpStatus(m.k, m.d, 'K 在 D 上方', 'K 在 D 下方');
    var rsiSt = m.rsi === null ? { t: NA, c: '' } :
      (m.rsi >= 70 ? { t: '超买', c: 'up' } : (m.rsi <= 30 ? { t: '超卖', c: 'down' } : { t: '中性', c: '' }));

    $('#indGrid').innerHTML =
      indTile('cMa20', 'MA20', tnv(m.ma20, 2), stMa20.t, stMa20.c, false) +
      indTile('cMa50', 'MA50', tnv(m.ma50, 2), stMa50.t, stMa50.c, false) +
      indTile('cRsi', 'RSI (14)', nv(m.rsi, 1), rsiSt.t, rsiSt.c, false) +
      indTile('cMacd', 'MACD', tnv(m.dif, 2), stMacd.t, stMacd.c, false) +
      indTile('cKdj', 'KDJ', (m.k === null || m.d === null) ? tnv(null, 1) : (fmt(m.k, 1) + ' / ' + fmt(m.d, 1)),
        stKdj.t, stKdj.c, false) +
      indTile('cAtr', 'ATR (14)', tnv(m.atr, 2), m.atrPct === null ? (NET_DOWN ? TECH_NA : NA) : nv(m.atrPct, 2) + '% 波动', '', false);
    if (NET_DOWN) {
      $('#indGrid').innerHTML += '<div class="notice" style="grid-column:1 / -1;margin:0">' +
        '技术指标（MA20 / MA50 / KDJ / MACD / ATR）因行情网络不可用未写入 JSON，本页不做任何本地计算或补值。</div>';
    }

    /* 评分 */
    $('#scoreRing').innerHTML = ring(s.s.final, 74, 'Final');
    $('#scoreSub').textContent = 'Final / Quant / AI 满分 100 · F ' + MAX_F + ' / T ' + MAX_T + ' / R ' + MAX_R;
    $('#scoreBars').innerHTML =
      scoreRow('Final Score', s.s.final, 100) +
      scoreRow('Quant Score', s.s.quant, 100) +
      scoreRow('AI Score', s.s.ai, 100) +
      scoreRow('Fundamental', s.s.fund, MAX_F) +
      scoreRow('Technical', s.s.tech, MAX_T) +
      scoreRow('Risk', s.s.risk, MAX_R);

    /* 9. 基本面矩阵（全部来自 pending CSV） */
    $('#fundSub').textContent = 'Mkt Cap ' + capTxt(s.f.mcap) + ' · ' + s.n;
    $('#fundMatrix').innerHTML =
      mx('PE TTM', nv(s.f.peTTM, 2)) +
      mx('PE Forward', nv(s.f.peFwd, 2)) +
      mx('PB', nv(s.f.pb, 2)) +
      mx('EPS', nv(s.f.eps, 2)) +
      mx('Revenue Growth', pctTxt(s.f.revGrowth), pctCls(num(s.f.revGrowth) || 0)) +
      mx('Earnings Growth', pctTxt(s.f.earnGrowth), pctCls(num(s.f.earnGrowth) || 0)) +
      mx('ROE', pctTxt(s.f.roe)) +
      mx('Profit Margin', pctTxt(s.f.margin)) +
      mx('Market Cap', capTxt(s.f.mcap)) +
      mx('Status', esc(s.status || NA)) +
      mx('Market Regime', esc(s.regime || NA)) +
      mx('VIX', nv(s.vix, 2)) +
      mx('RSI', nv(m.rsi, 1)) +
      mx('ATR %', nv(m.atrPct, 2)) +
      mx('MA20', tnv(m.ma20, 2)) +
      mx('MA50', tnv(m.ma50, 2)) +
      mx('技术确认', (s.confCount === '' || s.confCount === null) ? NA : String(s.confCount)) +
      mx('Event Score', nv(s.eventScore, 1)) +
      mx('Bias', nv(s.bias, 2)) +
      mx('20D 成交额', s.adv === null ? NA : capTxt(s.adv)) +
      mx('Sector RS 20D', nv(s.rs, 2)) +
      mx('Scan Date', esc(s.scanDate || NA));

    /* 10. AI：只渲染 Scan 已落盘的六段文本；未落盘一律 pending，前端不调用 GPT、不生成替代文案 */
    $('#aiScoreTxt').textContent = nv(s.s.ai, 1);

    var ai = s.ai || {};
    var aiAny = !!(ai.chain || ai.news || ai.conclusion || ai.catalysts || ai.risks || ai.invalidation);
    var pendList = (META.ai_fields_pending || []).slice();

    function aiPara(v) {
      return v ? esc(v) : '<span class="na">' + AI_EMPTY + '</span>';
    }
    function aiList(v) {
      if (!v) return '<li class="na">' + AI_EMPTY + '</li>';
      var parts = v.split(/；|;|\|/).map(function (x) { return x.trim(); }).filter(Boolean);
      if (!parts.length) parts = [v];
      return parts.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('');
    }

    if (!aiAny) {
      $('#aiPendingNotice').innerHTML = '<div class="notice"><b>' + AI_PENDING + '</b> · ' +
        '本页不调用 GPT，也不生成任何替代文案；AI 六段文本在 Scan 落盘后会自动显示。' +
        (pendList.length ? '待补字段：' + pendList.map(esc).join('、') + '。' : '') + '</div>';
      ['#aiChain', '#aiNews', '#aiConclusion', '#aiInvalid'].forEach(function (id) {
        var e = $(id); if (e) e.innerHTML = '<span class="na">' + AI_PENDING + '</span>';
      });
      $('#aiCatalysts').innerHTML = '<li class="na">' + AI_PENDING + '</li>';
      $('#aiRisks').innerHTML = '<li class="na">' + AI_PENDING + '</li>';
      if ($('#aiGrid')) $('#aiGrid').style.display = '';
      if ($('#aiObsSummary')) $('#aiObsSummary').style.display = 'none';
    } else if (s.bucket === 'obs') {
      /* Observation 观察池：极简模式——隐藏六段网格，只保留一句话总结
         （优先取盘前结论，其次产业链逻辑），不渲染其余字段 */
      var oneLiner = ai.conclusion || ai.chain || ai.news || '';
      $('#aiPendingNotice').innerHTML = '<div class="notice ok"><b>AI 分析已就绪</b> · ' +
        '观察池极简模式 · 来源：Scan ' + esc(META.ai_generated_at || s.scanDate || NA) +
        ' 已落盘文本 · 本页 0 次 GPT 调用</div>';
      $('#aiGrid').style.display = 'none';
      $('#aiObsSummary').style.display = '';
      $('#aiObsSummary').innerHTML = oneLiner
        ? esc(oneLiner)
        : '<span class="na">' + AI_EMPTY + '</span>';
    } else {
      /* Core：完整渲染六段 */
      if ($('#aiObsSummary')) $('#aiObsSummary').style.display = 'none';
      $('#aiGrid').style.display = '';
      $('#aiPendingNotice').innerHTML = '<div class="notice ok"><b>AI 分析已就绪</b> · ' +
        '来源：Scan ' + esc(META.ai_generated_at || s.scanDate || NA) + ' 已落盘的六段文本 · 本页 0 次 GPT 调用</div>';
      $('#aiChain').innerHTML = aiPara(ai.chain);
      $('#aiNews').innerHTML = aiPara(ai.news);
      $('#aiConclusion').innerHTML = aiPara(ai.conclusion);
      $('#aiCatalysts').innerHTML = aiList(ai.catalysts);
      $('#aiRisks').innerHTML = aiList(ai.risks);
      $('#aiInvalid').innerHTML = aiPara(ai.invalidation);
    }

    /* 11. Options（该标的自己的策略） */
    var mine = OPT_BY_TK[s.t] || [];
    $('#optSub').textContent = mine.length ? mine.length + ' 条 · option_strategies.csv' : '无记录';
    renderOptions(mine, $('#optList'), false);

    /* 12. Review（真实字段） */
    $('#revSub').textContent = s.bucketLabel + ' · ' + (s.status || NA);
    var stopPct = (s.stop !== null && s.px) ? (s.stop / s.px - 1) * 100 : null;
    $('#posMatrix').innerHTML =
      mx('Bucket', esc(s.bucketLabel)) +
      mx('Status', esc(s.status || NA)) +
      mx('Price', nv(s.px, 2)) +
      mx('Prev Close', nv(s.prevClose, 2)) +
      mx('Change 1D', s.pct === null ? NA : signed(s.pct) + '%', s.pct === null ? '' : dirCls(s.pct)) +
      mx('止损价', nv(s.stop, 2)) +
      mx('距止损', stopPct === null ? NA : fmt(stopPct, 1) + '%', 'down') +
      mx('止损方式', esc(s.stopMethod || NA)) +
      mx('RSI', nv(m.rsi, 1)) +
      mx('ATR %', nv(m.atrPct, 2)) +
      mx('Market Regime', esc(s.regime || NA)) +
      mx('VIX', nv(s.vix, 2)) +
      mx('Event Score', nv(s.eventScore, 1)) +
      mx('Bias', nv(s.bias, 2)) +
      mx('20D 成交额', s.adv === null ? NA : capTxt(s.adv)) +
      mx('Sector RS 20D', nv(s.rs, 2)) +
      mx('MA20', tnv(m.ma20, 2)) +
      mx('MA50', tnv(m.ma50, 2)) +
      mx('ATR (14)', tnv(m.atr, 2)) +
      mx('Scan Date', esc(s.scanDate || NA));

    var notes = (REVIEW.notes || []).slice(0, 2).map(function (n) {
      return '<div class="note">' + esc(n) + '</div>';
    }).join('');
    notes += '<div class="note">技术确认信号：<b>' + esc(s.conf || NA) + '</b>（' +
      ((s.confCount === '' || s.confCount === null) ? NA : String(s.confCount)) + '）</div>';
    $('#dReviewNotes').innerHTML = notes;

    $('#detail').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    $('#detail').scrollTop = 0;
    if (hasBars) window.requestAnimationFrame(function () { drawDetailCharts(); });
  }

  /* ---------------- 图表（真实 ohlcv 才画） ---------------- */
  var CLS_UP = '#d6372c', CLS_DOWN = '#0f9d58';
  function setup(cv) {
    var dpr = window.devicePixelRatio || 1;
    var w = cv.clientWidth || 300, h = cv.clientHeight || 120;
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    var ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.font = '10px -apple-system,Segoe UI,Roboto,sans-serif';
    return { ctx: ctx, w: w, h: h };
  }
  var AXIS = '#8b93a3', GRID = '#eef0f4';
  function xOf(i, n, w, p) { return p.l + (i + 0.5) * (w - p.l - p.r) / n; }
  function drawFrame(ctx, w, h, p, vals, fmtFn) {
    var min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
    if (max - min < 1e-9) max = min + 1;
    var padv = (max - min) * 0.08;
    min -= padv; max += padv;
    var ph = h - p.t - p.b;
    var yOf = function (v) { return p.t + (max - v) / (max - min) * ph; };
    ctx.strokeStyle = GRID; ctx.lineWidth = 1;
    ctx.fillStyle = AXIS; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    var rows = h < 90 ? 2 : 3;
    for (var i = 0; i <= rows; i++) {
      var v = min + (max - min) * i / rows, y = Math.round(yOf(v)) + 0.5;
      ctx.beginPath(); ctx.moveTo(p.l, y); ctx.lineTo(w - p.r, y); ctx.stroke();
      ctx.fillText(fmtFn ? fmtFn(v) : fmt(v, 1), w - p.r + 5, y);
    }
    return { yOf: yOf };
  }
  function drawXLabels(ctx, w, h, p, n, dates) {
    if (!dates) return;
    var cnt = w < 360 ? 3 : 5;
    ctx.fillStyle = AXIS; ctx.textBaseline = 'bottom';
    for (var i = 0; i < cnt; i++) {
      var idx = Math.round((n - 1) * i / (cnt - 1));
      var x = xOf(idx, n, w, p), d = dates[idx];
      if (!d) continue;
      ctx.textAlign = i === 0 ? 'left' : (i === cnt - 1 ? 'right' : 'center');
      ctx.fillText(String(d).slice(5).replace('-', '/'), x, h - 2);
    }
  }

  function drawCandles(cv, bars, ma20, ma50, dates) {
    var s = setup(cv), ctx = s.ctx, w = s.w, h = s.h;
    var p = { l: 6, r: 54, t: 8, b: 16 };
    var n = bars.length, vals = [];
    bars.forEach(function (b) { vals.push(b.h, b.l); });
    (ma20 || []).forEach(function (v) { if (v != null) vals.push(v); });
    (ma50 || []).forEach(function (v) { if (v != null) vals.push(v); });
    var f = drawFrame(ctx, w, h, p, vals, function (v) { return fmt(v, 0); });
    var bw = Math.max(1.4, Math.min(9, (w - p.l - p.r) / n * 0.64));
    for (var i = 0; i < n; i++) {
      var b = bars[i], x = xOf(i, n, w, p), up = b.c >= b.o;
      ctx.strokeStyle = up ? CLS_UP : CLS_DOWN; ctx.fillStyle = up ? CLS_UP : CLS_DOWN; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(Math.round(x) + 0.5, f.yOf(b.h)); ctx.lineTo(Math.round(x) + 0.5, f.yOf(b.l)); ctx.stroke();
      var y1 = f.yOf(Math.max(b.o, b.c)), y2 = f.yOf(Math.min(b.o, b.c));
      ctx.fillRect(x - bw / 2, y1, bw, Math.max(1, y2 - y1));
    }
    function mline(arr, color) {
      if (!arr) return;
      ctx.strokeStyle = color; ctx.lineWidth = 1.3; ctx.beginPath();
      var st = false;
      for (var i = 0; i < n; i++) {
        var v = arr[i]; if (v == null) continue;
        var x = xOf(i, n, w, p), y = f.yOf(v);
        if (!st) { ctx.moveTo(x, y); st = true; } else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    mline(ma50, '#7b5cf0');
    mline(ma20, '#f0a020');
    var lastC = bars[n - 1].c, yl = f.yOf(lastC);
    ctx.fillStyle = lastC >= bars[n - 1].o ? CLS_UP : CLS_DOWN;
    ctx.fillRect(w - p.r + 3, yl - 7, p.r - 6, 14);
    ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(fmt(lastC, 2), w - p.r + 3 + (p.r - 6) / 2, yl);
    drawXLabels(ctx, w, h, p, n, dates);
  }

  function drawVolume(cv, bars, dates) {
    var s = setup(cv), ctx = s.ctx, w = s.w, h = s.h;
    var p = { l: 6, r: 54, t: 6, b: 14 };
    var n = bars.length, max = 0;
    bars.forEach(function (b) { max = Math.max(max, b.v); });
    if (max <= 0) max = 1;
    var ph = h - p.t - p.b, bw = Math.max(1.4, Math.min(9, (w - p.l - p.r) / n * 0.64));
    for (var i = 0; i < n; i++) {
      var b = bars[i], x = xOf(i, n, w, p), bh = b.v / max * ph;
      ctx.fillStyle = b.c >= b.o ? 'rgba(214,55,44,.55)' : 'rgba(15,157,88,.55)';
      ctx.fillRect(x - bw / 2, p.t + ph - bh, bw, bh);
    }
    ctx.strokeStyle = GRID; ctx.beginPath();
    ctx.moveTo(p.l, h - p.b + 0.5); ctx.lineTo(w - p.r, h - p.b + 0.5); ctx.stroke();
    ctx.fillStyle = AXIS; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    ctx.fillText('Vol ' + (max / 1e6).toFixed(1) + 'M', w - p.r + 5, p.t + 6);
    drawXLabels(ctx, w, h, p, n, dates);
  }

  function drawSpark(cv, closes) {
    var s = setup(cv), ctx = s.ctx, w = s.w, h = s.h;
    var n = Math.min(closes.length, 90);
    var arr = closes.slice(closes.length - n);
    var min = Math.min.apply(null, arr), max = Math.max.apply(null, arr);
    if (max - min < 1e-9) max = min + 1;
    var y = function (v) { return 3 + (max - v) / (max - min) * (h - 6); };
    var up = arr[arr.length - 1] >= arr[0];
    ctx.beginPath();
    for (var i = 0; i < n; i++) {
      var x = i / (n - 1) * w, yy = y(arr[i]);
      if (i === 0) ctx.moveTo(x, yy); else ctx.lineTo(x, yy);
    }
    ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
    ctx.fillStyle = up ? 'rgba(214,55,44,.10)' : 'rgba(15,157,88,.10)'; ctx.fill();
    ctx.beginPath();
    for (var j = 0; j < n; j++) {
      var x2 = j / (n - 1) * w, y2 = y(arr[j]);
      if (j === 0) ctx.moveTo(x2, y2); else ctx.lineTo(x2, y2);
    }
    ctx.strokeStyle = up ? CLS_UP : CLS_DOWN; ctx.lineWidth = 1.3; ctx.stroke();
  }

  function drawDetailCharts() {
    if (!cur || !cur.ohlcv.length) return;
    var n = Math.min(curRange, cur.ohlcv.length);
    var bars = slice(cur.ohlcv, n);
    var dates = bars.map(function (b) { return b.d; });
    var cvP = $('#chartPrice'), cvV = $('#chartVol');
    if (cvP) drawCandles(cvP, bars, null, null, dates);   /* MA 线仅在 JSON 提供序列时叠加 */
    if (cvV) drawVolume(cvV, bars, dates);
  }

  function closeDetail() {
    $('#detail').classList.add('hidden');
    document.body.style.overflow = '';
    cur = null;
  }

  function drawAllSparks() {
    [].forEach.call(document.querySelectorAll('[data-spark]'), function (cv) {
      var tk = cv.getAttribute('data-spark'), s = null;
      for (var i = 0; i < STOCKS.length; i++) if (STOCKS[i].t === tk) s = STOCKS[i];
      if (!s || s.ohlcv.length < 2) return;
      drawSpark(cv, s.ohlcv.map(function (b) { return b.c; }));
    });
  }

  /* ---------------- 事件 ---------------- */
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var card = t.closest('.pcard,.ocard');
    if (card) { openDetail(card.getAttribute('data-tk')); return; }
    if (t.closest('#btnBack')) { closeDetail(); return; }
    var chip = t.closest('.chip');
    if (chip) {
      curRange = parseInt(chip.getAttribute('data-n'), 10);
      [].forEach.call(document.querySelectorAll('.chip'), function (c) { c.classList.remove('on'); });
      chip.classList.add('on');
      drawDetailCharts();
    }
  });
  var rt;
  window.addEventListener('resize', function () {
    clearTimeout(rt);
    rt = setTimeout(function () { drawDetailCharts(); drawAllSparks(); }, 120);
  });

  /* ---------------- 启动 ---------------- */
  boot();
})();
