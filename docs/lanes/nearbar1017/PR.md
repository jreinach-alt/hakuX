# nearbar1017: three near-bar titles on the 0.5.2 build -- do they clear Playable now

State: draft

Lane: nearbar1017            Issue: #433
Base: master @ 07b7b6d9960ba029076b675faa7ce6b5cd7f26c5
Files: docs/lanes/nearbar1017/NOTES.md, docs/lanes/nearbar1017/PR.md
Prediction: none: analysis-only (held device runs, judged by hand against the existing ledger bar; no code change to predict against)
Needs device: yes    Needs NDK: no

Re-running Panzer Elite Action, Aeon Flux, and Medal of Honor: Frontline on
the current (0.5.2) build: each scored below the 90%-at->=30fps Playable bar
on a pre-0.5.2 build, and 0.5.2 turned on `HAKUX_S2T_CVT` (16-bit render
target texture path) by default, so the build under test has changed.

Step 0 (committed): `docs/lanes/nearbar1017/NOTES.md` has the already-tried
table -- no open `nv2a_issues.toml` defect names any of the three, and each
has a prior held run and recorded path/route. In progress: the three 600 s
held runs on the Nova, one at a time (none of the three was staged on the
Nova's own storage; staging from the D: cache first, one title at a time,
removed after its run to stay clear of lane.local's 25 GB shuffle floor).

Will update with the per-title table (play seconds, share at bar, median
fps, clear/miss, telemetry bound for any miss) before marking ready.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
