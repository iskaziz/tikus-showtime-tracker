# Vendored Malaysia map data

`malaysia.state.min.geojson` is supplied from:

- Source: https://github.com/atifmustaffa/malaysia-geojson
- File: `malaysia.state.min.geojson`
- License: MIT

The tracker loads this file **locally** from `assets/data/` at runtime.

If the GeoJSON file is missing, run:

```bash
python scripts/vendor_malaysia_geojson.py
```

The GitHub Actions update workflow also runs that command automatically and
commits the file when it is first needed. Once present, later runs validate and
reuse the local copy instead of re-downloading it.
