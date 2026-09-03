#!/usr/bin/env python3
"""
Authenticated GSC booking diagnostics for TIKUS!.

Requires GSC_AUTH_JSON environment variable containing Playwright storage state
JSON created by scripts/gsc_auth_setup.py.

This collector:
- loads the authenticated session;
- navigates GSC's booking app;
- captures session/showtime/hall/seat-related network traffic;
- does not attempt to bypass login;
- does not submit payment;
- does not store username/password;
- avoids selecting seats unless/until a later version explicitly needs it.

The goal is to discover whether seat availability can be read after normal
authentication without creating a booking.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, asyncio, os, re, tempfile

ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT/"data/gsc-auth-diagnostics.json"

MOVIE_URL = "https://www.gsc.com.my/movie/tikus/"
BOOKING_BASE = "https://epaymentwebapp.gsc.com.my/"
KEYS = ("seat","hall","showtime","session","movie","cinema","ticket","booking","schedule")

async def main():
    from playwright.async_api import async_playwright

    raw = os.environ.get("GSC_AUTH_JSON")
    if not raw:
        raise SystemExit("Missing GSC_AUTH_JSON secret.")

    # Validate secret JSON without printing it.
    state = json.loads(raw)
    auth_file = Path(tempfile.gettempdir())/"gsc-auth-state.json"
    auth_file.write_text(json.dumps(state), encoding="utf-8")

    now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds")
    diag = {
        "collectorVersion":"10.0",
        "observedAt":now,
        "policy":"normal authenticated session reuse; no password storage; no auth bypass",
        "moviePage":MOVIE_URL,
        "networkCandidates":[],
        "sessionLikeElements":[],
        "notes":[
            "Uses a normal GSC login session supplied by the account owner.",
            "No password is stored by this collector.",
            "No payment is submitted.",
            "No attempt is made to defeat authentication."
        ]
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state=str(auth_file),
            viewport={"width":1440,"height":1100},
            locale="en-MY",
            user_agent="Mozilla/5.0 (compatible; TIKUSPerformanceTracker/1.0)"
        )
        page = await context.new_page()

        async def capture(resp):
            u = resp.url
            low = u.lower()
            if any(k in low for k in KEYS):
                req = resp.request
                item = {
                    "url":u,
                    "method":req.method,
                    "status":resp.status,
                    "contentType":resp.headers.get("content-type"),
                    "postData":req.post_data
                }
                try:
                    if "json" in (item["contentType"] or "").lower():
                        item["sample"] = (await resp.text())[:16000]
                except Exception:
                    pass
                diag["networkCandidates"].append(item)

        page.on("response", capture)

        # Go straight into the app root and verify that the saved session is still valid.
        try:
            await page.goto(BOOKING_BASE, wait_until="domcontentloaded", timeout=90000)
        except Exception as exc:
            diag["navigationWarning"] = type(exc).__name__
        await page.wait_for_timeout(5000)

        diag["initialUrl"] = page.url
        initial_body = await page.locator("body").inner_text()
        diag["initialBodySample"] = initial_body[:5000]
        diag["authenticated"] = "/login" not in page.url.lower()

        if not diag["authenticated"]:
            DIAG.write_text(json.dumps(diag, indent=2), encoding="utf-8")
            await browser.close()
            raise SystemExit("Saved GSC session is not authenticated or has expired.")

        # Open public movie page and attempt normal booking link navigation.
        try:
            await page.goto(MOVIE_URL, wait_until="domcontentloaded", timeout=90000)
        except Exception:
            pass
        await page.wait_for_timeout(4000)

        # Resolve an epayment link from the public page.
        buy_url = None
        for a in await page.locator("a").all():
            try:
                href = await a.get_attribute("href")
                text = (await a.inner_text()).strip()
            except Exception:
                continue
            if href and "epaymentwebapp.gsc.com.my" in href:
                buy_url = href
                if "buy" in text.lower() or "ticket" in text.lower():
                    break
        diag["resolvedBuyUrl"] = buy_url

        if buy_url:
            try:
                await page.goto(buy_url, wait_until="domcontentloaded", timeout=90000)
            except Exception as exc:
                diag["buyNavigationWarning"] = type(exc).__name__
            await page.wait_for_timeout(7000)
        else:
            # Fallback: authenticated app may route internally.
            try:
                await page.goto("https://epaymentwebapp.gsc.com.my/showtime-by-movies",
                                wait_until="domcontentloaded", timeout=90000)
            except Exception:
                pass
            await page.wait_for_timeout(7000)

        diag["finalUrl"] = page.url
        body = await page.locator("body").inner_text()
        html = await page.content()
        diag["bodySample"] = body[:12000]

        # Collect likely session/showtime controls without selecting a seat.
        for sel in ["a","button","[role='button']","option","label","input"]:
            loc = page.locator(sel)
            for i in range(min(await loc.count(), 1800)):
                el = loc.nth(i)
                try:
                    txt = (await el.inner_text()).strip() if sel != "input" else ""
                    href = await el.get_attribute("href")
                    val = await el.get_attribute("value")
                    attrs = await el.evaluate("""e => {
                        const o={};
                        for (const a of e.attributes) {
                            if (a.name.startsWith('data-') || ['id','class','aria-label','name','type'].includes(a.name)) {
                                o[a.name]=a.value;
                            }
                        }
                        return o;
                    }""")
                except Exception:
                    continue

                hay = (txt+" "+str(href)+" "+str(val)+" "+json.dumps(attrs)).lower()
                if (
                    re.search(r"\b(?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:am|pm)\b", txt, re.I)
                    or any(k in hay for k in ("showtime","session","cinema","hall","ticket","seat"))
                ):
                    diag["sessionLikeElements"].append({
                        "tag":sel,
                        "text":txt[:180],
                        "href":href,
                        "value":val,
                        "attrs":attrs
                    })

        # Scan DOM for IDs that can help identify sessions/halls.
        diag["sourceIds"] = list(dict.fromkeys(re.findall(
            r"(?:session|showtime|hall|cinema)[^A-Za-z0-9]{0,6}([A-Za-z0-9_-]{3,})",
            html,
            re.I
        )))[:500]

        await browser.close()

    # de-duplicate
    seen=set(); clean=[]
    for x in diag["networkCandidates"]:
        key=(x["method"],x["url"],x.get("postData"))
        if key not in seen:
            seen.add(key); clean.append(x)
    diag["networkCandidates"]=clean[:300]

    seen=set(); clean=[]
    for x in diag["sessionLikeElements"]:
        key=json.dumps(x,sort_keys=True)
        if key not in seen:
            seen.add(key); clean.append(x)
    diag["sessionLikeElements"]=clean[:500]

    DIAG.write_text(json.dumps(diag, indent=2), encoding="utf-8")
    print("GSC authenticated diagnostics complete:", DIAG)

if __name__ == "__main__":
    asyncio.run(main())
