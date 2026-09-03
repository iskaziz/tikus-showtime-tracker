#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import urllib.request, urllib.parse, re, json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/gsc-seat-api-static-analysis.json"
APP = "https://epaymentwebapp.gsc.com.my/"
UA = "Mozilla/5.0 (compatible; TIKUSPerformanceTracker/1.0)"

NEEDLES = [
    "InitSalesTransaction","initSalesTransaction","SeatSelection","seatSelection",
    "GetSeat","getSeat","SeatMap","seatMap","LockSeat","lockSeat",
    "UnlockSeat","unlockSeat","GetShowtime","showtimesApiModel",
    "showID","locationID","childCode","hallGroup",
]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")

def unique(seq):
    return list(dict.fromkeys(seq))

def main():
    html = fetch(APP)
    srcs = re.findall(r'<script[^>]+src=["\\\']([^"\\\']+)', html, re.I)
    urls = [urllib.parse.urljoin(APP, s) for s in srcs]

    report = {
        "collectorVersion": "13.0",
        "observedAt": datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds"),
        "policy": "static public JavaScript analysis only; no booking/seat endpoint invoked",
        "scriptUrls": urls,
        "stringCandidates": [],
        "neighborhoods": [],
        "apiLikeStrings": [],
    }

    for url in urls:
        if not url.endswith(".js"):
            continue
        try:
            js = fetch(url)
        except Exception as exc:
            report.setdefault("errors", []).append({"script": url, "error": type(exc).__name__})
            continue

        # Extract quoted literals conservatively.
        strings = re.findall(r'["\\\']([^"\\\']{2,220})["\\\']', js)
        api_strings = []
        for s in strings:
            low = s.lower()
            if (
                ("api/" in low or "service.asmx" in low or "seat" in low or
                 "sales" in low or "showtime" in low or "booking" in low)
                and len(s) <= 220
            ):
                api_strings.append(s)

        for s in unique(api_strings):
            report["apiLikeStrings"].append({"script": url, "value": s})

        lowjs = js.lower()
        for needle in NEEDLES:
            start = 0
            count = 0
            while count < 20:
                i = lowjs.find(needle.lower(), start)
                if i < 0:
                    break
                a = max(0, i - 1800)
                b = min(len(js), i + 2600)
                report["neighborhoods"].append({
                    "script": url,
                    "needle": needle,
                    "snippet": js[a:b]
                })
                start = i + len(needle)
                count += 1

        for m in re.finditer(
            r'(?:const|let|var)?\s*([A-Za-z_$][\w$]{0,30})\s*=\s*["\\\']([^"\\\']{2,120})["\\\']',
            js
        ):
            name, val = m.group(1), m.group(2)
            low = val.lower()
            if any(k in low for k in ("seat", "sales", "booking", "showtime", "ticket")):
                report["stringCandidates"].append({
                    "script": url, "symbol": name, "value": val
                })

    seen = set(); cleaned = []
    for x in report["apiLikeStrings"]:
        k = (x["script"], x["value"])
        if k not in seen:
            seen.add(k); cleaned.append(x)
    report["apiLikeStrings"] = cleaned[:1500]

    seen = set(); cleaned = []
    for x in report["stringCandidates"]:
        k = (x["script"], x["symbol"], x["value"])
        if k not in seen:
            seen.add(k); cleaned.append(x)
    report["stringCandidates"] = cleaned[:1000]

    seen = set(); cleaned = []
    for x in report["neighborhoods"]:
        k = (x["script"], x["needle"], x["snippet"])
        if k not in seen:
            seen.add(k); cleaned.append(x)
    report["neighborhoods"] = cleaned[:400]

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Wrote", OUT)

if __name__ == "__main__":
    main()
