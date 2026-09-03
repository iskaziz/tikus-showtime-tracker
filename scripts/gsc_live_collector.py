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
import json, urllib.request, urllib.parse, xml.etree.ElementTree as ET, re

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/current.json"
OUT=ROOT/"data/gsc-live-collector.json"

API="https://epaymentapi.gsc.com.my/showtimews/service.asmx/"
PARENT_ID="6363"
CHILD_CODE="1000005309"
UA="Mozilla/5.0 (compatible; TIKUSPerformanceTracker/1.0)"

TRACKED = {
    "gsc-midvalley": {"locationId":"210","names":["GSC Mid Valley","GSC Mid Valley Megamall"]},
    "gsc-ioi-city-mall": {"locationId":"257","names":["GSC IOI City Mall (West) (Putrajaya)"]},
    "gsc-aman-central": {"locationId":"133","names":["GSC Aman Central"]},
    "gsc-dataran-pahlawan": {"locationId":"331","names":["GSC Dataran Pahlawan"]},
    "gsc-paradigm-jb": {"locationId":"355","names":["GSC Paradigm Mall (Johor Bahru)"]},
    "gsc-kuantan-city-mall": {"locationId":"431","names":["GSC Kuantan City Mall"]},
    "gsc-imago": {"locationId":"531","names":["GSC IMAGO Shopping Mall"]},
    "gsc-the-spring": {"locationId":"552","names":["GSC The Spring (Kuching)"]},
}

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req,timeout=40) as r:
        return r.read().decode("utf-8","replace")

def hhmm(v):
    v=str(v).zfill(4)
    return f"{v[:2]}:{v[2:]}"

def norm_name(value):
    value=(value or "").lower()
    value=value.replace("&"," and ")
    value=re.sub(r"[^a-z0-9]+"," ",value)
    return " ".join(value.split())

def main():
    now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    data=json.loads(DATA.read_text(encoding="utf-8"))
    businessdate=data.get("date") or now.date().isoformat()
    url=API+"getShowTimesByMovie_ParentChild_V2?"+urllib.parse.urlencode({
        "parentid":PARENT_ID,
        "oprndate":businessdate
    })
    raw=fetch(url)
    root=ET.fromstring(raw)

    cinema_lookup={c["id"]:c for c in data.get("cinemas",[])}

    report={
        "collectorVersion":"19.4",
        "observedAt":now.isoformat(timespec="seconds"),
        "parentId":PARENT_ID,
        "childCode":CHILD_CODE,
        "businessDate":businessdate,
        "cinemas":{}
    }

    locations=list(root.findall(".//location"))
    by_name={}
    by_id={}
    for loc in locations:
        raw_name=loc.attrib.get("name","")
        by_name[norm_name(raw_name)]=loc

        # GSC has used slightly different attribute names across responses.
        # Index every plausible location-id field rather than assuming only "id".
        for key in ("id","locationid","location_id","locid","cinemaid","code"):
            value=loc.attrib.get(key)
            if value:
                by_id[str(value)]=loc

    for tracker_id,config in TRACKED.items():
        loc=None
        match_method=None

        expected_id=str(config.get("locationId") or "")
        if expected_id and expected_id in by_id:
            loc=by_id[expected_id]
            match_method="location-id"

        # Exact normalized aliases.
        if loc is None:
            for n in config.get("names",[]):
                candidate=by_name.get(norm_name(n))
                if candidate is not None:
                    loc=candidate
                    match_method="normalized-name"
                    break

        # Resilient token match for harmless GSC naming variations.
        # This is particularly useful for "Mid Valley" vs "Mid Valley Megamall".
        if loc is None:
            alias_tokens=[]
            for n in config.get("names",[]):
                tokens=[t for t in norm_name(n).split() if t not in {"gsc","mall","megamall","shopping","cinema"}]
                if tokens:
                    alias_tokens.append(set(tokens))
            for candidate in locations:
                candidate_tokens=set(norm_name(candidate.attrib.get("name","")).split())
                if any(tokens.issubset(candidate_tokens) for tokens in alias_tokens):
                    loc=candidate
                    match_method="token-name"
                    break
        row={"status":"not-found","sessions":[]}
        if loc is not None:
            resolved_location_id=(
                loc.attrib.get("id")
                or loc.attrib.get("locationid")
                or loc.attrib.get("location_id")
                or loc.attrib.get("locid")
                or loc.attrib.get("cinemaid")
                or expected_id
            )
            row={
                "status":"ok",
                "matchMethod":match_method,
                "officialLocationId":resolved_location_id,
                "officialName":loc.attrib.get("name"),
                "locationAttributes":dict(loc.attrib),
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
                        "officialLocationId":resolved_location_id,
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
                cinema = cinema_lookup[tracker_id]
                previous = cinema.get("sessions", [])

                current_ids = {
                    str(sess.get("sessionId"))
                    for sess in sessions
                    if sess.get("sessionId")
                }
                current_times = {
                    str(sess.get("time"))
                    for sess in sessions
                    if sess.get("time")
                }

                merged = list(sessions)

                for old_session in previous:
                    old_id = str(old_session.get("sessionId") or "")
                    old_time = str(old_session.get("time") or "")

                    # Current official row wins over any previous copy or seed row
                    # for the same official id / clock time.
                    if old_id in current_ids or old_time in current_times:
                        continue

                    kept = dict(old_session)

                    # Official sessions observed earlier today are preserved after
                    # GSC removes them from the current-showtime feed.
                    if old_id and not old_id.startswith("gsc-"):
                        kept["isExpired"] = True
                        kept["sourceStatus"] = "gsc-last-observed"
                        kept["lastObservedAt"] = (
                            kept.get("seatObservedAt")
                            or kept.get("observedAt")
                            or now.isoformat(timespec="seconds")
                        )
                        if kept.get("capacity") is not None:
                            kept["seatStatus"] = "last-observed"
                        else:
                            kept["seatStatus"] = kept.get("seatStatus") or "last-observed"
                        merged.append(kept)
                        continue

                    # Legacy seed rows may pre-date our first official observation.
                    # Keep them only as clearly labelled historical schedule rows;
                    # never fabricate official GSC identifiers for them.
                    if old_id.startswith("gsc-"):
                        kept["isExpired"] = True
                        kept["sourceStatus"] = "historical-seed"
                        kept["seatStatus"] = kept.get("seatStatus") or "historical-schedule"
                        merged.append(kept)

                def sort_key(sess):
                    value = str(sess.get("time") or "99:99")
                    try:
                        hh, mm = [int(x) for x in value.split(":")[:2]]
                        return hh * 60 + mm
                    except Exception:
                        return 9999

                cinema["sessions"] = sorted(merged, key=sort_key)
                cinema["sourceStatus"]="gsc-official-api"
                cinema["officialLocationId"]=resolved_location_id
                cinema["officialCinemaName"]=loc.attrib.get("name")
        report["cinemas"][tracker_id]=row

    data["updatedAt"]=now.isoformat(timespec="seconds")
    data["totalShowsVerified"]=sum(len(c.get("sessions",[])) for c in data.get("cinemas",[]))
    DATA.write_text(json.dumps(data,indent=2),encoding="utf-8")
    OUT.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("GSC live showtimes updated:",OUT)

if __name__=="__main__":
    main()
