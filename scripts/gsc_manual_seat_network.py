#!/usr/bin/env python3
"""
GSC v14 — LOCAL manual network capture.

Purpose:
Capture the real network requests that occur when the account owner manually
opens ONE TIKUS! showtime and reaches the seat-map screen.

Safety:
- Uses the owner's existing Playwright storage state from gsc-auth.json.
- The script itself does not click a showtime, select a seat, lock a seat,
  submit a booking, or make a payment.
- The user controls the browser manually.
- Stop once the seat map is visible. Do not click any seat.

Output:
  data/gsc-manual-seat-network.json

Run locally:
  python scripts/gsc_manual_seat_network.py
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio, json, re

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "gsc-auth.json"
OUT = ROOT / "data/gsc-manual-seat-network.json"

APP = "https://epaymentwebapp.gsc.com.my/showtime-by-movies"
KEYS = (
    "seat", "sales", "transaction", "booking", "showtime",
    "hall", "ticket", "session", "init", "lock"
)

def redact_headers(headers):
    safe = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in {"authorization", "cookie", "set-cookie", "x-api-key"}:
            safe[k] = "[REDACTED]"
        else:
            safe[k] = v
    return safe

def redact_body(text):
    if not text:
        return text
    # Conservative redaction for common identity/payment/auth fields.
    patterns = [
        (r'("?(?:accessToken|token|authorization|password|email|mobile|phone|memberid|memberId|cardNo|cardnumber)"?\s*[:=]\s*")[^"]*(")', r'\1[REDACTED]\2'),
        (r'(Bearer\s+)[A-Za-z0-9._\-]+', r'\1[REDACTED]'),
    ]
    out = text
    for pat, rep in patterns:
        out = re.sub(pat, rep, out, flags=re.I)
    return out[:30000]

async def main():
    if not AUTH.exists():
        raise SystemExit(
            "Missing gsc-auth.json in the repository root. "
            "Run scripts/gsc_auth_setup.py locally first."
        )

    report = {
        "collectorVersion": "14.0",
        "observedAt": datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds"),
        "policy": (
            "manual account-owner navigation; capture only; "
            "script performs no showtime click, seat selection, seat lock or payment"
        ),
        "startUrl": APP,
        "requests": [],
        "responses": [],
        "finalUrl": None,
        "notes": [
            "Navigate manually to TIKUS! and open one future showtime.",
            "Stop when the seat map becomes visible.",
            "Do not click or select any seat."
        ]
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=str(AUTH),
            viewport={"width": 1440, "height": 1000},
            locale="en-MY"
        )
        page = await context.new_page()

        def request_handler(req):
            low = req.url.lower()
            if any(k in low for k in KEYS):
                report["requests"].append({
                    "url": req.url,
                    "method": req.method,
                    "resourceType": req.resource_type,
                    "headers": redact_headers(req.headers),
                    "postData": redact_body(req.post_data or "")
                })

        async def response_handler(resp):
            low = resp.url.lower()
            if not any(k in low for k in KEYS):
                return
            item = {
                "url": resp.url,
                "status": resp.status,
                "headers": redact_headers(resp.headers),
            }
            try:
                ct = resp.headers.get("content-type", "")
                if any(x in ct.lower() for x in ("json", "xml", "text")):
                    item["bodySample"] = redact_body(await resp.text())
            except Exception:
                pass
            report["responses"].append(item)

        page.on("request", request_handler)
        page.on("response", response_handler)

        try:
            await page.goto(APP, wait_until="domcontentloaded", timeout=90000)
        except Exception:
            pass

        print("\nGSC MANUAL CAPTURE")
        print("------------------")
        print("1. In the opened browser, navigate to TIKUS!.")
        print("2. Open ONE future showtime.")
        print("3. Continue only until the seat map is visible.")
        print("4. DO NOT click/select any seat.")
        print("5. Return here and press Enter.\n")
        input("Press Enter after the seat map is visible: ")

        report["finalUrl"] = page.url

        # De-duplicate while preserving order.
        def dedupe(rows, fields):
            seen = set()
            out = []
            for row in rows:
                key = tuple(row.get(f) for f in fields)
                if key not in seen:
                    seen.add(key)
                    out.append(row)
            return out

        report["requests"] = dedupe(
            report["requests"], ("method", "url", "postData")
        )
        report["responses"] = dedupe(
            report["responses"], ("status", "url", "bodySample")
        )

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nSaved: {OUT}")
        await browser.close()

if __name__ == "__main__":
    from playwright.async_api import async_playwright
    asyncio.run(main())
