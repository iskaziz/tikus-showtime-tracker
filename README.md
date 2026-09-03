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
