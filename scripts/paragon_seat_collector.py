#!/usr/bin/env python3
"""
Paragon live seat-map collector for TIKUS!

Safe behaviour:
- opens known public Paragon session URLs
- never submits payment
- never confirms a booking
- records only positively identified seat-state counts
- saves raw diagnostic metadata when selectors are not yet confirmed
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, asyncio, re

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/current.json"
DIAG=ROOT/"data/paragon-seat-diagnostics.json"

CANDIDATE_SELECTORS=[
    "[class*='seat']", "[id*='seat']", "img[alt*='seat' i]",
    "[data-seat]", "[data-seat-number]", "button[aria-label*='seat' i]"
]
BOOKED_WORDS=("occupied","booked","sold","unavailable","taken","disabled")
AVAILABLE_WORDS=("available","vacant","free","selectable")

def classify(el):
    text=" ".join(str(el.get(k,"")) for k in ("class","id","aria","title","alt","disabled")).lower()
    if any(w in text for w in BOOKED_WORDS): return "booked"
    if any(w in text for w in AVAILABLE_WORDS): return "available"
    return None

async def inspect_session(page,url):
    await page.goto(url,wait_until="networkidle",timeout=45000)
    body=(await page.locator("body").inner_text())[:12000]
    if "TIKUS" not in body.upper():
        return {"status":"wrong-page-or-expired"}
    diagnostics={"url":url,"title":await page.title(),"selectors":{}}
    observed=[]
    for sel in CANDIDATE_SELECTORS:
        loc=page.locator(sel)
        count=await loc.count()
        diagnostics["selectors"][sel]=count
        for i in range(min(count,700)):
            el=loc.nth(i)
            attrs={}
            for a in ["class","id","aria-label","title","alt","disabled","data-seat","data-seat-number"]:
                try: attrs[a]=await el.get_attribute(a)
                except: attrs[a]=None
            state=classify({
                "class":attrs.get("class"),"id":attrs.get("id"),"aria":attrs.get("aria-label"),
                "title":attrs.get("title"),"alt":attrs.get("alt"),"disabled":attrs.get("disabled")
            })
            if state:
                observed.append((sel,i,state,attrs))
    # Dedupe by strongest seat identifier where available.
    dedup={}
    for sel,i,state,attrs in observed:
        key=attrs.get("data-seat") or attrs.get("data-seat-number") or attrs.get("aria-label") or attrs.get("id") or f"{sel}:{i}"
        dedup[str(key)]={"state":state,"attrs":attrs}
    booked=sum(1 for x in dedup.values() if x["state"]=="booked")
    available=sum(1 for x in dedup.values() if x["state"]=="available")
    diagnostics["classified"]=len(dedup)
    diagnostics["booked"]=booked
    diagnostics["available"]=available
    if booked+available>=20 and booked>0 and available>0:
        return {"status":"verified","booked":booked,"available":available,"capacity":booked+available,"diagnostics":diagnostics}
    return {"status":"needs-selector-confirmation","diagnostics":diagnostics}

async def main():
    from playwright.async_api import async_playwright
    data=json.loads(DATA.read_text(encoding="utf-8"))
    diag=[]
    now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds")
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        context=await browser.new_context(viewport={"width":1440,"height":1000},locale="en-MY")
        page=await context.new_page()
        for c in data["cinemas"]:
            if c["chain"]!="Paragon": continue
            for s in c.get("sessions",[]):
                url=s.get("bookingUrl")
                if not url: continue
                try:
                    result=await inspect_session(page,url)
                    diag.append({"cinema":c["name"],"time":s["time"],**result})
                    if result["status"]=="verified":
                        s["booked"]=result["booked"];s["available"]=result["available"];s["capacity"]=result["capacity"]
                        s["occupancy"]=round(result["booked"]/result["capacity"]*100,2)
                        s["seatStatus"]="verified";s["observedAt"]=now
                    else:
                        s["seatStatus"]=result["status"]
                except Exception as e:
                    diag.append({"cinema":c["name"],"time":s["time"],"status":"error","error":type(e).__name__})
                    s["seatStatus"]="collector-error"
        await browser.close()
    DATA.write_text(json.dumps(data,indent=2),encoding="utf-8")
    DIAG.write_text(json.dumps({"observedAt":now,"sessions":diag},indent=2),encoding="utf-8")
    print("Paragon collector complete.")

if __name__=="__main__":
    asyncio.run(main())
