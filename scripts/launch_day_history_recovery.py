#!/usr/bin/env python3
"""
TIKUS! launch-day history recovery for 2026-09-03.

This script restores the full confirmed same-day showtime list for the tracked
GSC and TGV cinemas so the dashboard's "shows today" count does not shrink as
cinema APIs remove expired sessions.

Rules:
- Never invent official identifiers.
- Reuse previously observed official IDs and seat snapshots only where captured.
- Otherwise preserve the confirmed showtime as historical/unmeasured.
- Existing newer live rows win over recovered historical rows.
"""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/current.json"

GSC_SCHEDULES = {
    "gsc-paradigm-jb": ["10:40","13:00","15:20","17:40","20:00"],
    "gsc-aman-central": ["10:40","13:00","15:20","17:40","20:00","22:20"],
    "gsc-midvalley": ["10:40","13:00","15:20","17:40","20:00"],
    "gsc-dataran-pahlawan": ["10:40","13:00","15:20","17:40","20:00","22:20"],
    "gsc-kuantan-city-mall": ["10:40","13:00","15:20","17:40","20:00","22:20"],
    "gsc-ioi-city-mall": ["10:40","13:00","15:20","17:40","20:00","22:20"],
    "gsc-imago": ["12:10","14:30","16:50","19:10","21:30"],
    "gsc-the-spring": ["12:10","14:30","16:50","19:10","21:30"],
}

TGV_SCHEDULES = {
    "tgv-tebrau": ["11:30","13:00","15:30","20:00","00:45"],
    "tgv-wangsa-walk": ["11:20","16:15","18:15","21:45"],
    "tgv-gurney": ["13:15","15:45","18:15","20:45"],
    "tgv-bukit-tinggi": ["11:45","14:10","18:05","20:30"],
    "tgv-1utama": [],
}

# Previously observed official GSC IDs/halls from earlier launch-day snapshots.
GSC_IDS = {
    "gsc-paradigm-jb": {
        "15:20": ("289307","2"), "17:40": ("289308","2"), "20:00": ("289309","2")
    },
    "gsc-aman-central": {
        "15:20": ("213310","4"), "17:40": ("213311","4"),
        "20:00": ("213312","4"), "22:20": ("213313","4")
    },
    "gsc-midvalley": {
        "15:20": ("924426","2"), "17:40": ("924427","2"), "20:00": ("924428","2")
    },
    "gsc-dataran-pahlawan": {
        "15:20": ("406743","7"), "17:40": ("406742","7"),
        "20:00": ("406740","7"), "22:20": ("406741","7")
    },
    "gsc-kuantan-city-mall": {
        "15:20": ("79949","4"), "17:40": ("79950","4"),
        "20:00": ("79951","4"), "22:20": ("79952","4")
    },
    "gsc-ioi-city-mall": {
        "15:20": ("339694","2"), "17:40": ("339695","2"),
        "20:00": ("339696","2"), "22:20": ("339697","2")
    },
    "gsc-imago": {
        "14:30": ("77183","1"), "16:50": ("77184","1"),
        "19:10": ("77185","1"), "21:30": ("77186","1")
    },
    "gsc-the-spring": {
        "14:30": ("77710","3"), "16:50": ("77711","3"),
        "19:10": ("77712","3"), "21:30": ("77713","3")
    },
}

# Previously observed TGV official session IDs from the 12:48 snapshot.
# 1Utama was confirmed as a tracked cinema, but no launch-day session list was
# captured in the earlier snapshot, so we do not invent showtimes for it.
TGV_IDS = {
    "tgv-tebrau": {
        "13:00": "430819", "15:30": "430820", "20:00": "430821", "00:45": "430822"
    },
    "tgv-wangsa-walk": {
        "16:15": "310888", "18:15": "310889", "21:45": "310890"
    },
    "tgv-gurney": {
        "13:15": "334693", "15:45": "334694", "18:15": "334695", "20:45": "334696"
    },
    "tgv-bukit-tinggi": {
        "14:10": "329906", "18:05": "329907", "20:30": "329908"
    },
}

