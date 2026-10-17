# lane.defaulton1017 NOTES (#1018, 0.5.2)

## Status

- 04:31 PDT 10-17: branch opened, origin/lane/halo1016 @ 58f86b192c merged (fast-forward).
- 04:55: the four defaults flipped and REPORT_EARLY's gate and instrument added (ed2b1d3333, master with
  halo1016's fold merged in). Syntax-checked against the nightly arm64 compile database; built only by the
  dispatcher.
- 05:10: screen plan below written before anything is queued. Prediction:
  `docs/testing/predictions/defaulton1017-screen.json` (title rows) and `defaulton1017-tsc.json` (the pgraph item).
- 05:15: pilot queued on the Nova (`scratch/queue_screen.sh HON HNI`): HON 1792238475-defaulton1017-3197170,
  HNI 1792238476-defaulton1017-3197283. The rest waits on the pilot's verdict.
- 05:30: `screenread.py` written and dry-run on old results before any row returned: it reproduces EIF's
  33.8 ms/f and windows 33.4-34.7, E's 35.9, MKSM on1's locked 54.4 fps and Top Spin on1's play 59.0 (each voids
  on the switch lines, as it should: those runs set the env). fps1015's readers name the arm from the env, so
  screenread calls their `read_run` and sets the arm to `on` itself. Correction to the prediction's `baseline`
  prose: the EIF id written there (0-0-x-1792231796-halo1016-2209151) is arm EV's; EIF is
  0-0-x-1792231794-halo1016-2208719. The figures quoted (33.8, 33.4-34.7) are EIF's and are what the legs use.
- 05:25: pilot judged (below, "Pilot verdict"). HIBC MISS, so by the registered rule IBC goes back to off by
  default: `accel/tcg/cpu-exec.c` and `include/accel/tcg/hakux-ibc.h` restored to master's. The rest of the
  screen runs on the same binary (ed2b1d3333) with `HAKUX_IBC=0`, which is what ships: the IBC code reads `0`
  and unset the same way once the flip is gone. `pilots/defaulton1017.ok` written.
- 05:30: default-on re-scan of the open lanes' PR.md and NOTES.md (`scratch/defaulton_scan.py`): no new
  candidate (memfast's F3 is still a plan; verdict433's line names kabukistall, not a switch). Queued
  (`scratch/queue_screen.sh`): HOFF 1792239587-defaulton1017-3307802, MKSM 1792239588-defaulton1017-3307916,
  TS 1792239589-defaulton1017-3308032, RS 1792239590-defaulton1017-3308140, SHR
  1792239591-defaulton1017-3308261, CLR 1792239593-defaulton1017-3308455, AMP 1792239593-defaulton1017-3308736,
  TSC1 1792239595-defaulton1017-3309294, TSC2 1792239595-defaulton1017-3309495. ~60 Nova minutes.
- 05:21 (host `date`; the two "05:30" lines above were estimates and came earlier): territory board request
  filed (board-requests/xbox.md, 05:21 entry) for reports.c, surface.c and translate.c; IBC's files are not in
  it. lane.xbox corrected the brief's release note: "holds 30 fps" overclaims (HNI 35.0 ms/f is 28.6 fps, its
  windows reach 38.2). The PR's line becomes "runs at about <N> fps through the hangar briefing (was <M> fps)",
  N from HNI (what ships: IBC off) and M from HOFF, over the same span.
- 05:28: HOFF judged: HIT, 58.9 ms/f (below, after "Pilot verdict"). Release note set from HNI and HOFF: "about 29
  fps (was 17 fps)". nv2a index: `nv2a_index.py check` against fold-pins (6743b6ab, 104 suites) passes, with line
  drift only (9 symbols, anchors unchanged). Its own output says not to commit a rebuild for drift; fold.sh
  refreshes line numbers. So the index stays out of the diff (unlike halo1016, which added two sites).
- 05:35: MKSM judged: MKF HIT (54.3 fps), MKE HIT, FL MISS (131k precision flips in the first 24 s). The
  registered conditional row runs: MKC 1792240507-defaulton1017-3391984, MKSM with `HAKUX_FLDCW_CHAIN=0`.
