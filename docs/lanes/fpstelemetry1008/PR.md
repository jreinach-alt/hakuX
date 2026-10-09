# fpstelemetry1008: one cause table for the below-bar titles -- perflog + GPU xfr + frame trace on the Nova (#433)

State: ready

Lane: fpstelemetry1008      Issue: #433 (dispatched directly, no tracker issue)
Base: master @ 4ea49d12e7 (attempt 4 merged origin/master, 17 commits, clean — picked up
  lane.profileddefault1008 and lane.surfdl1008's folds, neither touching this territory)
Files: docs/lanes/fpstelemetry1008/NOTES.md, docs/lanes/fpstelemetry1008/PR.md,
  docs/lanes/fpstelemetry1008/WAITING.md (removed — nothing left to wait on)
Prediction: none — telemetry survey, no golden, no A/B arm (every request `--no-expect`d)
Needs device: yes (Nova only, never the Thor). 13 soak requests landed across this lane's
  four attempts, ~95 min of device time this attempt alone; no crash, no hang, no thermal
  pause on any of them. Full id list in NOTES.md §3/§8/§10.
Needs NDK: no
Release note (none): analysis only; no emulator or Android code touched.

**Done.** The brief asked for one cause table covering the below-bar titles, built from
fresh perflog+`HAKUX_GPUXFR=1`+`HAKUX_FRAMETRACE=1` Nova runs taken after 5c35880d0a (the
GPU-stamp double-counting fix), replacing old CPU-only or pre-fix attributions. NOTES.md
§7 has that table, 13 rows, 11 backed by a fresh run this lane commissioned (Pilot Down,
Amped 2, MechAssault 2, Buffy, LOTR ROTK, Hulk UD, NHL 2K3, Spider-Man 2, Ninja Gaiden
Black, Dead or Alive 3, NBA Live 2005), one sharpened by lane.surfdl1008's concurrent work
(Midnight Club II, folded onto master during this attempt's merge), one still CPU-only
because its route can't be generated (NFS Most Wanted — see below). NOTES.md §11 is the
closing summary with the cause-class breakdown.

**Highlights**:
- NBA Live 2005: the per-flip synchronous surface-download finish-wait (13.1 ms) now
  *exceeds* the entire trusted GPU render budget (9.6 ms/frame) — sharper than the old
  pre-fix reading, same cause.
- Ninja Gaiden Black: resolves belowbar1005's open "GPU-fence vs other wait" question —
  `ph_GPU` rises in lockstep with the render thread's blocked time, so it is GPU cost.
- NHL 2K3 and Spider-Man 2 both turn out to be dual-cause (guest/renderer *and* a GPU-
  transfer or multi-download-per-flip component the old CPU-only reads never saw).
- Amped 2 is the cleanest guest-CPU-bound case in the table: guest idle is 0.00 ms in
  every window group, at bar and below.
- MK Shaolin Monks and Arctic Thunder both ran clean (fps_ok_share 1.00, zero below-bar
  windows) — their registry FAIL verdicts come from different routes/sessions this lane
  could not reach; recorded as an instrument-reach gap, not a fix (§10).
- Fantastic 4's generated route reaches gameplay briefly then cuts to cutscene (matching
  the source hold's own low play share) — a confirmed route defect, not forced through to
  a full run (NOTES.md §10).

**Gate-matching trap found and fixed mid-session**: `pm/prequeue.py` queried by loose
title name ("Lord of the Rings") can false-match a *different* title's Playable-ledger row
(Fellowship of the Ring, not Return of the King) and report a genuine-looking `BLOCK:
already in the Playable ledger`. Querying by exact title id instead gave the correct
`REVIEW`. Re-checked every title this attempt touched by id, not name (NOTES.md §10).

**Still open for a future lane** (not this one — out of route/tool fixes it can make):
NFS Most Wanted and Midnight Club II have no route because `steps2route.py` cannot encode
their recorded `RT+left`/`RT+right` combo steering tokens (a tool bug outside this lane's
territory); Fantastic 4 needs a different genre loop or a hand-built path; Dino Crisis 3
stays excluded (route/input defect, unrelated to fps); DOA3's belowbar1005 gold-dojo-stage
sync-download finding was not reproduced by this session's aquarium-stage fight (different
scene); NHL 2K3's generated route never sets period length, so its representativeness is
uncertain.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
