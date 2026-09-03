#!/usr/bin/env python3
"""
GSC v14.1 — broad LOCAL manual network capture.

Why v14.1:
Playwright storage_state preserves cookies/localStorage but NOT ordinary
sessionStorage. GSC stores important booking/login state in sessionStorage.
Therefore this capture allows the account owner to log in manually inside the
same browser session and captures ALL GSC XHR/fetch traffic rather than only
URLs containing words such as "seat" or "booking".

Safety:
- User controls all navigation.
- Script performs no showtime click.
- Script performs no seat selection or seat lock.
- Script performs no booking/payment action.
- Stop as soon as the seat map is visible; do not click any seat.

Output:
  data/gsc-manual-seat-network-v2.json
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio, json, re

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "gsc-auth.json"
OUT = ROOT / "data/gsc-manual-seat-network-v2.json"

START = "https://epaymentwebapp.gsc.com.my/showtime-by-movies"

GSC_HOSTS = (
    "epaymentwebapp.gsc.com.my",
    "epaymentapi.gsc.com.my",
    "epayment.gsc.com.my",
    "secure2.gsc.com.my",
    "gsc-api-wrapper.ascentis.com.sg",
)

def is_gsc(url):
    low = url.lower()
    return any(host in low for host in GSC_HOSTS)

def redact_headers(headers):
    safe = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in {
            "authorization", "cookie", "set-cookie", "x-api-key",
            "proxy-authorization"
        }:
            safe[k] = "[REDACTED]"
        else:
            safe[k] = v
    return safe

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
    return out[:50000]

async def main():
    report = {
        "collectorVersion": "14.1",
        "observedAt": datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds"),
        "policy": "manual navigation only; no scripted showtime click, seat selection, seat lock or payment",
        "startUrl": START,
        "usedStorageState": AUTH.exists(),
        "requests": [],
        "responses": [],
        "finalUrl": None,
        "notes": [
            "If GSC asks you to log in, log in manually in this browser.",
            "Navigate to TIKUS! and open one future showtime.",
            "Stop as soon as the seat map is visible.",
            "Do not click/select any seat."
        ]
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        kwargs = {
            "viewport": {"width": 1440, "height": 1000},
            "locale": "en-MY"
        }
        if AUTH.exists():
            kwargs["storage_state"] = str(AUTH)

        context = await browser.new_context(**kwargs)
        page = await context.new_page()

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
            item = {
                "url": resp.url,
                "status": resp.status,
                "resourceType": req.resource_type,
                "headers": redact_headers(resp.headers),
            }
            try:
                ct = resp.headers.get("content-type", "").lower()
                if any(x in ct for x in ("json", "xml", "text")):
                    item["bodySample"] = redact_text(await resp.text())
            except Exception:
                pass
            report["responses"].append(item)

        page.on("request", on_request)
        page.on("response", on_response)

        try:
            await page.goto(START, wait_until="domcontentloaded", timeout=90000)
        except Exception:
            pass

        print("\nGSC MANUAL CAPTURE v14.1")
        print("-------------------------")
        print("IMPORTANT: GSC uses sessionStorage, which gsc-auth.json may not fully restore.")
        print("If you are asked to log in, log in manually in this opened browser.")
        print("")
        print("1. Navigate to TIKUS!.")
        print("2. Open ONE future showtime.")
        print("3. Continue until the seat map is visible.")
        print("4. DO NOT click/select any seat.")
        print("5. Come back here and press Enter.")
        print("")
        input("Press Enter only after the seat map is visible: ")

        report["finalUrl"] = page.url

        def dedupe(rows):
            seen = set()
            out = []
            for row in rows:
                key = (
                    row.get("method"),
                    row.get("url"),
                    row.get("postData"),
                    row.get("status"),
                    row.get("bodySample"),
                )
                if key not in seen:
                    seen.add(key)
                    out.append(row)
            return out

        report["requests"] = dedupe(report["requests"])
        report["responses"] = dedupe(report["responses"])

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

        print("\nSaved:", OUT)
        print("Captured GSC requests:", len(report["requests"]))
        print("Captured GSC responses:", len(report["responses"]))

        await browser.close()

if __name__ == "__main__":
    from playwright.async_api import async_playwright
    asyncio.run(main())
