# surfdl1008: does the NBA Live 05 surface-download finding generalise? NBA Live 06/07, Midnight Club 2 (#433, 0.5)

State: ready

Lane: surfdl1008          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 7960e78e20
Files: docs/lanes/surfdl1008/NOTES.md, docs/lanes/surfdl1008/PR.md
Prediction: none: analysis-only, no device request queued, no code touched
Needs device: no (gate blocked both NBA titles; Midnight Club 2 was answered by an existing run, read not queued)    Needs NDK: no

NBA Live 06 and NBA Live 07 are not measured: both are gated off by
`pm/prequeue.py` (REVIEW and BLOCK respectively, both titles below-bar on
10-06 holds), and neither has an existing perflog soak on disk to read
instead. No device time was spent on either.

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

Full numbers, the prequeue gate readout for all three titles, and the
`pm/prequeue.py` gate bug noticed along the way (an exactly-0.0
`fps_ok_share` escapes its BLOCK rule via Python's `0.0 or 1`) are in
NOTES.md.

Release note: none (analysis only, no code or behaviour change).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
