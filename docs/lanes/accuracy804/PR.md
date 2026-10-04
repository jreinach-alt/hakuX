# accuracy804: why RalliSport's rival cars are drawn on alternate frames (#804)

State: ready

Lane: accuracy804          Issue: #804
Base: master @ 10f14d301d
Files: docs/lanes/accuracy804/NOTES.md, docs/lanes/accuracy804/OUTBOX.md, docs/lanes/accuracy804/PR.md, docs/lanes/accuracy804/alt_draws.py, docs/lanes/accuracy804/rallisport-804.route, docs/lanes/accuracy804/rallisport-804b.route, docs/lanes/accuracy804/rallisport-804c.route, docs/lanes/accuracy804/rallisport-804d.route, docs/lanes/accuracy804/reports-804.diff
Prediction: none: attribution captures (frame dumps), not an A/B arm
Needs device: yes (six Nova soaks, all run)    Needs NDK: no
Release note (none): analysis only; no emulator code changes.

**Result: the frame dump cannot identify the cause, because no instrumented run blinked.** The route
(`rallisport-804d.route`: Single Race, Safari SS1, player standing) reproduces the scene flicker801 caught, with
the Nissan passing within a car length of the camera at race clock ~7.3-8.6. In every dump the guest issues
the rival's body draws every frame of the pass. The last capture imaged every frame of the pass (118 frames,
race clock 5.49-9.58), and the body is drawn in all of them.

| capture | ref | what it showed |
|---|---|---|
| 1 `1791136124` | 5e4196fefd | Career route: no rival in view; visibility tests run every race frame (`qry` ~400-1800 per 60 flips) |
| 2 `1791147878` | 5e4196fefd | hat held 0.35 s auto-repeated to OPTIONS; never raced |
| 3 `1791150087` | 5e4196fefd | rival pass in the dump: body draws recorded every frame, no recorded field alternates, no async skip |
| (2 voids) | 5e4196fefd | the libfolders pref migration (`GamesFolders` removes `gamesFolderUri`) makes any pre-`10f14d301d` build fail to launch after a newer one; reported in OUTBOX |
| 4 `1791151872` | 10f14d301d | dump + screencaps: body drawn in the 1-2 shots inside the window (too sparse to rule out a blink) |
| 5 `1791153088` | 10f14d301d | no dump, screencaps: the same, equally inconclusive |
| 6 `1791153455` | 10f14d301d | dump with images, every frame of the close pass: **body drawn in all 118 frames** |

flicker801's three blinking runs used the non-perflog debug app (`4a3308a21e`), no frame dump, and screenrecord.
The nv2a code is identical to master. The next step needs video of a no-dump, non-perflog master run, which a
dispatched route cannot record. It is handed to the PM in OUTBOX, together with the cheaper option of RalliSport's
Playable confirmation run with the owner's flicker check.

The stale occlusion-read defect in `reports-804.diff` (NOTES section 3) is a real read-without-wait in
`vk/reports.c`. It is not shown to be #804's cause, so the patch is left unapplied.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
