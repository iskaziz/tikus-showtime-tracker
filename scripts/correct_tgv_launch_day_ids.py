#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/current.json"

CORRECT = {
    "tgv-tebrau": {"13:00":"430663","15:30":"430673","20:00":"430680","00:45":"430822"},
    "tgv-wangsa-walk": {"16:15":"310888","18:15":"310892","21:45":"310890"},
    "tgv-gurney": {"13:15":"220134","15:45":"220144","18:15":"220129","20:45":"220138"},
    "tgv-bukit-tinggi": {"14:10":"409356","18:05":"409359","20:30":"409357"},
    "tgv-1utama": {"15:00":"324678"},
}

def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    for cinema in data.get("cinemas", []):
        mapping = CORRECT.get(cinema.get("id"))
        if not mapping:
            continue
        for row in cinema.get("sessions", []):
            t = str(row.get("time"))
            if t in mapping:
                sid = mapping[t]
                row["sessionId"] = sid
                row["id"] = f"{cinema['id']}-{sid}"
    DATA.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("Corrected TGV launch-day session IDs to observed official values.")

if __name__ == "__main__":
    main()
