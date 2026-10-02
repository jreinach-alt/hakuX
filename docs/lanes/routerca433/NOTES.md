# routerca433 NOTES (#433): root cause of the missing path builder

Analysis lane, no device.  Working state; CAPA.md is the deliverable.

## Tools in this directory

- `ledger.py` -> `ledger.tsv`: one row per route-related dispatch request since 09-24
  (requesters titleroutes, titleroutes2, titleplay, titlebench, host-titlebench,
  lane.verdict433, autoverdict, routedriver, lane.local/lanelocal #433 confirmations,
  titlestate, hostops #433).  Deduplicated by request id (a request can have a
  queue-prefixed result dir and a bare-id alias).  Automatic class from run.log /
  verdict.json / WITHDRAWN / VOID, overridden by `review.tsv` (frame-reviewed).
- `review.tsv`: the runs whose frames I opened, with what each showed.
- `devtime.py`: device-minutes by state from `~/hakux-work/logs/devwatch/*.tsv`
  (per-minute samples, 09-26 00:00 to 10-02 ~07:00 PDT).

## Session 1 (2026-10-02)

In progress; see CAPA.md when complete.
