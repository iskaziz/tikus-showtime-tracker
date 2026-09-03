#!/usr/bin/env python3
"""
Vendor the MIT-licensed Malaysia state GeoJSON into the static site.

The website NEVER fetches the upstream GitHub file at runtime. This script is
for repository maintenance / GitHub Actions only. Once the file exists locally,
ordinary page loads use assets/data/malaysia.state.min.geojson.
"""
from pathlib import Path
import json
import urllib.request
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets/data/malaysia.state.min.geojson"
SOURCE = "https://raw.githubusercontent.com/atifmustaffa/malaysia-geojson/refs/heads/master/malaysia.state.min.geojson"

def validate(payload: bytes) -> dict:
    obj = json.loads(payload.decode("utf-8"))
    if obj.get("type") != "FeatureCollection":
        raise ValueError("Expected GeoJSON FeatureCollection")
    features = obj.get("features")
    if not isinstance(features, list) or len(features) < 10:
        raise ValueError("Malaysia state GeoJSON has too few features")
    return obj

def main():
    force = "--force" in sys.argv
    if DEST.exists() and not force:
        payload = DEST.read_bytes()
        validate(payload)
        print(
            "Malaysia GeoJSON already vendored:",
            DEST.relative_to(ROOT),
            f"{len(payload):,} bytes",
            hashlib.sha256(payload).hexdigest()[:16],
        )
        return

    request = urllib.request.Request(
        SOURCE,
        headers={"User-Agent": "TIKUS-Cinema-Tracker/20.3"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()

    validate(payload)
    DEST.parent.mkdir(parents=True, exist_ok=True)

    temp = DEST.with_suffix(".geojson.tmp")
    temp.write_bytes(payload)
    temp.replace(DEST)

    print(
        "Vendored Malaysia GeoJSON:",
        DEST.relative_to(ROOT),
        f"{len(payload):,} bytes",
        hashlib.sha256(payload).hexdigest()[:16],
    )

if __name__ == "__main__":
    main()
