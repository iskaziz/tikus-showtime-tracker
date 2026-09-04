# TIKUS! Cinema Performance Tracker

Static visual dashboard for the 15 allocated TIKUS! cinema locations.

## What works now
- Responsive national dashboard.
- Filters by chain, state and cinema.
- Show-by-show display.
- Headline stats for show count and reporting locations.
- Data structure ready for hall capacity, booked seats, available seats and occupancy.
- `data/current.json` contains a grounded launch-day snapshot for locations whose TIKUS! showtimes were confirmed during setup.
- GitHub Actions scaffold can refresh `data/current.json` every 15 minutes.

## Important: booked-seat tracking
A true booked-seat count is different from a showtime listing. It requires reading each individual cinema booking seat map. The dashboard intentionally displays `—` until a real seat-map observation exists.

Do **not** populate `booked`, `capacity` or `occupancy` with estimates.

For reliable live seat tracking, implement one adapter each for:
1. GSC
2. TGV
3. Paragon Cinemas
4. Mega Cineplex

The practical method is a scheduled Playwright browser job that opens each public booking session, reaches the seat-selection screen, counts unavailable/available seats, then writes a snapshot into `data/current.json`. The job should run no more frequently than necessary and must comply with the cinema site's access rules.

## Static hosting
The dashboard itself is fully static and can be hosted on GitHub Pages or ordinary hosting. Automated collection runs in GitHub Actions, so no public backend server is required.

Open `index.html` through a local static server for JSON loading:
`python -m http.server 8000`

Then visit `http://localhost:8000`.

## Data fields
Each session supports:
- time
- hall
- capacity
- booked
- available
- occupancy
- sourceStatus
- seatStatus

## Launch-day seed
The initial snapshot is dated 3 September 2026. It includes live-confirmed showtimes gathered during setup for:
- GSC Aman Central
- GSC Dataran Pahlawan
- GSC Kuantan City Mall
- Paragon Cinemas Batu Pahat
- Paragon Cinema KTCC

Other locations remain clearly marked as awaiting refresh rather than being filled with invented showtimes.


## Current verified launch-day coverage (3 Sep 2026)
All 15 allocated locations have now been checked. The dashboard contains 68 verified TIKUS! sessions across 14 cinemas. At the time of the check, Mega Cineplex Riverfront City did not list a TIKUS! session, so it is intentionally shown with zero rather than an invented session.

Paragon's public booking pages also verify that all seven launch-day TIKUS! sessions at KTCC and Batu Pahat are in Hall 3.

## Seat-count status
The included Playwright observer verifies reachable booking pages without completing a purchase. Exact booked/available counts remain blank until the seat-selection DOM can be positively identified for each cinema chain. This protects the tracker from publishing misleading sales numbers.


## v3 — Paragon seat collector + history
This package adds:
- a dedicated Playwright Paragon collector;
- conservative seat-state classification;
- diagnostic output when the live DOM cannot yet be confidently classified;
- 15-minute historical snapshots;
- sales-velocity calculation;
- occupancy ranking in the dashboard.

### First live run
Push the project to GitHub, enable Actions, then manually run **Update TIKUS tracker** once.

After the run, inspect:
`data/paragon-seat-diagnostics.json`

If `status` is `verified`, booked/available/capacity will immediately appear in the dashboard.

If it says `needs-selector-confirmation`, the diagnostic file lists the live page's seat-like DOM elements. That is the point where the exact Paragon selectors can be tightened without guessing.

This collector does not proceed to payment and does not create or confirm a purchase.


## v4 — Result of the first Paragon live run

The diagnostic run checked all seven Paragon TIKUS! sessions at Batu Pahat and
KTCC. Every one returned `needs-selector-confirmation`, with **0 classifiable
seat elements**.

The public Paragon ticket page says seats are allocated on a **best available**
basis. The tracker therefore no longer attempts to manufacture an occupancy
count from this consumer booking page.

