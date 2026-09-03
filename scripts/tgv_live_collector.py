#!/usr/bin/env python3
"""
TGV live collector for TIKUS!

Uses the same public, read-only API calls observed in TGV's public BUY NOW flow:
- moviesession_getmoviecinemas
- moviesession_get
- moviesession_getseatstatus

No seat is selected, no reservation is created, and no payment flow is entered.

Important interpretation:
TGV returns `seatstotal` and `seatsused`.
The tracker records these as:
  capacity = seatstotal
  booked = seatsused
  available = seatstotal - seatsused
  occupancy = seatsused / seatstotal

This is grounded in TGV's own public seat-status response, not a visual estimate.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, urllib.request, urllib.error

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/current.json"
DIAG=ROOT/"data/tgv-live-collector.json"

API="https://api.tgv.com.my/api"
MOVIE_ID="7b2216d1-27d8-479e-b420-8ab157847aa6"

# User's tracked TGV locations mapped to TGV's current official cinema IDs/names.
TRACKED={
    "tgv-tebrau": {"cinemaid":"TBR","officialName":"TEBRAU CITY"},
    "tgv-wangsa-walk": {"cinemaid":"WWM","officialName":"SUNWAY WANGSA MALL"},
    "tgv-gurney": {"cinemaid":"GUR","officialName":"GURNEY PARAGON"},
    "tgv-bukit-tinggi": {"cinemaid":"BBT","officialName":"BUKIT TINGGI"},
}

UA="Mozilla/5.0 (compatible; TIKUSPerformanceTracker/1.0)"

def post(path,payload):
    data=json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(
        API+path,
        data=data,
        headers={
            "User-Agent":UA,
            "Content-Type":"application/json",
            "Accept":"application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def walk_sessions(payload):
    """Yield session dicts from TGV's nested moviesession_get response."""
    results=payload.get("results") or {}
    businessday=results.get("businessday") or {}
    for cinema in businessday.get("cinemas") or []:
        for movie in cinema.get("movies") or []:
            if movie.get("movieid") != MOVIE_ID:
                continue
            for exp in movie.get("experiences") or []:
                for session in exp.get("sessions") or []:
                    yield session

def main():
    data=json.loads(DATA.read_text(encoding="utf-8"))
    now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    businessdate=now.date().isoformat()

    report={
        "collectorVersion":"8.0",
        "observedAt":now.isoformat(timespec="seconds"),
        "businessDate":businessdate,
        "movieId":MOVIE_ID,
        "tracked":{},
        "additionalTgvCinemasForMovie":[]
    }

    # Discover all cinemas showing the movie today, useful for detecting allocation changes.
    try:
        found=post("/boxoffice/v1/moviesession_getmoviecinemas",{
            "businessday":businessdate,
            "movieid":MOVIE_ID,
            "experienceGroup":""
        })
        locations=((found.get("results") or {}).get("locations") or [])
        tracked_ids={x["cinemaid"] for x in TRACKED.values()}
        for loc in locations:
            for c in loc.get("cinemaids") or []:
                if c.get("cinemaid") not in tracked_ids:
                    report["additionalTgvCinemasForMovie"].append({
                        "state":loc.get("state"),
                        "cinemaid":c.get("cinemaid"),
                        "name":c.get("name"),
                        "keyword":c.get("keyword")
                    })
    except Exception as exc:
        report["cinemaDiscoveryError"]=type(exc).__name__

    cinema_lookup={c["id"]:c for c in data.get("cinemas",[])}

    for tracker_id,meta in TRACKED.items():
        row={
            "cinemaid":meta["cinemaid"],
            "officialName":meta["officialName"],
            "sessions":[]
        }
        try:
            sessions_payload=post("/boxoffice/v1/moviesession_get",{
                "cinemaid":meta["cinemaid"],
                "businessdate":businessdate,
                "movieid":MOVIE_ID,
                "retrieveexpired":False
            })
            sessions=list(walk_sessions(sessions_payload))
            session_ids=[str(s["sessionid"]) for s in sessions if s.get("sessionid") is not None]

            status_by_id={}
            if session_ids:
                seat_payload=post("/boxoffice/v1/moviesession_getseatstatus",{
                    "cinemaid":meta["cinemaid"],
                    "sessionid":session_ids
                })
                for ss in ((seat_payload.get("results") or {}).get("seatstatuslist") or []):
                    status_by_id[str(ss.get("sessionid"))]=ss

            new_sessions=[]
            for s in sessions:
                sid=str(s.get("sessionid"))
                ss=status_by_id.get(sid,{})
                total=ss.get("seatstotal")
                used=ss.get("seatsused")
                total=int(total) if isinstance(total,(int,float)) else None
                used=int(used) if isinstance(used,(int,float)) else None
                available=(total-used) if total is not None and used is not None else None
                occupancy=(used/total*100) if total and used is not None else None
                showtime=(s.get("showtimemy") or "")
                time=showtime[11:16] if len(showtime)>=16 else showtime
                session={
                    "id":f"{tracker_id}-{sid}",
                    "time":time,
                    "hall":s.get("screenname") or "—",
                    "capacity":total,
                    "booked":used,
                    "available":available,
                    "occupancy":round(occupancy,2) if occupancy is not None else None,
                    "sourceStatus":"tgv-official-api",
                    "seatStatus":"tgv-official-seatstatus" if total is not None and used is not None else "seatstatus-unavailable",
                    "bookingUrl":"https://www.tgv.com.my/movies/details/tikus-2026",
                    "sessionId":sid,
                    "scheduledFilmId":s.get("scheduledfilmid"),
                    "experience":s.get("experience"),
                    "seatTypes":s.get("seattypes"),
                    "observedAt":now.isoformat(timespec="seconds")
                }
                new_sessions.append(session)
                row["sessions"].append({
                    "sessionId":sid,
                    "time":time,
                    "hall":s.get("screenname"),
                    "seatstotal":total,
                    "seatsused":used,
                    "available":available,
                    "occupancy":round(occupancy,2) if occupancy is not None else None
                })

            if tracker_id in cinema_lookup:
                cinema_lookup[tracker_id]["sessions"]=new_sessions
                cinema_lookup[tracker_id]["sourceStatus"]="tgv-official-api"
                cinema_lookup[tracker_id]["officialCinemaId"]=meta["cinemaid"]
                cinema_lookup[tracker_id]["officialCinemaName"]=meta["officialName"]
            row["status"]="ok"
        except Exception as exc:
            row["status"]="error"
            row["error"]=type(exc).__name__
        report["tracked"][tracker_id]=row

    data["updatedAt"]=now.isoformat(timespec="seconds")
    data["seatDataMode"]="tgv-live-official-api-plus-other-sources"
    data["totalShowsVerified"]=sum(len(c.get("sessions",[])) for c in data.get("cinemas",[]))

    DATA.write_text(json.dumps(data,indent=2),encoding="utf-8")
    DIAG.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("TGV live collector complete:",DIAG)

if __name__=="__main__":
    main()
