Lane: perdrawon1010       Issue: #433 (umbrella), none filed
Base: master @ 07937793af
Files: docs/lanes/perdrawon1010/**, docs/testing/predictions/perdrawon1010-*.json, docs/testing/titles/routes/nfs-mw-quickrace.route
Prediction: docs/testing/predictions/perdrawon1010-racestart.json @ 37a2eb0a8ac2aca2d9489e14bcc3a0cc9b1771c048a5a041a3f2629e6f9fb190 (race start, judged: V/S1/S2/S3/S4 all PASS)
Prediction: docs/testing/predictions/perdrawon1010-pgraph-inert.json @ 77f0c70db512b1cc02f4b8d88ecf6781070fa40261c620f7238b54e52476a508 (27-suite disc, must_not_move: no capture moves with the switches, after a runs=3 determinism check)
Prediction: docs/testing/predictions/perdrawon1010-nfs-motion.json @ 790dbf5366edc591b424c2a89dd1a208b2d9a87286cddcd37fa8130dd4606940 (prologue scene, superseded by the race start; M1/M2/M4 PASS, M3 and V FAIL)
Needs device: yes (Nova only, used)
Needs NDK: no
Release note (none): measurement only

Should perdraw1009's three default-off switches (`HAKUX_UNI_BULK`,
`HAKUX_UNI_UBERCACHE`, `HAKUX_UNI_FOGCACHE`) be on by default? This lane
measures them where the renderer limits NFS Most Wanted's frame rate: the race
start, by owner order on 10-10. All runs were on the Nova at `4ad1154e55`.
perdraw1009 is still not on master; `git diff 4ad1154e55 origin/master -- hw/`
is exactly its two files. No emulator code was changed and no default was
flipped.

**Route.** `nfs-mw-quickrace.route`: Quick Race, Custom Race, Sprint, Diamond &
Union (the default track), 2 opponents (3 racers), Fiat Grande Punto, Auto.
Every menu step was read from a frame. RT is held through each GO. One boot
gives twelve starts: the first, then eleven restarts through STANDINGS, Y
Restart, OK. All 84 starts in the seven 500-s runs are valid on frames.

**Race start, the first seconds after GO** (fixed-state arms: two off, two
on, bracketed off-on-on-off):

| window | switches off | switches on | on-off (raw; matched by draws/frame bin) |
|---|---|---|---|
| GO-1.5 .. GO+4.5, ~1,450 draws/frame | 19.1 fps, 52.5 ms (runs 19.0, 19.1) | **20.7 fps, 48.4 ms** (runs 20.5, 20.8) | +1.6 fps, -4.1 ms; +1.1 fps, -2.8 ms |
| countdown, ~1,580 draws/frame | 18.0 fps, 55.4 ms | 19.5 fps, 51.3 ms | +1.5 fps, -4.1 ms; +1.4 fps, -3.8 ms |
| fit at 1,374-1,658 draws/frame (the owner's 3-racer start) | 20.0-17.9 fps | **20.9-18.9 fps** | +0.9-1.0 fps, -2.1 to -2.8 ms |
| fit at 1,133-1,259 draws/frame (the owner's 1v1 start) | 22.2-21.0 fps | 22.9-21.8 fps | +0.8 fps |
| per-draw renderer cost, GO .. GO+10.5 | 10.65 us/draw | 8.87 us/draw | -1.76 us/draw (-17%) |

The registered judge, three `HAKUX_UNI_TOGGLE=4` runs, passes every leg:
matched-work +1.41 fps and -1.59 us/draw; each run on its own gives +1.79,
+1.09 and +2.11 fps. The toggled runs cannot see the heaviest start frames: a
perflog row is ~3.5 s there, longer than a 4-s toggle half-period allows.
That is why the fixed-state arms carry the table. In both fits, both on runs
are faster than both off runs at every load from 1,133 to 1,658 draws/frame.

**Pixels.** On the 27-suite pgraph disc, 5 of 1,060 captures moved, all in
Stencil REPLACE and GeometrySuperscreen. In a runs=3 determinism check, every
one of them takes both values within the off state alone. No capture moves
with the switches.

**Energy** (race-start arms, ~300 s scored window, the same in both states).
Off: 0.313 and 0.304 J/frame. On: 0.291 and 0.293 J/frame. That is -5% on two
runs per state, so a small saving with the same sign as the per-draw cut, not
a measured size.

**Recommendation: on by default.** The switches change no pixel and cut
renderer per-draw cost by 1.6-2.0 us (-15 to -18%) in every scene measured.
At the race start, they take 2-4 ms off each frame:
- the first seconds after GO go from 19.1 to 20.7 fps;
- at the owner's 1,374-1,658 draws/frame the start runs **18.9-20.9 fps with
  the switches on**, against 17.9-20.0 off.

They also save ~5% energy per frame. **The race start does not hold 28-30 fps
with the switches on.** It runs ~19-21 fps there, 48-53 ms per frame against
the 33.3 ms that 30 fps needs. A start frame would need to lose another
15-20 ms. These three switches are worth having, but they are not the fix
that gets the start to 30. A full playthrough would not show 28-30 at the
start on this evidence.

Tables, the run ids, the pass-by-pass route work, and what the next lane
should not repeat are in `docs/lanes/perdrawon1010/NOTES.md`, sections 3, 4,
7 and 8. Device time: ~2 h 35 min of 6 h, Nova only.

State: ready

🤖 Generated with [Claude Code](https://claude.com/claude-code)
