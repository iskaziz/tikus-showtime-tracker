#!/usr/bin/env python3
"""
GSC v12 seat-endpoint string discovery.

Read-only static analysis of the public GSC epayment web application's JS
bundles. It looks for endpoint/function names containing terms such as seat,
hall, booking, transaction and service.asmx.

It does not call any candidate seat endpoint and does not create a booking.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, urllib.request, re, urllib.parse

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/gsc-seat-endpoint-discovery.json"
APP="https://epaymentwebapp.gsc.com.my/"
UA="Mozilla/5.0 (compatible; TIKUSPerformanceTracker/1.0)"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=50) as r:
        return r.read().decode("utf-8","replace")

def main():
    html=fetch(APP)
    srcs=re.findall(r'<script[^>]+src=["\']([^"\']+)',html,re.I)
    urls=[]
    for s in srcs:
        urls.append(urllib.parse.urljoin(APP,s))

    report={
        "collectorVersion":"12.0",
        "observedAt":datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds"),
        "policy":"static JS inspection only; no candidate booking/seat endpoint invoked",
        "scriptUrls":urls,
        "matches":[]
    }

    needles=("seat","hall","service.asmx","transaction","booking","showtime","ticket")
    for url in urls:
        try:
            js=fetch(url)
        except Exception:
            continue
        low=js.lower()
        seen=set()
        for needle in needles:
            pos=0
            while True:
                i=low.find(needle,pos)
                if i<0: break
                a=max(0,i-350); b=min(len(js),i+650)
                snip=js[a:b]
                # Keep snippets that look API/route related rather than arbitrary UI text.
                if (
                    "service.asmx" in snip.lower()
                    or "http" in snip.lower()
                    or "getseat" in snip.lower()
                    or "seatmap" in snip.lower()
                    or "seatlayout" in snip.lower()
                    or "session" in snip.lower()
                ):
                    key=snip
                    if key not in seen:
                        seen.add(key)
                        report["matches"].append({
                            "script":url,
                            "needle":needle,
                            "snippet":snip
                        })
                pos=i+len(needle)
                if len(report["matches"])>=250:
                    break
            if len(report["matches"])>=250:
                break
        if len(report["matches"])>=250:
            break

    OUT.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("Wrote",OUT)

if __name__=="__main__":
    main()
