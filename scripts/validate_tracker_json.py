#!/usr/bin/env python3
from pathlib import Path
import json, sys

ROOT = Path(__file__).resolve().parents[1]
for rel in ("data/current.json", "data/seed-current.json"):
    path = ROOT / rel
    try:
        json.loads(path.read_text(encoding="utf-8"))
        print(f"OK: {rel}")
    except Exception as exc:
        print(f"INVALID: {rel}: {exc}")
        if rel.endswith("seed-current.json"):
            sys.exit(1)
