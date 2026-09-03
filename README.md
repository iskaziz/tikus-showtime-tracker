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
