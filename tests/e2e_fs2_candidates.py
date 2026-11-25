from playwright.sync_api import sync_playwright
import json
from pathlib import Path

out=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_fs23_e2e"); out.mkdir(exist_ok=True)
res={}
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    page=b.new_page(viewport={"width":1600,"height":1000})
    page.goto("http://127.0.0.1:8765/terminal/candidates.html", wait_until="networkidle")
    page.wait_for_timeout(1500)
    res["loaded"]= "Snapshot loaded" in page.inner_text("#status")
    res["meta"]=page.inner_text("#meta")
    res["rows_initial"]=page.locator("#rows tr").count()
    res["total_text"]=page.inner_text("#page")
    res["warning"]="RESEARCH ONLY" in page.inner_text("body")
    # style filter
    page.select_option("#style","VALUE_CANDIDATE"); page.wait_for_timeout(400)
    res["style_count_text"]=page.inner_text("#page")
    page.select_option("#style","")
    # tier
    page.select_option("#tier","TIER_1"); page.wait_for_timeout(400)
    res["tier_count_text"]=page.inner_text("#page")
    page.select_option("#tier","")
    # tradability
    page.select_option("#trad","BLOCKED"); page.wait_for_timeout(400)
    res["trad_count_text"]=page.inner_text("#page")
    page.select_option("#trad","")
    # security type
    page.select_option("#type","ADR"); page.wait_for_timeout(400)
    res["type_count_text"]=page.inner_text("#page")
    page.select_option("#type","")
    # industry
    inds=page.locator("#industry option").count()
    res["industry_options"]=inds
    if inds>1:
        page.select_option("#industry", index=1); page.wait_for_timeout(400)
        res["industry_count_text"]=page.inner_text("#page")
        page.select_option("#industry","")
    # liquidity
    page.select_option("#liq","high"); page.wait_for_timeout(400)
    res["liq_count_text"]=page.inner_text("#page")
    page.select_option("#liq","")
    # search ticker
    page.fill("#search","AAPL"); page.wait_for_timeout(400)
    res["search_rows"]=page.locator("#rows tr").count()
    res["search_total"]=page.inner_text("#page")
    page.locator("#rows tr").first.click(); page.wait_for_timeout(300)
    res["detail"]="AAPL" in page.inner_text("#detail")
    page.fill("#search",""); page.wait_for_timeout(300)
    # sort
    page.click("th[data-sort=ticker]"); page.wait_for_timeout(300)
    first=page.locator("#rows tr").first.inner_text()
    res["sort_first"]=first.split("\t")[0]
    # pagination and uniqueness
    page.click("#next"); page.wait_for_timeout(300)
    res["page2_text"]=page.inner_text("#page")
    res["page2_rows"]=page.locator("#rows tr").count()
    page.screenshot(path=str(out/"candidates_page.png"), full_page=False)
    # failure
    page.route("**/fs2_candidates_v1.json", lambda route: route.abort())
    page.reload(wait_until="domcontentloaded"); page.wait_for_timeout(1200)
    res["failure_status"]=page.inner_text("#status")
    res["failure_ok"]="UNAVAILABLE" in page.inner_text("#status")
    page.screenshot(path=str(out/"candidates_failure.png"), full_page=False)
    b.close()
print(json.dumps(res,indent=2))
Path(out/"e2e_result.json").write_text(json.dumps(res,indent=2),encoding="utf-8")
