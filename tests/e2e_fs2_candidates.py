from playwright.sync_api import sync_playwright
import json
from pathlib import Path

out=Path(os.environ.get("FS2_E2E_OUT", tempfile.mkdtemp(prefix="fs2-e2e-"))); out.mkdir(exist_ok=True)
res={}
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    page=b.new_page(viewport={"width":1600,"height":1000})
    page.goto("http://127.0.0.1:8765/terminal/candidates.html", wait_until="networkidle")
    page.wait_for_timeout(1200)
    res["loaded"]="Snapshot verified" in page.inner_text("#status")
    res["meta"]=page.inner_text("#meta")
    res["initial"]=page.inner_text("#page")
    res["warning"]="RESEARCH ONLY" in page.inner_text("body")
    # company name search
    page.fill("#search","Apple"); page.wait_for_timeout(400)
    res["company_search_count"]=page.locator("#rows tr").count()
    res["company_search_text"]=page.inner_text("#page")
    page.fill("#search","ZZZZNOPE"); page.wait_for_timeout(300)
    res["empty_search"]=page.inner_text("#rows")
    page.fill("#search","")
    # zero handling via page functions
    res["zero_logic"]=page.evaluate("({missing:isMissing(0),shown:fmt(0),nullv:fmt(null),undefinedv:fmt(undefined)})")
    # filter + refresh
    page.select_option("#tier","TIER_1"); page.fill("#search","A"); page.wait_for_timeout(300)
    page.reload(wait_until="networkidle"); page.wait_for_timeout(800)
    res["refresh_defaults"]=(page.input_value("#tier")=="" and page.input_value("#search")=="" and "of 5600" in page.inner_text("#page"))
    # full pagination
    seen=[]; pages=0
    while True:
        rows=page.locator("#rows tr")
        for i in range(rows.count()):
            seen.append(rows.nth(i).locator("td").first.inner_text().strip())
        pages+=1
        if page.locator("#next").is_disabled(): break
        before=page.inner_text("#page"); page.click("#next"); page.wait_for_timeout(50)
        if page.inner_text("#page")==before: break
    res["pages_visited"]=pages
    res["records_seen"]=len(seen)
    res["unique_seen"]=len(set(seen))
    res["duplicates"]=len(seen)-len(set(seen))
    # click detail
    page.click("#prev") if page.locator("#prev").is_enabled() else None
    page.wait_for_timeout(200)
    page.locator("#rows tr").first.click(); page.wait_for_timeout(200)
    res["detail"]=page.locator("#detail").is_visible()
    page.screenshot(path=str(out/"page.png"), full_page=False)
    # stale fallback: abort current version only
    page.route("**/fs2/versions/fs2_v1.4.json", lambda route: route.abort())
    page.reload(wait_until="networkidle"); page.wait_for_timeout(1200)
    res["stale_banner"]=page.inner_text("#banner")
    res["stale_status"]=page.inner_text("#status")
    res["stale_ok"]=("STALE ARCHIVED" in page.inner_text("#banner") and "fs2.v1.3" in page.inner_text("#meta") and "of 5600" in page.inner_text("#page"))
    page.screenshot(path=str(out/"stale.png"), full_page=False)
    # fail closed: manifest unavailable
    page.unroute("**/fs2/versions/fs2_v1.4.json")
    page.route("**/fs2_candidates_manifest.json", lambda route: route.abort())
    page.reload(wait_until="domcontentloaded"); page.wait_for_timeout(800)
    res["fail_closed"]="CANDIDATE SNAPSHOT UNAVAILABLE" in page.inner_text("#status")
    page.screenshot(path=str(out/"fail_closed.png"), full_page=False)
    b.close()
print(json.dumps(res,indent=2))
Path(out/"e2e_result.json").write_text(json.dumps(res,indent=2),encoding="utf-8")
