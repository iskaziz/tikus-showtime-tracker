#!/usr/bin/env python3
"""
GSC v14.3 — diagnose why the GSC Angular app is not bootstrapping.

This does NOT automate booking. It simply opens the confirmed TIKUS! page and
records:
- every GSC request/response (including JS/CSS, not only XHR/fetch);
- browser console messages;
- JavaScript page errors;
- failed requests;
- current page URL/title and a small DOM text sample.

Then the user can manually continue to one future showtime and stop at the
seat map without selecting a seat.

Output:
  data/gsc-browser-bootstrap-diagnostic.json
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio, json, re

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "gsc-auth.json"
OUT = ROOT / "data/gsc-browser-bootstrap-diagnostic.json"
START = "https://epaymentwebapp.gsc.com.my/showtime-by-movies/6363/tikus"

GSC_HOSTS = (
    "epaymentwebapp.gsc.com.my",
    "epaymentapi.gsc.com.my",
    "epayment.gsc.com.my",
    "secure2.gsc.com.my",
    "gsc-api-wrapper.ascentis.com.sg",
)

def is_gsc(url):
    u = (url or "").lower()
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
    return out[:50000]

async def main():
    report = {
        "collectorVersion": "14.3",
        "observedAt": datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds"),
        "policy": "diagnostic/manual navigation only; no scripted booking or seat action",
        "startUrl": START,
        "usedStorageState": AUTH.exists(),
        "requests": [],
        "responses": [],
        "failedRequests": [],
        "console": [],
        "pageErrors": [],
        "pagesSeen": [],
        "pageState": {},
    }

    async with async_playwright() as p:
        launch_kwargs = {"headless": False}
        # Prefer the user's normal installed Chrome when available; fall back to Chromium.
        try:
            browser = await p.chromium.launch(channel="chrome", **launch_kwargs)
            report["browserChannel"] = "chrome"
        except Exception:
            browser = await p.chromium.launch(**launch_kwargs)
            report["browserChannel"] = "chromium"

        kwargs = {
            "viewport": {"width": 1440, "height": 1000},
            "locale": "en-MY",
            "bypass_csp": True,
        }
        if AUTH.exists():
            kwargs["storage_state"] = str(AUTH)

        context = await browser.new_context(**kwargs)

        def on_request(req):
            if not is_gsc(req.url):
                return
            report["requests"].append({
                "url": req.url,
                "method": req.method,
                "resourceType": req.resource_type,
                "headers": redact_headers(req.headers),
                "postData": redact_text(req.post_data or ""),
            })

        async def on_response(resp):
            if not is_gsc(resp.url):
                return
            row = {
                "url": resp.url,
                "status": resp.status,
                "resourceType": resp.request.resource_type,
                "headers": redact_headers(resp.headers),
            }
            try:
                ct = resp.headers.get("content-type", "").lower()
                if any(x in ct for x in ("json", "xml", "text", "javascript")):
                    row["bodySample"] = redact_text(await resp.text())
            except Exception:
                pass
            report["responses"].append(row)

        def on_failed(req):
            if is_gsc(req.url):
                report["failedRequests"].append({
                    "url": req.url,
                    "method": req.method,
                    "resourceType": req.resource_type,
                    "failure": req.failure,
                })

        def attach_page(page):
            report["pagesSeen"].append(page.url)
            page.on("console", lambda msg: report["console"].append({
                "type": msg.type,
                "text": redact_text(msg.text),
            }))
            page.on("pageerror", lambda exc: report["pageErrors"].append(
                redact_text(str(exc))
            ))
            page.on("framenavigated", lambda frame: report["pagesSeen"].append(frame.url))

        context.on("request", on_request)
        context.on("response", on_response)
        context.on("requestfailed", on_failed)
        context.on("page", attach_page)

        page = await context.new_page()
        attach_page(page)

        try:
            await page.goto(START, wait_until="domcontentloaded", timeout=90000)
        except Exception as exc:
            report["gotoError"] = type(exc).__name__ + ": " + str(exc)

        # Give Angular time to bootstrap before asking the user to interact.
        await page.wait_for_timeout(8000)

        try:
            report["pageState"]["urlAfter8s"] = page.url
            report["pageState"]["titleAfter8s"] = await page.title()
            report["pageState"]["bodyTextAfter8s"] = redact_text(
                (await page.locator("body").inner_text())[:12000]
            )
            report["pageState"]["appRootHtmlAfter8s"] = redact_text(
                (await page.locator("app-root").inner_html())[:12000]
            )
        except Exception as exc:
            report["pageState"]["snapshotError"] = type(exc).__name__ + ": " + str(exc)

        print("\nGSC BOOTSTRAP DIAGNOSTIC v14.3")
        print("--------------------------------")
        print("Use ONLY the browser window opened by this script.")
        print("")
        print("If the TIKUS! showtime page loads:")
        print("1. Open ONE future showtime manually.")
        print("2. Stop when the seat map is visible.")
        print("3. DO NOT select any seat.")
        print("")
        print("If the page looks blank/stuck, do nothing further.")
        print("")
        input("Press Enter when finished (or immediately if the page is stuck): ")

        report["pagesSeen"] += [pg.url for pg in context.pages]
        try:
            report["pageState"]["finalUrl"] = page.url
            report["pageState"]["finalTitle"] = await page.title()
            report["pageState"]["finalBodyText"] = redact_text(
                (await page.locator("body").inner_text())[:12000]
            )
        except Exception:
            pass

        def dedupe(rows):
            seen, out = set(), []
            for row in rows:
                key = json.dumps(row, sort_keys=True, ensure_ascii=False)
                if key not in seen:
                    seen.add(key)
                    out.append(row)
            return out

        report["requests"] = dedupe(report["requests"])
        report["responses"] = dedupe(report["responses"])
        report["failedRequests"] = dedupe(report["failedRequests"])
        report["console"] = dedupe(report["console"])
        report["pageErrors"] = list(dict.fromkeys(report["pageErrors"]))
        report["pagesSeen"] = list(dict.fromkeys(x for x in report["pagesSeen"] if x))

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("\nSaved:", OUT)
        print("GSC requests:", len(report["requests"]))
        print("GSC responses:", len(report["responses"]))
        print("Failed requests:", len(report["failedRequests"]))
        print("Console entries:", len(report["console"]))
        print("Page errors:", len(report["pageErrors"]))

        await browser.close()

if __name__ == "__main__":
    from playwright.async_api import async_playwright
    asyncio.run(main())
