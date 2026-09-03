#!/usr/bin/env python3
"""
GSC v12 official live showtime collector for TIKUS!

Uses GSC's public read-only XML showtime endpoint discovered from the official
GSC booking app.

Movie identifiers:
  parent code: 6363
  child code: 1000005309

No account session, showtime click, seat selection, reservation, or payment.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, urllib.request, urllib.parse, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/current.json"
OUT=ROOT/"data/gsc-live-collector.json"

API="https://epaymentapi.gsc.com.my/showtimews/service.asmx/"
PARENT_ID="6363"
CHILD_CODE="1000005309"
UA="Mozilla/5.0 (compatible; TIKUSPerformanceTracker/1.0)"

TRACKED = {
    "gsc-midvalley": ["GSC Mid Valley"],
    "gsc-ioi-city-mall": ["GSC IOI City Mall (West) (Putrajaya)"],
    "gsc-aman-central": ["GSC Aman Central"],
    "gsc-dataran-pahlawan": ["GSC Dataran Pahlawan"],
    "gsc-paradigm-jb": ["GSC Paradigm Mall (Johor Bahru)"],
    "gsc-kuantan-city-mall": ["GSC Kuantan City Mall"],
    "gsc-imago": ["GSC IMAGO Shopping Mall"],
    "gsc-the-spring": ["GSC The Spring (Kuching)"],
}

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req,timeout=40) as r:
        return r.read().decode("utf-8","replace")

def hhmm(v):
    v=str(v).zfill(4)
    return f"{v[:2]}:{v[2:]}"

def main():
    now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    businessdate=now.date().isoformat()
    url=API+"getShowTimesByMovie_ParentChild_V2?"+urllib.parse.urlencode({
        "parentid":PARENT_ID,
        "oprndate":businessdate
    })
    raw=fetch(url)
    root=ET.fromstring(raw)

    data=json.loads(DATA.read_text(encoding="utf-8"))
    cinema_lookup={c["id"]:c for c in data.get("cinemas",[])}

    report={
        "collectorVersion":"12.0",
        "observedAt":now.isoformat(timespec="seconds"),
        "parentId":PARENT_ID,
        "childCode":CHILD_CODE,
        "businessDate":businessdate,
        "cinemas":{}
    }

    by_name={}
    for loc in root.findall(".//location"):
        by_name[loc.attrib.get("name","")]=loc

    for tracker_id,names in TRACKED.items():
        loc=None
        for n in names:
            if n in by_name:
                loc=by_name[n]; break
        row={"status":"not-found","sessions":[]}
        if loc is not None:
            row={
                "status":"ok",
                "officialLocationId":loc.attrib.get("id"),
                "officialName":loc.attrib.get("name"),
                "epaymentName":loc.attrib.get("epayment_name"),
                "isEpayment":loc.attrib.get("is_epayment"),
                "sessions":[]
            }
            child=None
            for ch in loc.findall("child"):
                if ch.attrib.get("code")==CHILD_CODE:
                    child=ch; break
            sessions=[]
            if child is not None:
                for s in child.findall("show"):
                    if s.attrib.get("date") != businessdate:
                        continue
                    sess={
                        "id":f"{tracker_id}-{s.attrib.get('id')}",
                        "time":hhmm(s.attrib.get("time","")),
                        "hall":s.attrib.get("hname") or s.attrib.get("hid") or "—",
                        "capacity":None,
                        "booked":None,
                        "available":None,
                        "occupancy":None,
                        "sourceStatus":"gsc-official-api",
                        "seatStatus":"seat-endpoint-not-yet-discovered",
                        "bookingUrl":None,
                        "sessionId":s.attrib.get("id"),
                        "officialLocationId":loc.attrib.get("id"),
                        "hallId":s.attrib.get("hid"),
                        "hallFull":s.attrib.get("hallfull"),
                        "type":s.attrib.get("type"),
                        "observedAt":now.isoformat(timespec="seconds"),
                    }
                    sessions.append(sess)
                    row["sessions"].append({
                        "sessionId":s.attrib.get("id"),
                        "time":hhmm(s.attrib.get("time","")),
                        "hall":s.attrib.get("hname"),
                        "hallId":s.attrib.get("hid"),
                        "hallFull":s.attrib.get("hallfull"),
                    })
            if tracker_id in cinema_lookup:
                cinema_lookup[tracker_id]["sessions"]=sessions
                cinema_lookup[tracker_id]["sourceStatus"]="gsc-official-api"
                cinema_lookup[tracker_id]["officialLocationId"]=loc.attrib.get("id")
                cinema_lookup[tracker_id]["officialCinemaName"]=loc.attrib.get("name")
        report["cinemas"][tracker_id]=row

    data["updatedAt"]=now.isoformat(timespec="seconds")
    data["totalShowsVerified"]=sum(len(c.get("sessions",[])) for c in data.get("cinemas",[]))
    DATA.write_text(json.dumps(data,indent=2),encoding="utf-8")
    OUT.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("GSC live showtimes updated:",OUT)

if __name__=="__main__":
    main()
