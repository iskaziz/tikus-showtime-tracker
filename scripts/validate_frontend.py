
#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "js/app.js").read_text(encoding="utf-8")

errors = []

# Direct $('#id') references must have a corresponding DOM id.
html_ids = set(re.findall(r'id="([^"]+)"', HTML))
direct_ids = set(re.findall(r"\$\('#([^']+)'\)", JS))
missing = sorted(direct_ids - html_ids)
if missing:
    errors.append("Missing DOM ids referenced by app.js: " + ", ".join(missing))

# Regression guards for the two browser crashes found in v22.x.
if "map-location-count" in JS:
    errors.append("Stale #map-location-count reference reintroduced.")

m = re.search(r"function\s+highlightCinemaCard\s*\([^)]*\)\s*\{(.*?)\n\}", JS, re.S)
if not m:
    errors.append("highlightCinemaCard() not found.")
else:
    body = m.group(1)
    if re.search(r"\bhighlightCinemaCard\s*\(", body):
        errors.append("highlightCinemaCard() recursively calls itself.")

# Basic frontend version/cache-bust guard.
if 'js/app.js?v=22.3' not in HTML:
    errors.append("index.html is not cache-busting app.js as v22.3.")
if 'css/styles.css?v=22.3' not in HTML:
    errors.append("index.html is not cache-busting styles.css as v22.3.")

# Fail if unresolved Git merge markers exist in critical public files.
for rel in ("index.html", "js/app.js", "css/styles.css"):
    text = (ROOT / rel).read_text(encoding="utf-8")
    if any(marker in text for marker in ("<<<<<<<", "=======", ">>>>>>>")):
        errors.append(f"Unresolved Git merge marker in {rel}.")

if errors:
    print("FRONTEND VALIDATION FAILED")
    for error in errors:
        print(" -", error)
    sys.exit(1)

print(f"Frontend validation OK: {len(html_ids)} HTML ids, {len(direct_ids)} direct JS id references.")
