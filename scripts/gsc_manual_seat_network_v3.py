#!/usr/bin/env python3
"""
GSC v14.2 — context-wide manual network capture.

Fixes the previous capture by:
- opening TIKUS! directly using its confirmed GSC parent id 6363;
- capturing requests/responses at BROWSER CONTEXT level so redirects, new tabs
  and popups are included;
- capturing all GSC API/proxy traffic, including generic /api calls;
- keeping the workflow fully manual.

The script does not click a showtime, select/lock a seat, or submit a booking.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio, json, re

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "gsc-auth.json"
OUT = ROOT / "data/gsc-manual-seat-network-v3.json"

# Confirmed GSC parent movie id for TIKUS!
START = "https://epaymentwebapp.gsc.com.my/showtime-by-movies/6363/tikus"

GSC_HOSTS = (
    "epaymentwebapp.gsc.com.my",
    "epaymentapi.gsc.com.my",
    "epayment.gsc.com.my",
    "secure2.gsc.com.my",
    "gsc-api-wrapper.ascentis.com.sg",
)

def is_gsc(url):
    u = url.lower()
    return any(host in u for host in GSC_HOSTS)

def redact_headers(headers):
    out = {}
    for k, v in headers.items():
        if k.lower() in {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}:
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out

def redact_text(text):
    if not text:
        return text
    out = text
    patterns = [
        r'("?(?:accessToken|token|authorization|password|email|emailid|mobile|mobileno|phone|phoneno|memberid|mbrid|cardNo|cardnumber)"?\s*[:=]\s*")[^"]*(")',
        r'(Bearer\s+)[A-Za-z0-9._\-]+',
    ]
    for pat in patterns:
        if "Bearer" in pat:
            out = re.sub(pat, r'\1[REDACTED]', out, flags=re.I)
        else:
            out = re.sub(pat, r'\1[REDACTED]\2', out, flags=re.I)
    return out[:80000]

async def main():
    report = {
        "collectorVersion": "14.2",
        "observedAt": datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds"),
        "policy": "manual owner navigation only; no scripted booking action",
        "startUrl": START,
        "usedStorageState": AUTH.exists(),
        "requests": [],
        "responses": [],
        "pagesSeen": [],
        "notes": [
            "Use ONLY the browser window opened by this script.",
            "If login is requested, log in manually there.",
            "Open one future TIKUS! showtime.",
            "Stop once the seat map is visible.",
            "Do not click/select any seat."
        ]
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        kwargs = {"viewport": {"width": 1440, "height": 1000}, "locale": "en-MY"}
        if AUTH.exists():
            kwargs["storage_state"] = str(AUTH)
        context = await browser.new_context(**kwargs)

        def on_request(req):
            if req.resource_type not in ("xhr", "fetch", "document"):
                return
            if not is_gsc(req.url):
                return
            report["requests"].append({
                "url": req.url,
                "method": req.method,
                "resourceType": req.resource_type,
                "headers": redact_headers(req.headers),
                "postData": redact_text(req.post_data or "")
            })

        async def on_response(resp):
            req = resp.request
            if req.resource_type not in ("xhr", "fetch", "document"):
                return
            if not is_gsc(resp.url):
                return
            row = {
                "url": resp.url,
                "status": resp.status,
                "resourceType": req.resource_type,
                "headers": redact_headers(resp.headers),
            }
            try:
                ct = resp.headers.get("content-type", "").lower()
                if any(x in ct for x in ("json", "xml", "text")):
                    row["bodySample"] = redact_text(await resp.text())
            except Exception:
                pass
            report["responses"].append(row)

        def on_page(page):
            report["pagesSeen"].append(page.url)
            page.on("framenavigated", lambda frame: report["pagesSeen"].append(frame.url))

        context.on("request", on_request)
        context.on("response", on_response)
        context.on("page", on_page)

        page = await context.new_page()
        try:
            await page.goto(START, wait_until="domcontentloaded", timeout=90000)
        except Exception:
            pass

        print("\nGSC MANUAL CAPTURE v14.2")
        print("-------------------------")
        print("IMPORTANT: use ONLY the Chromium window opened by this script.")
        print("")
        print("1. TIKUS! should already be open.")
        print("2. If GSC asks you to log in, log in manually in THIS window.")
        print("3. Open ONE future TIKUS! showtime.")
        print("4. Continue until the actual seat map is visible.")
        print("5. DO NOT click/select any seat.")
        print("6. Return here and press Enter.")
        print("")
        input("Press Enter only after the seat map is visible: ")

        report["pagesSeen"] += [pg.url for pg in context.pages]

        def dedupe(rows):
            seen, out = set(), []
            for row in rows:
                key = json.dumps(row, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    out.append(row)
            return out

        report["requests"] = dedupe(report["requests"])
        report["responses"] = dedupe(report["responses"])
        report["pagesSeen"] = list(dict.fromkeys(x for x in report["pagesSeen"] if x))

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("\nSaved:", OUT)
        print("Pages seen:", len(report["pagesSeen"]))
        print("Captured GSC requests:", len(report["requests"]))
        print("Captured GSC responses:", len(report["responses"]))
        await browser.close()

if __name__ == "__main__":
    from playwright.async_api import async_playwright
    asyncio.run(main())
