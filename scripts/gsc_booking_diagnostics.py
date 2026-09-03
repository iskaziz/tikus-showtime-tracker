#!/usr/bin/env python3
"""
GSC non-invasive booking diagnostics for TIKUS!.

Why this is conservative:
GSC's own FAQ states that if a customer selects seats and cancels before
payment, those seats can display a Lock symbol and remain locked for 15 minutes.
This collector therefore DOES NOT select seats, reserve seats, or submit a
transaction. It only inspects public showtime/session metadata and network
responses exposed before seat selection.

The first objective is to discover:
- the official GSC TIKUS! movie/showtime route;
- allocated cinema names;
- session buttons/links and any session IDs exposed in DOM/network traffic;
- whether a public seat-layout endpoint is called before a seat is selected.

If a seat layout is exposed read-only, a later collector can count states.
Otherwise, exact GSC seat tracking should use an authorised data source.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, asyncio, re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/"data/current.json"
DIAG = ROOT/"data/gsc-seat-diagnostics.json"

GSC_TIKUS_PAGE = "https://www.gsc.com.my/movie/tikus/"
GSC_SHOWTIMES = "https://epaymentwebapp.gsc.com.my/showtime-by-movies"

ALLOCATED = {
    "gsc-paradigm-jb": ["Paradigm Mall", "Paradigm JB"],
    "gsc-aman-central": ["Aman Central"],
    "gsc-midvalley": ["Mid Valley Megamall", "Mid Valley"],
    "gsc-dataran-pahlawan": ["Dataran Pahlawan"],
    "gsc-kuantan-city-mall": ["Kuantan City Mall"],
    "gsc-ioi-city-mall": ["IOI City Mall"],
    "gsc-imago": ["IMAGO Mall", "Imago"],
    "gsc-the-spring": ["The Spring", "Spring Kuching", "The Spring Shopping Mall"],
}

SEAT_KEYS = ("seat","layout","hall","showtime","session","occupancy","sold","available")
SESSION_PATTERNS = [
    r"session(?:id)?[=:/'\"]+([A-Za-z0-9_-]{4,})",
    r"showtime(?:id)?[=:/'\"]+([A-Za-z0-9_-]{4,})",
    r"transaction(?:id)?[=:/'\"]+([A-Za-z0-9_-]{4,})",
]

async def main():
    from playwright.async_api import async_playwright
    now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds")
    diag={
        "observedAt":now,
        "policy":"read-only pre-seat-selection inspection",
        "moviePage":GSC_TIKUS_PAGE,
        "showtimePage":GSC_SHOWTIMES,
        "allocated":{},
        "networkCandidates":[],
        "notes":[
            "No seat is selected by this collector.",
            "No transaction is created or submitted.",
            "GSC documents that cancelled seat selections can remain locked for 15 minutes."
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

        async def capture_response(resp):
            url=resp.url
            low=url.lower()
            if any(k in low for k in SEAT_KEYS):
                item={"url":url,"status":resp.status,"contentType":resp.headers.get("content-type")}
                try:
                    if "json" in (item["contentType"] or "").lower():
                        txt=await resp.text()
                        item["sample"]=txt[:1800]
                except Exception:
                    pass
                diag["networkCandidates"].append(item)

        page.on("response", capture_response)

        # First resolve the official Buy Tickets link, because the movie ID can change.
        try:
            await page.goto(GSC_TIKUS_PAGE, wait_until="domcontentloaded", timeout=90000)
        except Exception as exc:
            diag["moviePageNavigationWarning"] = type(exc).__name__
        await page.wait_for_timeout(5000)
        buy=None
        for a in await page.locator("a").all():
            try:
                text=(await a.inner_text()).strip()
                href=await a.get_attribute("href")
                if href and ("buy" in text.lower() or "epaymentwebapp.gsc.com.my" in href):
                    buy=href
                    if "epaymentwebapp.gsc.com.my" in href:
                        break
            except Exception:
                pass
        diag["resolvedBuyUrl"]=buy

        if buy:
            if buy.startswith("/"):
                buy="https://www.gsc.com.my"+buy
            try:
                await page.goto(buy, wait_until="domcontentloaded", timeout=90000)
            except Exception as exc:
                diag["buyPageNavigationWarning"] = type(exc).__name__
            await page.wait_for_timeout(5000)
        else:
            try:
                await page.goto(GSC_SHOWTIMES, wait_until="domcontentloaded", timeout=90000)
            except Exception as exc:
                diag["showtimePageNavigationWarning"] = type(exc).__name__
            await page.wait_for_timeout(5000)

        body=await page.locator("body").inner_text()
        html=await page.content()
        diag["pageTitle"]=await page.title()
        diag["finalUrl"]=page.url
        diag["bodySample"]=body[:3500]

        for cid,names in ALLOCATED.items():
            found_name=None
            for name in names:
                if name.lower() in body.lower():
                    found_name=name; break
            entry={"cinemaMatched":found_name,"sessionElements":[]}
            if found_name:
                # Capture nearby clickable controls without clicking.
                for sel in ["a","button","[role='button']"]:
                    loc=page.locator(sel)
                    count=await loc.count()
                    for i in range(min(count,900)):
                        el=loc.nth(i)
                        try:
                            txt=(await el.inner_text()).strip()
                            href=await el.get_attribute("href")
                            data_attrs=await el.evaluate("""e => {
                              const o={}; for (const a of e.attributes) {
                                if (a.name.startsWith('data-') || ['id','class','aria-label'].includes(a.name)) o[a.name]=a.value;
                              } return o;
                            }""")
                        except Exception:
                            continue
                        hay=(txt+" "+str(href)+" "+json.dumps(data_attrs)).lower()
                        # Keep time-shaped controls or elements whose metadata exposes session-like IDs.
                        if re.search(r"\b(?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:am|pm)\b",txt,re.I) or any(k in hay for k in ("session","showtime")):
                            entry["sessionElements"].append({
                                "text":txt[:100],"href":href,"attrs":data_attrs
                            })
                # De-duplicate.
                seen=set(); unique=[]
                for x in entry["sessionElements"]:
                    k=json.dumps(x,sort_keys=True)
                    if k not in seen:
                        seen.add(k); unique.append(x)
                entry["sessionElements"]=unique[:120]
            diag["allocated"][cid]=entry

        # Scan source for session/showtime ids even when buttons are JS-driven.
        ids=[]
        for pat in SESSION_PATTERNS:
            ids += re.findall(pat,html,re.I)
        diag["sourceSessionIds"]=list(dict.fromkeys(ids))[:250]

        await browser.close()

    # Trim duplicate network candidates.
    seen=set(); clean=[]
    for x in diag["networkCandidates"]:
        key=x["url"]
        if key not in seen:
            seen.add(key); clean.append(x)
    diag["networkCandidates"]=clean[:150]
    DIAG.write_text(json.dumps(diag,indent=2),encoding="utf-8")
    print("GSC diagnostics complete:", DIAG)

if __name__=="__main__":
    asyncio.run(main())