It also deliberately avoids repeatedly selecting tickets and advancing the
transaction, as doing so could create temporary seat holds and contaminate the
data being measured.

### Exact Paragon counts

v4 adds `scripts/merge_seat_observations.py`. Exact counts can now be ingested
from an authorised cinema/booking report or a manually verified observation.
See `data/seat-observations.example.json`.

The next automated seat-map target should be GSC or TGV.


## v5 — GSC read-only seat-map discovery

GSC is the next target.

GSC's official FAQ confirms that customers can choose their own seats online,
but it also states that seats selected and then abandoned can remain **locked
for 15 minutes**. Because repeated automated seat selections could distort
inventory, v5 does not click or reserve any seat.

Instead `scripts/gsc_booking_diagnostics.py`:
- resolves the official TIKUS! Buy Tickets route;
- inspects the current GSC showtime application;
- finds the eight allocated GSC cinemas;
- records session/showtime buttons, hrefs, DOM metadata and exposed IDs;
- watches network traffic for read-only session/hall/seat/layout endpoints.

### Next live run

Push v5 and run `Update TIKUS tracker` once. Then upload:

`data/gsc-seat-diagnostics.json`

If GSC exposes a read-only seat-layout/API before seat selection, the next
version can turn that into real capacity / unavailable / available counts
without creating seat holds.

If it does not, the dashboard will keep GSC showtimes live and exact sold-seat
data should come from an authorised cinema/distributor source.


## v6 — GSC result + TGV discovery

### GSC result
The live GSC diagnostic resolved the official TIKUS! booking button to
`https://epaymentwebapp.gsc.com.my/profile`, which then redirected to
`https://epaymentwebapp.gsc.com.my/login`.

No allocated cinema names, showtime/session IDs or seat-layout metadata were
exposed before authentication. The tracker therefore does not attempt to bypass
the login or create a booking session.

### Next target: TGV
v6 adds `scripts/tgv_booking_diagnostics.py`, which performs the same
non-invasive discovery against the public TGV TIKUS! page.

After running the workflow, upload:
`data/tgv-seat-diagnostics.json`


## v7 — TGV API discovery pass 2

The first TGV diagnostic was promising. It exposed the public API host
`api.tgv.com.my` and the TIKUS! movie UUID
`7b2216d1-27d8-479e-b420-8ab157847aa6`.

It also exposed a public box-office endpoint returning business dates from
3–9 September 2026.

v7 now clicks only the public **BUY NOW** control and records the exact API
request methods, POST payloads and JSON responses used for cinema/showtime
discovery. It may click a cinema selector, but it deliberately does not select
a showtime seat, reserve inventory or submit a booking.

After the workflow runs, upload the new:
`data/tgv-seat-diagnostics.json`


## v8 — TGV live seat status works

The latest TGV diagnostic exposed the official public box-office endpoints:

- `moviesession_getmoviecinemas`
- `moviesession_get`
- `moviesession_getseatstatus`

The seat-status response contains `seatstotal`, `seatsused` and
`usedpercentage`, so the tracker can now populate TGV capacity, booked seats,
available seats and occupancy without selecting or reserving a seat.

Tracked TGV cinema IDs:
- TBR — Tebrau City
- WWM — Sunway Wangsa Mall (the current TGV name corresponding to the tracked Wangsa location)
- GUR — Gurney Paragon
- BBT — Bukit Tinggi

The discovery response also showed TIKUS! at BU0 — TGV 1 Utama. v8 records it
as an additional TGV cinema rather than silently adding it to the user's
15-location tracker.

Run the workflow, then inspect:
`data/tgv-live-collector.json`

The dashboard will read the updated `data/current.json` and automatically show
TGV booked seats, remaining seats, occupancy and ranking.


## v9 — confirmed five-location TGV tracker

The TGV tracker now uses the user's confirmed public-facing names:

