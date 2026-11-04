"use strict";
/**
 * Real Chromium E2E for the independent Dividend Quality dashboard section.
 * Starts a local static server; never visits SEC or any external data source.
 */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert");
const { chromium } = require("playwright");

const ROOT = process.cwd();
const OUT = path.join(ROOT, "tests", "artifacts", "dividend-quality-e2e");
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon" };

function serve(req, res) {
  let rel = decodeURIComponent((req.url || "/").split("?")[0]);
  if (rel === "/") rel = "/index.html";
  const file = path.resolve(ROOT, "." + rel);
  if (!file.startsWith(ROOT + path.sep)) { res.writeHead(403); return res.end("forbidden"); }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); return res.end("not found"); }
    res.writeHead(200, { "Content-Type": MIME[path.extname(file)] || "application/octet-stream" });
    res.end(data);
  });
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const server = http.createServer(serve);
  await new Promise(r => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ headless: true });
  const errors = [];

  async function newPage(viewport, mutate) {
    const ctx = await browser.newContext({ viewport });
    const page = await ctx.newPage();
    page.on("pageerror", e => errors.push({ url: page.url(), stack: e.stack || e.message }));
    page.on("console", m => { if (m.type() === "error") errors.push({ url: page.url(), console: m.text() }); });
    if (mutate) await mutate(page);
    await page.goto(base + "/index.html", { waitUntil: "networkidle" });
    return { ctx, page };
  }

  // 1-7: happy path desktop
  const desktop = await newPage({ width: 1440, height: 1000 });
  const page = desktop.page;
  await page.waitForSelector("#dividendQualityRoot .dq-event", { timeout: 15000 });
  const order = await page.evaluate(() => {
    const q = document.getElementById("quantSec");
    const d = document.getElementById("dividendQualitySection");
    return Boolean(q && d && (q.compareDocumentPosition(d) & Node.DOCUMENT_POSITION_FOLLOWING));
  });
  assert.ok(order, "Dividend Quality must follow Quant");

  const section = page.locator("#dividendQualityRoot");
  const cat = section.locator('[data-ticker="CAT"]');
  const bac = section.locator('[data-ticker="BAC"]');
  assert.match(await cat.innerText(), /\$1\.63/);
  assert.match(await cat.innerText(), /\$1\.51/);
  assert.match(await cat.innerText(), /\+8%/);
  assert.match(await bac.innerText(), /\$0\.32/);
  assert.match(await bac.innerText(), /公告未披露/);
  assert.doesNotMatch(await section.innerText(), /\$0\.28/);
  assert.equal(await section.locator(".dq-event").count(), 2);
  assert.equal(await section.locator(".dq-event", { hasText: "公告未披露" }).count(), 2);
  assert.match(await section.locator(".dq-excl-wrap").innerText(), /1\.75/);
  assert.match(await section.locator(".dq-excl-wrap").innerText(), /PREFERRED/);

  const links = section.locator(".dq-source a");
  assert.equal(await links.count(), 4);
  for (let i = 0; i < 4; i++) {
    const href = await links.nth(i).getAttribute("href");
    assert.match(href, /^https:\/\/www\.sec\.gov\//);
  }
  const columnsDesktop = await section.locator(".dq-events").evaluate(el =>
    getComputedStyle(el).gridTemplateColumns.split(" ").length);
  assert.ok(columnsDesktop >= 2, "desktop should use two columns");
  await page.screenshot({ path: path.join(OUT, "desktop.png"), fullPage: true });
  await section.screenshot({ path: path.join(OUT, "desktop-section.png") });
  await desktop.ctx.close();

  // 10: mobile single column and no horizontal overflow
  const mobile = await newPage({ width: 390, height: 844 });
  await mobile.page.waitForSelector("#dividendQualityRoot .dq-event", { timeout: 15000 });
  const mobileInfo = await mobile.page.locator("#dividendQualityRoot .dq-events").evaluate(el => ({
    columns: getComputedStyle(el).gridTemplateColumns.split(" ").length,
    overflow: document.documentElement.scrollWidth - window.innerWidth,
  }));
  assert.equal(mobileInfo.columns, 1, "mobile should use one column");
  assert.ok(mobileInfo.overflow <= 1, "mobile must not overflow horizontally");
  await mobile.page.screenshot({ path: path.join(OUT, "mobile.png"), fullPage: true });
  await mobile.page.locator("#dividendQualitySection").screenshot({ path: path.join(OUT, "mobile-section.png") });
  await mobile.ctx.close();

  // 8: independent failure state
  const failed = await newPage({ width: 1200, height: 900 }, async p => {
    await p.route("**/dashboard/data/dividend_quality.json", route =>
      route.fulfill({ status: 200, contentType: "application/json", body: "not-json" }));
  });
  await failed.page.waitForSelector("#dividendQualityRoot .dq-error", { timeout: 15000 });
  assert.match(await failed.page.locator("#dividendQualityRoot").innerText(), /加载失败/);
  assert.equal(await failed.page.locator("#quantSec").count(), 1);
  await failed.page.screenshot({ path: path.join(OUT, "error.png"), fullPage: true });
  await failed.ctx.close();

  // 9: empty state
  const empty = await newPage({ width: 1200, height: 900 }, async p => {
    await p.route("**/dashboard/data/dividend_quality.json", route =>
      route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ metadata: { verified_event_count: 0 }, events: [], exclusions: [] }) }));
  });
  await empty.page.waitForSelector("#dividendQualityRoot .dq-error", { timeout: 15000 });
  assert.match(await empty.page.locator("#dividendQualityRoot").innerText(), /暂无可核验/);
  await empty.page.screenshot({ path: path.join(OUT, "empty.png"), fullPage: true });
  await empty.ctx.close();

  fs.writeFileSync(path.join(OUT, "console-errors.json"), JSON.stringify(errors, null, 2));
  const moduleErrors = errors.filter(e => /dividend_quality\.js/.test(e.stack || "") || /dividend_quality/.test(e.console || ""));
  assert.equal(moduleErrors.length, 0, "no Dividend Quality browser exception");
  console.log(JSON.stringify({ ok: true, browser: await browser.version(), screenshots: OUT,
    consoleErrors: errors.length, moduleErrors: moduleErrors.length }, null, 2));
  await browser.close();
  server.close();
}

main().catch(e => { console.error(e); process.exit(1); });
