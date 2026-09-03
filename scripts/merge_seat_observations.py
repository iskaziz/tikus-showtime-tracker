#!/usr/bin/env python3
"""
Merge exact seat observations from an authorised cinema/booking report or a
manual verified count. No estimates are accepted.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/current.json"
OBS=ROOT/"data/seat-observations.json"

if not OBS.exists():
    print("No authorised seat observations supplied; skipping.")
    raise SystemExit(0)

data=json.loads(DATA.read_text(encoding="utf-8"))
obs=json.loads(OBS.read_text(encoding="utf-8")).get("observations",[])
lookup={(o["cinemaId"],o["time"]):o for o in obs}
merged=0

for c in data["cinemas"]:
    for s in c.get("sessions",[]):
        o=lookup.get((c["id"],s["time"]))
        if not o: continue
        cap=int(o["capacity"]); booked=int(o["booked"])
        if cap <= 0 or booked < 0 or booked > cap:
            continue
        s["capacity"]=cap
        s["booked"]=booked
        s["available"]=cap-booked
        s["occupancy"]=round(booked/cap*100,2)
        s["seatStatus"]="verified-external-observation"
        s["seatSource"]=o.get("source","verified-observation")
        s["observedAt"]=o.get("observedAt") or datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds")
        merged += 1

DATA.write_text(json.dumps(data,indent=2),encoding="utf-8")
print(f"Merged {merged} seat observations.")