- TGV Tebrau City (`TBR`)
- TGV Wangsa Walk (`WWM`; TGV API currently labels this `SUNWAY WANGSA MALL`)
- TGV Gurney (`GUR`; TGV API currently labels this `GURNEY PARAGON`)
- TGV Bukit Tinggi (`BBT`)
- TGV 1Utama (`BU0`)

API labels are retained only as technical metadata. The dashboard uses the confirmed names above.

TGV 1Utama is now a first-class tracked cinema rather than an "additional cinema".


## v10 — authenticated GSC diagnostics

GSC's public booking route requires login. v10 supports a normal authenticated
session owned by the account holder without storing the GSC password.

### Local one-time setup

On your own computer:

1. `pip install playwright`
2. `playwright install chromium`
3. `python scripts/gsc_auth_setup.py`
4. Log into GSC manually in the browser window.
5. Return to the terminal and press Enter.

This creates `gsc-auth.json`.

### Put the session into GitHub Actions

Do **not** commit `gsc-auth.json`.

Open it locally, copy the entire JSON, then in GitHub:

`Settings → Secrets and variables → Actions → New repository secret`

Name:
`GSC_AUTH_JSON`

Value:
the full contents of `gsc-auth.json`

### Run

Use the manual workflow:

`Actions → GSC authenticated diagnostics → Run workflow`

Then download or inspect:

`data/gsc-auth-diagnostics.json`

If GSC exposes session/seat-status data after normal authentication, the next
version can turn that into the same live capacity/booked/available/occupancy
pipeline already working for TGV.

If the saved session expires, rerun `scripts/gsc_auth_setup.py` locally and
replace the GitHub secret.


## v11 — official GSC XML API discovery

The authenticated GSC diagnostic revealed two official read-only endpoints used
by the GSC web application:

- `getEpaymentMovie_ParentChild`
- `getShowTimesByMovie_ParentChild_V2`

v11 reads those endpoints directly to find TIKUS! and its official GSC
showtimes. It does not use the user's account, click a showtime, select a seat
or create a reservation.

Run the normal update workflow and upload:

`data/gsc-official-api.json`

If that file exposes GSC's TIKUS! parent movie id and session identifiers, the
next stage can target the official seat-status request without relying on the
incorrect generic booking link discovered in v10.


## v11.1 — GSC empty-result fix

v11 returned no TIKUS! movie records. v11.1 no longer assumes the ASMX
catalogue is ordinary nested XML. It:

- inspects the public GSC TIKUS! page for a numeric booking/movie ID;
- saves the official catalogue response prefix for structural diagnosis;
- unwraps ASMX `<string>` payloads and HTML-escaped XML;
- searches around every `Tikus` occurrence for candidate IDs;
- probes discovered IDs against the official showtime endpoint.

Run the normal workflow and upload the new:
`data/gsc-official-api.json`


## v12 — GSC official live showtimes + seat endpoint discovery

GSC identifiers confirmed by its official XML API:

- TIKUS! parent code: `6363`
- TIKUS! child film code: `1000005309`

The official showtime feed provides:
- GSC location ID
- session/show ID
- hall ID and hall name
- exact session time
- `hallfull` status

`gsc_live_collector.py` now replaces third-party GSC showtime data in
`data/current.json` with this official source on every update.

`gsc_seat_endpoint_discovery.py` performs read-only static inspection of GSC's
public booking-app JavaScript to find the name/signature of the next seat or
seat-map endpoint without selecting a showtime or creating a reservation.

After running the workflow, upload:
- `data/gsc-live-collector.json`
- `data/gsc-seat-endpoint-discovery.json`


## v13 — GSC deep static seat-API extraction

The v12 static scan confirmed that GSC's booking app contains:
- `seat-selection`
- `seatSelectionData`
- `lockSeatBody`
- `initSalesResponse`
- showtime parameters `parentID`, `oprndate`, `locationID`, `childCode`, `showID`, `hallGroup`