- 05:45: TS void on input (an A dropped at controller select; route never reached a match). Rerun queued:
  1792240997-defaulton1017-3446680.

## Pilot verdict (HON, HNI; screenread.py, as registered)

| row | result | span ms/f | 10-s windows +100..+210 | early share | stale / vis / desync per early | flips |
|---|---|---|---|---|---|---|
| HON | 1792238475-defaulton1017-3197170 | 34.6 | 33.4-35.6 | 0.9963 | 0.0109 / 0.0055 / 0 | 0 of 120.6M |
| HNI | 0-0-x-1792238476-defaulton1017-3197283 | 35.0 | 33.4-38.2 | 0.9961 | 0.0093 / 0.0045 / 0 | 0 of 119.5M |
| EIF (halo1016, reference) | 0-0-x-1792231794-halo1016-2208719 | 33.8 | 33.4-34.7 | 1.0000 | (no instrument) | 0 |

Both: every switch logged as the default with its variable unset (HNI: `[ibc507] on=0 ... HAKUX_IBC=0`),
`mark cinematic`, 30 `[rtrace] w` async windows in the span, route end, no crash.

- **HG MISS**: 34.6 ms/f (<= 34.5) and the +130 window 35.6 (<= 35.5). The plateau is gone (59.3 with all
  off); HON is 0.8 ms/f over EIF. That is inside halo1016's own run-to-run spread (A 42.6, A2 41.6 on one
  binary and env: 1.0 ms/f), so one run cannot tell whether the gap-1 gate costs anything. The gate's
  `skipn` (3,837 in the span, ~2 a frame) does not follow the excess window by window
  (`scratch/skipn_windows.py`): +130 is +0.9 over EIF with 31 skipn, +160 and +180 are -0.2 and +0.2 with
  622 and 906. The bar was set inside the noise; it is a miss as written.
- **HEA HIT** (0.9963): Halo re-queues almost every offset one guest frame later, as assumed. The 0.4% that
  are not (`skipn`) are written the old way.
- **HVIS HIT** (0.0055): one early answer in 180 shows an object visible where its own test hid it, or the
  reverse, for one frame. They cluster in +130..+150 (5,618 of the span's 5,723, 1.2% of those windows'
  answers), the two heaviest windows; the rest of the span is under 0.1%. Outside the span, small windows
  reach 0.4-0.7% (+70, +100, +220: 15-44k answers each). `stale` (any difference in the count) is 1.1%.
- **HDS HIT**: desync 0 in both, so the ring and the reader agree on every answer: the instrument is valid.
- **HIBC MISS**: HNI - HON = +0.43 ms/f (>= +0.5). By the rule written before the run, IBC goes back to off.
  Not judged, for the record: IBC's share is largest in the heaviest window (+130: 38.2 without, 35.6 with),
  and like HG, +0.43 is inside the run-to-run spread, so this does not say IBC does nothing for Halo, only that
  one run does not show the 0.5 ms/f that would pay for #507's energy cost (Forza x1.10 J/frame).
- **FL HIT**: 0 flips in 120M FLDCW calls.

What changes for the rest: the title rows (MKSM, TS, RS, SHR, CLR, AMP) are queued with `HAKUX_IBC=0`, the
shipped configuration; screenread's V reads the IBC state each row's request asks for. HOFF is unchanged.
Nothing else in the plan moves.

HOFF (1792239587-defaulton1017-3307802, 05:21-05:28): all four log off with `=0`, route end, held 423 s, no
crash. Span 58.9 ms/f; the +130..+180 windows are 62.4, 78.7, 52.5, 41.2, 95.2 and 73.1. **HOFF HIT** (>= 52): the
escape hatch restores the pre-fix behaviour (census A was 59.3). `[fldcw1018] n=` 93.3M and no `w` lines, as
expected with REPORT_EARLY off.

