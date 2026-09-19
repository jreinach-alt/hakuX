# lane.remotechannel — the delivery channel is a file the recipient cannot read

Status: in progress. This file is written before the long steps, so a
successor resumes from disk and not from a transcript.

## The three breaks, confirmed on this host

1. **The writer no longer exists.** `docs/ORCHESTRATION-DESIGN.md` §4 deleted
   the orchestrator role; nothing writes `deliveries/<lane>.md` now.
2. **The reader cannot reach the file.** §5: "the cloud sessions cannot see the
   dispatch directory". `deliveries/` is on this host's disk only.
3. **The wake-up has no destination.** `watch_remote_lane.sh` polls every 60s
   and prints to a session that was deleted.

Measured 2026-09-19 in `$DISPATCH_DIR`:

| path | mtime | size |
|---|---|---|
| `deliveries/remote.md` | 2026-09-18T20:48:08Z | 8779 |
| `deliveries/toolsmith.md` | 2026-09-14T11:53:57Z | 12441 |
| `lanes/remote.lastbrief` | 2026-09-14T10:35:15Z | 21 |
| `lanes/toolsmith.lastbrief` | 2026-09-14T08:28:48Z | 21 |

(Both `.lastbrief` stamps are four days older than the delivery files they are
a fallback for, which is the "second thing to remember" `check_coverage.py`'s
own comment predicted would be forgotten.)

## Plan

- `docs/testing/jobs/deliver.sh` — routing becomes a tagged GitHub comment.
- `check_coverage.py` — last-brief time derived from the newest delivery
  comment, via a cache the channel itself writes.
- `comment_sweep.sh` — absorbs `watch_remote_lane.sh`'s polling, gains a
  destination, refreshes the delivery cache.
- `watch_remote_lane.sh` — retired in place.

Detail lands here as it is built.
