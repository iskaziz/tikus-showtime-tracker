#!/usr/bin/env python3
"""
GSC v11 — read-only official XML API discovery for TIKUS!

The authenticated diagnostic revealed GSC's official epayment API:
  https://epaymentapi.gsc.com.my/showtimews/service.asmx/

This script does NOT use the account session and does NOT create a booking.
It only reads the same movie/showtime XML endpoints used by GSC's web app.

Outputs:
  data/gsc-official-api.json

It attempts to:
1. enumerate GSC movie parent/child records;
2. find TIKUS!;
3. retrieve today's official showtimes for the TIKUS! parent id;
4. extract cinema, time and session-like identifiers from the XML.

No seat is selected and no reservation is created.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, urllib.request, urllib.parse, xml.etree.ElementTree as ET, re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"data/gsc-official-api.json"

BASE = "https://epaymentapi.gsc.com.my/showtimews/service.asmx/"
UA = "Mozilla/5.0 (compatible; TIKUSPerformanceTracker/1.0)"

TRACKED_NAMES = [
    "Paradigm",
    "Aman Central",
    "Mid Valley",
    "Dataran Pahlawan",
    "Kuantan City Mall",
    "IOI City Mall",
    "Imago",
    "The Spring",
]

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read().decode("utf-8","replace")

def flatten(elem):
    out={}
    for e in elem.iter():
        tag=e.tag.split("}")[-1]
        text=(e.text or "").strip()
        if text:
            out.setdefault(tag,[]).append(text)
    return out

def find_tikus_records(xml_text):
    root=ET.fromstring(xml_text)
    hits=[]
    for el in root.iter():
        blob=" ".join((x or "") for x in [el.text,el.tail])
        # include descendants in each candidate container
        desc=" ".join((d.text or "") for d in el.iter())
        if "tikus" in desc.lower():
            flat=flatten(el)
            hits.append(flat)
    # De-dupe compact representations
    seen=set(); clean=[]
    for h in hits:
        key=json.dumps(h,sort_keys=True)
        if key not in seen:
            seen.add(key); clean.append(h)
    return clean[:30]

def extract_possible_ids(records):
    scored=[]
    id_keys=("parentid","movieid","id","parent","movie_id","parent_id","code")
    for rec in records:
        candidate=None
        for k,vals in rec.items():
            lk=k.lower()
            if lk in id_keys or "parent" in lk or ("movie" in lk and "id" in lk):
                for v in vals:
                    if re.fullmatch(r"\d{2,8}",v):
                        candidate=v
                        break
            if candidate: break
        if candidate:
            scored.append(candidate)
    return list(dict.fromkeys(scored))

def main():
    now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    report={
        "collectorVersion":"11.0",
        "observedAt":now.isoformat(timespec="seconds"),
        "policy":"read-only official GSC XML API; no booking creation",
        "movieRecords":[],
        "candidateParentIds":[],
        "showtimeResponses":[],
        "notes":[
            "No GSC password/session is required by this collector.",
            "No showtime is clicked.",
            "No seat is selected or reserved."
        ]
    }

    movies_url=BASE+"getEpaymentMovie_ParentChild?includeChild=true&parent="
    movies_xml=get(movies_url)
    hits=find_tikus_records(movies_xml)
    report["movieRecords"]=hits
    ids=extract_possible_ids(hits)
    report["candidateParentIds"]=ids

    date=now.date().isoformat()
    for pid in ids[:10]:
        url=BASE+"getShowTimesByMovie_ParentChild_V2?"+urllib.parse.urlencode({
            "parentid":pid,
            "oprndate":date
        })
        try:
            xml=get(url)
            root=ET.fromstring(xml)
            flat=flatten(root)
            text=" ".join(flat.get(k,[]) for k in []) if False else ""
            raw_text=" ".join((e.text or "") for e in root.iter())
            tracked=[n for n in TRACKED_NAMES if n.lower() in raw_text.lower()]
            report["showtimeResponses"].append({
                "parentId":pid,
                "url":url,
                "trackedCinemaMatches":tracked,
                "fields":flat,
                "rawSample":xml[:20000]
            })
        except Exception as exc:
            report["showtimeResponses"].append({
                "parentId":pid,
                "url":url,
                "error":type(exc).__name__
            })

    OUT.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("GSC official API discovery complete:",OUT)

if __name__=="__main__":
    main()
