# gtaroutes1011: routes into play for GTA III, Vice City, and a San Andreas driving route (#433, 0.5)

State: draft

Lane: gtaroutes1011        Issue: none (#433 umbrella)
Base: master @ 6d8947bb47
Files: docs/lanes/gtaroutes1011/NOTES.md, docs/lanes/gtaroutes1011/PR.md
Prediction: none: route data (inputs) and notes, no emulator code; route checks are --no-expect dispatch runs
Needs device: yes (Nova only, via request.sh/pathfind.py; no direct hold held across more than one title)

**Waiting on Nova device time.** Checked `$DISPATCH_DIR/{queue,running}` before taking any hold, per the brief's
rule not to hold the Nova while a lane.local `gtasa1011`/`gtasagpu1011`/`nfsdefault1011` request is queued or
running. Polled 09:53-11:07 PDT (about 74 minutes): the Nova was never once idle, and `queue` only touched 0 twice,
each for under a minute, too briefly to grab the hold. Both siblings' briefs show why: `gtasagpu1011` is an
open-ended GPU-defect hunt that re-queues after every run, and `nfsdefault1011` step 4 alone is "~74 runs ...
about 4.5 h" by its own brief. The brief's "they end about 10:15 PDT" was stale before this session started. Full
timeline in NOTES.md section 2.

No route, targets.toml row, or drive route has been produced yet -- steps 1-4 are untouched. Nothing else in this
lane's territory has been touched.

**What unblocks this:** `queue`/`running` clear of nova work from those three requesters for long enough to take
the pathfind hold, or lane.local/the PM scheduling an explicit gap (both sibling briefs already expect one).
