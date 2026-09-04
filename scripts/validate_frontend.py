#!/usr/bin/env python3
from pathlib import Path
import re, sys, json

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "index.html").read_text(encoding="utf-8")
js = (ROOT / "js/app.js").read_text(encoding="utf-8")

html_ids = set(re.findall(r'id="([^"]+)"', html))

# Only direct `$('<id>')....` usages are treated as required. References routed
# through setText() are intentionally optional.
direct = set(re.findall(r"\$\('#([^']+)'\)", js))
optional_via_settext = set(re.findall(r"setText\('#([^']+)'", js))
required = direct - optional_via_settext

missing = sorted(required - html_ids)
if missing:
    print("ERROR: JavaScript references missing required DOM ids:")
    for item in missing:
        print(" -", item)
    sys.exit(1)

for path in [
    ROOT / "data/current.json",
    ROOT / "data/history-index.json",
]:
    json.loads(path.read_text(encoding="utf-8"))

print(f"Frontend validation passed. {len(required)} required DOM ids resolved.")