v13 performs a deeper static-only inspection of GSC's public JavaScript to
extract exact operation/path strings around sales initialization, seat maps,
seat selection, and seat locking.

It deliberately does not invoke any candidate booking or seat endpoint.

After the workflow finishes, upload:

`data/gsc-seat-api-static-analysis.json`


## v13.1 workflow correction

v13 included `scripts/gsc_seat_api_static_analysis.py`, but the workflow did
not actually execute it. v13.1 fixes that and also corrects GitHub Actions
artifact paths to use YAML multiline lists.

After running the workflow, this file should be created and committed:

`data/gsc-seat-api-static-analysis.json`


## v14 — manual authenticated GSC seat-network capture

The v13 static analysis confirms GSC has a distinct seat-selection workflow,
`seatSelectionData`, `lockSeatBody`, `initSalesResponse`, a production
`apiServer`, an application proxy at `/api`, and Init Sales Transaction version
`4.0.0`. It does not reveal the exact seat-layout operation string by itself.

v14 therefore adds a **local manual capture**:

`python scripts/gsc_manual_seat_network.py`

The script opens GSC using your existing `gsc-auth.json`. You manually navigate
to TIKUS!, open ONE future showtime, and stop when the seat map appears. Do not
click any seat. The script records relevant request/response metadata while
redacting authentication and common personal fields.

Output:

`data/gsc-manual-seat-network.json`

This diagnostic is intentionally local and is not added to the recurring
GitHub Actions workflow.


## v14.1 — broad GSC manual capture

The first v14 capture only recorded the initial page load. Two issues were
identified:

1. the URL filter was too narrow and could miss GSC's generic `/api` requests;
2. Playwright `storage_state` does not preserve ordinary `sessionStorage`,
   while GSC stores important login/booking state there.

Run locally:

`python scripts/gsc_manual_seat_network_v2.py`

If GSC asks you to log in, log in manually inside that opened browser. Then
navigate to TIKUS!, open one future showtime, stop when the seat map appears,
and do not click any seat.

Upload:

`data/gsc-manual-seat-network-v2.json`


## v14.2 — direct TIKUS! + context-wide capture

The v14.1 diagnostic still showed only the initial page request and translation
file. It did not record a TIKUS! showtime or seat-map request.

v14.2:
- opens TIKUS! directly at `/showtime-by-movies/6363/tikus`;
- captures network traffic at BrowserContext level rather than one page;
- therefore also captures redirects, popups and new tabs.

Run locally:

`python scripts/gsc_manual_seat_network_v3.py`

Use only the Chromium window opened by the script. Stop as soon as a seat map
is visible and do not click any seat.

Upload:
`data/gsc-manual-seat-network-v3.json`


## v14.3 — GSC browser bootstrap diagnostic

v14.2 confirmed the network observer is attached correctly, but the GSC app
still made no showtime/API calls after loading the Angular shell. The problem is
therefore now the browser/app bootstrap, not the network filter.

Run locally:

`python scripts/gsc_browser_bootstrap_diagnostic.py`

This version prefers your installed Google Chrome, captures JS/CSS/API traffic,
console errors, page errors and failed requests, and waits eight seconds before
interaction.

If the page is blank or stuck, simply press Enter. If it loads normally, open
one future TIKUS! showtime and stop at the seat map without selecting a seat.

Upload:
`data/gsc-browser-bootstrap-diagnostic.json`


## v15 — official public GSC live seat status

The GSC browser capture identified the read-only endpoint used by GSC's own
seat-selection screen:

`getHallSeatStatus?locationid=<id>&hallid=<id>&showdate=YYYY-MM-DD&showtime=HHMM`

The XML response exposes individual seat nodes and their current status. In the
observed GSC UI traffic, `A` is available and `B` is unavailable/booked.

