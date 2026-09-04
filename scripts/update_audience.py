#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json, os, urllib.parse, urllib.request, urllib.error, time

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data/audience-config.json"
CURRENT = ROOT / "data/audience-current.json"
INDEX = ROOT / "data/audience-history-index.json"
HISTORY = ROOT / "data/audience-history"
MY = ZoneInfo("Asia/Kuala_Lumpur")

def read_json(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def write_json_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

def fetch_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def as_int(value):
    try:
        return int(value)
    except Exception:
        return None

def youtube_collect(cfg, previous, now):
    result = dict(previous or {})
    result.update({
        "videoId": cfg["videoId"],
        "url": cfg["url"],
        "label": cfg.get("label", "Official Trailer"),
    })

    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        result["sourceStatus"] = "youtube-api-key-not-configured"
        return result

    params = urllib.parse.urlencode({
        "part": "snippet,statistics",
        "id": cfg["videoId"],
        "key": key,
    })
    url = "https://www.googleapis.com/youtube/v3/videos?" + params

    try:
        payload = fetch_json(url, headers={"User-Agent": "TIKUS-Audience-Tracker/22"})
        items = payload.get("items") or []
        if not items:
            result["sourceStatus"] = "youtube-video-not-found"
            return result

        item = items[0]
        stats = item.get("statistics") or {}
        snippet = item.get("snippet") or {}
        views = as_int(stats.get("viewCount"))
        likes = as_int(stats.get("likeCount"))
        comments = as_int(stats.get("commentCount"))
        interactions = None if likes is None and comments is None else (likes or 0) + (comments or 0)
        engagement_rate = (interactions / views) if interactions is not None and views else None

        result.update({
            "title": snippet.get("title"),
            "channelTitle": snippet.get("channelTitle"),
            "views": views,
            "likes": likes,
            "comments": comments,
            "engagementCount": interactions,
            "engagementRate": engagement_rate,
            "sourceStatus": "youtube-official-data-api",
            "observedAt": now.isoformat(timespec="seconds"),
        })
        return result
    except Exception as exc:
        result["sourceStatus"] = "youtube-api-error"
        result["lastError"] = str(exc)[:300]
        return result

def x_last_observed(previous):
    try:
        raw = (((previous or {}).get("platforms") or {}).get("x") or {}).get("observedAt")
        return datetime.fromisoformat(raw) if raw else None
    except Exception:
        return None

def x_search(query, token, start_time, max_pages):
    url = "https://api.x.com/2/tweets/search/recent"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "TIKUS-Audience-Tracker/22",
    }
    next_token = None
    total = 0
    engagement = 0
    pages = 0

    while pages < max_pages:
        params = {
            "query": query,
            "start_time": start_time,
            "max_results": "100",
            "tweet.fields": "created_at,public_metrics",
            "sort_order": "recency",
        }
        if next_token:
            params["next_token"] = next_token
        payload = fetch_json(url + "?" + urllib.parse.urlencode(params), headers=headers)
        posts = payload.get("data") or []
        total += len(posts)
        for post in posts:
            metrics = post.get("public_metrics") or {}
            engagement += sum(as_int(metrics.get(k)) or 0 for k in (
                "like_count", "reply_count", "retweet_count", "quote_count", "bookmark_count"
            ))
        pages += 1
        next_token = (payload.get("meta") or {}).get("next_token")
        if not next_token:
            break

    return {"mentions": total, "engagement": engagement, "pages": pages}

