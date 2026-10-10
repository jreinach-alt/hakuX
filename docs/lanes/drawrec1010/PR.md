drawrec1010: HAKUX_DRAWREC=1 (default off): owe the vertex sync's TLB walk, and consume a stale shader_bindings_changed (#433, 0.5)
State: draft

Lane: drawrec1010       Issue: #433 (umbrella), none filed
Base: master @ c271f515b4
Files: hw/xbox/nv2a/pgraph/vk/draw.c, docs/lanes/drawrec1010/**, docs/testing/predictions/drawrec1010-*.json
Prediction: docs/testing/predictions/drawrec1010-pixels.json @ 958f10d9dd48e384c5e9b16eebffbaede5b2e8253fee21bf5b80c4b984cbd681, docs/testing/predictions/drawrec1010-nfs.json @ 7f465817484721653e51b27e84ae8ac4e77744b7a2d358265193b30cdb649d82
Needs device: yes (Nova, used)
Needs NDK: no
Release note (none): opt-in switch HAKUX_DRAWREC=1, default off

Step 3 of `docs/lanes/nfs30plan1010/PLAN.md`: cut the PFIFO thread's per-draw
recording cost at the NFS Most Wanted race start.

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
- After F1-F3 the largest phase is `Syn`, the vertex sync. Each dirty range
  pays a TLB walk over ~8,300 entries (~16 us) to re-arm about one entry:
  205-242 walks per flip, 3.4-3.9 ms of the 4.0 ms at the cold start.

Tables: NOTES sections 5.1-5.3.

## Change

`HAKUX_DRAWREC=1` (draw.c only, NOTES section 8):

- **VTX.** Test-and-clear and copy as before, but owe the TLB re-arm to a
  bitmap walked once per flip, or early after a re-copy budget. Owed pages
  are re-copied on every touch until then.
- **SHC.** Clear `shader_bindings_changed` after a full-path draw that has
  used it.

`HAKUX_DRAWREC_VTX=0` / `HAKUX_DRAWREC_SHC=0` turn one part off.

## Results

### Pilot (one run per state)

NFS race start, perflog, F1-F3 on, `drawread.py` over the countdown windows.
Runs: off `1-1791661644-drawrec1010-952014`, ON `1-1791661643-drawrec1010-951926`.
Both have 12 marks and a moving car in every `s*-g11.png` (30-96 mph).

| state | draws/frame | us/draw | Syn | Pipe (Sh) | Desc | Mfp | warm pace ms | v2 | vtx walks/flip |
|---|---|---|---|---|---|---|---|---|---|
| off | 1,603 | 7.77 | 3.97 | 3.84 (1.75) | 0.53 | 0.98 | 42.9 | 46.0% | 157 |
| ON | 1,614 | 6.16 | 1.91 | 2.96 (1.11) | 0.21 | 1.77 | 41.9 | 49.3% | 64 |

Legs of `drawrec1010-nfs.json` on the pilot:

| leg | verdict | why |
|---|---|---|
| U | PASS | us/draw -20.8%, Syn 1.91 ms |
| R | FAIL | 64 walks/flip against <= 20 predicted. The re-copy budget forces ~9 walk batches a flip, and each batch pays one full TLB scan per merged run (~5.5). |
| P | PASS on perflog | -1.0 ms/frame, at the edge of the predicted range |
| H | FAIL on perflog | v2 share +3.3 points |
| V | VOID | the plain runs are not in yet |

A fix for R is parked as `docs/lanes/drawrec1010/tlbmap.mbox`: one bitmap-filtered
TLB scan per batch. It touches `accel/tcg/cputlb.c`, `system/physmem.c` and two
headers, which are outside this lane, so it waits on a board request (NOTES
section 11). It has not been measured.

Pixels on the 27-suite disc, plain (A off `1-1791661643-drawrec1010-951834`,
B ON `1-1791661636-drawrec1010-950252`): 1,053 of 1,060 captures are
byte-identical. The 7 that moved:

- six are the named GeometrySuperscreen noise;
- one is Stencil_ZERO_ST, where A has the rare value. It read 30,000 px in
  32 of 35 earlier runs without the switch, B's value.

The prediction's runs=3 recheck is queued (NOTES section 10.1).

Plain A/B (2 runs per state) and the pixel recheck: queued, NOTES section 4.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
