#!/usr/bin/env python3
"""
One-time GSC historical recovery for launch day 2026-09-03.

Purpose:
Some official GSC session IDs/hall IDs were observed earlier in the day but
were lost from current.json before v17 preservation logic was deployed. This
script restores those already-observed identifiers and last-known seat states
for sessions we actually captured.

It does NOT invent identifiers and does NOT query booking endpoints.
"""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/current.json"

# Confirmed from earlier same-day official GSC snapshots already captured.
RECOVERY = {
    "gsc-paradigm-jb": {
        "20:00": {
            "sessionId": "289309",
            "hallId": "2",
            "hall": "2",
            "officialLocationId": "355",
            "capacity": 246,
            "available": 246,
            "booked": 0,
            "otherUnavailable": 0,
            "unavailable": 0,
            "occupancy": 0.0,
            "unavailableRate": 0.0,
            "statusCounts": {"A": 246},
            "seatTypeCounts": {"N": 226, "H": 4, "T": 14, "W": 2},
            "seatObservedAt": "2026-09-03T20:02:07+08:00"
        }
    },
    "gsc-midvalley": {
        "20:00": {
            "sessionId": "924428",
            "hallId": "2",
            "hall": "2",
            "officialLocationId": "210",
            "capacity": 164,
            "available": 162,
            "booked": 2,
            "otherUnavailable": 0,
            "unavailable": 2,
            "occupancy": 2 / 164,
            "unavailableRate": 2 / 164,
            "statusCounts": {"A": 162, "B": 2},
            "seatTypeCounts": {"N": 154, "H": 2, "T": 6, "W": 2},
            "seatObservedAt": "2026-09-03T20:02:07+08:00"
        }
    },
    "gsc-aman-central": {
        "20:00": {
            "sessionId": "213312",
            "hallId": "4",
            "hall": "4",
            "officialLocationId": "133",
            "capacity": 202,
            "available": 201,
            "booked": 1,
            "otherUnavailable": 0,
            "unavailable": 1,
            "occupancy": 1 / 202,
            "unavailableRate": 1 / 202,
            "statusCounts": {"A": 201, "B": 1},
            "seatTypeCounts": {"N": 186, "H": 4, "T": 10, "W": 2},
            "seatObservedAt": "2026-09-03T20:02:07+08:00"
        }
    },
    "gsc-dataran-pahlawan": {
        "20:00": {
            "sessionId": "406740",
            "hallId": "7",
            "hall": "7",
            "officialLocationId": "331",
            "capacity": 266,
            "available": 265,
            "booked": 0,
            "otherUnavailable": 1,
            "unavailable": 1,
            "occupancy": 0.0,
            "unavailableRate": 1 / 266,
            "statusCounts": {"A": 265, "D": 1},
            "seatTypeCounts": {"N": 248, "H": 4, "T": 14},
            "seatObservedAt": "2026-09-03T20:02:07+08:00"
        }
    },
    "gsc-kuantan-city-mall": {
        "20:00": {
            "sessionId": "79951",
            "hallId": "4",
            "hall": "HALL 4",
            "officialLocationId": "431",
            "capacity": 157,
            "available": 155,
            "booked": 0,
            "otherUnavailable": 2,
            "unavailable": 2,
            "occupancy": 0.0,
            "unavailableRate": 2 / 157,
            "statusCounts": {"A": 155, "D": 2},
            "seatTypeCounts": {"N": 142, "H": 2, "T": 12, "W": 1},
            "seatObservedAt": "2026-09-03T20:02:07+08:00"
        }
    },
    "gsc-ioi-city-mall": {
        "20:00": {
            "sessionId": "339696",
            "hallId": "2",
            "hall": "2",
            "officialLocationId": "257",
            "capacity": 220,
            "available": 218,
            "booked": 1,
            "otherUnavailable": 1,
            "unavailable": 2,
            "occupancy": 1 / 220,
            "unavailableRate": 2 / 220,
            "statusCounts": {"A": 218, "B": 1, "D": 1},
            "seatTypeCounts": {"N": 196, "H": 4, "T": 18, "W": 2},
            "seatObservedAt": "2026-09-03T20:02:07+08:00"
        }
    }
}

def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if data.get("date") != "2026-09-03":
        print("Recovery skipped: tracker date is not 2026-09-03")
        return

    now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(timespec="seconds")
    changed = 0

    for cinema in data.get("cinemas", []):
        cid = cinema.get("id")
        mapping = RECOVERY.get(cid)
        if not mapping:
            continue

        sessions = cinema.get("sessions", [])
        by_time = {str(s.get("time")): s for s in sessions}

        for time_text, recovered in mapping.items():
            existing = by_time.get(time_text)
            if not existing:
                existing = {
                    "id": f"{cid}-{recovered['sessionId']}",
                    "time": time_text,
                    "bookingUrl": None,
                }
                sessions.append(existing)

            # Never overwrite a newer official live observation for the same
            # session. Otherwise, restore only confirmed earlier observations.
            if existing.get("sessionId") and str(existing.get("sessionId")) == recovered["sessionId"]:
                target = existing
            elif existing.get("sourceStatus") == "gsc-official-api" and not existing.get("isExpired"):
                continue
            else:
                target = existing

            target.update({
                "id": f"{cid}-{recovered['sessionId']}",
                "sessionId": recovered["sessionId"],
                "time": time_text,
                "hall": recovered["hall"],
                "hallId": recovered["hallId"],
                "officialLocationId": recovered["officialLocationId"],
                "capacity": recovered["capacity"],
                "available": recovered["available"],
                "booked": recovered["booked"],
                "otherUnavailable": recovered["otherUnavailable"],
                "unavailable": recovered["unavailable"],
                "occupancy": recovered["occupancy"],
                "unavailableRate": recovered["unavailableRate"],
                "statusCounts": recovered["statusCounts"],
                "seatTypeCounts": recovered["seatTypeCounts"],
                "countSemantics": "gsc-A-available-B-booked-other-separate",
                "sourceStatus": "gsc-last-observed",
                "seatStatus": "last-observed",
                "seatObservedAt": recovered["seatObservedAt"],
                "lastObservedAt": recovered["seatObservedAt"],
                "isExpired": True,
                "observedAt": recovered["seatObservedAt"],
            })
            changed += 1

        cinema["sessions"] = sorted(
            sessions,
            key=lambda s: tuple(int(x) for x in str(s.get("time","99:99")).split(":")[:2])
        )

    data["updatedAt"] = now
    data["totalShowsVerified"] = sum(
        len(c.get("sessions", [])) for c in data.get("cinemas", [])
    )
    data["gscHistoricalRecovery"] = {
        "applied": True,
        "recoveredSessions": changed,
        "source": "previously observed official same-day GSC snapshots",
        "appliedAt": now,
    }

    DATA.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Recovered {changed} GSC historical sessions.")

if __name__ == "__main__":
    main()