def x_collect(cfg, previous_social, now):
    social = dict(previous_social or {})
    platform = dict((social.get("platforms") or {}).get("x") or {})
    token = os.environ.get("X_BEARER_TOKEN", "").strip()

    if not token:
        platform["status"] = "x-bearer-token-not-configured"
        social.setdefault("platforms", {})["x"] = platform
        return social

    refresh_minutes = int(cfg.get("refreshMinutes", 60))
    last = x_last_observed(social)
    if last and (now - last).total_seconds() < refresh_minutes * 60:
        platform["status"] = "x-official-api-throttled-reuse"
        social.setdefault("platforms", {})["x"] = platform
        return social

    lookback_hours = int(cfg.get("lookbackHours", 24))
    max_pages = int(cfg.get("maxPages", 5))
    start = (now.astimezone(timezone.utc) - timedelta(hours=lookback_hours)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    exclude = " -is:retweet" if cfg.get("excludeRetweets", True) else ""

    tags_out = []
    try:
        for tag in cfg.get("hashtags", []):
            metrics = x_search(f"{tag}{exclude}", token, start, max_pages)
            tags_out.append({
                "tag": tag,
                "mentions24h": metrics["mentions"],
                "engagement24h": metrics["engagement"],
            })

        precise_query = cfg.get("qualifiedQuery")
        qualified = x_search(precise_query, token, start, max_pages) if precise_query else None

        public_engagement = qualified["engagement"] if qualified else sum(x["engagement24h"] for x in tags_out)
        qualified_mentions = qualified["mentions"] if qualified else None
        top_tag = None
        if tags_out:
            top_tag = max(tags_out, key=lambda x: (x["mentions24h"] or 0, x["engagement24h"] or 0))["tag"]

        social["hashtags"] = tags_out
        social["qualifiedMentions24h"] = qualified_mentions
        social["publicEngagement24h"] = public_engagement
        social["topTag"] = top_tag
        social.setdefault("platforms", {})["x"] = {
            "status": "x-official-recent-search",
            "observedAt": now.isoformat(timespec="seconds"),
            "lookbackHours": lookback_hours,
        }
        return social
    except urllib.error.HTTPError as exc:
        social.setdefault("platforms", {})["x"] = {
            "status": f"x-api-http-{exc.code}",
            "observedAt": platform.get("observedAt"),
        }
        return social
    except Exception as exc:
        social.setdefault("platforms", {})["x"] = {
            "status": "x-api-error",
            "lastError": str(exc)[:300],
            "observedAt": platform.get("observedAt"),
        }
        return social

def nearest_24h_trailer(history_index, now):
    target = now - timedelta(hours=24)
    candidates = []
    for row in history_index.get("snapshots", []):
        raw = row.get("observedAt")
        if not raw or row.get("views") is None:
            continue
        try:
            dt = datetime.fromisoformat(raw)
        except Exception:
            continue
        if dt <= target:
            candidates.append((dt, row))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[-1][1]

def main():
    now = datetime.now(MY)
    cfg = read_json(CONFIG, {})
    previous = read_json(CURRENT, {}) or {}
    history_index = read_json(INDEX, {"snapshots": []}) or {"snapshots": []}

    trailer = youtube_collect(cfg.get("youtube") or {}, previous.get("trailer") or {}, now)
    social_cfg = dict((cfg.get("social") or {}).get("x") or {})
    social_cfg["hashtags"] = (cfg.get("social") or {}).get("hashtags") or []
    social = x_collect(social_cfg, previous.get("social") or {}, now)

    baseline = nearest_24h_trailer(history_index, now)
    if baseline and trailer.get("views") is not None:
        trailer["delta24hViews"] = trailer["views"] - baseline.get("views", trailer["views"])
    else:
        trailer["delta24hViews"] = None

    current = {
        "updatedAt": now.isoformat(timespec="seconds"),
        "trailer": trailer,
        "social": social,
    }
    write_json_atomic(CURRENT, current)

    day_dir = HISTORY / now.date().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%S%z")
    rel = f"audience-history/{now.date().isoformat()}/{stamp}.json"
    snapshot_path = day_dir / f"{stamp}.json"
    write_json_atomic(snapshot_path, current)

    history_index.setdefault("snapshots", []).append({
        "observedAt": current["updatedAt"],
        "views": trailer.get("views"),
        "likes": trailer.get("likes"),
        "comments": trailer.get("comments"),
        "qualifiedMentions24h": social.get("qualifiedMentions24h"),
        "publicEngagement24h": social.get("publicEngagement24h"),
        "file": rel,
    })
    history_index["snapshots"] = history_index["snapshots"][-1500:]
    write_json_atomic(INDEX, history_index)

    print(
        "Audience snapshot:",
        "YouTube", trailer.get("sourceStatus"),
        "| X", ((social.get("platforms") or {}).get("x") or {}).get("status"),
    )

if __name__ == "__main__":
    main()