Release note, from these rows over the same span (lane.xbox's correction, 05:2x): HNI, what ships, 35.0 ms/f =
28.6 fps; HOFF 58.9 ms/f = 17.0 fps, and its worst window, 95.2 ms/f, is 10.5 fps.
`Release note (performance): Halo: Combat Evolved's opening cinematic runs at about 29 fps through the hangar
briefing (was 17 fps)`.

## Title rows (screenread.py, as registered)

| row | result | switches logged | route end, held | early | flips / FLDCW | figure |
|---|---|---|---|---|---|---|
| MKSM | 1792239588-defaulton1017-3307916 | s2t on, early 1, chain 1 (unset); ibc 0 (`=0`) | yes, 333 s | 0 (no `w` line) | 131,073 / 1,048,576 | locked 54.3 fps |

- **MKF HIT**: 54.3 fps locked over 1,800 frames from s13 (fps1015's on: 54.2-54.4), V cut 79, signature 55,
  play 130, 30 locked windows. Cutscene and gameplay medians are 59.0 gfps each.
- **MKE HIT**: no early answer. MKSM queues no armed visibility report.
- **FL MISS** (P 0.5 as registered): MKSM flips precision, 1 call in 8, and only in its first 24 s. The
  conditional MKC row is queued (below, "Conditional rows").
- **TS VOID, input** (1792239589-defaulton1017-3308032): the route left at controller select. s13 is the same
  screen as fps1015's on run (0-1792170178-fps1015-2310292; mean difference 0.0 on 64x48 grey,
  `scratch/shotdiff.py`), with the same `press A` at the same offsets. There it went on to player select; here
  the A presses at s13 and s14 did nothing, and the rest of the route ran on the wrong screens (difference
  45-64 from s15 on). It ended at player select, never in a match, so tsread's V has no signature (0) and no
  `[s2tcvt]` line (the check is not reached in menus). Up to the divergence none of the switches shows it
  acted: no `[rearly1018] w` line (no report queued), no `[fldcw1018] n=` line (< 2^20 FLDCW), and no s2t
  line. Menus at 59 fps, no crash, pace to the end. A dropped input, not a defect the switches can be blamed
  for. Rerun once (single-run flake rule): TS 2nd queued, 1792240997-defaulton1017-3446680.

## Confirmed from the source files (not from the brief)

| cause | switch | over [mark+131, mark+191] | where read |
|---|---|---|---|
| 49 `cvt` surface downloads a frame | `HAKUX_S2T_CVT` | 59.3 -> 41.9 ms/f | halo1016 NOTES, fps1015 NOTES "The default and the board row" |
| ~544 armed visibility-test reports a frame, polled | `HAKUX_REPORT_EARLY` | 42.1 -> 35.9 | halo1016-early.json arms B, E |
| FLDCW exits, helper lookups | `HAKUX_FLDCW_CHAIN` + `HAKUX_IBC` | 35.9 -> 33.8 (windows 33.4-34.7) | arm EIF |

Without the early answer the vCPU arms were A 42.6, F 40.5, I 40.5, IF 39.2 ms/f. EF (the chain without IBC, with
the early answer) was never run, so whether IBC is needed for Halo's bar is unmeasured. It is row HNI below.

All four were off unless set to `1`. None is in MainActivity.kt's `FASTPATHS_VARS` (the shipped "Fast renderer
paths" list, which sets `HAKUX_REPORT_ASYNC=1`). So the shipped path reads the C getenv default, and the flip is
there, as FIST_ROUND's was (52aa206f93): unset or anything but `0` is on, `0` is off, and each logs which and why.
A request's `--env K=0` still reaches it, after the app's defaults. REPORT_EARLY still needs the async reader:
with "Fast renderer paths" off it logs `needs HAKUX_REPORT_ASYNC=1: off`.

## What changed in REPORT_EARLY, and why (no device time)

halo1016's early answer gives any armed GET_REPORT the count its offset was last written with. That is right for
Halo, which runs one test per offset per frame and polls it the next. It is wrong for two other patterns, both
read from existing logs (`scratch/armedscan.py`, every `[rtrace] w` window on disk):

| pattern | seen in | what the early answer would be | now |
|---|---|---|---|
| offset re-queued in the same guest frame | none on disk (Halo's reuse is 8-66.7 ms, NFS's > 66.7 ms) | another test's count | `skip0`: written as before |
| offset re-queued two or more frames later | NFS MW: 4-slot ring, 100% of ~35,000 reuses > 66.7 ms, ~29 reports/s at ~1 a frame, so each slot comes back 4 frames later; the guest reads the slot later and never waits on it (0 report waits in async, reportasync1010) | a count four frames old where the reader's own would arrive in ~28 ms: older, for no gain | `skipn`: written as before |
| offset re-queued one guest frame later | Halo: 2.55M reports, every one armed | the same test's count, one frame old | answered early |

The frame is `pg->frame_time` (FLIP_INCREMENT_WRITE, the PFIFO thread, the same thread that queues the report),
so the gap is exact in command order. halo1016's trace (`rt_flip_locked`) already stamps Halo's flips by it.

The instrument: each early answer goes into a ring. When the reader has the report's own count, `re_check()`
compares: `stale` = the answer differs, `vis` = one of them is 0 and the other is not (the guest drew or hid
something its own test would have decided the other way, for one frame), `desync` = the ring and the reader
disagree (the instrument's own validity). All on the 2 s `[rearly1018] w` line with `early cold unarmed submit
skip0 skipn full`. `vis` is the failure the brief names (a flare or a corona a frame late at a camera cut),
counted where it happens instead of looked for in frames.

## Where each switch acts: what is already on disk

- **S2T_CVT**: fps1015's `cvtcensus.py`: Top Spin, MKSM, Halo, Fuzion Frenzy, ToeJam & Earl III, NBA Live 07;
  PoP and Batman from dumps. Three of them are canaries already.
- **REPORT_EARLY** can act only where the guest runs visibility tests. The perflog line `hakuX-rpbrk ... qry`
  counts the render-pass breaks from query begin/end per 60 flips. `scratch/qrycensus.py` read it from every
  title run on disk (55 titles). qry > 0 in the share of windows shown, median of the nonzero windows:

  | title | windows qry>0 | median qry | runnable on the Nova now (profile gate) |
  |---|---|---|---|
  | Azurik | 95% | 5935 | Thor runs only |
  | Halo CE | 93% | 10031 | yes, canary |
  | Alias | 74% | 3150 | Thor runs only |
  | Amped 2 | 68% | 70 | yes, `amped2` (qry from ~window 43 in pmucounters' 578 s runs) |
  | Simpsons Hit & Run | 68% | 99 | yes, `simpsons-hit-run` (qry seen on gpunonrender's route; unread on this one) |
  | Blinx 2 / Blinx 1 | 65% / 33% | 240 / 1137 | survey runs only, no route; not since 10-08 |
  | NFS MW | 39% | 120 | no: no golden profile since the gate; the skipn argument above is from its logs |
  | RalliSport Challenge | 33% | 1774 | yes, `rallisport-804g` (accuracy804: every race frame) |
  | Top Spin | 32% | 94 | yes, canary (the match) |
  | Conker | 26% | 490 | yes, no route (memfast's 300 s boot reached qry > 0 at window 64) |
  | PGR, BF2MC, Halo 2, NGB, DOA1U | 4-25% | 32-60 | small |
  | 39 others, Forza, GTA SA, MKSM and Fuzion Frenzy among them | 0% | - | cannot act |

  Whether the guest arms the status word, and whether its offsets come back one frame later, only an ON run
  says. The rows below are the titles where it can act and that the Nova can run.
- **FLDCW_CHAIN**: `[fldcw1018] n= flips=` every 2^20 FLDCW calls, in every arm. Halo: 0 flips. Every ON row
  below is a flips census for free. A title with fewer than 2^20 calls logs no line.
- **IBC**: #507's record (docs/lanes/ibcache/NOTES.md 5c, 5d): GTA x1.02 and Forza x1.10 J/frame, fps unchanged,
  no defect, with the idle halt off (still the default). Where the vCPU is the bound, it is frame time.

## The screen (first pass)

One build, ed2b1d3333, the Nova only. ON = no switch env, which is the shipped default now. Every row's
`[s2tcvt]`, `[rearly1018] early=`, `[fldcw1018] chain=` and `[ibc507] on=` lines are its V.

| row | title, route, s | env beyond the default | what are we looking for | Nova min |
|---|---|---|---|---|
| HON | Halo, halo-cinematic, 420 | FRAMETRACE, PROBE_WAITS, REPORT_TRACE (as EIF) | the shipped default holds Halo's span at EIF's level (<= 34.5 ms/f, every 10 s window <= 35.5), the gap-1 gate keeps the early share >= 0.98, and how often an early answer flips visibility (`vis`) | 8.5 |
| HNI | the same | + `HAKUX_IBC=0` | IBC's share of Halo's bar: if HNI is within 0.5 ms/f of HON, IBC goes back to off (its energy cost buys nothing here) | 8.5 |
| HOFF | the same | + the four `=0` | the escape hatch: all four log off and the span is back above 52 ms/f | 8.5 |
| MKSM | MKSM, fps1015-mksm, 330 | none | S2T_CVT on by default reaches fps1015's on level (>= 52 fps; on was 54.2-54.4) to the route's end; early = 0 (no visibility tests) | 7.0 |
| TS | Top Spin, fps1015-topspin, 450 | none | S2T_CVT's match play (>= 56 fps; on was 59) to the route end; REPORT_EARLY in a second title: early share and `vis` in the match | 9.0 |
| RS | RalliSport, rallisport-804g, 240 | none | REPORT_EARLY where the race runs visibility tests every frame: does it act, `vis`; the rivals and their shadows in the d1-d20 shots, the #804 symptom | 5.5 |
| SHR | Simpsons, simpsons-hit-run, 300 | none | does REPORT_EARLY act on this route; `vis`; a valid end | 6.5 |
| CLR | Conker, no route, 300 | none | does REPORT_EARLY act; `vis`; a valid end | 6.5 |
| AMP | Amped 2, amped2, 578 | none | does REPORT_EARLY act (light, 70 a window, in most windows); `vis`; a valid end | 11.1 |
| TSC1, TSC2 | pgraph `Texture_shadow_comparator`, f5a67ba52c (fps1015's arm A) | none | fps1015's pixel item: A against A moves (run-to-run in a suite master broke) or is byte-identical (the switch moved the stale colours) | ~12-16 |

Total: ~84-88 Nova minutes, about 1.5 h, under the 3 h aim. Every ON row also gives the flips census.

Dropped, and why: Fuzion Frenzy (S2T acts there, but its only route is first-run and the title already has a
kept profile: the gate refuses it; S2T has three acting titles in the canaries), NFS MW (no golden profile since
the gate; its pattern is read from logs above), Azurik, Alias, Blinx (no Nova route).

Pilot: HON and HNI first (Halo jumps the queue until 07:30), judged before the rest.

Conditional rows, queued only on a trigger, each with its own line here first:

- a title with `vis` > 2% of its early answers: that title with `HAKUX_REPORT_EARLY=0`, and both with
  `--frames-every 1` over a camera cut, to look at what the flipped tests drew;
- an ON row that crashes, hangs or leaves its route where the last master run of it did not: that row again
  with one switch `=0` at a time (the owner's isolation rule);
- a title with flips > 0: its `HAKUX_FLDCW_CHAIN=0` arm, route end and frames against the ON row.
  - **Triggered, MKC** (05:35): MKSM's ON row logged `[fldcw1018] n=1048576 flips=131073 cw=007f` 24 s after
    start (boot and publisher logos, before s04), and no second line in the remaining 300 s (fewer than 2^20
    more calls). So the chain's exit, which `lookup_and_goto_ptr`s to the TB for the new precision, ran ~131k
    times there. What we are looking for: MKSM with `HAKUX_FLDCW_CHAIN=0` (the TB ends at every FLDCW, as on
    master) reaches the same route end, signature and locked fps, and its s01-s28 and hold shots match the ON
    row's screen for screen. A hang, crash, a different screen at a shot, or a fight that plays out differently
    (same inputs) in ON only is the chain's failure. 330 s, ~7 Nova min. Queued with `scratch/queue_screen.sh MKC`.

Judge: `docs/lanes/defaulton1017/screenread.py` (written before the first verdict) with halo1016's `vcpuread`
and `earlyread` readers for Halo, fps1015's `s2tread.py` and `tsread.py` for MKSM and Top Spin.

Re-scan for a new default-on candidate (open lanes' PR.md and NOTES.md) before the last row: at 04:45 there was
none.

## Questions

None yet.
