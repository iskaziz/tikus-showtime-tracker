#!/usr/bin/env python3
"""
Experimental seat-map observer.

Principle:
- only write a snapshot when a public booking page exposes a verifiable seat map;
- never infer bookings from ticket availability;
- never proceed to payment or create a purchase.

Usage in CI after Playwright is installed:
  python scripts/observe_seats.py

Currently Paragon session URLs are discovered and hall numbers are already stored.
The observer intentionally leaves booked/capacity null unless selectors can be
positively identified on the live seat-selection page.
"""
from pathlib import Path
import json, asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/current.json"

async def main():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed; skipping seat observation.")
        return

    data=json.loads(DATA.read_text(encoding="utf-8"))
    changed=0
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        page=await browser.new_page(viewport={"width":1280,"height":900})
        for cinema in data["cinemas"]:
            for session in cinema.get("sessions",[]):
                url=session.get("bookingUrl")
                if not url:
                    continue
                # At this stage we only verify the booking page/hall.
                # Seat selection requires adding a ticket, which is website-flow specific.
                try:
                    await page.goto(url,wait_until="domcontentloaded",timeout=30000)
                    body=(await page.locator("body").inner_text()).lower()
                    if "tikus!" in body and "hall" in body:
                        session["seatStatus"]="booking-page-verified"
                        session["observedAt"]=datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds")
                        changed+=1
                except Exception:
                    session["seatStatus"]="seat-observer-error"
        await browser.close()
    if changed:
        DATA.write_text(json.dumps(data,indent=2),encoding="utf-8")
    print(f"Verified {changed} booking-page sessions. No seat totals guessed.")

if __name__=="__main__":
    asyncio.run(main())
