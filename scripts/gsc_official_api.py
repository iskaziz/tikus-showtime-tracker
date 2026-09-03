#!/usr/bin/env python3
"""
GSC v11.1 — robust TIKUS! ID + official showtime discovery.

Read-only only:
- fetches the public GSC TIKUS! page;
- discovers the GSC movie/showtime numeric ID from links/page source if present;
- captures the official movie-catalogue response raw enough to diagnose its structure;
- unwraps XML string payloads / escaped XML;
- calls the official GSC showtime endpoint for discovered TIKUS! IDs.

No login, no showtime click, no seat selection, no booking.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import urllib.request, urllib.parse, re, json, html
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/gsc-official-api.json"

PUBLIC_MOVIE="https://www.gsc.com.my/movie/tikus/"
API="https://epaymentapi.gsc.com.my/showtimews/service.asmx/"
UA="Mozilla/5.0 (compatible; TIKUSPerformanceTracker/1.0)"

TRACKED=[
    "Paradigm", "Aman Central", "Mid Valley", "Dataran Pahlawan",
    "Kuantan City Mall", "IOI City Mall", "Imago", "The Spring"
]

def fetch(url):
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,
        "Accept":"text/html,application/xml,text/xml,application/json,*/*"
    })
    with urllib.request.urlopen(req,timeout=40) as r:
        body=r.read().decode("utf-8","replace")
        return body, dict(r.headers)

def unwrap_xml_string(s):
    """ASMX often returns <string>escaped payload</string>."""
    candidates=[s]
    try:
        root=ET.fromstring(s)
        text="".join(root.itertext()).strip()
        if text:
            candidates.append(html.unescape(text))
    except Exception:
        pass
    # multiple unescape passes
    cur=s
    for _ in range(3):
        nxt=html.unescape(cur)
        if nxt==cur: break
        candidates.append(nxt)
        cur=nxt
    return candidates

def ids_from_text(text):
    pats=[
        r"/showtime-by-movies/(\d+)/(?:tikus|[^\"'/?#<>\s]+)",
        r"showtime-by-movies%2F(\d+)%2F(?:tikus|[^&\"']+)",
        r"""["'](?:parentid|parentId|movieid|movieId|id)["']\s*[:=]\s*["']?(\d{2,8})""",
    ]
    out=[]
    for p in pats:
        out += re.findall(p,text,re.I)
    return list(dict.fromkeys(out))

def snippets(text, needle="tikus", radius=800):
    low=text.lower()
    out=[]
    start=0
    while len(out)<12:
        i=low.find(needle,start)
        if i<0: break
        a=max(0,i-radius); b=min(len(text),i+len(needle)+radius)
        out.append(text[a:b])
        start=i+len(needle)
    return out

def flatten_xml(text):
    try:
        root=ET.fromstring(text)
    except Exception:
        return {}
    out={}
    for e in root.iter():
        tag=e.tag.split("}")[-1]
        val=(e.text or "").strip()
        if val:
            out.setdefault(tag,[]).append(val)
    return out

def main():
    now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    report={
        "collectorVersion":"11.1",
        "observedAt":now.isoformat(timespec="seconds"),
        "policy":"read-only official GSC discovery; no booking creation",
        "publicMoviePage":{},
        "catalogue":{},
        "candidateParentIds":[],
        "showtimeResponses":[],
    }
    candidates=[]

    # 1) Public TIKUS page
    try:
        page,headers=fetch(PUBLIC_MOVIE)
        page_ids=ids_from_text(page)
        candidates += page_ids
        report["publicMoviePage"]={
            "status":"ok",
            "length":len(page),
            "candidateIds":page_ids,
            "tikusSnippets":snippets(page)[:5],
        }
    except Exception as exc:
        report["publicMoviePage"]={"status":"error","error":type(exc).__name__}

    # 2) Official GSC catalogue endpoint: preserve structure for diagnosis
    cat_url=API+"getEpaymentMovie_ParentChild?includeChild=true&parent="
    try:
        raw,headers=fetch(cat_url)
        versions=unwrap_xml_string(raw)
        cat_ids=[]
        tikus_versions=[]
        for idx,v in enumerate(versions):
            if "tikus" in v.lower():
                tikus_versions.append(idx)
                cat_ids += ids_from_text(v)
                # broad ID extraction near Tikus
                for sn in snippets(v):
                    cat_ids += re.findall(r"\b\d{3,7}\b",sn)
        cat_ids=list(dict.fromkeys(cat_ids))
        candidates += cat_ids
        report["catalogue"]={
            "status":"ok",
            "contentType":headers.get("Content-Type"),
            "rawLength":len(raw),
            "rawPrefix":raw[:5000],
            "unwrappedVariants":len(versions),
            "variantsContainingTikus":tikus_versions,
            "candidateIds":cat_ids,
            "tikusSnippets":[s for v in versions for s in snippets(v)][:10]
        }
    except Exception as exc:
        report["catalogue"]={"status":"error","error":type(exc).__name__}

    candidates=list(dict.fromkeys(candidates))
    report["candidateParentIds"]=candidates

    date=now.date().isoformat()
    for pid in candidates[:30]:
        url=API+"getShowTimesByMovie_ParentChild_V2?"+urllib.parse.urlencode({
            "parentid":pid,
            "oprndate":date
        })
        try:
            raw,headers=fetch(url)
            versions=unwrap_xml_string(raw)
            joined="\n".join(versions)
            # Keep only IDs whose response appears to contain TIKUS or our tracked cinema names,
            # but still report all attempted candidates compactly.
            matches=[n for n in TRACKED if n.lower() in joined.lower()]
            has_tikus="tikus" in joined.lower()
            entry={
                "parentId":pid,
                "status":"ok",
                "contentType":headers.get("Content-Type"),
                "rawLength":len(raw),
                "containsTikus":has_tikus,
                "trackedCinemaMatches":matches,
                "rawPrefix":raw[:8000],
            }
            # include more only for promising responses
            if has_tikus or matches:
                entry["unwrappedPrefix"]=versions[-1][:20000]
                entry["fields"]=flatten_xml(versions[-1])
            report["showtimeResponses"].append(entry)
        except Exception as exc:
            report["showtimeResponses"].append({
                "parentId":pid,"status":"error","error":type(exc).__name__
            })

    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print("Wrote",OUT)

if __name__=="__main__":
    main()
