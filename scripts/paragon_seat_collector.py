#!/usr/bin/env python3
"""
Paragon public-booking observer.

Finding from the first live run:
- all 7 Paragon TIKUS! sessions reached the ticket-selection page;
- zero selectable seat elements were exposed there;
- the page states seats are reserved on a "best available basis".

The collector therefore does NOT advance the booking transaction just to obtain
inventory information, because repeated automated transactions could create
temporary holds and distort the data.

It records only non-invasive public metadata.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, asyncio, re

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/current.json"
DIAG=ROOT/"data/paragon-seat-diagnostics.json"

async def inspect(page,url):
    await page.goto(url,wait_until="networkidle",timeout=45000)
    text=await page.locator("body").inner_text()
    low=text.lower()
    hall_match=re.search(r"Paragon Cinemas\s*-\s*(.+?)\s*-\s*(Hall\s+\d+)", text, re.I)
    prices={}
    for label, price in re.findall(r"(Adult Male|Adult Female|Children Male|Children Female)\s+(\d+\.\d{2})", text, re.I):
        prices[label]=float(price)
    return {
        "status":"booking-open" if "select the number and type of tickets" in low else "booking-page-unavailable",
        "bestAvailable": "best available basis" in low,
        "venue": hall_match.group(1).strip() if hall_match else None,
        "hall": hall_match.group(2).strip() if hall_match else None,
        "prices":prices,
        "seatCountStatus":"not-exposed-by-public-ticket-page"
    }

async def main():
    from playwright.async_api import async_playwright
    data=json.loads(DATA.read_text(encoding="utf-8"))
    now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds")
    rows=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        page=await browser.new_page(viewport={"width":1440,"height":1000},locale="en-MY")
        for c in data["cinemas"]:
            if c["chain"]!="Paragon": continue
            for s in c.get("sessions",[]):
                if not s.get("bookingUrl"): continue
                try:
                    r=await inspect(page,s["bookingUrl"])
                    s["seatStatus"]="not-publicly-exposed"
                    s["bookingStatus"]=r["status"]
                    if r.get("hall"): s["hall"]=r["hall"]
                    s["ticketPrices"]=r.get("prices",{})
                    s["observedAt"]=now
                    rows.append({"cinema":c["name"],"time":s["time"],**r})
                except Exception as e:
                    s["seatStatus"]="collector-error"
                    rows.append({"cinema":c["name"],"time":s["time"],"status":"error","error":type(e).__name__})
        await browser.close()
    DATA.write_text(json.dumps(data,indent=2),encoding="utf-8")
    DIAG.write_text(json.dumps({
        "observedAt":now,
        "finding":"Public Paragon ticket selection exposes no countable seat map in the observed stage.",
        "sessions":rows
    },indent=2),encoding="utf-8")
    print("Paragon public-booking status refresh complete.")

if __name__=="__main__":
    asyncio.run(main())