v15 calls this official endpoint directly for every live GSC TIKUS! session
already discovered by `gsc_live_collector.py`.

### Conservative counting

The tracker reports:

- `capacity`: number of seat nodes returned by GSC
- `available`: seats with status `A`
- `unavailable`: seats with any non-`A` status
- `occupancy`: unavailable / capacity

`unavailable` is deliberately not treated as confirmed paid ticket sales,
because a non-available seat can potentially include booked, held, blocked or
other unavailable inventory.

The XML field `maximumseats` is **not** used as auditorium capacity; observed
responses show it is a per-transaction selection limit.

### Privacy

Manual browser diagnostic files can contain account identifiers even when
password/authentication fields are redacted. Do not commit
`data/gsc-browser-bootstrap-diagnostic.json` or other manual authenticated
captures to a public repository.

Live tracker output is written to:

`data/gsc-live-seats.json`


## v15.1 — GitHub Actions commit fix

v15 successfully generated the GSC live-seat data, but its workflow had a
malformed `git add` command. `data/gsc-live-seats.json` was placed on a new
shell line without a preceding `git add`, so GitHub Actions tried to execute
the JSON file as a program and returned exit code 126 / Permission denied.

v15.1 replaces the fragile multiline command with one explicit `git add`
command per tracker file.


## v16 — GSC seat-status semantics correction

The live GSC seat feed is now split conservatively:

- `A` → `available`
- `B` → `booked`
- any other status (currently including `D`) → `otherUnavailable`

`occupancy` for GSC is now calculated as `booked / capacity`, while
`unavailableRate` separately tracks all non-available inventory.

This prevents `D` seats from being incorrectly counted as paid/booked seats.

The collector also preserves:
- `unavailable = booked + otherUnavailable`
- raw `statusCounts`
- per-session `countSemantics`

For the 2026-09-03 20:02 snapshot supplied during development, this distinction
would produce 4 booked seats and 14 other-unavailable seats across the measured
GSC sessions, rather than treating all 18 non-A positions as bookings.


## v17 — preserve GSC sessions after expiry

GSC removes earlier showtimes from its live movie feed as the day progresses.
v17 no longer replaces the whole cinema session list on every refresh.

It now:

- merges current official GSC sessions into the existing day;
- preserves official session ID, hall ID and hall number after a session expires;
- marks disappeared official sessions `isExpired: true`;
- retains the last measured seat snapshot as `seatStatus: "last-observed"`;
- prevents current official sessions from being duplicated by older seed rows
  with the same showtime;
- retains unavoidable pre-observation seed rows only as `historical-seed`;
- keeps `totalShowsVerified` based on the preserved daily session list.

This means a session that was measured earlier in the day remains part of the
daily performance record even after GSC stops returning it as a current show.


## v17.1 — one-time GSC launch-day historical recovery

Before v17 was deployed, several official GSC session IDs/hall IDs had already
fallen out of `current.json` as sessions expired.

v17.1 restores only identifiers and seat states that had already been observed
earlier on 2026-09-03. It does not invent data and does not call booking APIs.

Recovered launch-day sessions include the previously observed 20:00 official
sessions for Paradigm JB, Midvalley, Aman Central, Dataran Pahlawan, Kuantan
City Mall and IOI City Mall. Their last-known seat snapshots are marked
`isExpired: true` and `seatStatus: "last-observed"`.

Once recovered, the v17 preservation logic keeps them in the daily history on
subsequent refreshes.


## v18 — complete 2026-09-03 launch-day history

v18 restores the confirmed launch-day schedule across the tracked GSC and TGV
cinemas so the dashboard's daily show count no longer shrinks as APIs remove
expired sessions.

The recovery uses only:
- confirmed same-day showtimes already captured for the tracker; and
- official GSC/TGV session IDs and hall IDs that were previously observed.

Where no official identifier was captured, the row is retained as a confirmed
historical showtime with unmeasured seat data rather than inventing IDs.

