# defaulton1017: S2T_CVT, REPORT_EARLY and FLDCW_CHAIN on by default, after one default-on screen; IBC stays off (#1018)

State: ready

Lane: defaulton1017            Issue: #1018
Base: master @ 15f8524be1 (halo1016's fold, merged)
Files: hw/xbox/nv2a/pgraph/vk/reports.c, hw/xbox/nv2a/pgraph/vk/surface.c, target/i386/tcg/translate.c, docs/testing/predictions/defaulton1017-screen.json, docs/testing/predictions/defaulton1017-tsc.json, docs/lanes/defaulton1017/PR.md, docs/lanes/defaulton1017/NOTES.md, docs/lanes/defaulton1017/forgeq.py, docs/lanes/defaulton1017/screenread.py, docs/lanes/defaulton1017/scratch/
Prediction: docs/testing/predictions/defaulton1017-screen.json @ d1ef1f1f548fe8220b722fd29ad675d2775b53ca54ccba996dd220fb956557e9, docs/testing/predictions/defaulton1017-tsc.json @ feacd0253e4cb6fde8a3945199fe2b1ab71766e1670244882e403283571d8e3c
Needs device: yes    Needs NDK: yes

Release note (performance): Halo: Combat Evolved's opening cinematic runs at about 29 fps through the hangar briefing (was 17 fps)

Three of the four switches that remove Halo CE's opening-cinematic plateau (#1018) now read unset as on and
`=0` as off, and each logs which. None was in the app's "Fast renderer paths" list, so the shipped app reads
the C getenv default. `HAKUX_IBC` stays off by default, as on master. With the other three on, it was worth
0.43 ms/f on Halo's span in one run (HNI 35.0 against HON 34.6). That is under the 0.5 ms/f registered before
the run as what would pay for its energy cost.

REPORT_EARLY now answers early only an offset whose last GET_REPORT came one guest frame before, which is
Halo's pattern. Two other cases are written as before:

- an offset re-queued in the same frame, which would get another test's count;
- an offset re-queued two or more frames later, like NFS Most Wanted's slot ring, which its guest does not
  wait on.

Each early answer is compared with its own test's count once the reader has it. The results go on the 2 s
`[rearly1018] w` line as `stale`, `vis` (one is 0 and the other not) and `desync`.

## Halo, over [mark+131, mark+191]

| row | configuration | ms/f | fps | 10-s windows |
|---|---|---|---|---|
| HNI | what ships: S2T_CVT, REPORT_EARLY, FLDCW_CHAIN on, IBC off | 35.0 | 28.6 | 33.4-38.2 |
| HON | the same with IBC on | 34.6 | 28.9 | 33.4-35.6 |
| HOFF | all four `=0` (master's behaviour) | 58.9 | 17.0 | 41.2-95.2 |

## The screen: one verdict per switch

The screen ran on the Nova, one binary (ed2b1d3333). The rows were designed from each switch's mechanism, and
each was judged as written before it ran (`NOTES.md`, "The screen", "Pilot verdict", "Title rows").

| switch | verdict | evidence |
|---|---|---|
| S2T_CVT | ships on | MKSM locked 54.3 fps, fps1015's on level; Conker logs it on with a valid end. The pixel item (Texture_shadow_comparator) is closed against the switch: a pair without the switch moves 68 of 288, more than the switch's 64. |
| REPORT_EARLY | ships on | Halo answers 99.6% of its reports early, with `vis` 0.55% and `desync` 0. It acts in Simpsons Hit & Run (10,984 early, `vis` 0.07%) and RalliSport (7,640, 0.16%). The gate declines Conker's and Amped 2's late re-queues as designed. `desync` is 0 in every row. |
| FLDCW_CHAIN | ships on | 0 flips in Halo, RalliSport and Simpsons. MKSM flips at boot, and Conker on 99.5% of its FLDCWs. Each was run again with the chain off, and the runs matched (MKC: the same screen at every shot; CLF/CLC: the same attract sequence). |
| IBC | stays off | HIBC missed (+0.43 ms/f, bar 0.5) |

Top Spin is out of scope. It is not a Playable and has open defects (#992, #796), and the owner stopped the
screen at 07:00 on 10-17. Its route dropped A presses at controller select with this lane's switches on,
with the chain off, with FIST_ROUND off, and with all three switches off. This is not judged as a
regression of the flip.

## Not checked

The owner's own title screen comes next, and nothing was run to close these:

- REPORT_EARLY's one-frame visibility flips were counted but never looked at in frames. No title crossed the
  2% trigger for a frame row.
- Texture_shadow_comparator: since #1033 the suite moves 68-78 of 288 captures between runs of one binary,
  so whether S2T_CVT moves any of its pixels at all can't be read until #1033 is fixed.
- S2T_CVT and REPORT_EARLY inside Top Spin's match, on this binary (out of scope, above).
- #804's rival blink in RalliSport: no shot on the route catches the pass, master's included.

## Selftest fragments this change needs (read from the diff)

- `10-arms-list.sh` and `20-arms-queue.sh`. The diff adds two committed predictions. `arms.sh list` and
  `run` walk every committed prediction in the tree under test (`git ls-tree` over `$REPO`). Both fragments
  require each committed prediction to be fenced behind the watermark, so the live fixture stays the only
  pair queued. 20 consumes 10's state, so they run together and in that order.

Nothing else. No fragment reads `reports.c`, `surface.c` or `translate.c`. The diff shifts lines in two files
that `nv2a_index.json` cites by file:LINE (anchors unchanged; `nv2a_index.py check` passes with drift). The
fold's own `regen_index` step rebuilds the index for that from its pinned trees. That step is not a selftest,
and the diff changes neither `nv2a_index.py` nor the index, so `75-nv2a-index*.sh` (synthetic trees) cannot
move. `99-release-note-line.sh` reads `roles/lane.md` and `nightly_build.sh`, not this body, and the diff
changes neither.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
