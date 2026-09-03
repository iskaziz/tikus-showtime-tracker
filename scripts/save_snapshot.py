#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/current.json"
HIST=ROOT/"data/history"
INDEX=ROOT/"data/history-index.json"
HIST.mkdir(exist_ok=True)

data=json.loads(DATA.read_text(encoding="utf-8"))
now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
stamp=now.strftime("%Y%m%dT%H%M%S%z")
known=[]
for c in data["cinemas"]:
    for s in c.get("sessions",[]):
        if isinstance(s.get("booked"),int) and isinstance(s.get("capacity"),int):
            known.append({
                "cinemaId":c["id"],"cinema":c["name"],"time":s["time"],
                "booked":s["booked"],"available":s.get("available"),
                "capacity":s["capacity"],"occupancy":s.get("occupancy")
            })
snap={"observedAt":now.isoformat(timespec="seconds"),"sessions":known,
      "booked":sum(x["booked"] for x in known) if known else None,
      "capacity":sum(x["capacity"] for x in known) if known else None}
(HIST/f"{stamp}.json").write_text(json.dumps(snap,indent=2),encoding="utf-8")
try: idx=json.loads(INDEX.read_text(encoding="utf-8"))
except: idx={"snapshots":[]}
idx["snapshots"].append({"observedAt":snap["observedAt"],"booked":snap["booked"],"capacity":snap["capacity"],"file":f"history/{stamp}.json"})
idx["snapshots"]=idx["snapshots"][-200:]
INDEX.write_text(json.dumps(idx,indent=2),encoding="utf-8")
print("snapshot saved",stamp,len(known),"sessions")