def time_sort_key(s):
    t = str(s.get("time") or "99:99")
    try:
        h, m = [int(x) for x in t.split(":")[:2]]
    except Exception:
        return 9999
    # For TGV business-date semantics, 00:xx is a late-night show belonging to
    # the same business date, so sort it after evening sessions.
    if s.get("chainHint") == "TGV" and h < 4:
        h += 24
    return h * 60 + m

def recover_schedule(cinema, schedule, id_map, chain):
    sessions = cinema.setdefault("sessions", [])
    by_time = {str(s.get("time")): s for s in sessions}

    for t in schedule:
        if t in by_time:
            row = by_time[t]
            # Preserve current live rows. Add missing official IDs only if known.
            ident = id_map.get(t)
            if chain == "GSC" and ident:
                sid, hall = ident
                row.setdefault("sessionId", sid)
                row.setdefault("hallId", hall)
                if row.get("hall") in (None, "", "—"):
                    row["hall"] = hall
            elif chain == "TGV" and ident:
                row.setdefault("sessionId", ident)
            continue

        row = {
            "id": f"{cinema['id']}-{t.replace(':','')}",
            "time": t,
            "capacity": None,
            "booked": None,
            "available": None,
            "occupancy": None,
            "bookingUrl": None,
            "isExpired": True,
            "sourceStatus": "historical-confirmed-showtime",
            "seatStatus": "not-observed",
            "chainHint": chain,
        }

        ident = id_map.get(t)
        if chain == "GSC" and ident:
            sid, hall = ident
            row["id"] = f"{cinema['id']}-{sid}"
            row["sessionId"] = sid
            row["hallId"] = hall
            row["hall"] = hall
            row["seatStatus"] = "last-observed-identifiers"
        elif chain == "TGV" and ident:
            row["id"] = f"{cinema['id']}-{ident}"
            row["sessionId"] = ident
            row["seatStatus"] = "last-observed-identifiers"

        sessions.append(row)
        by_time[t] = row

    # Merge duplicate rows with same time, preferring official/live/observed data.
    merged = {}
    for s in sessions:
        key = str(s.get("time"))
        existing = merged.get(key)
        if existing is None:
            merged[key] = s
            continue

        def score(x):
            return (
                5 if x.get("sourceStatus") in ("gsc-official-api","tgv-official-api") else 0,
                4 if x.get("capacity") is not None else 0,
                3 if x.get("sessionId") else 0,
                2 if x.get("seatObservedAt") else 0,
                1 if not x.get("isExpired") else 0,
            )
        if score(s) > score(existing):
            merged[key] = s

    cinema["sessions"] = list(merged.values())
    for s in cinema["sessions"]:
        s.pop("chainHint", None)

def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if data.get("date") != "2026-09-03":
        print("Launch-day history recovery skipped: date is not 2026-09-03")
        return

    now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds")
    cinemas = {c.get("id"): c for c in data.get("cinemas", [])}

    for cid, schedule in GSC_SCHEDULES.items():
        cinema = cinemas.get(cid)
        if cinema:
            recover_schedule(cinema, schedule, GSC_IDS.get(cid, {}), "GSC")

    for cid, schedule in TGV_SCHEDULES.items():
        cinema = cinemas.get(cid)
        if cinema:
            recover_schedule(cinema, schedule, TGV_IDS.get(cid, {}), "TGV")

    # Stable order, with TGV 00:xx at end of business day.
    for cinema in data.get("cinemas", []):
        chain = cinema.get("chain")
        def key(s):
            t = str(s.get("time") or "99:99")
            try:
                h, m = [int(x) for x in t.split(":")[:2]]
            except Exception:
                return 9999
            if chain == "TGV" and h < 4:
                h += 24
            return h * 60 + m
        cinema["sessions"] = sorted(cinema.get("sessions", []), key=key)

    data["updatedAt"] = now
    data["launchDayHistoryRecovery"] = {
        "applied": True,
        "date": "2026-09-03",
        "source": "previously confirmed showtimes plus previously observed official IDs where captured",
        "appliedAt": now,
    }
    data["totalShowsVerified"] = sum(len(c.get("sessions", [])) for c in data.get("cinemas", []))

    DATA.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Launch-day history restored. totalShowsVerified={data['totalShowsVerified']}")

if __name__ == "__main__":
    main()
