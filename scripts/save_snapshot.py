#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/current.json"
HIST=ROOT/"data/history"
INDEX=ROOT/"data/history-index.json"

data=json.loads(DATA.read_text(encoding="utf-8"))
now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
dataset_date=data.get("date") or now.date().isoformat()
day_hist=HIST/dataset_date
day_hist.mkdir(parents=True,exist_ok=True)

stamp=now.strftime("%Y%m%dT%H%M%S%z")
known=[]
for c in data["cinemas"]:
    for s in c.get("sessions",[]):
        if isinstance(s.get("capacity"),int) and isinstance(s.get("booked"),int):
            known.append({
                "cinemaId":c["id"],"cinema":c["name"],"chain":c.get("chain"),
                "time":s["time"],"booked":s["booked"],
                "rawSeatsUsed":s.get("rawSeatsUsed"),
                "otherUnavailable":s.get("otherUnavailable"),
                "available":s.get("available"),"capacity":s["capacity"],
                "occupancy":s.get("occupancy"),"countSemantics":s.get("countSemantics")
            })

snap={
    "datasetDate":dataset_date,
    "observedAt":now.isoformat(timespec="seconds"),
    "sessions":known,
    "booked":sum(x["booked"] for x in known) if known else None,
    "capacity":sum(x["capacity"] for x in known) if known else None
}
rel=f"history/{dataset_date}/{stamp}.json"
(day_hist/f"{stamp}.json").write_text(json.dumps(snap,indent=2),encoding="utf-8")

try: idx=json.loads(INDEX.read_text(encoding="utf-8"))
except Exception: idx={"snapshots":[]}

idx["snapshots"].append({
    "datasetDate":dataset_date,
    "observedAt":snap["observedAt"],
    "booked":snap["booked"],
    "capacity":snap["capacity"],
    "file":rel
})
idx["snapshots"]=idx["snapshots"][-500:]
INDEX.write_text(json.dumps(idx,indent=2),encoding="utf-8")
print("snapshot saved",dataset_date,stamp,len(known),"sessions")