TGV preservation is also strengthened so expired business-date sessions remain
in the tracker, including the 00:45 Tebrau session as part of the same TGV
business day.

The recovery script runs before and after live collectors to keep the day's
history stable while allowing fresher live rows to win.


## v18.1 — corrupted current.json recovery

The failed GitHub Actions run was caused by malformed JSON in
`data/current.json`, not by the Node.js deprecation warning.

v18.1 adds:
- a guaranteed-valid `data/seed-current.json`;
- defensive loading in `scripts/update_showtimes.py`;
- automatic recovery from the seed if `current.json` cannot be parsed;
- a JSON validation helper.

After recovery, the existing v18 launch-day history and official GSC/TGV
collectors rebuild the known tracker state.


## v18.2 — TGV data-integrity correction

The v18 launch-day recovery had inferred several expired TGV session IDs.
v18.2 replaces them only with official IDs actually captured from TGV.

It also restores the earlier official TGV seat-status snapshots using
`countSemantics: "tgv-seatsused"` and `rawSeatsUsed`.

TGV 1Utama is restored for 2026-09-03 at 15:00, session 324678, with the
observed 117 total seats and 1 seat used.

All eight GSC cinemas now receive their known official location IDs during
history recovery, allowing the read-only seat collector to query recovered
sessions with known hall IDs.


## v19 — date-safe daily rollover

v19 separates each Malaysia calendar day so a post-midnight collector run can
never write 4 September sessions into a 3 September dataset.

Key changes:
- `scripts/rollover_tracker_day.py` runs before collectors.
- Previous days are stored under `data/days/YYYY-MM-DD.json`.
- `data/current.json` is reset to a clean current-day dataset on rollover.
- GSC and TGV official collectors query the date stored in `current.json`.
- Snapshot history is grouped by dataset date.
- The dashboard includes a date selector backed by `data/days/index.json`.
- The last clean 3 September snapshot is archived as `data/days/2026-09-03.json`.
- TGV UI wording reflects `seatsused`; GSC keeps B booked vs other unavailable.
- Location count is corrected to 16.

The launch-day-only recovery scripts now skip automatically when the dataset is
not 2026-09-03.


## v19.1 — GSC official API date-source fix

v19 changed `gsc_official_api.py` to read the tracker date from
`data/current.json`, but the script did not define the `DATA` path constant.
v19.1 adds `DATA = ROOT / "data/current.json"` so the official GSC API step can
run normally.


## v19.2 — GSC seat collector initialization fix

v19 made the GSC seat collector dataset-date aware, but the date was read from
`data` before `data/current.json` had been loaded.

v19.2 loads `current.json` first, then derives the dataset date. The affected
collector scripts were also syntax-checked.


## v19.3 — stable GSC cinema matching

The 4 September rollover is working correctly, but Midvalley was still falling
back to the secondary showtime source because its official GSC display name did
not exactly match the older string in the collector.

v19.3 matches all eight tracked GSC cinemas by their official numeric location
IDs first, with names retained only as fallback. This should restore official
session IDs, hall IDs and live seat measurements for GSC Midvalley while making
the mapping more resilient to future GSC display-name changes.


## v19.4 — robust GSC Midvalley matching

v19.3 confirmed that the 4 September daily rollover is stable, but GSC
Midvalley still did not match the official XML location element.

v19.4 no longer assumes GSC's location identifier is always stored in an
attribute named `id`. It checks common ID attribute variants, normalized names,
and finally a conservative token-name match. This covers naming variants such
as `GSC Mid Valley`, `GSC Mid Valley Megamall`, and location labels containing
extra Kuala Lumpur text.

The GSC collector diagnostic now records `matchMethod` and the matched
location's attributes, making any future mapping issue directly diagnosable.


## v19.5 — Midvalley source-truth handling

