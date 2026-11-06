(() => {
  const $ = (s, el=document) => el.querySelector(s);
  const $$ = (s, el=document) => [...el.querySelectorAll(s)];
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (v, d=2) => v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? "N/A" : Number(v).toLocaleString(undefined,{maximumFractionDigits:d});
  const chg = v => v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? "N/A" : pct(Number(v)/100);
  const pct = v => v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? "N/A" : (Number(v)*100).toFixed(2)+"%";
  const usd = v => v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? "N/A" : "$"+Number(v).toLocaleString(undefined,{maximumFractionDigits:2});
  let snapshot = null;
  let selected = null;
  let pending = null;
  let apiOnline = false;
  let csrfToken = "";

  const renderKpis = (items, el) => { $(el).innerHTML = items.map(x => `<div class="kpi"><div class="label">${esc(x.label)}</div><div class="value ${x.cls||""}">${x.html ?? esc(x.value)}</div>${x.sub?`<div class="muted">${esc(x.sub)}</div>`:""}</div>`).join(""); };
  const statusPill = s => `<span class="pill ${s==="PASS"?"good":s==="FAIL"?"warn":""}">${esc(s)}</span>`;

  function nav() {
    $$(".tabs button").forEach(b => b.onclick = () => {
      $$(".tabs button").forEach(x => x.classList.toggle("active", x===b));
      $$(".panel").forEach(p => p.classList.toggle("active", p.id===b.dataset.tab));
      window.scrollTo({top:0,behavior:"smooth"});
    });
  }

  function renderDashboard() {
    const s = snapshot, a = s.account, q = s.data_quality;
    $("#asof").textContent = "as of " + (s.generated_at || "").replace("T"," ").slice(0,19);
    $("#dataQuality").textContent = q.status;
    $("#dataQuality").className = "pill " + (q.status === "OK" ? "good" : "warn");
    const vix = (s.macro.assets||[]).find(x => x.symbol === "^VIX");
    const gspc = (s.macro.assets||[]).find(x => x.symbol === "^GSPC");
    renderKpis([
      {label:"Account NAV", value:usd(a.nav), sub:"PAPER-50000"},
      {label:"Cash", value:usd(a.cash), sub:"no margin"},
      {label:"Market regime", value:s.macro.regime?.market || "UNKNOWN", sub:s.macro.regime?.source || ""},
      {label:"VIX / 20D S&P", value:vix?`${fmt(vix.price)} / ${chg(gspc?.change_20d)}`:"N/A", sub:"frozen daily snapshot"},
    ], "#kpis");
    const assets = s.macro.assets || [];
    $("#marketAssets").innerHTML = assets.map(x => `<div class="asset"><span>${esc(x.name||x.symbol)} <small>${esc(x.symbol)}</small></span><span class="${Number(x.change_1d)>=0?"pos":"neg"}">${fmt(x.price)} <small>${x.change_1d==null?"":chg(x.change_1d)}</small></span></div>`).join("") || `<div class="empty">无市场资产数据</div>`;
    $("#marketUpdated").textContent = s.macro.updated_at || "";
    const news = s.news?.items;
    const newsText = !news ? "无新闻快照（不补造）" : typeof news === "string" ? news : JSON.stringify(news).slice(0,800);
    const inds = s.macro.indicators?.items || [];
    const fc = s.macro.forecast?.items || [];
    $("#macroNews").innerHTML = `<div class="list-row"><span>指标</span><strong>${inds.length}/${s.macro.indicators?.count ?? "?"}</strong></div>` +
      inds.slice(0,5).map(x=>`<div class="list-row"><span>${esc(x.name)}</span><strong>${fmt(x.value)} ${esc(x.unit||"")}</strong></div>`).join("") +
      `<div class="list-row"><span>经济事件</span><strong>${fc.length}</strong></div>` +
      fc.slice(0,4).map(x=>`<div class="list-row"><span>${esc(x.indicator)} · ${esc(x.period)}</span><strong>${fmt(x.actual)} vs ${fmt(x.forecast)}</strong></div>`).join("") +
      `<div class="note">${esc(newsText)}</div>`;
    $("#scannerCount").textContent = `${s.scanner.count} tracked`;
    $("#opportunities").innerHTML = (s.scanner.stocks||[]).map(x => `<div class="opp"><div><strong>${esc(x.ticker)}</strong> ${esc(x.name||"")}<div class="muted">${esc(x.recommendation_tag||"")} · ${esc(x.status||"")}</div></div><div style="text-align:right"><strong>${usd(x.current_price ?? x.price)}</strong><div class="${Number(x.change_1d)>=0?"good-text":"bad-text"}">${chg(x.change_1d)}</div></div></div>`).join("") || `<div class="empty">当前没有股票机会快照；不生成占位推荐。</div>`;
  }

  function renderScanner() {
    const stocks = snapshot.scanner.stocks || [];
    $("#stockCount").textContent = `${stocks.length} stocks`;
    const draw = (filter="") => {
      const f = filter.toLowerCase();
      $("#stockRows").innerHTML = stocks.filter(x => !f || `${x.ticker} ${x.name}`.toLowerCase().includes(f)).map(x =>
        `<tr data-t="${esc(x.ticker)}"><td><strong>${esc(x.ticker)}</strong><div class="muted">${esc(x.name||"")}</div></td><td>${usd(x.current_price ?? x.price)}</td><td class="${Number(x.change_1d)>=0?"good-text":"bad-text"}">${chg(x.change_1d)}</td><td>${fmt(x.final_score,1)}</td><td>${fmt(x.rsi,1)}</td><td>${usd(x.stop_loss)}</td><td>${esc(x.status||"")}</td></tr>`).join("") || `<tr><td colspan="7"><div class="empty">无匹配股票</div></td></tr>`;
      $$("#stockRows tr").forEach(tr => tr.onclick = () => { const x = stocks.find(y => y.ticker === tr.dataset.t); if (x) renderDetail(x); });
    };
    draw();
    $("#stockSearch").oninput = e => draw(e.target.value);
  }

  function renderDetail(x) {
    selected = x;
    const a = x.ai || {}, t = x.technical || {};
    $("#stockDetail").innerHTML = `<div class="card-head"><h2>${esc(x.ticker)} · ${esc(x.name||"")}</h2><span class="pill">${esc(x.bucket||"")}</span></div>
      <div class="detail-grid">
        <div><span class="muted">Price</span><br><strong>${usd(x.current_price ?? x.price)}</strong></div>
        <div><span class="muted">Final score</span><br><strong>${fmt(x.final_score,1)}</strong></div>
        <div><span class="muted">Stop</span><br><strong>${usd(x.stop_loss)}</strong></div>
        <div><span class="muted">RSI / ATR%</span><br><strong>${fmt(x.rsi,1)} / ${fmt(x.atr_pct,2)}</strong></div>
        <div><span class="muted">MA20 / MA50</span><br><strong>${fmt(t.ma20)} / ${fmt(t.ma50)}</strong></div>
        <div><span class="muted">Last bar</span><br><strong>${esc(t.last_bar_date||"N/A")}</strong></div>
        <div><span class="muted">PE TTM / PB</span><br><strong>${fmt(x.pe_ttm)} / ${fmt(x.pb)}</strong></div>
        <div><span class="muted">ROE / Revenue growth</span><br><strong>${fmt(x.roe,3)} / ${fmt(x.revenue_growth,3)}</strong></div>
        <div><span class="muted">Market cap</span><br><strong>${usd(x.market_cap)}</strong></div>
      </div>
      <div class="grid two" style="margin-top:12px"><div><h3>Catalysts</h3><p class="muted">${esc(a.catalysts || "No verified catalyst in snapshot.")}</p></div><div><h3>Risks</h3><p class="muted">${esc(a.risks || "No verified risk field in snapshot.")}</p></div></div>
      <div class="grid two"><div><h3>Invalidation</h3><p class="muted">${esc(a.invalidation || "No verified invalidation in snapshot.")}</p></div><div><h3>Valuation / fundamentals</h3><p class="muted">PE forward: ${esc(x.pe_forward ?? "N/A")} · EPS TTM: ${esc(x.eps_ttm ?? "N/A")} · Profit margin: ${esc(x.profit_margin ?? "N/A")}</p></div></div>
      <h3>Style signals</h3><div class="tags">${Object.entries(x.signals||{}).map(([k,v])=>`<span class="tag">${esc(k)}: ${esc(v.status)}</span>`).join("")}</div>
      <p class="note">Industry chain: N/A · per-stock news: N/A · no verified source in snapshot.</p>`;
    const p = $("#orderTicker"); if (p) p.value = x.ticker;
    const price = x.current_price ?? x.price; if (price && $("#orderPrice")) $("#orderPrice").value = Number(price).toFixed(2);
    const asof = x.current_price_updated_at || snapshot.generated_at; if (asof && $("#orderAsof")) $("#orderAsof").value = asof;
  }

  function renderStrategies() {
    $("#strategyCards").innerHTML = snapshot.strategies.map(s => `<article class="card strategy"><h3>${esc(s.name)} ${statusPill(s.status)}</h3><div class="reason">${esc(s.status_reason)}</div>
      <div class="tags"><span class="tag">${esc(s.version)}</span><span class="tag">${esc(s.rebalance)}</span></div>
      <details><summary>规则、成本与证据</summary><p><b>股票池：</b>${esc(s.universe)}</p><p><b>选择：</b>${esc(s.selection)}</p><p><b>买入/卖出：</b>${esc(s.entry)} / ${esc(s.exit)}</p><p><b>调仓/仓位：</b>${esc(s.rebalance)} / ${esc(s.position)}</p><p><b>风险：</b>${esc(s.risk)}</p><p><b>成本：</b>${esc(s.costs)}</p><ul>${s.evidence.map(e=>`<li>${esc(e)}</li>`).join("")}</ul><p class="note">${s.not_claimed.map(esc).join(" · ")}</p></details></article>`).join("");
    $("#benchmarks").innerHTML = snapshot.benchmarks.map(b => `<div class="benchmark"><div><strong>${esc(b.id)}</strong> ${esc(b.name)}<div class="muted">${esc(b.reason||"")}</div></div><span class="status">${esc(b.status)}</span></div>`).join("");
  }

  function renderPortfolio() {
    const a = snapshot.account, p = snapshot.portfolio;
    renderKpis([
      {label:"NAV", value:usd(p.nav), sub:"current"},
      {label:"Cash", value:usd(a.cash), sub:"available"},
      {label:"Realized P&L", value:usd(a.realized_pnl), sub:"ledger"},
      {label:"Pending orders", value:a.pending_order_count, sub:"manual confirmation"},
    ], "#accountKpis");
    $("#positions").innerHTML = (a.positions||[]).length ? a.positions.map(x=>`<div class="list-row"><span>${esc(x.ticker)} <small>${x.shares} sh @ ${usd(x.avg_cost)}</small></span><strong>${usd(x.shares * x.avg_cost)}</strong></div>`).join("") : `<div class="empty">No positions. Cash only.</div>`;
    const orders = a.orders || [];
    $("#orders").innerHTML = orders.length ? orders.map(o=>`<div class="list-row"><span>${esc(o.ticker)} ${esc(o.side)} ${o.shares}<div class="muted">${esc(o.strategy)} · ${esc(o.status)}</div></span><code>${esc(o.order_id)}</code></div>`).join("") : `<div class="empty">No orders.</div>`;
    const h = a.history || [];
    $("#ledger").innerHTML = h.length ? h.map(x=>`<div class="list-row"><span>${esc(x.type||"FILL")} ${esc(x.ticker||"")}</span><span>${usd(x.amount ?? x.net_amount ?? x.cash_delta)}</span></div>`).join("") : `<div class="empty">Append-only ledger is empty.</div>`;
    $("#apiStatus").textContent = apiOnline ? "Local authenticated PAPER API · same-origin" : "Read-only static snapshot · local PAPER API unavailable";
  }

  function renderRisk() {
    const r = snapshot.risk;
    $("#riskStatus").textContent = r.status;
    renderKpis([
      {label:"Cash weight", value:pct(r.cash_weight), sub:"100% = no positions"},
      {label:"Max position", value:pct(r.max_position_weight), sub:"single-name"},
      {label:"Volatility", value:r.volatility_annualized == null ? "N/A" : pct(r.volatility_annualized), sub:"requires return history"},
      {label:"Max drawdown", value:r.drawdown?.max_drawdown == null ? "N/A" : pct(r.drawdown.max_drawdown), sub:"requires NAV history"},
    ], "#riskKpis");
    $("#riskConcentration").innerHTML = (r.top_positions||[]).length ? r.top_positions.map(x=>`<div class="list-row"><span>${esc(x.ticker)}</span><strong>${pct(x.weight)}</strong></div>`).join("") : `<div class="empty">No positions; concentration N/A.</div>`;
    $("#riskCorrelation").innerHTML = `<div class="empty">Correlation and sector concentration require a return history and sector map; marked NOT_AVAILABLE, not zero.</div>`;
    $("#riskWarnings").innerHTML = (r.warnings||[]).map(w=>`<div class="list-row"><span>${esc(w)}</span><span class="warn-text">warning</span></div>`).join("") || `<div class="empty">No warnings.</div>`;
    const invested = r.invested || 0;
    $("#stress").innerHTML = [-0.1,-0.2,-0.3].map(x=>`<div class="list-row"><span>Equity shock ${pct(x)}</span><strong>NAV ${usd(r.nav + invested*x)}</strong></div>`).join("") + `<p class="note">Only current invested exposure is stressed; cash is unchanged. Not a historical VaR.</p>`;
  }

  function renderPerformance() {
    const p = snapshot.portfolio.performance;
    $("#perfStatus").textContent = p.status;
    renderKpis([
      {label:"NAV", value:usd(p.nav), sub:"paper"},
      {label:"Realized", value:usd(p.realized_pnl), sub:"ledger"},
      {label:"Fees", value:usd(p.total_fees), sub:"IBKR model"},
      {label:"Benchmarks", value:"0/4", sub:"current quote availability"},
    ], "#perfKpis");
    $("#navChart").textContent = p.nav_series?.length ? "" : "暂无 NAV 历史；不伪造曲线。";
    $("#perfBenchmarks").innerHTML = (p.benchmarks||[]).map(b=>`<div class="benchmark"><div><strong>${esc(b.id)}</strong><div class="muted">${esc(b.reason||"")}</div></div><span class="status">${esc(b.status)}</span></div>`).join("");
    $("#reviewPanel").innerHTML = `<div class="empty">No closed trades. Review requires a non-empty append-only ledger.</div>`;
  }

  async function load() {
    try {
      const r = await fetch("dashboard/data/invest_terminal_data.json", {cache:"no-store"});
      if (!r.ok) throw new Error("snapshot HTTP "+r.status);
      snapshot = await r.json();
      nav(); renderDashboard(); renderScanner(); renderStrategies(); renderPortfolio(); renderRisk(); renderPerformance();
      const stocks = snapshot.scanner.stocks || [];
      if (stocks.length) renderDetail(stocks[0]);
      await connectLocal();
      if (snapshot.account.orders?.length) {
        const p = snapshot.account.orders.find(o=>o.status==="PENDING");
        if (p) showConfirm(p);
      }
    } catch (e) {
      document.querySelector("main").innerHTML = `<div class="card"><h2>Snapshot unavailable</h2><p class="muted">${esc(e.message)}. No fake data is rendered.</p></div>`;
    }
  }

  async function connectLocal() {
    try {
      const r = await fetch("/api/session", {credentials:"same-origin", cache:"no-store"});
      if (!r.ok) throw new Error("read-only");
      const j = await r.json();
      if (!j.authenticated || !j.csrf_token) throw new Error("read-only");
      apiOnline = true; csrfToken = j.csrf_token;
      applyLocalState(j);
    } catch (e) {
      apiOnline = false; csrfToken = "";
      const el = $("#apiStatus"); if (el) el.textContent = "Read-only static snapshot · local PAPER API unavailable";
    }
  }

  function calcNav(a) {
    const invested = (a.positions||[]).reduce((n,p)=>n + Number(p.shares||0)*Number(p.avg_cost||0), 0);
    return Number(a.cash||0) + invested;
  }

  function applyLocalState(j) {
    const a = {...snapshot.account, ...j.account};
    a.orders = j.orders || []; a.history = j.history || [];
    const tokens = new Map((j.pending_confirmations||[]).map(x=>[x.order_id, x.confirm_token]));
    a.orders = a.orders.map(o => tokens.has(o.order_id) ? {...o, confirm_token:tokens.get(o.order_id)} : o);
    a.pending_order_count = a.orders.filter(o=>o.status==="PENDING").length;
    a.nav = calcNav(a);
    a.account_status = a.account_status || "LOCAL_DB_AVAILABLE";
    snapshot.account = a;
    const positions = a.positions || [];
    const invested = positions.reduce((n,p)=>n + Number(p.shares||0)*Number(p.avg_cost||0), 0);
    snapshot.portfolio.nav = a.nav; snapshot.portfolio.cash = a.cash; snapshot.portfolio.positions = positions;
    snapshot.portfolio.performance = {...(snapshot.portfolio.performance||{}), nav:a.nav, cash:a.cash,
      status: a.history?.length ? "AVAILABLE" : "NO_HISTORY", realized_pnl:a.realized_pnl, total_fees:a.total_fees};
    snapshot.risk = {...(snapshot.risk||{}), cash:a.cash, invested, nav:a.nav,
      cash_weight: a.nav ? Number(a.cash)/a.nav : null,
      max_position_weight: positions.length && a.nav ? Math.max(...positions.map(p=>Number(p.shares)*Number(p.avg_cost)/a.nav)) : null,
      positions: positions.map(p=>({ticker:p.ticker,value:Number(p.shares)*Number(p.avg_cost),weight:a.nav?Number(p.shares)*Number(p.avg_cost)/a.nav:null})),
      top_positions: positions.map(p=>({ticker:p.ticker,value:Number(p.shares)*Number(p.avg_cost),weight:a.nav?Number(p.shares)*Number(p.avg_cost)/a.nav:null})),
      status: positions.length ? "AVAILABLE" : "CASH_ONLY", warnings: positions.length ? [] : ["NO_POSITIONS"]};
    renderDashboard(); renderPortfolio(); renderRisk(); renderPerformance();
  }

  async function refreshLocal() {
    try {
      const r = await fetch("/api/account", {credentials:"same-origin", cache:"no-store"});
      if (!r.ok) throw new Error("read-only");
      applyLocalState(await r.json());
    } catch (e) {
      apiOnline = false;
      const el = $("#apiStatus"); if (el) el.textContent = "Read-only static snapshot · local PAPER API unavailable";
    }
  }

  function showConfirm(order) {
    pending = order;
    const box = $("#confirmBox"); if (!box) return;
    box.hidden = false;
    $("#confirmToken").textContent = `order_id: ${order.order_id} · token: ${order.confirm_token || order.confirmation_token || "(not returned)"}`;
    $("#confirmBtn").onclick = () => confirmOrder(order);
    $("#cancelBtn").onclick = () => cancelOrder(order);
  }
  async function post(path, body) {
    if (!apiOnline || !csrfToken) throw new Error("Read-only mode: local authenticated API is unavailable");
    const r = await fetch(path, {method:"POST", credentials:"same-origin",
      headers:{"Content-Type":"application/json","X-CSRF-Token":csrfToken}, body:JSON.stringify(body)});
    const j = await r.json(); if (!r.ok) throw new Error(j.error || "request failed"); return j;
  }
  async function confirmOrder(order) {
    try { await post("/api/paper/confirm", {order_id:order.order_id, token:order.confirm_token || order.confirmation_token});
      $("#confirmBox").hidden = true; await refreshLocal(); }
    catch(e){ alert(e.message); }
  }
  async function cancelOrder(order) {
    try { await post("/api/paper/cancel", {order_id:order.order_id}); $("#confirmBox").hidden = true; await refreshLocal(); }
    catch(e){ alert(e.message); }
  }
  $("#orderForm").onsubmit = async e => {
    e.preventDefault();
    const body = {client_order_id:"WEB-"+Date.now(), ticker:$("#orderTicker").value.trim().toUpperCase(), side:$("#orderSide").value,
      shares:Number($("#orderShares").value), reference_price:Number($("#orderPrice").value), price_asof:$("#orderAsof").value,
      strategy:$("#orderStrategy").value, price_source:"DASHBOARD_SNAPSHOT", price_type:"LAST"};
    try { const o = await post("/api/paper/propose", body); showConfirm(o); }
    catch(err){ $("#apiStatus").textContent = err.message; }
  };
  load();
})();
