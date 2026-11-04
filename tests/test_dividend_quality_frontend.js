"use strict";
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const DQ = require("../dashboard/dividend_quality.js");

const event = (over = {}) => Object.assign({
  ticker: "CAT", event_type: "DECLARED", security_type: "COMMON",
  declared_per_share: 1.63, previous_per_share: 1.51,
  previous_per_share_status: "VERIFIED", increase_per_share: 0.12,
  increase_pct: 8, announcement_date: "2026-06-10", record_date: "2026-07-20",
  payment_date: "2026-08-19", ex_date: null, ex_date_status: "NOT_DISCLOSED_IN_FILING",
  verification_status: "VERIFIED",
  sources: [
    { role: "EXHIBIT", source_type: "SEC Exhibit 99.1", url: "https://www.sec.gov/a", sha256: "a".repeat(64) },
    { role: "PRIMARY", source_type: "SEC Form 8-K", url: "https://www.sec.gov/b", sha256: "b".repeat(64) },
  ]
}, over);

assert.match(DQ.eventHtml(event()), /\$1\.63/);
assert.match(DQ.eventHtml(event()), /\$1\.51/);
assert.match(DQ.eventHtml(event()), /\+8%/);
assert.match(DQ.eventHtml(event()), /公告未披露/);
assert.match(DQ.eventHtml(event({ ticker: "BAC", declared_per_share: 0.32, previous_per_share: null,
  previous_per_share_status: "NOT_DISCLOSED_IN_FILING", increase_per_share: 0.04, increase_pct: 14 })), /\$0\.32/);
assert.doesNotMatch(DQ.eventHtml(event({ ticker: "BAC", previous_per_share: null })), /\$0\.28/);
assert.match(DQ.eventHtml(event({ ticker: "BAC", previous_per_share: null })), /公告未披露/);
assert.match(DQ.eventHtml(event({ sources: [
  { role: "EXHIBIT", source_type: "SEC Exhibit 99.1", url: "https://www.sec.gov/a", sha256: "a".repeat(64) }
]})), /https:\/\/www\.sec\.gov\/a/);
assert.strictEqual(DQ.safeSecUrl("http://www.sec.gov/x"), null);
assert.strictEqual(DQ.safeSecUrl("https://evil.example/x"), null);
assert.strictEqual(DQ.escapeHtml("<script>alert(1)</script>"), "&lt;script&gt;alert(1)&lt;/script&gt;");
assert.match(DQ.eventHtml(event({ ticker: "<img src=x onerror=1>" })), /&lt;img/);
const renderRoot = { innerHTML: "" };
DQ.render({ metadata: { verified_event_count: 2, generated_at: "t" }, events: [event()], exclusions: [] }, renderRoot);
assert.match(renderRoot.innerHTML, /定向样本/);

const data = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "dashboard", "data", "dividend_quality.json"), "utf8"));
assert.strictEqual(data.metadata.scope, "TARGETED_SAMPLE");
assert.strictEqual(data.metadata.verified_event_count, 2);
assert.strictEqual(data.events.length, 2);
assert.strictEqual(data.events.find(e => e.ticker === "BAC").previous_per_share, null);
assert.strictEqual(data.exclusions[0].declared_per_share, 1.75);
assert.ok(!JSON.stringify(data).includes("0.28"));
const actualRoot = { innerHTML: "" };
DQ.render(data, actualRoot);
assert.match(actualRoot.innerHTML, /CAT/);
assert.match(actualRoot.innerHTML, /BAC/);
assert.match(actualRoot.innerHTML, /\$1\.63/);
assert.match(actualRoot.innerHTML, /公告未披露/);
assert.match(actualRoot.innerHTML, /PREFERRED_STOCK_EXCLUDED_FROM_COMMON_DIVIDEND/);
assert.match(actualRoot.innerHTML, /并非完整覆盖/);

const css = fs.readFileSync(path.join(__dirname, "..", "dashboard", "dividend_quality.css"), "utf8");
assert.match(css, /@media\s*\(max-width:\s*760px\)/);

(async () => {
  const root = { innerHTML: "" };
  const oldFetch = global.fetch;
  global.fetch = async () => { throw new Error("network"); };
  await DQ.load(root);
  assert.match(root.innerHTML, /加载失败/);
  global.fetch = oldFetch;
  console.log("dividend quality frontend tests passed");
})();