The v19.4 diagnostic proves that `gsc-midvalley` is absent from GSC's official
TIKUS! showtime response for business date 2026-09-04. This is not a name or
location-ID matching failure.

v19.5 preserves secondary-source Midvalley showtimes but labels them explicitly
as fallback-only. It does not infer session IDs, hall IDs or seat counts where
GSC's official feed does not provide them.

This keeps the tracker source-safe and prevents a missing official listing from
being mistaken for a collector bug.


## v20 — Malaysia cinema map hero

Adds a cinematic map hero above the dashboard. All 16 tracked TIKUS! locations
are rendered as percentage-positioned interactive markers. Selecting a marker
opens an accessible information card with cinema/state, listed shows, latest
observed used/booked count, observed capacity and the next listed showtime.
The card can jump directly to that cinema's detailed dashboard section.

The map is intentionally labelled `SCHEMATIC MAP · NOT TO SCALE`; marker
positions are visual placement aids, not survey-grade coordinates.


## v20.1 — refined Malaysia map

The map hero now uses a more detailed, state-separated schematic:
- individual simplified state areas in Peninsular Malaysia
- separate Sarawak, Sabah and Labuan shapes
- state and major-city labels
- better marker spacing in Klang Valley and Johor
- chain colour coding retained
- tooltip now shows the source status for each cinema
- dense Klang Valley markers use a slightly smaller treatment

The geometry is still intentionally labelled as simplified/not-to-scale rather
than being presented as authoritative administrative GIS boundaries.


## v20.2 — authoritative Malaysia state geometry

The hero map now renders real Malaysia state geometry from the MIT-licensed
`atifmustaffa/malaysia-geojson` dataset rather than using the hand-drawn state
silhouettes.

Implementation:
- state data: `malaysia.state.min.geojson`
- source: https://github.com/atifmustaffa/malaysia-geojson
- license: MIT
- state paths are projected directly into the existing cinematic SVG
- cinema markers now use latitude/longitude coordinates rather than hand-set
  map percentages
- if the external GeoJSON cannot load, the bundled schematic outline remains
  as a graceful fallback
- attribution is displayed beneath the map and included in
  `assets/data/MALAYSIA-GEOJSON-NOTICE.txt`

No mapping framework or external animation library is introduced.


## v20.3 — locally vendored Malaysia GeoJSON

The deployed website no longer requests Malaysia state geometry from GitHub on
every page load.

Runtime path:
`assets/data/malaysia.state.min.geojson`

The maintenance script:
`python scripts/vendor_malaysia_geojson.py`

downloads and validates the MIT-licensed upstream file only when the local copy
is absent (or when manually run with `--force`). The scheduled GitHub Actions
workflow runs this before the collectors and commits the asset into the repo.

After the first successful workflow run, the map is fully self-contained on
GitHub Pages/static hosting and also works locally when the project is served
from a local static server. The existing schematic SVG remains a graceful
fallback if the GeoJSON asset is missing or invalid.


## v21 — static illustrated map overlay + tighter dashboard

This version replaces the undersized dynamic vector Malaysia map with a static,
detailed illustrated hero map based on the approved poster-style reference and
the generated TIKUS! location artwork.

What changed:
- the hero map is now a bundled static image:
  `assets/images/ui/tikus-cinema-map-hero.png`
- cinema markers are overlaid as dynamic hotspots aligned to the illustrated map
- markers pulse, show live show-count badges, and auto-cycle through locations
- the tooltip updates live and can jump to the matching cinema card
- the lower dashboard is tightened for more information at a glance
- headline metrics are more compact
- filters are condensed into a tighter control bar
- cinema detail is now a dense card grid instead of expand/collapse rows
- each cinema card shows key stats plus compact session chips immediately

The MIT GeoJSON asset is still retained in the repository, but the dashboard
hero now prioritises the illustrated static map for stronger visual control and
better hotspot alignment.


## v21.1
Minor UI patch: highlighted cinema cards now sync immediately with the map spotlight after first render.


