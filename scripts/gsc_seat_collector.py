#!/usr/bin/env python3
"""
GSC v15 — public read-only seat-status collector for TIKUS!

Confirmed official GSC endpoint:
  GET https://epaymentapi.gsc.com.my/showtimews/service.asmx/getHallSeatStatus
      ?locationid=<location>
      &hallid=<hall>
      &showdate=YYYY-MM-DD
      &showtime=HHMM

This endpoint is called by GSC's own seat-selection screen before a seat is
selected. It returns XML seat nodes with status values such as:
  A = available
  B = unavailable/booked in observed GSC UI traffic

Important:
- No GSC account/login is required.
- No sales transaction is initialized.
- No seat is selected or locked.
- No booking/payment action is performed.
- For conservative reporting, non-A seats are labelled "unavailable" because
  a non-A state may include booked, held, blocked or otherwise unavailable
  inventory. The tracker keeps `booked` only as a compatibility field.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/current.json"
OUT = ROOT / "data/gsc-live-seats.json"

API = (
    "https://epaymentapi.gsc.com.my/showtimews/service.asmx/"
    "getHallSeatStatus"
)
UA = "Mozilla/5.0 (compatible; TIKUSPerformanceTracker/1.0)"

def fetch(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/xml,text/xml,*/*",
            "Referer": "https://epaymentwebapp.gsc.com.my/",
        },
    )
    with urllib.request.urlopen(req, timeout=40) as response:
        return response.read().decode("utf-8", "replace")

def hhmm(time_text):
    return str(time_text or "").replace(":", "")[:4].zfill(4)

def session_date(session, fallback):
    return (
        session.get("businessDate")
        or session.get("showDate")
        or fallback
    )

def parse_seat_xml(raw):
    root = ET.fromstring(raw)
    seats = list(root.findall(".//col"))

    status_counts = Counter((seat.attrib.get("status") or "?") for seat in seats)
    type_counts = Counter((seat.attrib.get("type") or "?") for seat in seats)

    available = status_counts.get("A", 0)
    unavailable = len(seats) - available

    # `maximumseats` observed in GSC responses is the maximum selectable seats
    # per transaction, NOT the auditorium's physical capacity. Capacity is
    # therefore derived from returned seat nodes.
    capacity = len(seats)

    return {
        "hallNo": root.attrib.get("no"),
        "seatNodes": capacity,
        "capacity": capacity,
        "available": available,
        "unavailable": unavailable,
        "statusCounts": dict(status_counts),
        "seatTypeCounts": dict(type_counts),
        "maximumSelectableSeats": (
            int(root.attrib["maximumseats"])
            if root.attrib.get("maximumseats", "").isdigit()
            else None
        ),
        "rawHallBooked": (
            int(root.attrib["hbooked"])
            if root.attrib.get("hbooked", "").isdigit()
            else None
        ),
        "rawHallBlocked": (
            int(root.attrib["hblocked"])
            if root.attrib.get("hblocked", "").isdigit()
            else None
        ),
        "houseSeatsReleased": root.attrib.get("hsereleased"),
        "reservedReleased": root.attrib.get("resvreleased"),
    }

def main():
    now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    today = now.date().isoformat()

    data = json.loads(DATA.read_text(encoding="utf-8"))

    report = {
        "collectorVersion": "15.0",
        "observedAt": now.isoformat(timespec="seconds"),
        "policy": (
            "official public GSC seat-status XML; read-only; "
            "no transaction, seat selection, lock or payment"
        ),
        "countSemantics": (
            "capacity = returned seat nodes; available = status A; "
            "unavailable = all non-A states"
        ),
        "cinemas": {},
        "totals": {
            "sessionsQueried": 0,
            "sessionsMeasured": 0,
            "capacity": 0,
            "available": 0,
            "unavailable": 0,
        },
    }

    for cinema in data.get("cinemas", []):
        if not str(cinema.get("id", "")).startswith("gsc-"):
            continue

        cinema_report = {
            "name": cinema.get("name"),
            "officialLocationId": cinema.get("officialLocationId"),
            "sessions": [],
        }

        for session in cinema.get("sessions", []):
            location_id = (
                session.get("officialLocationId")
                or cinema.get("officialLocationId")
            )
            hall_id = session.get("hallId")
            show_date = session_date(session, today)
            show_time = hhmm(session.get("time"))

            item = {
                "sessionId": session.get("sessionId") or session.get("id"),
                "time": session.get("time"),
                "hall": session.get("hall"),
                "locationId": location_id,
                "hallId": hall_id,
                "showDate": show_date,
                "status": "not-queried",
            }

            if not location_id or not hall_id or len(show_time) != 4:
                item["status"] = "missing-identifiers"
                cinema_report["sessions"].append(item)
                continue

            report["totals"]["sessionsQueried"] += 1

            url = API + "?" + urllib.parse.urlencode(
                {
                    "locationid": location_id,
                    "hallid": hall_id,
                    "showdate": show_date,
                    "showtime": show_time,
                }
            )

            try:
                raw = fetch(url)
                measured = parse_seat_xml(raw)
                item.update(measured)
                item["status"] = "ok"
                item["endpoint"] = url

                capacity = measured["capacity"]
                available = measured["available"]
                unavailable = measured["unavailable"]
                occupancy = (
                    unavailable / capacity
                    if capacity
                    else None
                )

                # Compatibility fields used by the existing tracker UI.
                # `booked` should be displayed as unavailable/used for GSC,
                # not guaranteed completed ticket sales.
                session["capacity"] = capacity
                session["available"] = available
                session["unavailable"] = unavailable
                session["booked"] = unavailable
                session["occupancy"] = occupancy
                session["rawUnavailable"] = unavailable
                session["statusCounts"] = measured["statusCounts"]
                session["seatTypeCounts"] = measured["seatTypeCounts"]
                session["countSemantics"] = "gsc-status-A-vs-non-A"
                session["seatStatus"] = "gsc-public-seat-status"
                session["seatObservedAt"] = now.isoformat(timespec="seconds")

                report["totals"]["sessionsMeasured"] += 1
                report["totals"]["capacity"] += capacity
                report["totals"]["available"] += available
                report["totals"]["unavailable"] += unavailable

            except Exception as exc:
                item["status"] = "error"
                item["error"] = type(exc).__name__

            cinema_report["sessions"].append(item)

        report["cinemas"][cinema["id"]] = cinema_report

    # Coverage-aware summary. Do not imply unmeasured chains are zero.
    data["updatedAt"] = now.isoformat(timespec="seconds")
    data["gscSeatCoverage"] = {
        "sessionsMeasured": report["totals"]["sessionsMeasured"],
        "sessionsQueried": report["totals"]["sessionsQueried"],
        "capacity": report["totals"]["capacity"],
        "available": report["totals"]["available"],
        "unavailable": report["totals"]["unavailable"],
        "countSemantics": "gsc-status-A-vs-non-A",
        "observedAt": now.isoformat(timespec="seconds"),
    }

    DATA.write_text(json.dumps(data, indent=2), encoding="utf-8")
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        "GSC seats measured:",
        report["totals"]["sessionsMeasured"],
        "/",
        report["totals"]["sessionsQueried"],
    )
    print("Wrote:", OUT)

if __name__ == "__main__":
    main()
