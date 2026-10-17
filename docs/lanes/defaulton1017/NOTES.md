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
- 05:48: attempt 1 ended on its 300-turn cap, not on a defect or a block. Everything was pushed (575698eb5f).
  It spent its turns on short status polls and one-call-per-question reads while nine rows ran; attempt 2
  waits on DONE files with one long call each and judges each row in one script call.
- 05:50 (attempt 2): SHR done, unjudged; CLR on the Nova since 05:47:49. RS never ran: its results dir holds
  only `ERROR`, "title not on device: 4D53000F-RalliSport_Challenge.xiso.iso". "Runnable on the Nova now" in
  the table below was wrong for it: the profile gate's list was read, not a live listing of the device.
  lane.xbox asked lane.local to push the ISO; RS is requeued only once a live listing shows it.
- 05:52: SHR judged (all hit). Live listing at 05:51: RalliSport Challenge (4D53000F) still not on the Nova
  (only RalliSport Challenge 2). The master regression behind TSC is filed already: #1033 (open).
- 05:57: CLR judged: FL MISS (99.5% of FLDCW flip). Conditional rows CLF 1792241775-defaulton1017-3512155
  and CLC 1792241776-defaulton1017-3512282 queued (Conker, frames every 5 s, ON and CHAIN=0).
- 06:06: AMP judged (valid end). RS still not on the Nova (live `ls` of its path). Default-on re-scan
  (`scratch/defaulton_scan.py`, 12 open lane PRs): the same two lines as at 05:30, memfast's F3 plan and
  verdict433's mention of kabukistall; no new candidate.
