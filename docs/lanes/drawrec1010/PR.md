drawrec1010: HAKUX_DRAWREC=1 (default off) cuts NFS race-start recording 21%/draw; recorder-thread probes say do not build (#433, 0.5)
State: ready

Lane: drawrec1010       Issue: #433 (umbrella), none filed
Base: master @ c271f515b4, merged to b74cff74ed
Files: hw/xbox/nv2a/pgraph/vk/draw.c, docs/lanes/drawrec1010/**, docs/testing/predictions/drawrec1010-*.json, docs/testing/nv2a_index.json (regenerated)
Prediction: docs/testing/predictions/drawrec1010-pixels.json @ 958f10d9dd48e384c5e9b16eebffbaede5b2e8253fee21bf5b80c4b984cbd681, docs/testing/predictions/drawrec1010-nfs.json @ 7f465817484721653e51b27e84ae8ac4e77744b7a2d358265193b30cdb649d82, docs/testing/predictions/drawrec1010-probe.json @ 4bd24c464b34e68005c1fac14745f9d1048fb935b4fd5d7a3a9b368ab81e27a9
Needs device: yes (Nova, used)
Needs NDK: no
Release note (none): opt-in switch HAKUX_DRAWREC=1 and measurement-only probes HAKUX_PROBE_*, all default off

Step 3 of `docs/lanes/nfs30plan1010/PLAN.md`: cut the PFIFO thread's per-draw
recording cost at the NFS Most Wanted race start. Addendum 1 adds probes that
test whether a recorder thread is worth building.

## Results

**Recorder thread (Addendum 1): DO NOT BUILD.**
- **Floor:** NULLREC 33.5 ms/frame warm is the title's vblank, not the vCPU or the
  GPU waits: 96% of frames at v2, vCPU busy 19.1 ms/frame, waits 0.06 ms/frame.
- **Warm:** the base arm (every switch on) already runs 34.2 ms/frame, p50 33.3. A
  recorder could win 0.7 ms/frame and the handoff costs 3.4-4.3 (SNAPQ=2 / SNAPQ=1).
- **Cold:** base - floor is 4.7-7.2 ms/frame, of which 3.56 is GPU ring fence waits a
  recorder still pays. That leaves ~0.5-3 ms/frame for a 15-25 lane-day design.

The probe runs, two per arm on `bf43e8c4ef`:
- base: `1-1791672296-drawrec1010-4030728`, `1-1791672308-drawrec1010-4034875`;
- NULLREC: `1-1791672299-drawrec1010-4031484`, `1-1791672305-drawrec1010-4033552`;
- SNAPQ=1: `1-1791672298-drawrec1010-4031146`, `1-1791672307-drawrec1010-4034091`;
- SNAPQ=2: `1-1791672301-drawrec1010-4032023`, `1-1791672303-drawrec1010-4032671`.

Judged by `proberead.py`; tables in NOTES section 16.

| warm countdown | pace ms/frame (per run) | v2 | vCPU busy / idle | mid-frame GPU waits |
|---|---|---|---|---|
| base | 34.2 (34.3, 34.1) | 63.5% | 24.6 / 9.6 | 0.49/frame, 3.68 ms each |
| NULLREC (floor) | 33.5 (33.6, 33.5) | 96.0% | 19.1 / 14.4 | 0.23/frame, 0.25 ms each |
| SNAPQ=1 (41 KB record) | 38.5 (39.4, 37.8) | 61.7% | 28.4 / 10.4 | |
| SNAPQ=2 (1.2 KB record) | 37.6 (36.7, 38.6) | 66.3% | 27.8 / 9.7 | |

The handoff's cost is the enqueue into the existing render-thread queue (3.5-3.9
us/draw), not the copy (0.4-2.0 us/draw). Point ranges: `P_floor` was out, because a
pace floor cannot go under the v2 period. `P_snapq2_d` was out (3.38 against
[0.2, 3.0]). The other three were in.

### HAKUX_DRAWREC=1 at the race start (`drawrec1010-nfs.json`: REFUTED on R)

Plain build b10dcdb737, F1-F3 in both states, two runs each:
- off `1-1791670433-drawrec1010-3707918` and `1-1791670442-drawrec1010-3709079`;
- ON `1-1791670434-drawrec1010-3708043` and `1-1791670441-drawrec1010-3708870`.

us/draw is from the perflog pilot pair (off `...-952014`, ON `...-951926`). Every
run has a moving car in all 12 g11 frames.

| | off | ON | ON - off |
|---|---|---|---|
| warm countdown pace, ms/frame (per run) | 38.8 (39.2, 38.5) | 37.3 (37.4, 37.2) | **-1.5** |
| warm v2 share | 66.1% | 75.3% | +9.2 points |
| vertex-sync TLB walks/flip, warm | 165.8 (2.62 ms) | 66.5 (0.99 ms) | -60% |
| us/draw (perflog) | 7.77 | 6.16 | **-20.8%** |

| leg | verdict |
|---|---|
| V | PASS |
| R | **FAIL**: 68 walks/flip, <= 20 predicted. Each budget batch pays one full-TLB scan per merged run. |
| U | PASS: -20.8%, Syn 1.91 ms |
| P | PASS: -1.5 ms/frame |
| H | PASS: +9.2 points |

Every speed leg passed, but the mechanism's size was wrong, so the verdict is
REFUTED. The fix for R is `docs/lanes/drawrec1010/tlbmap.mbox`, one
bitmap-filtered TLB scan per batch. It is parked: it edits `accel/tcg/cputlb.c`,
`system/physmem.c` and two headers, and the board request for them has no answer.
Brief's targets:
- warm ON <= 38: met;
- cold ON <= 52: met, n=2;
- v2 +10: not met, +9.2.

### Pixels (`drawrec1010-pixels.json`): no capture moves with the switch

27-suite disc, 3 runs per arm:
- A off: `1-1791661643-drawrec1010-951834` and `1-1791670443-drawrec1010-3709316` (x2);
- B ON: `1-1791661636-drawrec1010-950252` and `1-1791670444-drawrec1010-3709731` (x2).

`ab_compare.py` on the recheck pair: 1,059 of 1,060 byte-identical. It calls
GeometrySuperscreen_0.5626 "attributable" and gives FAIL. That capture is the
prediction's named noise:
- across the three runs each arm produced two different images;
- one image, sha 0cf84e6c (570 px), appears in both arms (A's pilot, both B
  rechecks).

Stencil_ZERO_ST, the pilot's one unnamed move, is byte-identical in five of six runs
across both arms. By the registered runs=3 rule, the leg passes. The tool's one-pair
FAIL is recorded, not overridden (NOTES section 15).

## Census and decision

`HAKUX_DRAWCENSUS=1` (default off, no behaviour change), run
`1-1791656193-drawrec1010-4097387` (perflog, F1-F3 on, 12 starts, 68 windows,
4,749,007 draws):

| class of a draw against the one before | % of draws | cum % |
|---|---|---|
| same (nothing changed) | 24.4 | 24.4 |
| dyn (dynamic state only) | 0.0 | 24.4 |
| uni (uniforms only) | 38.6 | 63.0 |
| reg (a key-feeding register) | 9.5 | 72.6 |
| tex | 15.6 | 88.2 |
| pipe / shader / surf | 0.2 / 9.9 / 1.7 | 100.0 |

**Decision: same + dyn + uni = 63.0% >= 50%, so step 2 (reuse).** Two causes
came out of the census:
- 31% of draws take the full path and write a fresh UBO set only because
  `shader_bindings_changed` stays set after the change it reports.
- After F1-F3 the largest phase is `Syn`, the vertex sync. Each dirty range pays a
  TLB walk over ~8,300 entries (~16 us) to re-arm about one entry: 205-242 walks per
  flip, 3.4-3.9 ms of the 4.0 ms at the cold start.

Tables: NOTES sections 5.1-5.3. The `simpleperf` record of the PFIFO thread was not
taken. No lane-reachable path runs simpleperf, and the board request has no answer
(NOTES section 3). The decision did not need it.

## Change

`HAKUX_DRAWREC=1` (draw.c only, NOTES section 8):
- **VTX.** Test-and-clear and copy as before, but owe the TLB re-arm to a bitmap walked
  once per flip, or early after a re-copy budget. Owed pages are re-copied on every
  touch until then.
- **SHC.** Clear `shader_bindings_changed` after a full-path draw that has used it.

`HAKUX_DRAWREC_VTX=0` / `HAKUX_DRAWREC_SHC=0` turn one part off.

Addendum 1 probes (draw.c, default off, measurement only, never for default; NOTES
section 13):
- `HAKUX_PROBE_NULLREC=1` keeps PFIFO's part of a recorder design and skips the
  pipeline, uniform, descriptor and recording work: the floor.
- `HAKUX_PROBE_SNAPQ=1` adds a ~40 KB input snapshot plus the payload per draw to the
  unchanged path, enqueued to the render thread: the handoff's upper bound.
- `HAKUX_PROBE_SNAPQ=2` does the same with a ~1 KB record: the lower bound.
- `HAKUX_PROBE_WAITS=1` counts and times every GPU wait on the PFIFO thread, mid-frame
  vs at the flip.

## Recommendations

- **`HAKUX_DRAWREC=1`: default-on after one Nova title screen, not now.** The speed
  legs and the pixels pass. But VTX changes when vertex pages are re-armed, on a
  correctness argument read from the code. Only NFS and the 27-suite disc have
  exercised it. Before flipping, screen the Playable titles with the switch on against
  off: frames region-compared, no new fatal signal.
- **perdrawon1010's three (`HAKUX_UNI_BULK/UBERCACHE/FOGCACHE`): default-on,** as
  perdrawon1010 recommends. This lane ran them in all 15 NFS runs (no fatal signal)
  and all 6 pixel-disc runs. That is stability evidence, not a new measurement.
- **Recorder thread: do not build** (Results above). Warm, the race start is at vblank.
  The cold start's remaining gap is mostly GPU ring fence waits and PFIFO lock waits
  (NOTES sections 16-17).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
