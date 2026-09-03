#!/usr/bin/env python3
"""
TGV read-only booking diagnostics for TIKUS!.

Goal:
Discover whether TGV exposes movie/session/hall or seat-layout metadata before
any seat is selected or reserved.

This script:
- opens the public TIKUS! movie/showtime path;
- inspects DOM controls and hrefs;
- records network requests/responses whose URLs look related to movie,
  showtime, session, hall, cinema, seat or layout;
- DOES NOT select a seat;
- DOES NOT submit a booking or payment.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, asyncio, re

ROOT=Path(__file__).resolve().parents[1]
DIAG=ROOT/"data/tgv-seat-diagnostics.json"

TGV_HOME="https://www.tgv.com.my/"
TGV_TIKUS="https://www.tgv.com.my/movie/tikus-2026"

ALLOCATED={
    "tgv-tebrau":["Tebrau"],
    "tgv-wangsa-walk":["Wangsa Walk"],
    "tgv-gurney":["Gurney"],
    "tgv-bukit-tinggi":["Bukit Tinggi"],
}
KEYS=("seat","layout","hall","showtime","session","cinema","movie","booking","schedule")

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
        "policy":"read-only pre-seat-selection inspection",
        "moviePage":TGV_TIKUS,
        "allocated":{},
        "networkCandidates":[],
        "sessionLikeElements":[],
        "notes":[
            "No seat is selected.",
            "No booking is submitted.",
            "No payment flow is entered."
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
            low=u.lower()
            if any(k in low for k in KEYS):
                item={"url":u,"status":resp.status,"contentType":resp.headers.get("content-type")}
                try:
                    ct=(item["contentType"] or "").lower()
                    if "json" in ct:
                        txt=await resp.text()
                        item["sample"]=txt[:2500]
                except Exception:
                    pass
                diag["networkCandidates"].append(item)

        page.on("response",capture)

        await safe_goto(page,TGV_TIKUS,diag,"moviePageNavigationWarning")
        diag["pageTitle"]=await page.title()
        diag["finalUrl"]=page.url
        body=await page.locator("body").inner_text()
        html=await page.content()
        diag["bodySample"]=body[:5000]

        # Record cinema matches.
        for cid,names in ALLOCATED.items():
            matched=next((n for n in names if n.lower() in body.lower()),None)
            diag["allocated"][cid]={"cinemaMatched":matched}

        # Record likely actionable controls without clicking.
        for sel in ["a","button","[role='button']"]:
            loc=page.locator(sel)
            count=await loc.count()
            for i in range(min(count,1200)):
                el=loc.nth(i)
                try:
                    txt=(await el.inner_text()).strip()
                    href=await el.get_attribute("href")
                    attrs=await el.evaluate("""e => {
                        const o={}; for (const a of e.attributes) {
                            if (a.name.startsWith('data-') || ['id','class','aria-label'].includes(a.name)) o[a.name]=a.value;
                        } return o;
                    }""")
                except Exception:
                    continue
                hay=(txt+" "+str(href)+" "+json.dumps(attrs)).lower()
                if (re.search(r"\b(?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:am|pm)\b",txt,re.I)
                    or any(k in hay for k in ("showtime","session","ticket","book","cinema"))):
                    diag["sessionLikeElements"].append({
                        "text":txt[:140],"href":href,"attrs":attrs
                    })

        # Scan HTML for obvious IDs.
        patterns=[
            r"session(?:id)?[=:/'\"]+([A-Za-z0-9_-]{4,})",
            r"showtime(?:id)?[=:/'\"]+([A-Za-z0-9_-]{4,})",
            r"cinema(?:id)?[=:/'\"]+([A-Za-z0-9_-]{2,})",
            r"movie(?:id)?[=:/'\"]+([A-Za-z0-9_-]{2,})"
        ]
        ids=[]
        for pat in patterns:
            ids += re.findall(pat,html,re.I)
        diag["sourceIds"]=list(dict.fromkeys(ids))[:300]

        await browser.close()

    # De-dupe
    seen=set(); nc=[]
    for x in diag["networkCandidates"]:
        if x["url"] not in seen:
            seen.add(x["url"]); nc.append(x)
    diag["networkCandidates"]=nc[:200]

    seen=set(); se=[]
    for x in diag["sessionLikeElements"]:
        k=json.dumps(x,sort_keys=True)
        if k not in seen:
            seen.add(k); se.append(x)
    diag["sessionLikeElements"]=se[:250]

    DIAG.write_text(json.dumps(diag,indent=2),encoding="utf-8")
    print("TGV diagnostics complete:",DIAG)

if __name__=="__main__":
    asyncio.run(main())