- 06:08: TSC1 done. lane.xbox: hakux-0b pushed RalliSport to the Nova at 06:05 (sha256 matches the host's),
  and the 88 s push overlapped about the first minute of TSC1. So if TSC1 and TSC2 differ, the push is one
  possible cause and the difference does not decide the pixel item; if they match byte for byte, the
  overlap does not matter. Live listing confirms the ISO; RS requeued: 1792242364-defaulton1017-3562768.
- 06:15: TSC1/TSC2 judged: FAIL as registered (37 moved), and a pair without TSC1 (fps1015 A vs TSC2, 68
  moved) removes the push confound. S2T_CVT's pixel item closed against the switch (below). #1033 comment
  19738.
- 06:20: MKC judged: the same as MKSM ON screen for screen, fps and end (below). Waiting on TS rerun, CLF,
  CLC, RS.
- 06:44: TS 2nd void the same way, so the A drop is not a flake. The base also moved: FIST_ROUND has been on
  since 10-16 18:47 (below). Isolation rows queued, after their lines under "Triggered, TS isolation":
  TSF 1792243851-defaulton1017-3688312, TSFR 1792243854-defaulton1017-3689026, TSOFF
  1792243856-defaulton1017-3689586, TSR 1792243858-defaulton1017-3690150, TSS 1792243860-defaulton1017-3690596.
  CLF done; CLC on the Nova; RS queued.
- 06:50: CLF/CLC judged: the same attract sequence, in sync for the first ~95 s; no hang or crash (below).
  The FLDCW chain's exit path, taken on 99.5% of Conker's FLDCWs, shows nothing these frames can see.
- 06:58: RS judged: every leg hit; REPORT_EARLY acts there (7,640 early, vis 0.16%). No rival is in any
  shot, master's included, so #804's blink can't be read from this route (below). Waiting on the five TS
  rows.
- 06:48 (host `date`; the "06:50" and "06:58" above were estimates and ran ahead: TSF's own shots end at
  06:45:58, and RS and CLF/CLC were judged before it finished): TSF (chain off) DROPS like ON, so the chain
  alone is not the cause (below, "TS isolation"). Waiting on TSFR, TSOFF, TSR, TSS.
- ~06:58: TSFR (FIST_ROUND off) DROPS the same way. The TS base pair (master 15f8524be1, fps1015's
  f5a67ba52c) is written and is queued if TSOFF drops.

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
| SHR | 1792239591-defaulton1017-3308261 | early 1, chain 1 (unset); ibc 0 (`=0`); no s2t line | yes, 302 s | 10,984 in 116 windows, share 0.9999 | 0 / 1,048,576 | valid end, pace 308 s |
| CLR | 1792239593-defaulton1017-3308455 | s2t on, early 1, chain 1 (unset); ibc 0 (`=0`) | no route; held 303 s | 82 (skipn 22,459), share 0.0036 | 1,043,567 / 1,048,576 | valid end, pace 301 s |
| RS | 1792242364-defaulton1017-3562768 | early 1, chain 1 (unset); ibc 0 (`=0`); no s2t line | yes, 243 s | 7,640 (skipn 13,697, unarmed 1,120), share 0.358 | 0 / 13,631,488 | valid end, pace 252 s |
| AMP | 1792239593-defaulton1017-3308736 | early 1, chain 1 (unset); ibc 0 (`=0`); no s2t line | yes, 580 s | 9 (skipn 5,551), share 0.0016 | no line (< 2^20 FLDCW) | valid end, pace 535 s |

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
- **TS 2nd VOID the same way: not a flake** (1792240997-defaulton1017-3446680). Controller select from s13
  to s16: the A at s13, the A at s14, the START at s15 and the A at s16 all did nothing. The d-pad (`axis
  HATX min`) after s16 moved 1P to Team One (s17), and the A after it took (s18, player select). But the As
  at s18 and s19 and all 54 in the hold loop left player select with no READY banner. tsread: 117 play
  windows, 0 with a signature (no match). Route end, no crash, menus at 59 fps. Both runs: a digital input
  (the d-pad) registers, the analog face button (an Xbox A is a pressure byte) mostly does not.
  `scratch/tsroute.py` (every run of this route family on disk) and tsread on fps1015's three runs of
  the route (f5a67ba52c): an A at s13 that does nothing is ordinary there too (s13 to s14 unchanged in 6 of
  the 7 runs by other lanes, fps1015's off run included). But each of fps1015's three runs lost at most
  that one A and reached the match (off 55 of 55 play windows with its signature, on 68 of 70, frame-dump
  on 87 of 88). `scratch/sheet.py` s13-s19, master's two against these two: master is at player select by
  s14/s15 and in the match by s16; these runs are still at controller select at s16.
  **The base moved too.** fps1015 ran f5a67ba52c (10-16 ~10:45). This binary also carries master's
  52aa206f93 (10-16 18:47, #939): `HAKUX_FIST_ROUND` on by default, so inline FIST/FISTP round per the
  guest's RC on aarch64 instead of truncating. Top Spin logs `perfarch fist round=ON (default)` and emits
  rounding FISTs from 4 s after launch, well before controller select. Of this lane's switches, only
  FLDCW_CHAIN can have acted before the divergence. There is no `[s2tcvt]` line at all (S2T's check is
  never reached), no `[rearly1018] w` line (no report queued), and IBC is 0. Read in the source, the two
  are consistent: the call to helper_fldcw runs `gen_bb_epilogue()`, which clears `flcr_set`, and FIST goes
  through `get_st0` -> `gen_flcr`, which reloads FPCR from the new RC. The MXCSR-to-FPCR RC swap is
  right, and only FIST/FISTP emit `cvt*f_i*` (`ops_fpu.h:330,335`). So runs decide it (below, "Triggered,
  TS isolation").
- **SHR: SV HIT, VIS:SHR HIT, HDS HIT, FL HIT.** REPORT_EARLY acts in a second title: Simpsons Hit & Run
  answers 10,984 reports early over the route (~47 a second), with 1 cold and no skip0/skipn, so it re-queues
  each offset one guest frame later, as Halo does. vis 8 of 10,984 (0.07%, bar 2%), stale 1.5%, desync 0. No
  crash, route end, pace to the log's end. No conditional row is triggered.
- **CLR: CV HIT, HDS HIT, FL MISS; VIS:CLR not judged** (early 82 < 1000). Conker logs `[s2tcvt] on`
  (S2T's check is reached), and REPORT_EARLY's gate declines almost every report: 22,459 `skipn` (offset
  re-queued two or more guest frames later, NFS's pattern), 34 cold, 82 early, desync 0. The gap-1 gate does
  what it was added for, in a title nobody had read it in. FLDCW: **1,043,567 flips in 1,048,576 calls**:
  Conker alternates the precision bit on nearly every FLDCW, so the chain's exit (eip past the FLDCW, then
  `lookup_and_goto_ptr` under the new hflags) is the path it takes, ~3,500 times a second. No crash, valid
  end, pace 301 s. No route, so no shots to look at. Triggers the FLDCW conditional row (below, CLF/CLC).
- **MKC (conditional, MKSM with `HAKUX_FLDCW_CHAIN=0`): no difference from MKSM ON.** 1792240507-defaulton1017-3391984:
  `[fldcw1018] chain=0 HAKUX_FLDCW_CHAIN=0`, the same 131,073 flips in the first 2^20 calls (the counter is in
  the helper, so it counts with the chain off too), route end, held 333 s, no crash, locked 54.4 fps (ON
  54.3), s2tread's V the same shape (cut 78, signature 52, play 131). `scratch/shotdiff.py` ON vs MKC: s01-s09,
  s12, s19-s28, gameplay and the first hold within 0.4 (same picture); s10, s13-s18 3.6-12.4 and holds 2-3
  8.9-11.3 (same screen, a few frames apart); s11 31.0. s11, s18 and hold 2 looked at side by side: s11 is the
  intro's palace pan a few frames later, s18 the same cutscene shot as its letterbox comes in, hold 2 Liu
  Kang on the same spot in the same room with the orb a little further along. No screen, fight or end
  differs. **MKSM's FL miss is not a defect:** the chain's exit runs 131k times at boot and the run without it
  is the same.
- **AMP: AV HIT, HDS HIT; VIS:AMP not judged** (early 9), FL not reached (fewer than 2^20 FLDCW in 578 s).
  Amped 2 re-queues its report offsets two or more guest frames later too: 5,551 `skipn`, 3 cold, 9 early.
  REPORT_EARLY's gate leaves it on the reader's path, as on master. Route end, held 580 s, no crash.
- **RS: RV HIT, VIS:RS HIT, HDS HIT, FL HIT.** It ran once RalliSport was on the Nova (lane.xbox, 06:05;
  live listing 06:08). REPORT_EARLY acts in the title whose visibility tests #804 was about: 7,640 early
  answers in 243 s, alongside 13,697 `skipn` and 1,120 `unarmed`, so RalliSport re-queues some offsets one
  guest frame later and others later still. vis 12 of 7,640 (0.16%, bar 2%), stale 6.2%, desync 0.
  0 flips in 13.6M FLDCW. Route end, no crash. The #804 look (`scratch/sheet.py` d1-d20, RS against
  accuracy804's two master runs of rallisport-804g, 1791167624 and 1791167617, 10-04): no rival car
  appears in any d-shot of any of the three runs. The player is at POS 4 OF 4 behind the field, and
  master's d1 at race clock 7.13 is an empty road too. So the route's shots, 2.7 s apart, never catch the
  close pass where #804's blink lives (race clock ~7.3-8.5), and they say nothing about it either way. RS's race
  starts ~7 s later in the route's timeline (d2 is race clock 0:00; master's d1 is 0:07), and the hold
  drive still steers the course. Two RS shots are dark (d8, d19); master's are too (d13 in both runs, d3 in
  1791167617), so they are not the switches'.
- **CLF/CLC (conditional, Conker ON against `HAKUX_FLDCW_CHAIN=0`, frames every 5 s): no difference the
  chain causes that these frames can show.** CLF 1792241775-defaulton1017-3512155 and CLC
  1792241776-defaulton1017-3512282: chain=1 (unset) and chain=0 (`=0`), as asked. Both valid ends (pace 300
  and 302 s), no crash, held 304 and 305 s, and the same report pattern as CLR (skipn 21,598 and 24,854;
  early 60 and 62; desync 0). The flip share is the same: 1,043,395 and 1,041,923 of the first 2^20, so
  CLR's 99.5% repeats and CLC's helper counts flips with the chain off too. I paired the frames on each
  run's launch clock (`scratch/clcompare.py`; sheet at
  /tmp/claude-1000/-home-justin-hakuX/clf_clc.png). The sequence and its order are the same in both: the
  Conker logo, Microsoft Game Studios, the attract montage, the logo, the montage, Rare, the intro, the
  "Xbox Live & Co" menu idling from about +105 s, a second montage with the logo in it, and back to the
  menu by +298/+287 s. For the first ~95 s, the same clip is on screen at the same second: the HUD clip
  at +20 (difference 17, the same frame a moment apart), the logo at +43, the cave at +54 (7), space at
  +60, Rare at +77 (4). The menu idle is 9-17 apart throughout, the same screen. The second montage
  starts ~17 s earlier in CLC (+222 against +239). Its 1-2 s cuts are sampled every 5 s, and there is no
  recording (`video/` holds only meta.json), so the frames can compare that montage only by structure,
  not clip for clip. That is the limit of this verdict. A hang, a freeze, an error screen or a
  wrong-world frame would have shown, and none did.
  Reported, not judged: CLC drew 4.6% more frames by +290 s (10,800 against 10,320 pace frames) and
  reached 2^20 FLDCW 12 s sooner (+174 against +186), which fits CLC reaching the second montage first.
  That is about twice the spread halo1016 measured between two runs of one binary (2.4%), from a single
  pair of frame-dumping runs, so it is not a reading of the chain's cost. By mechanism the chain's flip exit (one `lookup_and_goto_ptr`) is no more
  work than master's `exit_tb` to the main loop and a lookup there.

### TS isolation (`scratch/tsiso.py`, the reading written at 06:40, before any row returned)

| row | result | env beyond ON | switch lines | controller select, s13-s25 | later | tsread play windows, signature | verdict |
|---|---|---|---|---|---|---|---|
| TSF | 1792243851-defaulton1017-3688312 | `HAKUX_FLDCW_CHAIN=0` | s2t on, early 1, chain 0 (`=0`), fist round ON | every A and the START dropped; the d-pad moved 1P to Team One (s17) and nothing took after it | player select by hold 2 (+40 s into the hold loop), match intro (PRESS START) by hold 3 | 33 of 105 on | **DROPS** |
| TSFR | 1792243854-defaulton1017-3689026 | `HAKUX_FIST_ROUND=0` | s2t on, early 1, chain 1 (unset), `fist round=OFF (env HAKUX_FIST_ROUND=0)` | the same: shot distances to master's s15-s19 are TSF's to the unit (24, 47, 53, 47, 56) | match intro only, in the hold loop | 24 of 110 on | **DROPS** |

- **TSF drops, so the chain alone is not what breaks Top Spin's input.** Shots s13-s25 against master's
  off run (sheets at /tmp/claude-1000/-home-justin-hakuX/tsf_s13_s19.png and tsf_s20_s25.png): master is
  at player select by s15 and in the match by s16. TSF is still at controller select at s25, the same
  failure as ON's two runs. Only the hold loop's dozens of As got it through, about one in a dozen taking.
  That is where its first `[s2tcvt] on` line comes from (ON's runs never reached a match, so they had no
  S2T line at all) and its 33 signature windows: the match intro, not the match. Route end, no crash.
- **TSFR drops, so FIST_ROUND alone is not what breaks it either.** The switch reached the code (its OFF
  line), and the route failed at the same place in the same way. No Top Spin run on disk is newer than
  fps1015's three (`scratch/tsroute.py`: 13 runs of the route family, 10-03 to today), so nothing on
  disk separates the base from the device. That is the next pair (above, "Triggered next, TS base").

## S2T_CVT's pixel item: TSC1, TSC2 (defaulton1017-tsc.json, as registered)

`ab_compare.py --a TSC1 --b TSC2 --expect defaulton1017-tsc.json --allow-same-binary`: **FAIL, 37 of 288
must-not-move captures moved** (23 better, 14 worse, each by 80-86 px, about one marker; 3P24_..._NE by 86 on
1,142). The registered prior was P 0.6 that it fails. FAIL means run-to-run movement in a suite master broke,
nothing against the switch.

lane.xbox's confound (the RalliSport push overlapped TSC1's first minute) is removed by a pair that does not
include TSC1: `scratch/tscpairs.py` hashes the suite's captures in every result dir on disk that has them (60).

| pair, one APK (2336324475f6, f5a67ba52c), Nova | env | captures moved of 288 |
|---|---|---|
| fps1015 A (0-1792163881-fps1015-716411, 10-16) vs TSC2 (1792239595-defaulton1017-3309495) | none, none | **68** |
| fps1015 A vs TSC1 (1792239595-defaulton1017-3309294) | none, none | 78 |
| TSC1 vs TSC2 | none, none | 74 |
| fps1015 B (0-1792163875-fps1015-716177) vs fps1015 A | `HAKUX_S2T_CVT=1`, none | 64 (fps1015's A/B) |
| fps1015 B vs TSC1, TSC2 | `HAKUX_S2T_CVT=1`, none | 75, 73 |

Before the regression the suite is bit-reproducible: every one of the 12 binaries on disk with two or more runs
(Nova and Thor, 09-13 to 10-10, e654516849 included) gives 0 of 288 moved in every pair. After it, three no-env
runs of one binary move 68-78 between each other, and the switch's 64 is inside that. **Verdict: S2T_CVT's
pixel item is closed against the switch.** Its 10 worse captures are this suite's run-to-run movement, which the
regression introduced (#1033). No third copy needed: the clean pair (fps1015 A vs TSC2) decides it alone.
Added to #1033 (forge comment 19738, body `scratch/c1033.md`): the regression also made the suite
non-deterministic, so one run per bisect step cannot be read as an exact check.

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
  - **Triggered, CLF + CLC** (05:58): CLR flipped on 99.5% of 1,048,576 FLDCW. MKSM runs the chain's
    stay path 7 calls in 8; Conker runs its exit path almost alone, so the two rows test the two halves.
    CLR has no route and kept no frames, so a CHAIN=0 row alone would have nothing to be compared with. A
    no-input Conker boot (rtdbench-3, 0-0-y-1790395182, frames every 10 s; its `frames/f000*.png`)
    plays the Rare logo, the intro, the "Xbox Live & Co" menu and attract-mode gameplay clips with a HUD
    and a running clock. If those clips are in-engine replays of recorded input, a precision fault shows as
    a replay that walks somewhere else. Two rows, one binary, both `--frames-every 5` (frames cost frame
    rate, so their pace is compared only with each other): CLF = Conker ON (the shipped configuration), CLC
    = the same with `HAKUX_FLDCW_CHAIN=0` (the TB ends at every FLDCW, as on master). What we are looking
    for: the same attract sequence in both, in the same order at about the same times, and the gameplay
    clips showing the same scenes; a hang, a crash, a screen or a clip in CLF that CLC does not show (or the
    reverse) is the chain's failure. 2 x 300 s, ~13 Nova min. Queued with `scratch/queue_screen.sh CLF CLC`.
  - **Triggered, TS isolation** (06:40): TS left its route twice where fps1015's master runs did not (above,
    "TS 2nd"). The owner's rule gives the three one-switch rows (IBC is already 0 in every title row). Two
    more rows separate this lane's switches from the base, which also moved (FIST_ROUND). Every row is TS
    as queued (fps1015-topspin, 450 s, ed2b1d3333, `HAKUX_IBC=0`) plus:
    - TSF `HAKUX_FLDCW_CHAIN=0`: the one switch here whose mechanism acts before the divergence;
    - TSFR `HAKUX_FIST_ROUND=0`: the base change that acts in Top Spin before the divergence (#939, in 0.5.1);
    - TSOFF the four `=0` (HOFF's env): this lane's switches all off on the same binary;
    - TSR `HAKUX_REPORT_EARLY=0` and TSS `HAKUX_S2T_CVT=0`: the rule's other two. Neither acted before the
      divergence, so both are expected to drop like ON.

    What we are looking for in each: does the route reach the match? That means the route's As move
    controller select on with at most one dropped (as on master), player select shows READY, the gameplay
    shots are a court, and two thirds of tsread's play windows carry the signature for the row's S2T state.
    "Drops" means three or more As in a row at controller or player select with no change, and no match. A
    row counts as reaching only by the match signature, because master drops one A at times. Reading:
    - TSF reaches while ON drops: the chain breaks Top Spin's input on this base, so it does not ship on.
    - TSFR reaches, and TSF and TSOFF drop: FIST_ROUND, which is master's and in 0.5.1. It goes to #939 by
      board request; this lane's switches are cleared for Top Spin.
    - TSOFF reaches and every one-switch row drops: two switches together; the pairs next.
    - All five drop: neither the switches nor FIST_ROUND. The next row is master's own binary on this route.

    5 x (450 + 90) s = 45 Nova min, under `pilots/defaulton1017.ok` (05:25). Queued in decision order with
    `scratch/queue_screen.sh TSF TSFR TSOFF TSR TSS`.
  - **Triggered next, TS base** (written ~06:58, after TSF and TSFR dropped, before TSOFF returned): queued
    once TSOFF drops. TSR and TSS cannot clear a row that TSOFF, with all three off, fails, so their verdicts
    do not hold this up. Two rows, the same route, 450 s, no env, no `--expect` (neither is this lane's
    binary):
    - TSM: master's own binary, 15f8524be1 (origin/master now, this lane's base; 0.5.1's 73dbe8796a is in
      it);
    - TSB: fps1015's binary, f5a67ba52c, the one whose three runs reached the match on 10-16, run today on
      the same device, route file and harness.

    Already ruled out by reading, no device time: the route runner (`docs/testing/titles/route.sh`, last
    changed 10-16 07:58, before fps1015's runs), the pads (both eras log the same two: 'Retroid Pocket
    Controller' on port 1, 'Xbox 360 Controller' on port 2, and the route drives `/dev/input/event7` in
    both), and the base's APU changes (`HAKUX_APU_METER`, `_USE_DSP` off by default; `_HRTF_NORM` defaults
    to upstream's l1). Input works on this binary in every other row (MKSM matched master shot for shot).

    What we are looking for: the same match test as the isolation rows. Reading:
    - TSM drops and TSB reaches: a master regression between f5a67ba52c and 15f8524be1 that is not
      FIST_ROUND (TSFR) and not this lane's switches (TSOFF). This lane's switches are cleared for Top Spin
      (ON does what master does). The regression goes to the board as a new issue, with the range to bisect.
    - Both drop: the device or harness has changed since 10-16 10:45, not the code. The switches are cleared.
      The route goes to lane.xbox for whoever owns it.
    - TSM reaches: something in this lane's diff that is not behind the three switches (reports.c's ring
      and gate, surface.c). Read the diff, then bisect it on the device.

    2 x (450 + 90) s = 18 Nova min. Queued with `scratch/queue_screen.sh TSM TSB`.

Judge: `docs/lanes/defaulton1017/screenread.py` (written before the first verdict) with halo1016's `vcpuread`
and `earlyread` readers for Halo, fps1015's `s2tread.py` and `tsread.py` for MKSM and Top Spin.

Re-scan for a new default-on candidate (open lanes' PR.md and NOTES.md) before the last row: at 04:45 there was
none.

## Questions

None yet.