## v21.2 — map alignment + dense dashboard polish

- Static poster hero is cropped at 700 px source height so the duplicated bottom
  location-list artwork is no longer part of the visible hero.
- Dynamic markers were re-aligned to the actual numbered poster markers.
- A live exhibitor panel covers the poster's static top-right legend/summary and
  replaces it with current show counts and best observed occupancy.
- Klang Valley uses the poster inset; Bukit Tinggi uses the main-map Klang
  Valley anchor to avoid marker collisions.
- Cinema card sorting is available by occupancy, used/booked seats, velocity,
  show count or cinema name.
- Per-cinema velocity uses the two latest detailed same-day snapshots when
  available.
- National occupancy and ranking panels sit side-by-side on desktop.
- Cinema cards use a 3-column large-desktop grid and tighter session chips.
- On mobile, the detailed hero map becomes a local horizontal scroller instead
  of shrinking until labels and markers are unreadable.
- The unused GeoJSON vendoring workflow was removed because the illustrated
  static poster is now the dashboard's map source.


## v22 — Audience Pulse

Configured trailer:
- https://youtu.be/zP-A0q7aVko
- YouTube video ID: `zP-A0q7aVko`

Tracked social tags:
- `#Tikus`
- `#SiapaBunuhDatinSaliha`
- `#feiskproductions`

The dashboard now contains a compact Audience Pulse panel below the headline
cinema metrics.

### YouTube
`scripts/update_audience.py` calls the official YouTube Data API `videos.list`
endpoint when repository secret `YOUTUBE_API_KEY` is configured. It records
views, likes and comments and calculates `(likes + comments) / views` as a
dashboard engagement rate. The calculation is clearly treated as a tracker
metric rather than an official YouTube metric.

### X hashtag listening
When repository secret `X_BEARER_TOKEN` is configured, the same collector uses
X's official recent-search endpoint. X collection is throttled to once per hour
even though the cinema workflow runs every 15 minutes.

The three exact tags are counted separately. Because `#Tikus` is broad and can
contain unrelated mouse/rat posts, the tracker also stores a stricter
`qualifiedMentions24h` query based on the distinctive campaign tags plus TIKUS!
context.

### Files
- `data/audience-config.json`
- `data/audience-current.json`
- `data/audience-history-index.json`
- `data/audience-history/YYYY-MM-DD/*.json`
- `scripts/update_audience.py`

The collector fails soft: missing API credentials do not break the cinema
tracker. The widget displays `—` and a credential-status message until the
relevant GitHub secret is configured.


## v22.1 — explicit GitHub Pages deployment

The live Pages site can become stale because data commits made from the
scheduled tracker workflow use GitHub's workflow token. Those commits update
`main`, but should not be relied upon to trigger a second workflow implicitly.

`deploy-pages.yml` fixes this by deploying in three cases:
- a normal push to `main`
- a manual Pages deployment
- successful completion of `Update TIKUS tracker`

The deployment stages a safe `_site` artifact containing only frontend assets
and public dashboard JSON. Collector diagnostics are intentionally excluded.

GitHub repository setting required once:
`Settings → Pages → Build and deployment → Source → GitHub Actions`.

Core CSS and JavaScript also use `?v=22.1` cache-busting query strings.


## v22.2 — frontend runtime loading fix

The live page was loading the current HTML and JavaScript, but JavaScript failed
during the first render.

Root cause:
- v21.2 removed `#map-location-count` from `index.html`
- `renderMap()` still executed
  `$('#map-location-count').textContent = ...`
- that null dereference stopped all later dashboard rendering

A second latent issue was fixed at the same time:
`highlightCinemaCard()` contained an accidental recursive self-call.

v22.2 removes both failures, makes nonessential map-summary fields safe, adds
a visible runtime error message, cache-busts the repaired frontend files, and
validates JavaScript/DOM references before every Pages deployment.
