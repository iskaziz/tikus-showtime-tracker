#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, shutil

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/current.json"
TEMPLATE = ROOT / "data/day-template.json"
DAYS = ROOT / "data/days"
INDEX = DAYS / "index.json"
MY = ZoneInfo("Asia/Kuala_Lumpur")

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def blank_day(date_text, now):
    tpl = read_json(TEMPLATE)
    tpl["date"] = date_text
    tpl["updatedAt"] = now.isoformat(timespec="seconds")
    tpl["totalShowsVerified"] = 0
    for cinema in tpl.get("cinemas", []):
        cinema["sessions"] = []
        cinema["sourceStatus"] = "awaiting-refresh"
    return tpl

def update_index(current_date):
    try:
        idx = read_json(INDEX)
    except Exception:
        idx = {"days": []}

    rows = []
    seen = set()

    for row in idx.get("days", []):
        d = row.get("date")
        if not d or d in seen:
            continue
        seen.add(d)
        rows.append({
            "date": d,
            "file": "current.json" if d == current_date else f"days/{d}.json",
            "label": row.get("label") or d,
            "status": "current" if d == current_date else "archived",
        })

    if current_date not in seen:
        rows.append({
            "date": current_date,
            "file": "current.json",
            "label": current_date,
            "status": "current",
        })

    rows.sort(key=lambda x: x["date"])
    write_json(INDEX, {"days": rows})

def main():
    now = datetime.now(MY)
    today = now.date().isoformat()
    DAYS.mkdir(exist_ok=True)

    try:
        current = read_json(DATA)
    except Exception:
        current = blank_day(today, now)
        write_json(DATA, current)
        update_index(today)
        print("current.json unreadable; created clean day:", today)
        return

    current_date = current.get("date")
    if current_date == today:
        update_index(today)
        print("No rollover needed:", today)
        return

    if current_date:
        archive = DAYS / f"{current_date}.json"
        # Archive only if we do not already have a historical copy.
        # This prevents a post-midnight contaminated current.json from replacing
        # an earlier clean archive.
        if not archive.exists():
            archived = dict(current)
            archived["archiveStatus"] = "automatic-rollover"
            archived["archivedAt"] = now.isoformat(timespec="seconds")
            write_json(archive, archived)
            print("Archived:", current_date)
        else:
            print("Archive already exists; preserved existing copy:", current_date)

    fresh = blank_day(today, now)
    fresh["rollover"] = {
        "fromDate": current_date,
        "toDate": today,
        "rolledAt": now.isoformat(timespec="seconds"),
    }
    write_json(DATA, fresh)
    update_index(today)
    print("Started new tracker day:", today)

if __name__ == "__main__":
    main()
