#!/usr/bin/env python3
"""
TGV booking-flow diagnostics v2 for TIKUS!.

The first diagnostic established that TGV exposes a public box-office API and
identified the TIKUS! movie UUID:
  7b2216d1-27d8-479e-b420-8ab157847aa6

This second pass safely advances only into the public BUY NOW / showtime
discovery flow. It does NOT select a seat, reserve a seat, submit a booking or
enter payment.

It captures:
- API request method + POST payload
- JSON responses from api.tgv.com.my
- cinema/date/showtime DOM after BUY NOW
- session/showtime IDs exposed before seat selection
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, asyncio, re

ROOT=Path(__file__).resolve().parents[1]
DIAG=ROOT/"data/tgv-seat-diagnostics.json"

TGV_TIKUS="https://www.tgv.com.my/movie/tikus-2026"
MOVIE_ID="7b2216d1-27d8-479e-b420-8ab157847aa6"

ALLOCATED={
    "tgv-tebrau":["Tebrau"],
    "tgv-wangsa-walk":["Wangsa Walk"],
    "tgv-gurney":["Gurney"],
    "tgv-bukit-tinggi":["Bukit Tinggi"],
}

async def safe_goto(page,url,diag,key):
    try:
        await page.goto(url,wait_until="domcontentloaded",timeout=90000)
    except Exception as exc:
        diag[key]=type(exc).__name__
    await page.wait_for_timeout(5000)

async def main():
    from playwright.async_api import async_playwright
    now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds")
    diag={
        "observedAt":now,
        "policy":"read-only booking discovery; no seat selection",
        "moviePage":TGV_TIKUS,
        "movieId":MOVIE_ID,
        "allocated":{},
        "apiTraffic":[],
        "buyNow":{"clicked":False},
        "sessionLikeElements":[],
        "notes":[
            "BUY NOW may be opened.",
            "Cinema/date/showtime discovery is permitted.",
            "No seat is selected.",
            "No booking or payment is submitted."
        ]
    }

    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        context=await browser.new_context(
            viewport={"width":1440,"height":1100},
            locale="en-MY",
            user_agent="Mozilla/5.0 (compatible; TIKUSPerformanceTracker/1.0)"
        )
        page=await context.new_page()

        async def capture(resp):
            u=resp.url
            if "api.tgv.com.my" not in u:
                return
            req=resp.request
            item={
                "url":u,
                "method":req.method,
                "status":resp.status,
                "contentType":resp.headers.get("content-type"),
                "postData":req.post_data
            }
            try:
                ct=(item["contentType"] or "").lower()
                if "json" in ct:
                    txt=await resp.text()
                    item["sample"]=txt[:12000]
            except Exception:
                pass
            diag["apiTraffic"].append(item)

        page.on("response",capture)

        await safe_goto(page,TGV_TIKUS,diag,"moviePageNavigationWarning")
        diag["pageTitleBefore"]=await page.title()
        diag["urlBefore"]=page.url

        # Click the public BUY NOW CTA. This is before seat selection.
        candidates=[
            page.get_by_text("BUY NOW",exact=True),
            page.get_by_role("button",name=re.compile("buy now",re.I)),
            page.get_by_role("link",name=re.compile("buy now",re.I))
        ]
        clicked=False
        for loc in candidates:
            try:
                if await loc.count() and await loc.first.is_visible():
                    await loc.first.click(timeout=10000)
                    clicked=True
                    break
            except Exception:
                pass
        diag["buyNow"]["clicked"]=clicked
        await page.wait_for_timeout(8000)

        diag["pageTitleAfter"]=await page.title()
        diag["urlAfter"]=page.url
        body=await page.locator("body").inner_text()
        html=await page.content()
        diag["bodyAfterBuySample"]=body[:10000]

        for cid,names in ALLOCATED.items():
            matched=next((n for n in names if n.lower() in body.lower()),None)
            diag["allocated"][cid]={"cinemaMatched":matched}

        # Capture likely controls after BUY NOW without selecting seats.
        for sel in ["a","button","[role='button']","option","label","input"]:
            loc=page.locator(sel)
            count=await loc.count()
            for i in range(min(count,1800)):
                el=loc.nth(i)
                try:
                    txt=(await el.inner_text()).strip() if sel not in ("input",) else ""
                    href=await el.get_attribute("href")
                    val=await el.get_attribute("value")
                    attrs=await el.evaluate("""e => {
                        const o={}; for (const a of e.attributes) {
                            if (a.name.startsWith('data-') || ['id','class','aria-label','name','type'].includes(a.name)) o[a.name]=a.value;
                        } return o;
                    }""")
                except Exception:
                    continue
                hay=(txt+" "+str(href)+" "+str(val)+" "+json.dumps(attrs)).lower()
                if (
                    re.search(r"\b(?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:am|pm)\b",txt,re.I)
                    or any(n.lower() in hay for names in ALLOCATED.values() for n in names)
                    or any(k in hay for k in ("showtime","session","cinema","hall","ticket"))
                ):
                    diag["sessionLikeElements"].append({
                        "tag":sel,"text":txt[:160],"href":href,"value":val,"attrs":attrs
                    })

        # Extract UUIDs and session-ish IDs from current DOM.
        uuids=re.findall(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b",
            html
        )
        diag["sourceUUIDs"]=list(dict.fromkeys(uuids))[:500]

        # If cinema names are present, click only the matching cinema control
        # where obvious. Do not click a showtime.
        diag["cinemaClicks"]=[]
        for cid,names in ALLOCATED.items():
            done=False
            for name in names:
                try:
                    loc=page.get_by_text(re.compile(re.escape(name),re.I))
                    if await loc.count():
                        for j in range(min(await loc.count(),10)):
                            el=loc.nth(j)
                            if await el.is_visible():
                                tag=await el.evaluate("e=>e.tagName")
                                diag["cinemaClicks"].append({"cinemaId":cid,"name":name,"tag":tag,"attempted":True})
                                await el.click(timeout=5000)
                                await page.wait_for_timeout(3000)
                                done=True
                                break
                except Exception as exc:
                    diag["cinemaClicks"].append({"cinemaId":cid,"name":name,"attempted":True,"error":type(exc).__name__})
                if done: break

        # Capture final body after harmless cinema exploration.
        diag["bodyFinalSample"]=(await page.locator("body").inner_text())[:12000]

        await browser.close()

    # De-dupe API traffic by method+url+postData.
    seen=set(); api=[]
    for x in diag["apiTraffic"]:
        k=(x["method"],x["url"],x.get("postData"))
        if k not in seen:
            seen.add(k); api.append(x)
    diag["apiTraffic"]=api[:250]

    seen=set(); elems=[]
    for x in diag["sessionLikeElements"]:
        k=json.dumps(x,sort_keys=True)
        if k not in seen:
            seen.add(k); elems.append(x)
    diag["sessionLikeElements"]=elems[:400]

    DIAG.write_text(json.dumps(diag,indent=2),encoding="utf-8")
    print("TGV v2 diagnostics complete:",DIAG)

if __name__=="__main__":
    asyncio.run(main())
