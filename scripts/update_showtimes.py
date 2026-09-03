#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, re, urllib.request

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/current.json"
UA="Mozilla/5.0 (compatible; TIKUSShowtimeMonitor/1.1)"

SOURCES={
"gsc-paradigm-jb":"https://xinemas.com/cinema/in-johor-bahru/gsc-paradigm-mall-johor.html",
"gsc-aman-central":"https://xinemas.com/cinema/in-alor-setar/gsc-aman-central-alor-setar.html",
"gsc-midvalley":"https://xinemas.com/cinema/in-kuala-lumpur/gsc-mid-valley-megamall-kuala-lumpur.html",
"gsc-dataran-pahlawan":"https://xinemas.com/cinema/in-melaka/gsc-dataran-pahlawan-melaka.html",
"gsc-kuantan-city-mall":"https://xinemas.com/cinema/in-kuantan/gsc-kuantan-city-mall.html",
"gsc-ioi-city-mall":"https://xinemas.com/cinema/in-putrajaya/gsc-ioi-city-mall-kuala-lumpur.html",
"gsc-imago":"https://xinemas.com/cinema/in-kota-kinabalu/gsc-imago-mall.html",
"gsc-the-spring":"https://xinemas.com/cinema/in-kuching/gsc-the-spring-shopping-mall.html",
"tgv-tebrau":"https://xinemas.com/cinema/in-johor-bahru/tgv-tebrau-city.html",
"tgv-wangsa-walk":"https://xinemas.com/cinema/in-kuala-lumpur/tgv-wangsa-walk.html",
"tgv-gurney":"https://xinemas.com/cinema/in-penang/tgv-gurney-paragon.html",
"tgv-bukit-tinggi":"https://xinemas.com/cinema/in-klang/tgv-bukit-tinggi.html",
}

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Cache-Control":"no-cache"})
    with urllib.request.urlopen(req,timeout=25) as r:
        return r.read().decode("utf-8","ignore")

def textify(html):
    html=re.sub(r"<script.*?</script>|<style.*?</style>"," ",html,flags=re.S|re.I)
    html=re.sub(r"<[^>]+>"," ",html)
    return re.sub(r"\s+"," ",html)

def normalize_time(t):
    t=t.upper().strip()
    dt=datetime.strptime(t,"%I:%M %p")
    return dt.strftime("%H:%M")

def xinemas_tikus_times(html):
    text=textify(html)
    # isolate the TIKUS! entry until the next WATCH IN OTHER CINEMA / movie heading
    m=re.search(r"Tikus!\s*P?13(.{0,2600}?)(?:WATCH IN OTHER CINEMA|Can't find|COMING SOON)",text,re.I)
    if not m: return []
    block=m.group(1)
    raw=re.findall(r"\b(?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:AM|PM)\b",block,re.I)
    return list(dict.fromkeys(normalize_time(x) for x in raw))

def load_tracker_data():
    raw = DATA.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        template = ROOT / "data/day-template.json"
        if not template.exists():
            raise
        now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
        recovered = json.loads(template.read_text(encoding="utf-8"))
        recovered["date"] = now.date().isoformat()
        recovered["updatedAt"] = now.isoformat(timespec="seconds")
        for cinema in recovered.get("cinemas", []):
            cinema["sessions"] = []
            cinema["sourceStatus"] = "awaiting-refresh"
        print(
            f"WARNING: data/current.json invalid "
            f"(line {exc.lineno}, column {exc.colno}); "
            "created a clean current-day tracker."
        )
        DATA.write_text(json.dumps(recovered, indent=2), encoding="utf-8")
        return recovered

def main():
    data=load_tracker_data()
    now=datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
    for cinema in data["cinemas"]:
        cid=cinema["id"]
        if cid not in SOURCES:
            continue
        try:
            times=xinemas_tikus_times(fetch(SOURCES[cid]))
            old={s["time"]:s for s in cinema.get("sessions",[])}
            cinema["sessions"]=[]
            for t in times:
                prev=old.get(t,{})
                cinema["sessions"].append({
                    "id":f"{cid}-{t.replace(':','')}",
                    "time":t,
                    "hall":prev.get("hall","—"),
                    "capacity":prev.get("capacity"),
                    "booked":prev.get("booked"),
                    "available":prev.get("available"),
                    "occupancy":prev.get("occupancy"),
                    "sourceStatus":"live-showtime-confirmed",
                    "seatStatus":prev.get("seatStatus","not-yet-observed"),
                    "bookingUrl":prev.get("bookingUrl")
                })
            cinema["sourceStatus"]="live-showtime-confirmed" if times else "no-shows-found"
        except Exception as e:
            cinema["sourceStatus"]=f"refresh-error:{type(e).__name__}"
    data["updatedAt"]=now.isoformat(timespec="seconds")
    data["totalShowsVerified"]=sum(len(c.get("sessions",[])) for c in data["cinemas"])
    DATA.write_text(json.dumps(data,indent=2),encoding="utf-8")
    print("showtime refresh complete",data["updatedAt"],data["totalShowsVerified"])

if __name__=="__main__": main()
