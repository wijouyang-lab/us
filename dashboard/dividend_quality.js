(function (global) {
  "use strict";

  const SEC_HOST = "www.sec.gov";

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function safeSecUrl(value) {
    try {
      const u = new URL(String(value || ""));
      return u.protocol === "https:" && u.hostname === SEC_HOST ? u.href : null;
    } catch (e) { return null; }
  }

  function money(value) {
    return typeof value === "number" && isFinite(value) ? "$" + value.toFixed(2) : null;
  }

  function displayOrMissing(value, missingText) {
    return value == null || value === "" ? missingText : value;
  }

  function statusLabel(status) {
    if (status === "NOT_DISCLOSED_IN_FILING") return "公告未披露";
    return displayOrMissing(status, "未核验");
  }

  function sourceHtml(source) {
    const url = safeSecUrl(source && source.url);
    if (!url) return "";
    const role = escapeHtml(source.role || source.source_type || "SEC");
    const type = escapeHtml(source.source_type || "");
    const sha = escapeHtml(source.sha256 || "");
    return '<li class="dq-source"><a href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">' +
      role + (type ? " · " + type : "") + "</a>" +
      '<code title="SHA-256">' + sha + "</code></li>";
  }

  function eventHtml(event) {
    const sources = (event.sources || []).map(sourceHtml).filter(Boolean).join("");
    const prev = money(event.previous_per_share);
    const prevText = prev || "公告未披露";
    const increase = money(event.increase_per_share);
    const pct = typeof event.increase_pct === "number" ? event.increase_pct : null;
    const incText = increase ? "+" + increase + (pct != null ? " (+" + pct + "%)" : "") : "公告未披露";
    const ex = event.ex_date ? escapeHtml(event.ex_date) : "公告未披露";
    return '<article class="dq-event" data-ticker="' + escapeHtml(event.ticker) + '">' +
      '<div class="dq-event-head"><strong>' + escapeHtml(event.ticker) + "</strong>" +
      '<span class="dq-status">' + escapeHtml(event.verification_status || "UNKNOWN") + "</span></div>" +
      '<div class="dq-grid">' +
      '<div><span>普通股股息</span><b>' + escapeHtml(money(event.declared_per_share) || "—") + "</b></div>" +
      '<div><span>前值</span><b>' + escapeHtml(prevText) + "</b></div>" +
      '<div><span>增幅</span><b>' + escapeHtml(incText) + "</b></div>" +
      '<div><span>公告日</span><b>' + escapeHtml(displayOrMissing(event.announcement_date, "公告未披露")) + "</b></div>" +
      '<div><span>登记日</span><b>' + escapeHtml(displayOrMissing(event.record_date, "公告未披露")) + "</b></div>" +
      '<div><span>支付日</span><b>' + escapeHtml(displayOrMissing(event.payment_date, "公告未披露")) + "</b></div>" +
      '<div><span>除息日</span><b>' + ex + '</b><small>' +
      escapeHtml(event.ex_date ? statusLabel(event.ex_date_status) : "未推算") + "</small></div>" +
      "</div><ul class=\"dq-sources\">" + sources + "</ul></article>";
  }

  function exclusionHtml(item) {
    return '<li class="dq-exclusion"><b>' + escapeHtml(item.ticker) + "</b> " +
      escapeHtml(item.security_type || "PREFERRED") + " · " +
      escapeHtml(money(item.declared_per_share) || "—") + " · " +
      escapeHtml(item.status || "EXCLUDED") + "</li>";
  }

  function render(data, root) {
    const meta = data.metadata || {};
    const events = Array.isArray(data.events) ? data.events : [];
    const exclusions = Array.isArray(data.exclusions) ? data.exclusions : [];
    if (!events.length) {
      root.innerHTML = '<div class="dq-error">暂无可核验的普通股股息事件。</div>';
      return;
    }
    root.innerHTML =
      '<div class="dq-banner"><strong>定向样本</strong> 仅 CAT/BAC 两家定向验证，并非完整覆盖。' +
      '<span>已验证事件：' + escapeHtml(meta.verified_event_count != null ? meta.verified_event_count : events.length) +
      " · 更新：" + escapeHtml(meta.generated_at || "—") + "</span></div>" +
      '<div class="dq-events">' + events.map(eventHtml).join("") + "</div>" +
      (exclusions.length ? '<div class="dq-excl-wrap"><h3>优先股排除项（不计入普通股）</h3><ul>' +
        exclusions.map(exclusionHtml).join("") + "</ul></div>" : "");
  }

  async function load(root) {
    try {
      const res = await fetch("dashboard/data/dividend_quality.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      render(data, root);
    } catch (err) {
      root.innerHTML = '<div class="dq-error">股息质量数据加载失败。请稍后重试。</div>';
    }
  }

  const api = { escapeHtml, safeSecUrl, money, displayOrMissing, statusLabel, eventHtml, render, load };
  global.DividendQuality = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document !== "undefined") {
    const root = document.getElementById("dividendQualityRoot");
    if (root) load(root);
  }
})(typeof window !== "undefined" ? window : globalThis);
