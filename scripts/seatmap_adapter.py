#!/usr/bin/env python3
"""
Seat-map adapter contract.

A production adapter should return ONLY counts directly observed from the
cinema's public booking seat map for a specific session.

Return shape:
{
  "hall": "Hall 3",
  "capacity": 180,
  "booked": 47,
  "available": 133,
  "observedAt": "2026-09-03T10:30:00+08:00"
}

Do not estimate sold seats from ticket availability, pricing, or visual guesses.
GSC, TGV, Paragon and Mega each need their own adapter because their booking
flows differ and may change.
"""
def get_seat_snapshot(chain, session_url):
    raise NotImplementedError("Per-chain browser/seat-map adapter required.")
