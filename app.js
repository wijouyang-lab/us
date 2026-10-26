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
  var MACRO = null;
  var QUANT = {};                           /* dashboard_data.json 的 quant 键（Quant Phase 1–7 研究状态） */
  var REVIEWS = [];                         /* review.records[] —— 数据仍由 dashboard_data.json 提供；
                                            第 10C 已移除首页历史推荐列表，此处仅保留引用供后续 Evolution 使用，不渲染任何卡片 */
  var REV_MS = {};                          /* review.records[] → (Ticker|Rec_Date|Tag) 索引，供当前卡片挂 Review 里程碑 */
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

  /* 宽松数值：账本里 Stop_Loss 可能是 "$197.69" / "197.69" / 197.69 三种形态，
     只做字符清洗后转数字；仍不可解析则返回 null（绝不按 0 处理）。 */
  function numLoose(v) {
    if (v === null || v === undefined || v === '') return null;
    if (typeof v === 'number') return isFinite(v) ? v : null;
    var n = Number(String(v).replace(/[^0-9.\-]/g, ''));
    return isFinite(n) ? n : null;
  }

  /* Actionable Option 判定（与后端 MIN_REWARD_RISK = 2.0 同口径）：
     · Status 必须为 Active
     · reward_risk 必须可计算且 >= 2.0
     · reward_risk 缺失/NaN 时绝不默认 Active
     Rejected 数据仍保留在 CSV 底层，此处只做展示层过滤。 */
  var MIN_ACTIONABLE_REWARD_RISK = 2.0;
  function isActionableOption(o) {
    if (!o) return false;
    if (String(o.status || '').toLowerCase() !== 'active') return false;
    var rr = num(o.reward_risk);
    if (rr === null) return false;
    return rr >= MIN_ACTIONABLE_REWARD_RISK;
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
    /* Actionable Options 口径：只有 Status=Active 且 Reward/Risk >= 2.0 才展示。
       Rejected 仍完整保留在 option_strategies.csv 底层数据中（审计/统计），
       此处仅在展示层过滤，绝不删除任何数据。 */
    OPTIONS = (data.options || []).filter(isActionableOption);
    REVIEW = data.review || {};
    HISTORY = data.history || [];
    QUANT = data.quant || {};
    MACRO = data.macro || null;
    REVIEWS = (REVIEW && Array.isArray(REVIEW.records)) ? REVIEW.records.slice() : [];

    /* Review 里程碑索引：严格按 Ticker + Rec_Date + Tag 关联 review.records[]（第 10D）。
       只建立索引、不重算任何里程碑值；同一事件若有多条 record，取 days_held 最大（最新一次 Review）。 */
    REV_MS = {};
    (REVIEWS || []).forEach(function (r) {
      if (!r) return;
      var k = msKey(r.ticker, r.rec_date, r.tag);
      var prev = REV_MS[k];
      if (!prev) { REV_MS[k] = r; return; }
      var dv = num(r.days_held), pv = num(prev.days_held);
      if (dv !== null && (pv === null || dv > pv)) REV_MS[k] = r;
    });

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
        /* 三个价格语义严格区分，互不替代：
           px        = 当前价（Current Price）
           recPrice  = 正式买入价（= 推荐日真实 Open，缺失为 null）
           prevClose = 前收（Prev Close） */
        px: num(s.price),
        recPrice: num(s.rec_price),
        pct: num(s.change_1d),
        prevClose: num(s.prev_close),
        s: {
          final: num(s.final_score), quant: num(s.quant_score), ai: num(s.ai_score),
          aiDisplay: s.ai_score_display || null,
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
  /* ---------------- $50,000 Long-Term Portfolio ---------------- */
  /* 数据来源：portfolio_50000_*.csv（由 portfolio_50000.py 维护），
     经 dashboard_export.py 原样透传。前端只做展示与两位小数格式化，不重算盈亏。 */
  /* 持仓卡片：以 portfolio.positions[] 为主，按 ticker join STOCKS[] 取评分/技术面/AI/K线。 */
  function sparkHtml(s, small) {
    if (s && s.ohlcv && s.ohlcv.length > 1) {
      return '<canvas class="spark' + (small ? ' spark-sm' : '') + '" data-spark="' + esc(s.t) + '"></canvas>';
    }
    return '<div class="spark-na' + (small ? ' sm' : '') + '">K线数据暂不可用</div>';
  }

  function posTechFoot(s) {
    var m = s.m;
    var items = [
      ['MA20', tnv(m.ma20, 2)],
      ['MA50', tnv(m.ma50, 2)],
      ['RSI', nv(m.rsi, 1)],
      ['MACD', tnv(m.dif, 2)],
      ['KDJ', (m.k === null || m.d === null) ? NA : (fmt(m.k, 1) + '/' + fmt(m.d, 1))],
      ['ATR%', nv(m.atrPct, 2)]
    ];
    return '<div class="pos-foot">' + items.map(function (x) {
      return '<div><div class="fk">' + x[0] + '</div><div class="fv' + (naIf(x[1]) ? ' na' : '') + '">' + x[1] + '</div></div>';
    }).join('') + '</div>';
  }

  /* 扩展时段标签：盘前 / 盘后 / 盘中（按 ET 时点的小时判断）。 */
  function extLabel(t) {
    var m = /(\d{1,2}):(\d{2})/.exec(t || '');
    if (!m) return '盘后';
    var h = parseInt(m[1], 10), mi = parseInt(m[2], 10);
    var mins = h * 60 + mi;
    if (mins < 9 * 60 + 30) return '盘前';
    if (mins >= 16 * 60) return '盘后';
    return '盘中';
  }

  /* p: portfolio.positions[] 条目；s: STOCKS[] 里同 ticker 的详情（找不到则 null → 降级只显示持仓字段） */
  function positionCard(p, s) {
    var tk = String(p.ticker || '').toUpperCase();
    var up = num(p.unrealized_pnl) || 0;
    var rt = num(p.unrealized_pnl_pct) || 0;
    var upCls = up > 0 ? 'up' : (up < 0 ? 'down' : 'flat');

    var extLine = (p.extended_price != null && p.extended_price !== '')
      ? '<div class="pos-ext">' + extLabel(p.extended_time) + ' $' + nv(p.extended_price, 2)
        + (p.extended_time ? ' (' + esc(p.extended_time) + ')' : '') + '</div>'
      : '';

    var head = '<div class="pos-top">' +
      '<div class="pos-id">' +
      '<div class="pos-tk">' + esc(tk) + '</div>' +
      '<div class="pos-nm">' + esc(s ? s.n : '') + '</div>' +
      '<div class="pos-px">$' + nv(p.current_price, 2) + '</div>' +
      extLine +
      '</div>' +
      (s ? '<div class="pos-ring">' + ring(s.s.final, 54, 'Final') + '</div>' : '') +
      '</div>';

    var quick = s
      ? '<div class="pos-quick">' +
        '<span class="qb">Quant ' + nv(s.s.quant, 1) + '</span>' +
        '<span class="qb">AI ' + nv(s.s.ai, 1) + '</span>' +
        '<span class="qb g">' + esc(s.bucketLabel || '') + '</span>' +
        '</div>'
      : '';

    var bars = s
      ? '<div class="bars">' +
        scoreRow('Quant', s.s.quant, 100) +
        scoreRow('AI', s.s.ai, 100) +
        scoreRow('Fundamental', s.s.fund, MAX_F) +
        scoreRow('Technical', s.s.tech, MAX_T) +
        scoreRow('Risk', s.s.risk, MAX_R) +
        '</div>'
      : '';

    var foot = s ? posTechFoot(s) : '';

    /* 风控线：账本里的 Stop_Loss 是「移动止损/移动止盈」同一条线
       （review 浮盈后只抬止损、不强制止盈）。线上分两种语义展示：
         · 止损线在入场价下方 → 「止损」（距入场 %）；
         · 已抬到入场价上方 → 「移动止盈」（锁定 +%）。 */
    var stopP = (p.stop_loss_price != null) ? num(p.stop_loss_price) : numLoose(p.stop_loss);
    var entryP = num(p.entry_price);
    var riskK = '止损', riskV = p.stop_loss || NA, riskCls = '';
    if (stopP != null) {
      riskV = '$' + fmt(stopP, 2);
      if (entryP) {
        var lockPct = (stopP / entryP - 1) * 100;
        riskV += '（' + (lockPct >= 0 ? '锁定 +' : '距入场 ') + fmt(lockPct, 1) + '%）';
        if (stopP >= entryP) { riskK = '移动止盈'; riskCls = 'up'; }
        else { riskCls = 'down'; }
      }
    }
    var risk = '<div><span class="pmk">' + riskK + '</span><b class="' + riskCls + '">' + esc(riskV) + '</b></div>';

    /* 风控距离条：把 止损线 / 入场价 / 现价 落在同一条轴上，
       一眼看出「离止损还有多远」。三个价格都有效才画，任何缺失则整条不画。 */
    var curP = num(p.current_price);
    var riskBar = '';
    if (stopP != null && entryP && curP != null && curP > 0 && stopP > 0) {
      var lo = Math.min(stopP, entryP, curP), hi = Math.max(stopP, entryP, curP);
      if (hi > lo) {
        var pad = (hi - lo) * 0.12;
        lo -= pad; hi += pad;
        var pos = function (v) {
          return Math.max(0, Math.min(100, (v - lo) / (hi - lo) * 100)).toFixed(1);
        };
        var distStop = (curP / stopP - 1) * 100;
        var distEntry = (curP / entryP - 1) * 100;
        riskBar = '<div class="pos-risk">' +
          '<div class="prb-track">' +
            '<i class="prb-stop" style="left:' + pos(stopP) + '%" title="止损 $' + fmt(stopP, 2) + '"></i>' +
            '<i class="prb-entry" style="left:' + pos(entryP) + '%" title="入场 $' + fmt(entryP, 2) + '"></i>' +
            '<i class="prb-cur" style="left:' + pos(curP) + '%" title="现价 $' + fmt(curP, 2) + '"></i>' +
          '</div>' +
          '<div class="prb-legend">' +
            '<span class="prb-s">止损 $' + fmt(stopP, 2) + '（距现价 ' +
              (distStop >= 0 ? '+' : '') + fmt(distStop, 1) + '%）</span>' +
            '<span class="prb-e">入场 $' + fmt(entryP, 2) + '（' +
              (distEntry >= 0 ? '+' : '') + fmt(distEntry, 1) + '%）</span>' +
            '<span class="prb-c">现价 $' + fmt(curP, 2) + '</span>' +
          '</div>' +
        '</div>';
      }
    }

    var meta = '<div class="pos-meta">' +
      '<div><span class="pmk">股数</span><b>' + (p.shares == null ? NA : p.shares) + '</b></div>' +
      '<div><span class="pmk">Entry</span><b>$' + nv(p.entry_price, 2) + '</b></div>' +
      '<div><span class="pmk">市值</span><b>$' + nv(p.market_value, 2) + '</b></div>' +
      '<div><span class="pmk">浮盈</span><b class="' + upCls + '">' + (up > 0 ? '+' : '') + '$' + nv(up, 2) +
      ' (' + (rt > 0 ? '+' : '') + nv(rt, 2) + '%)</b></div>' +
      '<div><span class="pmk">权重</span><b>' + nv(p.weight_pct, 2) + '%</b></div>' +
      '<div><span class="pmk">持有</span><b>' + (p.holding_days == null ? NA : p.holding_days) + ' 天</b></div>' +
      risk +
      '</div>';

    return '<article class="poscard' + (s ? '' : ' poscard-na') + '" data-tk="' + esc(tk) + '">' +
      head + quick + (s ? sparkHtml(s, false) : '') + bars + foot + meta + riskBar +
      '</article>';
  }

  /* 盘中机械止损横幅：扫描 pf.transactions 中 Reason="Intraday Stop Loss" 的 SELL，
     在持仓区下方展示"🔴 盘中止损"徽章 + 触发价 + 原因（AI 回填后原因会变）。
     只展示「最新交易日」触发的盘中止损：标题此前写"今日触发"却列出全部历史，
     与事实不符；这里以流水最大日期为锚，历史止损请到「已止损记录」板块看。
     注：dashboard_export.build_portfolio 只保留 Status=OPEN 的持仓，CLOSED 仓位不进 positions[]，
     故盘中止损经由交易流水展示，而非 positionCard。 */
  function renderIntradayStops(pf) {
    var txEl = document.querySelector('#pfTxns');   // 自行获取，避免依赖外层局部变量作用域
    if (!txEl) return;
    var ts = pf.transactions || [];
    var maxDate = '';
    ts.forEach(function (t) {
      var d = String(t.date || '');
      if (d && d > maxDate) maxDate = d;
    });
    var stops = ts.filter(function (t) {
      if (String(t.action || '').toUpperCase() !== 'SELL') return false;
      if (String(t.reason || '') !== 'Intraday Stop Loss') return false;
      return !maxDate || String(t.date || '') === maxDate;
    });
    if (window.__intradayStopEl && window.__intradayStopEl.parentNode) {
      window.__intradayStopEl.parentNode.removeChild(window.__intradayStopEl);
      window.__intradayStopEl = null;
    }
    if (!stops.length) return;
    var rows = stops.map(function (t) {
      var reasonTxt = t.reason || 'Intraday Stop Loss';
      return '<div class="is-row">' +
        '<span class="is-tk">' + esc(t.ticker || NA) + '</span>' +
        '<span class="is-px">$' + nv(t.price, 2) + '</span>' +
        '<span class="is-tag">🔴 盘中止损</span>' +
        '<span class="is-reason">' + esc(reasonTxt) + '</span>' +
        '</div>';
    }).join('');
    var banner = document.createElement('div');
    banner.className = 'intraday-stop';
    banner.innerHTML = '<div class="is-hd">⚠️ 盘中机械止损（' +
      esc(maxDate || '最新交易日') + ' 触发）</div>' + rows;
    txEl.parentNode.insertBefore(banner, txEl);
    window.__intradayStopEl = banner;
  }

  /* AI 目标持仓板块：读 DATA.portfolio.target（dashboard_export 在 ENABLE_TARGET_FILE=1 时注入）。
     target 为 null/空 → 静默隐藏；否则渲染 Ticker + Action + 数量 + 参考价 + 理由（点击展开）。 */
  function renderTarget() {
    var el = $('#pfTarget');
    if (!el) return;
    var pf = DATA.portfolio;
    var target = pf && pf.target;
    if (!target || !target.length) {
      el.hidden = true;
      el.innerHTML = '';
      return;
    }
    el.hidden = false;
    var rows = target.map(function (t) {
      var act = (t.action || '').toUpperCase();
      var actCls = act === 'BUY' ? 'buy' : (act === 'SELL' ? 'sell' : 'hold');
      var price = (t.ref_price != null && t.ref_price !== '') ? '$' + nv(t.ref_price, 2) : NA;
      var shares = (t.target_shares == null) ? NA : t.target_shares;
      var reason = t.ai_reason || '';
      // 盘前目标必须带风控线：止损价来自 portfolio_50000_target.csv 的 Stop_Loss，
      // 同时给出相对参考价的跌幅，便于一眼判断这笔计划的单笔风险。
      var stopP = (t.stop_loss_price != null) ? num(t.stop_loss_price) : numLoose(t.stop_loss);
      var refP = num(t.ref_price);
      var stopTxt = '', stopPctTxt = '';
      if (stopP != null) {
        stopTxt = '$' + fmt(stopP, 2);
        if (refP) stopPctTxt = fmt((stopP / refP - 1) * 100, 1) + '%';
      } else if (t.stop_loss) {
        stopTxt = String(t.stop_loss);
      }
      var stopHtml = stopTxt
        ? '<span class="at-stop">止损 <b>' + esc(stopTxt) + '</b>' +
          (stopPctTxt ? '<i>' + esc(stopPctTxt) + '</i>' : '') + '</span>'
        : '<span class="at-stop na">止损 ' + NA + '</span>';
      return '<div class="at-row">' +
        '<div class="at-head">' +
          '<span class="at-tk">' + esc(t.ticker || NA) + '</span>' +
          '<span class="at-act ' + actCls + '">' + esc(act || NA) + '</span>' +
          '<span class="at-shares">×' + esc(String(shares)) + '</span>' +
          '<span class="at-price">' + price + '</span>' +
        '</div>' +
        '<div class="at-risk">' + stopHtml + '</div>' +
        (reason ? '<div class="at-reason" onclick="this.classList.toggle(\'open\')">' + esc(reason) + '</div>' : '') +
      '</div>';
    }).join('');
    var sub = (target[0] && target[0].scan_date) ? 'Scan ' + esc(target[0].scan_date) + ' · 点击理由展开' : '盘前目标 · 点击理由展开';
    el.innerHTML = '<div class="sec-h sub"><h3>AI 目标持仓</h3><span class="sec-sub">' + sub + '</span></div>' +
      '<div class="at-list">' + rows + '</div>';
  }

  function renderPortfolio() {
    var pf = DATA.portfolio;
    var sumEl = $('#pfSummary'), posEl = $('#pfPositions'),
        txEl = $('#pfTxns'), cv = $('#pfCurve');
    if (!sumEl) return;

    if (!pf) {
      sumEl.innerHTML = '<div class="mx"><div class="k">状态</div>' +
        '<div class="v na">尚未初始化（首次 Review 运行后自动建立）</div></div>';
      if (posEl) posEl.innerHTML = '';
      if (txEl) txEl.innerHTML = '';
      if (cv) cv.style.display = 'none';
      return;
    }
    if (cv) cv.style.display = '';

    // --- 概览 ---
    var tp = num(pf.total_pnl) || 0;
    var ret = num(pf.return_pct) || 0;
    var cells = '';
    cells += cell('Initial Capital', '$' + nv(pf.initial_capital, 2));
    cells += cell('Total Equity', '$' + nv(pf.total_equity, 2));
    cells += cell('Total PnL', (tp > 0 ? '+' : '') + '$' + nv(tp, 2), pctCls(tp));
    cells += cell('Return %', (ret > 0 ? '+' : '') + nv(ret, 2) + '%', pctCls(ret));
    cells += cell('Cash', '$' + nv(pf.cash, 2));
    cells += cell('Stock Value', '$' + nv(pf.stock_value, 2));
    cells += cell('Realized PnL', '$' + nv(pf.realized_pnl, 2), pctCls(num(pf.realized_pnl)));
    cells += cell('Unrealized PnL', '$' + nv(pf.unrealized_pnl, 2), pctCls(num(pf.unrealized_pnl)));
    cells += cell('持仓只数', (pf.open_positions == null ? NA : pf.open_positions) + ' 只' +
      (pf.open_pct == null ? '' : '（股票 ' + pf.open_pct + '%）'));
    cells += cell('Start Date', esc(pf.start_date || NA));
    sumEl.innerHTML = '<div class="matrix">' + cells + '</div>';

    // --- 持仓（卡片网格：positions[] 主表，按 ticker join STOCKS[]）---
    var ps = pf.positions || [];
    if (!ps.length) {
      posEl.innerHTML = '<div class="mx"><div class="k">当前持仓</div>' +
        '<div class="v na">空仓（等待新的 Core 推荐触发建仓）</div></div>';
    } else {
      var stockByTk = {};
      STOCKS.forEach(function (s) { if (s.t) stockByTk[String(s.t).toUpperCase()] = s; });
      posEl.innerHTML = ps.map(function (p) {
        var s = stockByTk[String(p.ticker || '').toUpperCase()] || null;
        return positionCard(p, s);
      }).join('');
    }

    // --- 盘中机械止损横幅（从交易流水展示）---
    renderIntradayStops(pf);

    // --- 最近交易 ---
    var ts = pf.transactions || [];
    if (!ts.length) {
      txEl.innerHTML = '';
    } else {
      var missingTime = false;
      ts.forEach(function (t) { if (!t.time) missingTime = true; });
      var th = '<div class="pf-hd">Recent Portfolio Transactions' +
        '<span class="pf-note">美东时间 ET' +
        (missingTime ? ' · 部分历史成交未记录时刻' : '') + '</span></div>' +
        '<div class="pf-wrap"><table class="pf-tbl"><thead><tr><th>Date</th><th>Action</th><th>Ticker</th>' +
        '<th>Shares</th><th>Price</th><th>Amount</th><th>Realized PnL</th><th>Holding</th><th>Reason</th>' +
        '</tr></thead><tbody>';
      ts.forEach(function (t) {
        var rp = num(t.realized_pnl);
        th += '<tr>' +
          '<td class="pf-date">' + esc(t.date || NA) + txnTimeHtml(t) + '</td>' +
          '<td class="' + (String(t.action).toUpperCase() === 'BUY' ? 'up' : 'down') + '">' +
          esc(t.action || NA) + '</td>' +
          '<td class="tk">' + esc(t.ticker || NA) + '</td>' +
          '<td>' + (t.shares == null ? NA : t.shares) + '</td>' +
          '<td>$' + nv(t.price, 2) + '</td>' +
          '<td>$' + nv(t.amount, 2) + '</td>' +
          '<td class="' + (rp ? pctCls(rp) : '') + '">' +
          (rp == null ? NA : (rp > 0 ? '+' : '') + '$' + nv(rp, 2)) + '</td>' +
          txnHoldingHtml(t) +
          '<td class="rsn">' + esc(t.reason || NA) + '</td>' +
          '</tr>';
      });
      th += '</tbody></table></div>';
      txEl.innerHTML = th;
    }

    drawPortfolioCurve(pf);
  }

  /* ---------------- 交易流水：成交时刻 / 持有时间 ----------------
     字段全部来自 dashboard_export.build_portfolio（后端单一数据源）：
       time          : 本笔成交时刻 HH:MM（美东）｜历史无侧车 → null
       entry_date/time : 买入日/时（SELL 行由后端按 Unit 配对回填）
       exit_date/time  : 卖出日/时（BUY 行已平仓时回填，未平仓为 null）
       holding_days   : 净持有天数（未平仓 BUY 以最新快照日为基准）
       holding_hours  : 首尾都有时刻时的持有总小时数（否则 null）
       holding_open   : BUY 未平仓 = true
     铁律：缺失显示 "—"，绝不按 0 / 当天 / 猜测时间填充。 */
  function txnTimeHtml(t) {
    return t.time ? '<span class="pf-time">' + esc(String(t.time)) + '</span>' : '';
  }

  function shortDT(d, tm) {
    var s = d ? String(d).slice(5) : '';          /* YYYY-MM-DD → MM-DD */
    if (!tm) return s;
    return s ? (s + ' ' + tm) : String(tm);
  }

  /* 持有时间文本：两端都有成交时刻 → 天+小时；否则退化为天数；未知 → '' */
  function holdText(t) {
    if (t.holding_hours != null) {
      return t.holding_hours >= 24
        ? (Math.floor(t.holding_hours / 24) + ' 天 ' + (t.holding_hours % 24) + ' 小时')
        : (t.holding_hours + ' 小时');
    }
    if (t.holding_days != null) return t.holding_days + ' 天';
    return '';
  }

  function txnHoldingHtml(t) {
    var entryD = t.entry_date || null, entryT = t.entry_time || null;
    var exitD = t.exit_date || null, exitT = t.exit_time || null;
    var main = NA, sub = '', tip = '';

    if (t.holding_open && entryD) {
      main = '持有中' + (t.holding_days == null ? '' : ' · ' + t.holding_days + ' 天');
      sub = '自 ' + shortDT(entryD, entryT);
    } else if (entryD && exitD) {
      if (t.holding_hours != null) {
        main = (t.holding_hours >= 24)
          ? (Math.floor(t.holding_hours / 24) + ' 天 ' + (t.holding_hours % 24) + ' 小时')
          : (t.holding_hours + ' 小时');
      } else if (t.holding_days != null) {
        main = t.holding_days + ' 天';
      }
      sub = shortDT(entryD, entryT) + ' → ' + shortDT(exitD, exitT);
    } else if (exitD) {
      sub = '卖出 ' + shortDT(exitD, exitT);
    } else if (entryD) {
      sub = '买入 ' + shortDT(entryD, entryT);
    }

    if (entryD) tip = '买入 ' + entryD + (entryT ? ' ' + entryT : '');
    if (exitD) tip += (tip ? ' → ' : '') + '卖出 ' + exitD + (exitT ? ' ' + exitT : '');
    return '<td class="pf-hold"' + (tip ? ' title="' + esc(tip) + '"' : '') + '>' +
      '<div class="pf-hold-main">' + main + '</div>' +
      (sub ? '<div class="pf-hold-sub">' + esc(sub) + '</div>' : '') +
      '</td>';
  }

  /* 月度汇总：把已平仓记录按 YYYY-MM 分组，给出「笔数 · 净额」。
     只聚合当前板块已筛选出的记录（同一 30 天窗口/同一离场类型），
     不重算、不引入新数据源。 */
  function monthSummaryHtml(list, label) {
    if (!list || !list.length) return '';
    var by = {}, order = [];
    list.forEach(function (t) {
      var m = String(t.date || '').slice(0, 7);
      if (!m) return;
      if (!by[m]) { by[m] = { n: 0, pnl: 0 }; order.push(m); }
      by[m].n++;
      var rp = num(t.realized_pnl);
      if (rp !== null) by[m].pnl += rp;
    });
    order.sort().reverse();
    var chips = order.map(function (m) {
      var x = by[m];
      return '<span class="stp-mchip">' + esc(m) + ' · ' + x.n + ' 笔 · ' +
        (x.pnl >= 0 ? '+$' : '-$') + fmt(Math.abs(x.pnl), 2) + '</span>';
    }).join('');
    return '<div class="stp-months">' + (label ? '<span class="stp-mlab">' + esc(label) + '</span>' : '') +
      chips + '</div>';
  }

  /* 已止损记录板块（近 30 天）：纯前端只读 portfolio.transactions，
     筛选 Action=SELL 且 Reason 含 "Stop Loss" 的记录，按日期降序展示。
     兼容两种真实写法：`Stop_Loss_Hit`（账本，Review exit）与 `Stop Loss`（盘中止损）。
     注意：止盈离场 `Trailing_Profit_Take` 不含 stop-loss 语义，按设计排除在本板块外。
     字段来源（dashboard_export.build_portfolio 透传）：
       date / time / ticker / action / shares / price(成交价=退出价) / amount /
       realized_pnl / reason / entry_price / entry_date / entry_time /
       holding_days / holding_hours
     说明：
       · transactions 后端只保留最近 20 条（不分 action，见 dashboard_export.py），
         故本板块可见范围受此上限约束；止损离场多为近期事件，实践中可见。
       · 入场价优先用配对出的 entry_price；老数据缺失时退回
         cost_basis = amount - realized_pnl 反推，绝不捏造。 */
  function renderStopped() {
    var subEl = $('#stoppedSub'), bodyEl = $('#stoppedBody');
    if (!subEl || !bodyEl) return;
    var pf = DATA && DATA.portfolio;
    var ts = (pf && pf.transactions) || [];

    if (!ts.length) {
      subEl.textContent = '—';
      bodyEl.innerHTML = '<div class="mx"><div class="k">已止损记录</div>' +
        '<div class="v na">暂无止损记录</div></div>';
      return;
    }

    // 锚点：以交易流水中最新日期为"今天"基准（不依赖本地时钟，避免时区漂移）
    var maxDate = '';
    ts.forEach(function (t) {
      var d = String(t.date || '');
      if (d && d > maxDate) maxDate = d;
    });
    var anchor = maxDate ? new Date(maxDate) : null;
    var threshold = anchor ? new Date(anchor.getTime() - 30 * 86400000) : null;

    // 筛选：SELL + Reason 含 "stop loss"（不含时兼容下划线 Stop_Loss_Hit）+ 落在近 30 天
    var stops = ts.filter(function (t) {
      if (String(t.action || '').toUpperCase() !== 'SELL') return false;
      if (!/stop[\s_-]*loss/i.test(String(t.reason || ''))) return false;
      if (threshold) {
        var d = new Date(String(t.date || ''));
        if (!isNaN(d.getTime()) && d < threshold) return false;
      }
      return true;
    }).sort(function (a, b) {
      var da = String(a.date || ''), db = String(b.date || '');
      return db > da ? 1 : (db < da ? -1 : 0);
    });

    if (!stops.length) {
      subEl.textContent = '—';
      bodyEl.innerHTML = '<div class="mx"><div class="k">已止损记录</div>' +
        '<div class="v na">暂无止损记录</div></div>';
      return;
    }

    // 统计：总计 / 胜率（样本<10 显 "—"）/ 平均收益率
    var n = stops.length, wins = 0, sumRet = 0, counted = 0;
    stops.forEach(function (t) {
      var rp = num(t.realized_pnl), amt = num(t.amount);
      if (rp !== null && rp > 0) wins++;
      var cost = (amt !== null && rp !== null) ? (amt - rp) : null;
      if (cost !== null && cost > 0) { sumRet += rp / cost * 100; counted++; }
    });
    var wr = n < 10 ? '—' : Math.round(wins / n * 100) + '%';
    var avg = counted ? (sumRet / counted >= 0 ? '+' : '') +
      fmt(sumRet / counted, 1) + '%' : '—';
    subEl.textContent = '总计: ' + n + ' 笔 | 胜率: ' + wr + ' | 平均: ' + avg;

    var rows = stops.map(function (t) {
      var tk = t.ticker || NA;
      var dt = String(t.date || '').slice(5);            // YYYY-MM-DD → MM-DD
      if (t.time) dt += ' ' + t.time;
      var px = num(t.price), sh = num(t.shares),
          amt = num(t.amount), rp = num(t.realized_pnl);
      var entryPx = num(t.entry_price), exitPx = num(t.exit_price);
      var cost = (entryPx !== null && sh !== null && sh > 0) ? entryPx * sh
        : ((amt !== null && rp !== null) ? (amt - rp) : null);
      var entryTxt, retTxt;
      if (entryPx !== null && exitPx !== null) {
        entryTxt = '$' + fmt(entryPx, 2) + ' → $' + fmt(exitPx, 2);
      } else if (cost !== null && cost > 0 && sh !== null && sh > 0) {
        entryTxt = '$' + fmt(cost / sh, 2) + ' → $' + nv(px, 2);
      } else {
        entryTxt = (px === null ? NA : '$' + fmt(px, 2));
      }
      if (cost !== null && cost > 0 && rp !== null) {
        var retPct = rp / cost * 100;
        retTxt = (retPct >= 0 ? '+' : '') + fmt(retPct, 1) + '%';
      } else {
        retTxt = '—';
      }
      var retCls = rp !== null ? pctCls(rp) : '';
      var holdTxt = holdText(t);
      var reason = t.reason || NA;
      return '<div class="stp-row">' +
        '<div class="stp-line1">' +
          '<span class="stp-tk">' + esc(tk) + '</span>' +
          '<span class="stp-date">' + esc(dt || NA) + '</span>' +
          '<span class="stp-px">' + esc(entryTxt) + '</span>' +
          '<span class="stp-ret ' + retCls + '">' + esc(retTxt) + '</span>' +
        '</div>' +
        '<div class="stp-reason">原因: ' + esc(reason) +
          (holdTxt ? ' · 持有 ' + esc(holdTxt) : '') + '</div>' +
      '</div>';
    }).join('');

    bodyEl.innerHTML = '<div class="stp-list">' + rows + '</div>' +
      monthSummaryHtml(stops, '按月');
  }

  /* 已止盈记录板块（近 30 天）：只读 portfolio.transactions。
     后端的止盈是「移动止盈 + 保本线」：浮盈后只抬高止损线，触发离场时若
     卖出价 > 入场价记为 Trailing_Profit_Take（见 review._classify_exit_status）。
     筛选 Action=SELL 且 Reason 含 profit take / trailing_profit，按日期降序。
     与「已止损记录」并列，避免止盈离场只藏在流水行里。 */
  function renderProfitTaken() {
    var subEl = $('#profitSub'), bodyEl = $('#profitBody');
    if (!subEl || !bodyEl) return;
    var pf = DATA && DATA.portfolio;
    var ts = (pf && pf.transactions) || [];

    var empty = function (txt) {
      subEl.textContent = '—';
      bodyEl.innerHTML = '<div class="mx"><div class="k">已止盈记录</div>' +
        '<div class="v na">' + txt + '</div></div>';
    };
    if (!ts.length) { empty('暂无止盈记录'); return; }

    var maxDate = '';
    ts.forEach(function (t) {
      var d = String(t.date || '');
      if (d && d > maxDate) maxDate = d;
    });
    var anchor = maxDate ? new Date(maxDate) : null;
    var threshold = anchor ? new Date(anchor.getTime() - 30 * 86400000) : null;

    var takes = ts.filter(function (t) {
      if (String(t.action || '').toUpperCase() !== 'SELL') return false;
      if (!/profit[\s_]*take|trailing_profit/i.test(String(t.reason || ''))) return false;
      if (threshold) {
        var d = new Date(String(t.date || ''));
        if (!isNaN(d.getTime()) && d < threshold) return false;
      }
      return true;
    }).sort(function (a, b) {
      var da = String(a.date || ''), db = String(b.date || '');
      return db > da ? 1 : (db < da ? -1 : 0);
    });

    if (!takes.length) { empty('暂无止盈记录'); return; }

    var n = takes.length, sumPnl = 0, sumRet = 0, counted = 0;
    takes.forEach(function (t) {
      var rp = num(t.realized_pnl), amt = num(t.amount);
      if (rp !== null) sumPnl += rp;
      var cost = (amt !== null && rp !== null) ? (amt - rp) : null;
      if (cost !== null && cost > 0) { sumRet += rp / cost * 100; counted++; }
    });
    var avg = counted ? (sumRet / counted >= 0 ? '+' : '') + fmt(sumRet / counted, 1) + '%' : NA;
    var pnlTxt = (sumPnl >= 0 ? '+$' : '-$') + fmt(Math.abs(sumPnl), 2);
    subEl.textContent = '总计: ' + n + ' 笔 | 合计: ' + pnlTxt + ' | 平均: ' + avg;

    var rows = takes.map(function (t) {
      var tk = t.ticker || NA;
      var dt = String(t.date || '').slice(5);            // YYYY-MM-DD → MM-DD
      if (t.time) dt += ' ' + t.time;
      var rp = num(t.realized_pnl), amt = num(t.amount);
      var entryP = num(t.entry_price), exitP = num(t.exit_price);
      var cost = (amt !== null && rp !== null) ? (amt - rp) : (entryP !== null && num(t.shares) ? entryP * num(t.shares) : null);
      var retPct = (cost !== null && cost > 0 && rp !== null) ? rp / cost * 100 : null;
      var pxTxt;
      if (entryP !== null && exitP !== null) {
        pxTxt = '$' + fmt(entryP, 2) + ' → $' + fmt(exitP, 2);
      } else {
        pxTxt = (num(t.price) === null ? NA : '$' + fmt(num(t.price), 2));
      }
      var retTxt = retPct === null ? NA :
        (retPct >= 0 ? '+' : '') + fmt(retPct, 1) + '%';
      var holdTxt = holdText(t);
      var metaTxt = [];
      if (holdTxt) metaTxt.push('持有 ' + holdTxt);
      if (rp !== null) metaTxt.push((rp >= 0 ? '+' : '') + '$' + fmt(rp, 2));
      metaTxt.push(t.reason || NA);
      return '<div class="stp-row pt">' +
        '<div class="stp-line1">' +
          '<span class="stp-tk">' + esc(tk) + '</span>' +
          '<span class="stp-date">' + esc(dt || NA) + '</span>' +
          '<span class="stp-px">' + esc(pxTxt) + '</span>' +
          '<span class="stp-ret ' + pctCls(retPct) + '">' + esc(retTxt) + '</span>' +
        '</div>' +
        '<div class="stp-reason">' + esc(metaTxt.join(' · ')) + '</div>' +
      '</div>';
    }).join('');

    bodyEl.innerHTML = '<div class="stp-list">' + rows + '</div>' +
      monthSummaryHtml(takes, '按月');
  }

  /* 交易观测面板：只读 portfolio.trade_stats（dashboard_export 计算，前端绝不重算）。
     边界：
       · trade_stats 缺失 / null → 隐藏整块（不渲染、不报错）
       · 无交易（买+卖均 0）→ 显「暂无交易记录」
       · 平仓样本 < 10 → 胜率显「样本不足」（不显示数字）
       · 不依赖本地时钟（锚点取交易流水最新日期，由后端算好） */
  function renderTradeStats() {
    var subEl = $('#tradeSub'), bodyEl = $('#tradeBody');
    if (!subEl || !bodyEl) return;
    var pf = DATA && DATA.portfolio;
    var ts = pf && pf.trade_stats;

    // 缺失 / null → 隐藏整块
    if (!pf || !ts) {
      var card = (typeof subEl.closest === 'function') ? subEl.closest('.card') : null;
      if (card && card.style) card.style.display = 'none';
      return;
    }

    var total = (ts.total_buys || 0) + (ts.total_sells || 0);
    if (total === 0) {
      subEl.textContent = '频率 · 胜率 · 盈亏（观测）';
      bodyEl.innerHTML = '<div class="mx"><div class="k">交易观测</div>' +
        '<div class="v na">暂无交易记录</div></div>';
      return;
    }

    var b7 = ts.buys_last_7d || 0, b30 = ts.buys_last_30d || 0;
    var s7 = ts.sells_last_7d || 0, s30 = ts.sells_last_30d || 0;
    var tb = ts.total_buys || 0, tso = ts.total_sells || 0;
    var closed = ts.closed_count || 0, wins = ts.wins || 0;

    // 胜率：样本(<10 平仓) → 「样本不足」；否则整数百分比 + (wins/closed)
    var wr = closed < 10 ? '样本不足' : (ts.win_rate != null ? Math.round(ts.win_rate) + '%' : '—');
    var wrDetail = closed < 10 ? '' : ' (' + wins + '/' + closed + ')';
    var winPct = ts.avg_win_pct != null ? '+' + fmt(ts.avg_win_pct, 1) + '%' : '—';
    var lossPct = ts.avg_loss_pct != null ? fmt(ts.avg_loss_pct, 1) + '%' : '—';
    var hold = ts.avg_holding_days != null ? fmt(ts.avg_holding_days, 1) + ' 天' : '—';
    var rp = ts.total_realized_pnl;
    var rpTxt = rp != null ? (rp >= 0 ? '+$' : '-$') + fmt(Math.abs(rp), 0) : '—';
    var rpCls = rp != null ? (rp >= 0 ? 'up' : 'down') : '';

    subEl.textContent = '频率 · 胜率 · 盈亏（观测）';
    bodyEl.innerHTML =
      '<div class="ts-grid">' +
        '<div class="ts-row"><span class="ts-k">最近 7 天</span><span class="ts-v">买 ' + b7 + ' · 卖 ' + s7 + '</span></div>' +
        '<div class="ts-row"><span class="ts-k">最近 30 天</span><span class="ts-v">买 ' + b30 + ' · 卖 ' + s30 + '</span></div>' +
        '<div class="ts-row"><span class="ts-k">历史总计</span><span class="ts-v">买 ' + tb + ' · 卖 ' + tso + '</span></div>' +
      '</div>' +
      '<div class="ts-div"></div>' +
      '<div class="ts-grid">' +
        '<div class="ts-row"><span class="ts-k">胜率</span><span class="ts-v">' + wr + wrDetail + '</span></div>' +
        '<div class="ts-row"><span class="ts-k">平均盈利</span><span class="ts-v up">' + winPct + '</span></div>' +
        '<div class="ts-row"><span class="ts-k">平均亏损</span><span class="ts-v down">' + lossPct + '</span></div>' +
        '<div class="ts-row"><span class="ts-k">平均持仓</span><span class="ts-v">' + hold + '</span></div>' +
        '<div class="ts-row"><span class="ts-k">累计盈亏</span><span class="ts-v ' + rpCls + '">' + rpTxt + '</span></div>' +
      '</div>';
  }

  /* Equity Curve：横轴日期、纵轴 Total Equity，起点恒为 $50,000 */
  function drawPortfolioCurve(pf) {
    var cv = document.getElementById('pfCurve');
    if (!cv || typeof cv.getContext !== 'function') return;
    var curve = pf.equity_curve || [];
    var dpr = window.devicePixelRatio || 1;
    var w = cv.clientWidth || 600, h = 180;
    cv.width = w * dpr; cv.height = h * dpr;
    var g = cv.getContext('2d');
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);

    var pts = [];
    curve.forEach(function (c) { var v = num(c.total_equity); if (v != null) pts.push(v); });
    if (!pts.length) return;

    var pad = 26, base = num(pf.initial_capital) || 50000;
    var min = Math.min.apply(null, pts.concat([base]));
    var max = Math.max.apply(null, pts.concat([base]));
    if (max - min < 1) { max = min + 1; }
    var span = max - min;
    var X = function (i) { return pad + (pts.length === 1 ? (w - 2 * pad) / 2 : i * (w - 2 * pad) / (pts.length - 1)); };
    var Y = function (v) { return h - pad - (v - min) / span * (h - 2 * pad); };

    // 初始本金基准线 $50,000
    g.strokeStyle = 'rgba(148,163,184,.45)';
    g.setLineDash([4, 4]);
    g.beginPath(); g.moveTo(pad, Y(base)); g.lineTo(w - pad, Y(base)); g.stroke();
    g.setLineDash([]);
    g.fillStyle = 'rgba(148,163,184,.85)';
    g.font = '10px system-ui,sans-serif';
    g.fillText('$' + fmt(base, 0), 2, Y(base) - 3);

    // 净值折线
    var last = pts[pts.length - 1];
    var color = last >= base ? '#ef4444' : '#22c55e';   // 涨红跌绿（中国习惯）
    g.strokeStyle = color; g.lineWidth = 2;
    g.beginPath();
    pts.forEach(function (v, i) { var x = X(i), y = Y(v); i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.stroke();

    pts.forEach(function (v, i) {
      g.fillStyle = color; g.beginPath(); g.arc(X(i), Y(v), 2.2, 0, Math.PI * 2); g.fill();
    });

    g.fillStyle = color;
    g.font = '11px system-ui,sans-serif';
    g.fillText('$' + fmt(last, 2), Math.min(X(pts.length - 1) + 4, w - 58), Y(last) - 6);
    g.fillStyle = 'rgba(148,163,184,.9)';
    g.fillText(esc((curve[0] || {}).date || ''), pad, h - 8);
    g.fillText(esc((curve[curve.length - 1] || {}).date || ''), w - pad - 52, h - 8);
  }

  /* ---------------- Quant / 量化研究 ---------------- */
  /* 数据来源：dashboard_data.json 的 quant 键（由 dashboard_export.build_quant 输出）。
     前端只做研究状态展示：无真实数据时只显示 NOT_ENOUGH_DATA / DISABLED / NOT_READY 徽章，
     绝不渲染任何伪造的 IC / Sharpe / Return / Win Rate / 因子得分 / 权重等数字。 */

  /* 状态徽章：中性 / 语义化颜色，绝不使用涨跌红绿表达 Quant 状态 */
  function qBadgeCls(s) {
    switch (s) {
      case 'NOT_ENOUGH_DATA': return 'q-notenough';
      case 'DISABLED': return 'q-disabled';
      case 'SHADOW_DISABLED': return 'q-disabled';
      case 'NOT_READY': return 'q-notready';
      case 'V1_ACTIVE': return 'q-active';
      case 'PRODUCTION_ACTIVE': return 'q-active';
      case 'RESEARCH': return 'q-research';
      case 'PROMISING': return 'q-promising';
      case 'OK': return 'q-ok';
      case 'DATA_AVAILABLE': return 'q-ok';
      default: return 'q-disabled';
    }
  }
  function qBadge(s) {
    if (!s) return '';
    return '<span class="q-badge ' + qBadgeCls(s) + '">' + esc(s) + '</span>';
  }
  function qCell(k, inner) {
    return '<div class="mx"><div class="k">' + k + '</div><div class="v">' + inner + '</div></div>';
  }
  function qChips(items) {
    if (!items || !items.length) return '';
    return '<div class="q-chips">' + items.map(function (it) {
      return '<span class="q-chip">' + esc(it) + '</span>';
    }).join('') + '</div>';
  }

  function qPhaseCard(p) {
    if (!p) return '';
    var body = '';
    switch (p.phase) {
      case 1: // Factor Library
        body = qChips((p.factors || []).map(function (f) { return f.label; })) +
          '<div class="q-sub">' + (p.factor_count || 0) + ' 个扩展因子 · snapshot ' +
          (p.snapshot_rows > 0 ? (p.snapshot_rows + ' 行') : '无数据') + '</div>';
        break;
      case 2: // Backtest
        body = qChips((p.horizons || []).map(function (h) { return h.label; })) +
          '<div class="q-sub">' + (p.factors || NA) + ' 个因子 × 3 个持有期</div>';
        break;
      case 3: // Validation
        body = '<div class="q-sub">' + esc(p.combo_label || NA) +
          '（' + (p.combos == null ? NA : p.combos) + ' 行）</div>';
        break;
      case 4: // Quant Score 2.0
        body = qChips((p.models || []).map(function (m) { return m.label; })) +
          (p.note ? '<div class="q-note">' + esc(p.note) + '</div>' : '');
        break;
      case 5: // Walk-Forward / OOS
        body = qChips((p.models || []).map(function (m) { return m.label; }));
        break;
      case 6: // Shadow Mode
        body = (p.note ? '<div class="q-note">' + esc(p.note) + '</div>' : '');
        break;
      case 7: // Production Governance
        body = '<div class="q-prod">' +
          '<span class="q-prod-item">' + esc(p.active_version || NA) + ' ' + qBadge(p.status) + '</span>' +
          '<span class="q-prod-item">V2 ' + qBadge(p.v2_status) + '</span>' +
          '<span class="q-prod-item">Gate ' + qBadge(p.production_gate) + '</span>' +
          '</div>' + (p.note ? '<div class="q-note">' + esc(p.note) + '</div>' : '');
        break;
    }
    return '<div class="q-phase">' +
      '<div class="q-phase-h">' +
        '<span class="q-phase-t">Phase ' + p.phase + ' · ' + esc(p.label || '') + '</span>' +
        qBadge(p.status) +
      '</div>' + body + '</div>';
  }

  function renderQuant() {
    var q = QUANT || {};
    var sumEl = $('#quantSummary'), phEl = $('#quantPhases');
    if (!sumEl) return;

    if (!q || typeof q !== 'object' || !q.production) {
      sumEl.innerHTML = '<div class="mx"><div class="k">Quant 状态</div>' +
        '<div class="v na">尚未接入（dashboard_data.json 缺少 quant 键）</div></div>';
      if (phEl) phEl.innerHTML = '';
      return;
    }

    var prod = q.production || {};
    var shadow = q.shadow || {};

    // --- 概览：Quant Status ---
    var cells = '';
    cells += qCell('Current Production Model',
      '<b class="q-model">' + esc(prod.active_version || NA) + '</b> ' + qBadge(prod.status));
    cells += qCell('Quant V2', qBadge(prod.v2_enabled ? 'ENABLED' : 'DISABLED'));
    cells += qCell('Production Gate', qBadge(prod.production_gate || NA));
    cells += qCell('Shadow', qBadge(shadow.status || 'DISABLED'));
    cells += qCell('Data Availability', qBadge(q.data_availability || 'NOT_ENOUGH_DATA'));
    sumEl.innerHTML = '<div class="matrix">' + cells + '</div>' +
      (q.note ? '<div class="q-note">' + esc(q.note) + '</div>' : '');

    // --- Phase 1–7 列表 ---
    if (phEl) {
      var keys = ['factor_lab', 'backtest', 'validation', 'score_v2', 'walk_forward', 'shadow', 'production'];
      var html = '';
      keys.forEach(function (k) { if (q[k]) html += qPhaseCard(q[k]); });
      phEl.innerHTML = html;
    }
  }

  function renderDashboard(data) {
    normalize(data);
    hideBoot();

    renderHeader();
    renderRuntime();
    renderGmBar();
    renderGlobal();
    renderMarketIndicators();
    /* Review 复盘 KPI + History 跟踪趋势：重新联动 review.records[] / history[]，
       数据仍由 dashboard_export.py 从 review_history.csv 原样展开，前端不重算。 */
    renderReview();
    renderOptions(OPTIONS, $('#optHomeList'), true);
    renderHistory();
    renderTarget();
    renderPortfolio();
    renderStopped();
    renderProfitTaken();
    renderTradeStats();
    renderQuant();
    renderNews();
    renderMacro();
    renderSkillSerenity();
    drawAllSparks();

    console.info('[Dashboard] loaded ' + DATA_URL +
      ' · Options ' + OPTIONS.length + ' · Market ' + MARKET.assets.length +
      ' · History ' + HISTORY.length + ' · ReviewRecords ' + REVIEWS.length +
      ' · network=' + (META.network_status || 'n/a'));

    window.IT = {
      data: DATA, stocks: STOCKS, market: MARKET, options: OPTIONS,
      review: REVIEW, reviews: REVIEWS, history: HISTORY, reload: boot, open: openDetail
    };

    /* 每 60 秒自动刷新 Runtime 状态（只更新 runtimes，不整页 reload）*/
    if (!window.__runtimeTimer) {
      window.__runtimeTimer = setInterval(refreshRuntime, 60000);
    }
  }

  /* ---------------- 金融新闻板块（市场流 + 个股联动，Q6 混合方案）---------------- */
  /* 数据来源：DATA.news（dashboard_export.py 从 news_data.json 嵌入 dashboard_data.json）。
     不参与 60s runtime 刷新，仅整页加载时渲染一次。null / 空 → 显示「暂无新闻」不报错。 */
  function renderNews() {
    var news = DATA && DATA.news;
    var mEl = $('#newsMarket'), tEl = $('#newsTickers'), uEl = $('#newsUpdated');
    if (!mEl || !tEl) return;

    if (!news) {
      mEl.innerHTML = '<div class="na">暂无新闻（数据尚未生成）</div>';
      tEl.innerHTML = '';
      return;
    }
    if (uEl) {
      var g = news.generated_at || '';
      uEl.textContent = g ? ('更新 ' + g.replace('T', ' ').replace('Z', ' UTC')) : '';
    }
    if (news.error) {
      mEl.innerHTML = '<div class="na">新闻暂不可用：' + esc(news.error) + '</div>';
      tEl.innerHTML = '';
      return;
    }

    /* 市场流：top 10（过滤无市场影响的条目 + 砍掉中性情绪） */
    var m = (news.market_news || []).filter(isNewsVisible);
    if (!m.length) {
      mEl.innerHTML = '<div class="na">暂无相关市场新闻</div>';
    } else {
      mEl.innerHTML = '<div class="news-sub">📡 市场动态</div>' +
        m.slice(0, 10).map(newsRow).join('');
    }

    /* 持仓联动：只显示当前持仓 ticker（news.positions），空仓显示「暂无持仓」 */
    var tk = news.ticker_news || {};
    var positions = news.positions || [];
    if (!positions.length) {
      tEl.innerHTML = '<div class="news-sub">🏷️ 持仓 / 推荐联动</div>' +
        '<div class="na">暂无持仓</div>';
      return;
    }
    var pool = {};
    STOCKS.forEach(function (s) { if (s.ticker) pool[String(s.ticker).toUpperCase()] = (s.bucket || ''); });
    tEl.innerHTML = '<div class="news-sub">🏷️ 持仓 / 推荐联动</div>' + positions.map(function (sym) {
      var list = (tk[sym] || []).filter(isNewsVisible);
      var on = pool[sym] ? ' news-ticker-on' : '';
      var body = list.length
        ? list.slice(0, 5).map(newsRow).join('')
        : '<div class="na">暂无</div>';
      var tag = pool[sym] ? ' <span class="news-tag">' + esc(pool[sym]) + '</span>' : '';
      return '<div class="news-ticker' + on + '"><div class="news-ticker-h">' +
        esc(sym) + tag + '</div>' + body + '</div>';
    }).join('');
  }

  /* ---------------- 美股宏观板块（经济数据 + 重要人物讲话）---------------- */
  /* 数据来源：DATA.macro（dashboard_export.py 从 macro_data.json 嵌入 dashboard_data.json）。
     由 scan.py 在 ENABLE_MACRO_PANEL=1 时生成；未开启 / 缺失 → 显示「尚未开启」，不报错。 */
  function renderMacro() {
    var m = MACRO;
    var wrap = $('#macroBody');
    var sub = $('#macroSub');
    if (!wrap) return;

    if (!m) {
      wrap.innerHTML = '<div class="na">宏观板块尚未开启（scan 未生成 macro_data.json）。' +
        '开启 ENABLE_MACRO_PANEL=1 后自动出现。</div>';
      return;
    }
    if (sub) {
      var g = m.generated_at || '';
      sub.textContent = g ? ('更新 ' + g.replace('T', ' ').replace('Z', ' UTC')) : '';
    }
    if (m.error) {
      wrap.innerHTML = '<div class="na">宏观数据暂不可用：' + esc(String(m.error)) + '</div>';
      return;
    }

    var econ = m.economic || [];
    var spk = m.speakers || [];

    var econHtml = '<div class="news-sub">📊 经济数据</div>';
    if (!econ.length) {
      econHtml += '<div class="na">暂无经济数据</div>';
    } else {
      econHtml += '<div class="macro-econ-grid">' + econ.map(macroEconCard).join('') + '</div>';
      var cpiItem = econ.find(function (e) { return e.indicator === 'CPI'; });
      if (cpiItem && num(cpiItem.value) !== null) {
        var cpiVal = num(cpiItem.value);
        var cpiConclusion = cpiVal >= 4 ? '通胀显著偏高 —— 利率环境承压，估值扩张受限'
          : cpiVal > 3 ? '通胀偏高 —— 宏观利率环境承压，限制估值扩张'
          : cpiVal >= 2 ? '通胀温和 —— 处于目标区间附近，对估值中性'
          : '通胀偏低 —— 利好久期资产，警惕需求走弱';
        econHtml += '<div class="mi-conclusion" style="font-size:12px;color:#d97706;margin-top:4px;">' + esc(cpiConclusion) + '</div>';
      }
    }

    var spkHtml = '<div class="news-sub" style="margin-top:10px">🎙️ 重要人物讲话</div>';
    if (!spk.length) {
      spkHtml += '<div class="na">暂无重要讲话</div>';
    } else {
      spkHtml += spk.map(macroSpeakerCard).join('');
    }

    wrap.innerHTML = econHtml + spkHtml;
  }


  /* ---------------- 市场情绪指标板块（F&G + FedWatch；数据来自 DATA.market_indicators）---------------- */
  /* flag 关 / 文件缺失 → dashboard_export 不注入 market_indicators → 读不到 → 隐藏整块（与现在逐字节一致）。
     不调用任何 AI；纯展示从 market_indicators.json 透传的行情 / 概率数据。 */
  function miBandClass(score) {
    var v = num(score);
    if (v === null) return 'mi-neutral';
    if (v < 25) return 'mi-fear-extreme';
    if (v < 45) return 'mi-fear';
    if (v <= 55) return 'mi-neutral';
    if (v < 75) return 'mi-greed';
    return 'mi-greed-extreme';
  }

  /* 市场情绪指标：中文映射（**纯展示层** —— 后端 JSON 保持英文原值不动，避免改契约）
     注意：真实数据是小写（neutral / extreme fear / greed），测试 fake 用大写（Greed / Fear），
     因此查表前必须 toLowerCase()；未命中一律回退原值，绝不吞数据。
     另注：配色走 miBandClass() 的**数值**阈值，与语言无关 —— 切勿翻译 CSS 类名。 */
  var MI_RATING_CN = {
    'extreme fear': '极度恐惧',
    'fear': '恐惧',
    'neutral': '中性',
    'greed': '贪婪',
    'extreme greed': '极度贪婪'
  };
  var MI_SUB_CN = {
    'market_momentum_sp500': '标普动能',
    'stock_price_strength': '股价强度',
    'stock_price_breadth': '股价广度',
    'put_call_options': '看跌/看涨期权',
    'market_volatility_vix': '市场波动(VIX)',
    'junk_bond_demand': '垃圾债需求',
    'safe_haven_demand': '避险需求'
  };
  function miRatingCN(r) {
    if (r === null || r === undefined || r === '') return '';
    return MI_RATING_CN[String(r).trim().toLowerCase()] || String(r);
  }
  function miSubCN(k) {
    if (k === null || k === undefined || k === '') return '';
    return MI_SUB_CN[String(k).trim().toLowerCase()] || String(k);
  }
  /* 一组 FedWatch 概率条（key = hold / cut_Nbp / hike_Nbp）。抽出以便多会议复用。 */
  function miProbsBars(probs) {
    return '<div class="mi-bars">' + Object.keys(probs).map(function (k) {
      var val = num(probs[k]) || 0;
      var label = k.replace('cut_', '降息 ').replace('hike_', '加息 ').replace('bp', 'bp').replace('_', ' ');
      var cls = k.indexOf('cut') === 0 ? 'mi-cut' : (k.indexOf('hike') === 0 ? 'mi-hike' : 'mi-hold');
      return '<div class="mi-bar-row">' +
        '<span class="mi-bar-label">' + esc(label) + '</span>' +
        '<span class="mi-bar-track"><span class="mi-bar-fill ' + cls + '" style="width:' + val.toFixed(1) + '%"></span></span>' +
        '<span class="mi-bar-val">' + val.toFixed(1) + '%</span>' +
        '</div>';
    }).join('') + '</div>';
  }

  function renderMarketIndicators() {
    var mi = DATA && DATA.market_indicators;
    var card = $('#marketIndicatorsCard');
    var body = $('#marketIndicatorsBody');
    if (!card || !body) return;
    if (!mi) {
      card.style.display = 'none';
      return;
    }
    card.style.display = 'block';

    var html = '';
    var fg = mi.fear_greed;
    var fw = mi.fedwatch;

    // ---- F&G：环形图（复用 ring，按 score 自动配色）+ 5 档文字标签 ----
    html += '<div class="mi-block">';
    html += '<div class="mi-title">🌡️ CNN 恐惧贪婪指数</div>';
    if (fg && num(fg.score) !== null) {
      var v = num(fg.score);
      html += '<div class="mi-fg">';
      html += ring(v, 84, miRatingCN(fg.rating));
      html += '<div class="mi-fg-meta">';
      html += '<span class="mi-band ' + miBandClass(v) + '">' + esc(fg.rating ? miRatingCN(fg.rating) : NA) + '</span>';
      if (fg.timestamp) {
        html += '<span class="mi-ts">' + esc(String(fg.timestamp).replace('T', ' ').replace('Z', ' UTC')) + '</span>';
      }
      html += '</div>';
      if (fg.subindicators && Object.keys(fg.subindicators).length) {
        html += '<div class="mi-sub">';
        html += Object.keys(fg.subindicators).map(function (k) {
          var s = fg.subindicators[k] || {};
          return '<span class="mi-sub-item"><b>' + esc(miSubCN(k)) + '</b> ' +
            (num(s.score) === null ? NA : num(s.score).toFixed(1)) +
            ' <em class="' + miBandClass(s.score) + '">' + esc(s.rating ? miRatingCN(s.rating) : '') + '</em></span>';
        }).join('');
        html += '</div>';
      }
      html += '</div>';
    } else {
      html += '<div class="na">暂不可用</div>';
    }
    html += '</div>';

    // ---- FedWatch：FOMC 会议（最多 N 次）+ 概率条形图（hold / cut_Nbp / hike_Nbp）----
    // 新后端给 fw.meetings[]；旧后端只有 next_meeting + probabilities → 回退成单会议。
    html += '<div class="mi-block">';
    html += '<div class="mi-title">🏦 CME FedWatch</div>';
    var fwMeetings = [];
    if (fw) {
      if (fw.meetings && fw.meetings.length) {
        fwMeetings = fw.meetings;
      } else if (fw.next_meeting) {
        fwMeetings = [{ date: fw.next_meeting, probabilities: fw.probabilities }];
      }
    }
    fwMeetings = fwMeetings.filter(function (m) {
      return m && m.probabilities && Object.keys(m.probabilities).length;
    });
    if (fwMeetings.length) {
      var ct = fw.current_target ? ('当前目标区间 ' + esc(fw.current_target)) : '';
      html += fwMeetings.map(function (m, i) {
        return '<div class="mi-fw-meet' + (i ? ' mi-fw-meet-sep' : '') + '">' +
          '<div class="mi-fw-head">' + (i === 0 ? '下次 FOMC：' : '随后 FOMC：') +
          '<b>' + esc(m.date || NA) + '</b>' +
          (i === 0 && ct ? ' <span class="mi-ts">' + ct + '</span>' : '') + '</div>' +
          miProbsBars(m.probabilities) +
          '</div>';
      }).join('');
    } else {
      html += '<div class="na">暂不可用</div>';
    }
    html += '</div>';

    if (mi.error) {
      html += '<div class="mi-err">数据异常：' + esc(JSON.stringify(mi.error)) + '</div>';
    }

    body.innerHTML = html;
  }

  /* ---------------- serenity-skill 持仓供应链分析板块 ----------------
     数据来自 DATA.skill_serenity（dashboard_export 注入；flag 关 / 文件缺失 → 无该键 → 隐藏整块）。
     纯展示：不重算、不调 AI、不改写任何字段。 */
  function ssList(arr, cls) {
    if (!arr || !arr.length) return '';
    return '<ul class="ss-list ' + cls + '">' + arr.map(function (x) {
      return '<li>' + esc(String(x)) + '</li>';
    }).join('') + '</ul>';
  }
  function ssRow(label, val) {
    if (!val) return '';
    return '<div class="ss-row"><span class="ss-k">' + esc(label) + '</span>' +
      '<span class="ss-v">' + esc(String(val)) + '</span></div>';
  }
  /* v2：**研究优先级卡片**（priorities[]）。这是研究排序，不是买入建议。
     v1 的 evidence 折叠块 / business_position / valuation / gaps 等字段 v2 已不再产出。 */
  function renderSkillSerenity() {
    var sk = DATA && DATA.skill_serenity;
    var card = $('#skillSerenityCard');
    var body = $('#skillSerenityBody');
    if (!card || !body) return;
    var list = sk && sk.priorities;
    if (!list || !list.length) {
      card.style.display = 'none';
      return;
    }
    card.style.display = 'block';
    // v2 语义已从「持仓分析」变为「候选池筛选」—— 静态 h2 文案在这里就地纠正
    // （index.html 不在本次改动范围内；测试脚手架的 mock 元素没有 querySelector，故做能力判断）
    var h2 = (card.querySelector ? card.querySelector('h2') : null);
    if (h2) h2.textContent = '🔗 供应链研究优先级';
    var sub = $('#skillSerenitySub');
    if (sub) {
      sub.textContent = 'serenity-skill' + (sk.skill_version ? ' ' + sk.skill_version : '') +
        ' · TOP ' + list.length + ' 研究优先级（非买入建议）' +
        (sk.universe_size ? ' · 候选池 ' + sk.universe_size + ' 只' : '') +
        (sk.asof ? ' · ' + sk.asof : '');
    }
    var offline = String(sk.mode || '').indexOf('offline') === 0;
    var html = '';
    if (offline) {
      html += '<div class="ss-note">⚠️ 离线筛选：AI 仅基于<strong>候选池字段 + serenity 方法论</strong>推理排序，' +
        '<strong>未联网核验</strong>公告 / 财报 / 客户信息；无法核验的内容一律列在「待核验」里。' +
        '<strong>本板块只给研究优先级，不构成买入建议。</strong></div>';
    }
    html += '<div class="ss-grid">' + list.map(function (p) {
      var rank = num(p.priority_rank);
      return '<div class="ss-card">' +
        '<div class="ss-head"><span class="ss-rank">🎯 ' + (rank === null ? '-' : rank) + '</span>' +
        '<b>' + esc(p.ticker || '') + '</b></div>' +
        ssRow('为什么', p.why) +
        ssRow('待核验', p.what_to_verify) +
        '</div>';
    }).join('') + '</div>';
    html += '<div class="ss-foot">仅研究优先级排序，非买入建议' + (offline ? ' · 未联网核验' : '') + '</div>';
    if (sk.error) html += '<div class="ss-bad">数据异常：' + esc(String(sk.error)) + '</div>';
    body.innerHTML = html;
  }

  function macroEconCard(e) {
    if (!e) return '';
    var delta = macroDelta(e.value, e.prev);
    var sent = e.sentiment ? sentIcon(e.sentiment) : '';
    var rationale = (e.sentiment && e.rationale)
      ? '<div class="news-rationale">' + esc(e.rationale) + '</div>' : '';
    var prevTxt = (e.prev != null && e.prev !== '') ? ('前值 ' + esc(String(e.prev))) : '';
    var src = e.source ? (' · ' + esc(e.source)) : '';
    var date = e.date ? (' · ' + esc(String(e.date))) : '';
    return '<div class="macro-econ">' +
      '<div class="macro-econ-h">' + esc(e.indicator || '') + ' ' + sent + '</div>' +
      '<div class="macro-econ-v">' + esc(e.value != null && e.value !== '' ? String(e.value) : '—') +
      (delta ? (' <span class="macro-d ' + delta.cls + '">' + delta.txt + '</span>') : '') + '</div>' +
      '<div class="macro-econ-m">' + prevTxt + src + date + '</div>' +
      rationale +
      '</div>';
  }

  function macroSpeakerCard(s) {
    if (!s) return '';
    var person = s.person ? ('<b class="macro-spk-person">' + esc(s.person) + '</b> ') : '';
    var sent = s.sentiment ? sentIcon(s.sentiment) : '';
    var rationale = (s.sentiment && s.rationale)
      ? '<div class="news-rationale">' + esc(s.rationale) + '</div>' : '';
    var meta = [s.time, s.source, s.age_tag].filter(Boolean).map(esc).join(' · ');
    return '<div class="macro-spk">' +
      '<div class="macro-spk-h">' + person + sent + '</div>' +
      '<div class="macro-spk-c">' + esc(s.content_cn || s.content || '') + '</div>' +
      (meta ? ('<div class="macro-econ-m">' + meta + '</div>') : '') +
      rationale +
      '</div>';
  }

  /* 经济数据 value/prev 均为百分比字符串（如 "3.20%"）；计算方向（百分点），仅展示箭头不重算。
     通胀类 prev=None → 无 delta；利率类 prev 有值 → 显示 ▲/▼ 与差值。 */
  function macroDelta(v, prev) {
    var a = pctNum(v), b = pctNum(prev);
    if (a === null || b === null || b === 0) return null;
    var d = a - b;
    if (Math.abs(d) < 0.005) return { txt: '→', cls: 'na' };
    return { txt: (d > 0 ? '▲' : '▼') + Math.abs(d).toFixed(2) + 'pt', cls: d > 0 ? 'up' : 'down' };
  }

  function pctNum(s) {
    if (s == null || s === '') return null;
    var m = String(s).match(/-?\d+(\.\d+)?/);
    return m ? parseFloat(m[0]) : null;
  }

  function newsRow(x) {
    if (!x || !x.headline) return '';
    var t = fmtBJ(x.datetime);
    var src = x.source ? ' · ' + esc(x.source) : '';
    var url = x.url || '';
    var title = x.headline_cn || x.headline;
    var head = '<a class="news-h" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' +
      esc(title) + '</a>';
    var icon = sentIcon(x.sentiment);
    /* rationale：1 句中文简评（≤30字）；为空则不渲染该行 */
    var rationale = x.rationale
      ? '<div class="news-rationale">' + esc(x.rationale) + '</div>' : '';
    return '<div class="news-item">' + icon + '<span class="news-t">' + esc(t) + '</span>' + head +
      '<span class="news-src">' + src + '</span>' + rationale + '</div>';
  }

  function isMarketRelevant(x) {
    // market_relevant === false → 过滤掉（AI 判定对美股市场无直接或间接影响）；
    // 缺失 / true / 其它值 → 显示（保守，不误删，且向后兼容旧数据）。
    return !x || x.market_relevant !== false;
  }

  function isNewsVisible(x) {
    // 统一可见性：市场相关 且 非中性情绪。砍掉所有 neutral 条目（中性不提供方向信息）。
    // · market_relevant === false → 隐藏；· sentiment === 'neutral' → 隐藏；
    // · 缺失 / true / bullish / bearish → 保留（向后兼容旧数据，缺失情绪不误删）。
    return isMarketRelevant(x) && !(x && x.sentiment === 'neutral');
  }

  function sentIcon(s) {
    if (s === 'bullish') return '<span class="news-sent" title="利好">🟢</span>';
    if (s === 'bearish') return '<span class="news-sent" title="利空">🔴</span>';
    if (s === 'neutral') return '<span class="news-sent" title="中性">⚪</span>';
    return '';
  }

  function fmtBJ(ts) {
    if (!ts) return '';
    try {
      /* 转北京时间 UTC+8：把 epoch 毫秒 +8h 后用 UTC getter 取，即北京本地时间 */
      var bj = new Date(ts * 1000 + 8 * 3600 * 1000);
      function p(n) { return (n < 10 ? '0' : '') + n; }
      return p(bj.getUTCMonth() + 1) + '-' + p(bj.getUTCDate()) + ' ' +
        p(bj.getUTCHours()) + ':' + p(bj.getUTCMinutes());
    } catch (e) { return ''; }
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

    /* 陈旧告警：最新 AI 快照（stocks[].scan_date）距今超过 2 个交易日 -> 顶部横幅。
       复用现有 .notice.err 样式；数据缺失一律不显示，绝不猜测。 */
    (function () {
      var rows = (DATA && DATA.stocks) || [];
      var dates = [];
      for (var i = 0; i < rows.length; i++) {
        var ds = (rows[i] && rows[i].scan_date) ? String(rows[i].scan_date).slice(0, 10) : '';
        if (/^\d{4}-\d{2}-\d{2}$/.test(ds)) dates.push(ds);
      }
      if (!dates.length) return;
      dates.sort();
      var maxDate = dates[dates.length - 1];
      var base = (DATA && DATA.generated_at) ? String(DATA.generated_at).slice(0, 10) : maxDate;
      var md = new Date(maxDate + 'T00:00:00Z'), bd = new Date(base + 'T00:00:00Z');
      if (isNaN(md.getTime()) || isNaN(bd.getTime())) return;
      var days = Math.round((bd - md) / 86400000), biz = 0, cur = md;
      for (var k = 0; k < days; k++) {
        cur = new Date(cur.getTime() + 86400000);
        var wd = cur.getUTCDay();
        if (wd !== 0 && wd !== 6) biz++;
      }
      if (biz <= 2) return;
      var msg = '\u26a0\ufe0f AI \u5206\u6790\u5df2 ' + biz +
                ' \u4e2a\u4ea4\u6613\u65e5\u672a\u66f4\u65b0\uff08\u6700\u65b0\uff1a' +
                maxDate + '\uff09';
      if (META.ai_status === 'partial') {
        msg += '\uff08\u90e8\u5206\u6570\u636e\u6765\u81ea\u7f13\u5b58\u56de\u586b\uff09';
      }
      var box = document.getElementById('aiStaleBanner');
      if (!box) {
        box = document.createElement('div');
        box.id = 'aiStaleBanner';
        box.className = 'notice err';
        var host = document.getElementById('view') || document.body;
        host.insertBefore(box, host.firstChild);
      }
      box.textContent = msg;
    })();
  }

  /* ---------------- 顶部：Scan/Review/Evolve 运行状态（独立字段，绝不互相覆盖） ---------------- */
  function toBeijingTime(iso) {
    if (!iso) return NA;
    var d = new Date(iso);
    if (isNaN(d.getTime())) return NA;
    // 北京时间 = UTC+8，固定无夏令时，不依赖浏览器本地时区
    var bj = new Date(d.getTime() + 8 * 3600 * 1000);
    var p = function (n) { return (n < 10 ? '0' : '') + n; };
    return bj.getUTCFullYear() + '-' + p(bj.getUTCMonth() + 1) + '-' + p(bj.getUTCDate()) +
      ' ' + p(bj.getUTCHours()) + ':' + p(bj.getUTCMinutes()) + ':' + p(bj.getUTCSeconds());
  }

  function renderRuntime() {
    var RT = DATA.runtimes || {};
    function renderOne(key) {
      var entry = RT[key] || {};
      var latest = entry.latest || null;
      var lastSuccess = entry.last_success || null;
      var statusEl = $('#' + key + 'Status');
      var timeEl = $('#' + key + 'RunTime');
      var shaEl = $('#' + key + 'RunSha');

      var status = latest ? latest.status : null;
      var conclusion = latest ? latest.conclusion : null;

      var badge = '', cls = 'rt-nodata', timeText = NA;

      if (!latest) {
        badge = 'NO DATA';
        cls = 'rt-nodata';
      } else if (status === 'in_progress') {
        badge = 'RUNNING';
        cls = 'rt-running';
        timeText = 'Started ' + toBeijingTime(latest.started_at || latest.created_at);
      } else if (status === 'queued' || status === 'pending' || status === 'waiting' || status === 'requested') {
        badge = 'QUEUED';
        cls = 'rt-queued';
        timeText = 'Queued ' + toBeijingTime(latest.created_at);
      } else if (status === 'completed') {
        if (conclusion === 'success') { badge = 'SUCCESS'; cls = 'rt-success'; }
        else if (conclusion === 'failure') { badge = 'FAILED'; cls = 'rt-failed'; }
        else if (conclusion === 'cancelled') { badge = 'CANCELLED'; cls = 'rt-cancelled'; }
        else if (conclusion === 'skipped') { badge = 'SKIPPED'; cls = 'rt-skipped'; }
        else { badge = (conclusion || 'COMPLETED').toUpperCase(); cls = 'rt-skipped'; }
        timeText = 'Last run: ' + toBeijingTime(latest.updated_at);
      } else {
        badge = (status || 'UNKNOWN').toUpperCase();
        cls = 'rt-nodata';
        timeText = toBeijingTime(latest.created_at);
      }

      var sha = (latest && latest.head_sha) || (lastSuccess && lastSuccess.head_sha) || '';
      var runNum = (latest && latest.run_number) ? ('Run #' + latest.run_number) : '';

      if (statusEl) {
        statusEl.textContent = badge;
        statusEl.className = 'rt-status ' + cls;
      }
      if (timeEl) {
        timeEl.textContent = timeText;
        timeEl.title = 'Asia/Shanghai (UTC+8) · latest.status/conclusion 来自 GitHub Actions 原始值';
      }
      if (shaEl) {
        shaEl.textContent = sha ? (sha + (runNum ? '  ·  ' + runNum : '')) : '';
      }
      paintRuntimeModel(key, statusEl);
    }
    renderOne('scan');
    renderOne('review');
    renderOne('evolve');
  }

  /* ---------------------------------------------------------
     运行时模型：让用户一眼看出中转站是否偷换了模型。
     数据来自 dashboard_data.json 的 model_usage（由 clawsocket_compat.py
     在真实 POST 成功那一刻记录 upstream_model，不是我们请求的模型）。
     无记录 / model 为空 → 不渲染任何小字；fallback=true → warn 样式 + ⚠️。
     --------------------------------------------------------- */
  function runtimeModelHtml(kind, id) {
    var mu = (DATA && DATA.model_usage) || {};
    var rec = mu[kind];
    if (!rec || !rec.model) return '';
    var full = String(rec.model);
    var short = full.indexOf('claude-') === 0 ? full.slice(7) : full;   /* claude-fable-5-1 → fable-5-1 */
    return '<span id="' + id + '" class="runtime-model' + (rec.fallback ? ' warn' : '') + '"' +
      ' title="请求 ' + esc(rec.requested || '?') + ' · 实际 ' + esc(full) +
      (rec.fallback ? '（运行时降级）' : '') + '">' +
      (rec.fallback ? '⚠️ ' : '') + esc(short) + '</span>';
  }

  /* 幂等：先摘掉上一次渲染的同一个 id，再插到状态徽章之后（refreshRuntime 每 60 秒会重渲染） */
  function paintRuntimeModel(key, statusEl) {
    if (!statusEl) return;
    var id = 'rtModel' + key.charAt(0).toUpperCase() + key.slice(1);
    var prev = (document.getElementById ? document.getElementById(id) : null);
    if (prev && prev.parentNode) prev.parentNode.removeChild(prev);
    var html = runtimeModelHtml(key, id);
    if (!html || typeof statusEl.insertAdjacentHTML !== 'function') return;
    statusEl.insertAdjacentHTML('afterend', html);
  }

  /* 每 60 秒只刷新 runtime 数据，不整页 reload，不触碰其他页面状态 */
  function refreshRuntime() {
    window.fetch(dataUrl(), { cache: 'no-store' })
      .then(function (res) { return res.ok ? res.json() : Promise.reject(new Error('HTTP ' + res.status)); })
      .then(function (d) {
        if (d && d.runtimes) {
          DATA.runtimes = d.runtimes;
          renderRuntime();
        }
      })
      .catch(function (err) {
        console.warn('[Dashboard] runtime refresh failed:', err && err.message);
      });
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

  /* 状态（市场状态 / 行情状态）：只用 dashboard_data.json 的真实字段，不硬编码、不推测。
     1) market.regime.market —— 真实 Market Regime（来自 pending CSV 的 Market_Regime 列）
     2) 该字段为 null 时（meta.missing_fields 会标记 regime.market），用真实行情状态兜底：
        meta.network_status / market.live_quote_count / market.frozen_outside_session_count / market.total_count */
  function regimeTxt(rg) {
    var src = (rg && rg.source) ? String(rg.source) : 'Market Regime 未提供';
    if (rg && rg.market) {
      return { txt: String(rg.market), title: 'Market Regime · market.regime.market' };
    }
    var live = num(MARKET.live_quote_count), total = num(MARKET.total_count),
        frozen = num(MARKET.frozen_outside_session_count);
    var net = META.network_status ? String(META.network_status) : '';
    var txt = NA;
    if (net && net.toLowerCase() !== 'ok') {
      txt = '网络 ' + net;                                  /* 真实 network_status */
    } else if (total !== null && total > 0 && (live !== null || frozen !== null)) {
      txt = '实时 ' + (live === null ? NA : live) + '/' + total +
        (frozen ? ' · 冻结 ' + frozen : '');                 /* 真实实时 / 冻结计数 */
    }
    return { txt: txt, title: 'Market Regime 为 null（' + src + '）· 此处显示真实行情状态' };
  }

  function renderGmBar() {
    var rg = MARKET.regime || {};
    var date = META.pending_scan_date || (DATA && DATA.generated_at ? DATA.generated_at.slice(0, 10) : NA);
    var rs = regimeTxt(rg);

    var html = '<div class="gm-grid"><div class="gm-cell hero">' +
      '<div class="gm-date">' + date + ' <small>Scan 日期 · 真实数据（非模拟）</small></div>' +
      '<span class="regime" title="' + esc(rs.title) + '"><i></i>' + esc(rs.txt) + '</span>' +
      '<div class="regime-meta">VIX <b>' + nv(rg.vix, 2) + '</b> · Options <b>' + OPTIONS.length + '</b></div>' +
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

  /* Review 里程碑索引 key（normalize 里用 msKey 建 REV_MS 索引，供其它模块复用） */
  function msKey(ticker, recDate, tag) {
    return String(ticker || '') + '|' + String(recDate || '') + '|' + String(tag || '');
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
    // Core 胜率：仅当样本（core_closed_count）≥ 10 时显示真实值；样本不足时显示「—」（不改数值逻辑）。
    var coreWinRate = (r.core_closed_win_rate !== null && (r.core_closed_count || 0) >= 10)
      ? r.core_closed_win_rate : null;
    $('#reviewTiles').innerHTML =
      reviewTile('Core Closed', r.core_closed_count, r.core_closed_count_status, r.core_closed_unresolved) +
      reviewTile('Core Open', r.core_open_count, r.core_open_count_status, r.core_open_unresolved) +
      reviewTile('Actual Active', r.actual_active_count, r.actual_active_count_status, r.actual_active_unresolved) +
      reviewTile('Stop Loss 触发', r.stop_loss_hit_count, 'complete', 0) +
      reviewTile('Core 胜率', coreWinRate, coreWinRate === null ? 'unavailable' : 'complete', 0);

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
    $('#aiScoreTxt').textContent = s.s.aiDisplay != null ? s.s.aiDisplay : nv(s.s.ai, 1);

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
      /* 买入价 = 正式买入价（推荐日真实 Open）；缺失时 nv() 返回 —，不会 NaN/undefined */
      mx('买入价', nv(s.recPrice, 2)) +
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
    var card = t.closest('.poscard');
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
