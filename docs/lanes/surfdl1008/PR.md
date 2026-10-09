# surfdl1008: does the NBA Live 05 surface-download finding generalise? NBA Live 06/07, Midnight Club 2 (#433, 0.5)

State: draft

Lane: surfdl1008          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 93fbc525fc (attempt 1's own fold, merged into this branch)
Files: docs/lanes/surfdl1008/NOTES.md, docs/lanes/surfdl1008/PR.md, docs/lanes/surfdl1008/WAITING, docs/lanes/surfdl1008/routes/nbalive06.route, docs/lanes/surfdl1008/routes/nbalive07.route
Prediction: none: telemetry survey, not an A/B arm
Needs device: yes, two Nova requests queued (below)    Needs NDK: no

**Attempt 2** (owner addendum 22:05 PDT, 5 min after attempt 1's own fold):
the addendum clears NBA Live 06/07's below-bar `prequeue.py` BLOCK for this
lane's telemetry requests specifically. Re-checked the gate (both now print
that one BLOCK, no other reason), built a route for each from pathfind's own
10-06 confirmation-hold paths (`steps2route.py`, NBA 2005's own basketball
loop tokens, mark cut at each run's first `gameplay` step), and queued two
Nova soaks: `1-1791525334-surfdl1008-4042714` (NBA Live 06, route
`nbalive06`, 460s) and `1-1791525340-surfdl1008-4043345` (NBA Live 07, route
`nbalive07`, 480s), both `--perflog --env HAKUX_GPUXFR=1 --env
HAKUX_FRAMETRACE=1 --priority study`. At queue time 9 `lane.profileddefault1008`
requests sat ahead of both in `dispatch/queue/`; neither has run yet. See
`docs/lanes/surfdl1008/WAITING` and NOTES.md's "Attempt 2" section for the
full gate re-check, route recipe, and a correction to attempt 1's claimed
`prequeue.py` gate bug (does not reproduce on a careful read of the code).

Midnight Club 2's analysis (below) is unchanged from attempt 1, already
answered from an existing run, no device time spent on it.

Midnight Club 2 cleared the gate (`CLEAR`, ISO confirmed on the Nova), but
rather than queue a new 5-minute request, an existing perflog+`HAKUX_GPUXFR=1`
Nova soak from an unrelated lane (`lane.gpunonrender`'s
`1-1791274137-lane.gpunonrender-2624798`, 2026-10-06, 330 s) already covers
the gameplay window end to end. Reading it with `fps20786`'s `decompose.py`/
`sdsurvey.py`/`extras.py` (mark set at the route's own `mark gameplay`,
03:50:05) and cross-checking against `lane.gpunonrender`'s own `[sdcall]`
caller-attribution lines from the same run:

| metric (post-mark, 97 of 97 rows, no thermal pause) | Midnight Club 2 | NBA Live 2005 (fps20786, for comparison) |
|---|---|---|
| gfps | 24.3 | 24.2 |
| Ri (render thread parked) | 0.00 | 5.7-8.2 |
| ph_GPU | 34.6 (already over the 33.3 ms ceiling) | 18.5 (comfortably under) |
| ph_Fin (all finishes) | 16.45 | 13.8-13.9 |
| surface-download finish only (`[sdcall]`, isolates the flip's own finish out) | 8.0 | ~11.4 (`reuse`) |
| forcing caller | `range`: texture.c:2100, inside `create_texture()` | `reuse`: surface.c, `deferred_downloads_clear_surface` |
| lockw | 0.00 | 2.3 |

**Partial generalisation.** Midnight Club 2 makes the same class of
synchronous `SURFACE_DOWN` finish every frame (~8.0 ms of the 16.45 ms
`ph_Fin`; the rest is the flip's own fence wait, present on every title).
But the caller is `texture.c:2100`'s surface-range scan
(`pgraph_vk_download_surfaces_in_range_if_dirty`, called from
`create_texture()` when a texture bind cannot read a surface's image
directly), not NBA's `surface.c` `reuse` site. `async794`'s own evidence on
the structurally identical texture-bind class (Counter-Strike, Top Spin)
already showed the NBA fix (wait at the guest's next sync point) does not
remove this wait, because the consumer is the emulator's own texture upload,
on the CPU, before any guest sync point. The function that would have to
change is `create_texture()`'s call site at texture.c:2100, replaced with a
GPU-side surface-to-texture conversion -- not the `surface.c` deferral
`async794` built (fix 1, refuted and stripped) or kept (fix 2, lock release,
unrelated: Midnight Club 2 has no lock contention to release). Even that fix
is not shown here to be sufficient alone: Midnight Club 2's GPU cost
(34.6 ms/frame) already exceeds the 33.3 ms two-VBLANK ceiling before the
finish wait is counted, unlike NBA 2005's 18.5 ms. No patch attempted (out
of scope per the brief).

Full numbers and the prequeue gate readout for all three titles are in
NOTES.md. (Attempt 1's claimed `pm/prequeue.py` gate bug -- an exactly-0.0
`fps_ok_share` escaping the BLOCK rule via `0.0 or 1` -- does not reproduce;
see NOTES.md's correction.)

Release note: none (analysis only, no code or behaviour change; two Nova
telemetry soaks queued, results pending).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
