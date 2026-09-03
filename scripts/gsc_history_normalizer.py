#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/current.json"

def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds")

    for cinema in data.get("cinemas", []):
        if not str(cinema.get("id", "")).startswith("gsc-"):
            continue

        for session in cinema.get("sessions", []):
            sid = str(session.get("sessionId") or "")

            if sid.startswith("gsc-"):
                session.setdefault("sourceStatus", "historical-seed")
                session.setdefault("seatStatus", "historical-schedule")

            if session.get("isExpired"):
                session.setdefault(
                    "lastObservedAt",
                    session.get("seatObservedAt")
                    or session.get("observedAt")
                    or now
                )
                if session.get("capacity") is not None:
                    session["seatStatus"] = "last-observed"

    data["updatedAt"] = now
    data["totalShowsVerified"] = sum(
        len(cinema.get("sessions", []))
        for cinema in data.get("cinemas", [])
    )
    DATA.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("GSC historical sessions normalized.")

if __name__ == "__main__":
    main()
