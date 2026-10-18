# perflog1016 notes (#433; motivating defect #998)

The owner asked, 10-16: "Can I get a toggle in the pause menu for turning that
on and off?" and "If I encounter a defect like the flicker in ESPN Baseball,
I'd like to be able to capture that without having to restart my run."

## Where this stands (2026-10-18, attempt 3)

- Done on this branch:
  - the run-time switch in `debug.h`;
  - the TCG `[tcg787]` hooks under it (`cputlb.c`, `translate-all.c`);
  - the pause-menu buttons (`PauseMenuOverlay.kt`): Perflog OFF/ON, Mark this
    moment, Frame dump;
  - **the three granted files**, `pgraph/profile.c`, `vk/renderer.c` and
    `pfifo.c`. lane.local put them on this row 10-16 09:49 PDT. This lane's own
    patches were applied at ce91b11b74, after a merge of origin/master
    7e00c7cf73. With them, the switch can turn on: profile.c compiles
    set/poll, renderer.c polls, and pfifo.c's puller/pusher timers follow the
    switch;
  - the host selftest. `selftest.py` gives SELFTEST OK:
    - 16+4+2 passes;
    - header mutants 11/11;
    - 9 Kotlin cross-file checks, KT mutants 14/14;
    - 6 wiring checks on the three granted files, WIRE mutants 11/11;
    - 10 reader fixtures for `abread.py`;
  - the NDK compile check on the merged tree: 0 new errors.
- **Dropped:** `vk/surface.c` (OUTBOX NEED 4). lane.gta3instr1018 holds it, so
  under the switch the `xemu-surf` line's own timers print 0.
  `surface.c.patch` stays in this directory for whoever holds the file next.
- **Not needed:** the `MainActivity.kt`/`strings.xml` JNI wiring. The switch is a
  marker file in the app's external files dir, the same dir as
  `frame_dump.on`, written by `PauseMenuOverlay.kt` (mine). The labels are
  literal strings.
- **P1, the default-path A/B before the patches (10-16): CLEARED.** It covers
  debug.h and TCG only. The tables are in "The default-path A/B" below.
- **P2, after the patches:** registered at b1ca4da762 before anything was
  queued, then queued 10-18. It is the ON proof plus the default-path A/B on the
  full PR. Every run waits behind the owner's Nova hold (lane.local, owner play,
  from 16:40Z). The ids are in "P2" below.

`[lane.perflog1016] waiting:` (10-18) for the six P2 requests on the Nova:
`1-1792344816-perflog1016-1365941` (ON), `1-1792344821-perflog1016-1366376`
(A1), `1-1792344826-perflog1016-1366882` (B1), `1-1792344832-perflog1016-1368963`
(A2), `1-1792344837-perflog1016-1369630` (B2), `1-1792344843-perflog1016-1370194`
(A3). They resolve when every one has a result dir with `result.json`. Then run
abread.py `--judge perflog1016-postlend.json --on <ON dir>` and write the
verdict here and in PR.md.

PR.md is `State: ready`: the code, inventory and goal-4 statement are done. The
device proof is listed as pending, as the brief allows while the owner hold
persists.

## Why attempt 2 did not finish

Attempt 2 ended correctly, with a `waiting:` on its four A/B requests and on
"the lend". Both resolved within hours, and nobody acted on either for 48 h:

- The A/B finished 10-16. Read now, it is CLEARED (below).
- The lend was granted at 10-16 09:49 PDT, but not the way attempt 2 was
  watching for. lane.local put `profile.c`, `renderer.c` and `pfifo.c` on this
  lane's own territory row; it did not land the patches in fps1015 or
  x1port1012. `lend_check.py` checked only whether those lanes' branches
  carried the patches, so it kept reporting "not landed". The board checkout
  that would have shown the grant was 116 commits stale.
- The 10-16 resume brief repeated the stale reading ("none of your 4 OUTBOX
  patches have been lent/landed yet"). So that session wrote WAITING on lane.local,
  and nothing woke the lane until the 10-18 territory audit.

For the next lane: a lend can arrive as a territory grant to your own row.
Check `origin/board:territory.toml` for your row's `files`, not only the
holder's branch.

## Why attempt 1 did not finish

Attempt 1's session log (`logs/lane/perflog1016.20261016T140238Z.json`) ends
with `"terminal_reason":"max_turns"`, `"num_turns":301`,
`"subtype":"error_max_turns"`: it ran into the 300-turn cap. It had committed
the code and the patches (last commit e40443c754, 07:41 PDT) and was choosing
the A/B scene (`scan_soaks.py` written 07:44, never committed) when the cap cut
it off at 07:45:53. It had never written NOTES.md, a WAITING file, or a
`waiting:` line, so nothing told the board it was waiting on the lend. Spending
turns on design and verification before writing the notes left nothing behind
when the cap came. Attempt 2 wrote NOTES.md and WAITING before queueing device
work.

## Design

| piece | where | what |
|---|---|---|
| flag | `debug.h` `NV2AStats.perflog_rt` | an `int`, `aligned(64)`, alone on its cache line: the PFIFO and render threads write the accumulators beside it |
| read | `debug.h` `nv2a_perflog_on()` | `__atomic_load_n(..., RELAXED) != 0` under `__builtin_expect(.., 0)`; constant `true` in a perflog build |
| timers | `debug.h` `NV2A_PHASE_TIMER_*` (non-perflog branch) | BEGIN stores `t0 = on ? clock : 0`; END tests `t0`, not the flag, so a phase the flip lands in books all of itself or nothing. Off: one load + one not-taken branch at BEGIN, one not-taken branch at END, no clock read |
| counters | `debug.h` `nv2a_profile_inc_counter()` | increments only while on |
| set | `debug.h` `nv2a_perflog_set()` (under `NV2A_PERFLOG_RT_IMPLEMENTATION`, defined at `profile.c:22`) | `__atomic_exchange_n`; logs only on a change: `[perflog] runtime tier ON (frame N, by marker)` on hakuX-perf (`by env` when pinned) |
| poll | `nv2a_perflog_poll(dir)`, called once, from `vk/renderer.c:2465` in `fdump_poll_marker()` | at the flip, at most once a second (the frame dump's own rate limit), after that limit and before the dump's early returns, `access(dir/perflog.on)`. `XEMU_PERFLOG_RT=1` read once at the first poll, pins on for the run; a request sets it with `--env` (the env_vars pref, `setenv` in xemu_android.cpp, logged `env: K=V`). A perflog build says once `[perflog] perflog build: every phase is timed at all times; the run-time switch is inert` |
| UI | `PauseMenuOverlay.kt` `rebuildDebugSection()` | `Perflog: OFF` / `Perflog: ON` / `Perflog: ON (perflog build)` / `Perflog: ON (XEMU_PERFLOG_RT)`; press toggles the marker and logs `[perflog] pause menu: ON requested` |
| launch reset | `PauseMenuOverlay.kt` init | deletes a stale `perflog.on`, logs `[perflog] pause menu: cleared the last run's marker; OFF at launch` |
| mark | `PauseMenuOverlay.kt` `createMarkButton()` | `Log.i("hakuX-route", "mark owner-N")`, the route driver's `log -t hakuX-route "mark <label>"` shape, numbered so it never collides with `gameplay`/`play` |
| frame dump | `PauseMenuOverlay.kt` `createFrameDumpButton()` | writes `30` to `frame_dump.on` (the existing marker) and dismisses the menu |

The tag is hakuX-perf, not a new hakuX-perflog tag. The dispatcher's
LOGCAT_SPEC is a tag list, so a new tag would be dropped from every queued run.

### What an ON-path hit looks like (said before any read)

On a plain debug build at this head, with the marker dropped (or the button
pressed and the menu resumed), these appear in order:

1. `hakuX-perf: [perflog] pause menu: ON requested` (button path only).
2. Within about 1 s of resume: `hakuX-perf: [perflog] runtime tier ON (frame N, by marker)`, exactly once.
3. From the next 60-frame boundary, every 60 frames, the block at `profile.c:948`
   prints under the switch: `hakuX-phase` (`Surf: Tex: TxH: Shd: Draw: Sfp:
   Mfp: FTx: ... Fin:(Sub: Fen:) Flip: Idle:(Fr: St:)`, the perflog build's
   shape), `hakuX-cpu`, `xemu-vsync`, `xemu-surf`, `xemu-pace`, `xemu-work` and
   `xemu-gpu`. A plain build prints none of them. The only caller of
   `nv2a_profile_get_phase_timing_str()` is that block, so making its
   TxH/Sfp/Mfp/FTx fields unconditional changes no line a plain build prints.
   - Under the switch, `xemu-surf`'s own timers print 0, because the surface.c
     hunk was dropped.
   - `xemu-pace` shows min/max/Df already reset. The always-on hakuX-perf line
     (`profile.c:821-826`) reads the pacing string first, and that read resets
     them. A perflog build behaves the same way, and the always-on line is
     unaffected.
4. `[tcg787] w=...` lines once a window (`cputlb.c`), which a plain build never
   prints.

Pressing OFF gives `runtime tier OFF (frame M, by marker)` once; the phase lines
and `[tcg787]` stop at the next window. A marker with no `runtime tier` line is
a failed switch, not an idle one.

## Inventory (goal 1)

Line numbers: files this lane edits, at this branch's head (ce91b11b74 for the
three granted files). Files it does not edit, at origin/master 4bf47129b1; the
class C rows are unchanged by the merge of 7e00c7cf73 in what they record,
though their line numbers may have moved. Classes:

- **A**: switchable with a negligible-cost check (a relaxed flag read).
- **B**: switchable only with the check hoisted out of a hot loop, or at a
  frame boundary.
- **C**: needs a rebuild. Either the check would slow the default path, or the
  gated code changes struct layout or allocates per-build resources.

### Class A through `debug.h`, no edit at the call site

| site | what it records | class | why |
|---|---|---|---|
| `debug.h` `NV2A_PHASE_TIMER_BEGIN/END`, `_EXCL`, `_EXCL_CHILD` (lane head 620-657) | every frame-phase timer: surface update, texture upload, shader compile, draw dispatch and its sub-phases (vtx attr/sync, prim rw, Sfp, Mfp, FTx, TxH, ...), finish, flip idle | A | off: one relaxed load of an L1-resident line and a not-taken branch per BEGIN, a not-taken branch on a local per END, no clock read |
| `debug.h` `nv2a_profile_inc_counter()` (605) | the per-frame `NV2A_PROF_*` counters | A | same flag read; the increment only when on |
| `debug.h` `FramePhaseTimingWork/Stats` `draw_sfp/mfp/ftx`, `tex_hash` (master 261-269, 310-315 `#if NV2A_PERF_LOG`) | the four Sfp/Mfp/FTx/TxH accumulators | A (layout made unconditional) | 32+16 bytes in `g_nv2a_stats`, not in any per-draw struct; needed so the switch has somewhere to book |
| call sites of the macros | `vk/draw.c` ~101, `vk/surface.c` 14, `vk/texture.c` 10, `vk/vertex.c` 4, `vk/shaders.c` 3, `gl/*` 19, `pfifo.c` 2 (flip idle), `pgraph.c` 1, `vk/command.c` 1, `vk/display.c` 1 | A | the macro carries the check; no file edit, so held files (draw.c, texture.c, pgraph.c) are covered without a lend |

### Class A/B in the three granted files (applied at ce91b11b74; the patches stay in this dir)

| site (lane head) | what it records | class | why | patch |
|---|---|---|---|---|
| `pgraph/profile.c:22` | defines `NV2A_PERFLOG_RT_IMPLEMENTATION` before the first include: the set/poll bodies compile here | - | **required**: without it nothing can turn the switch on | profile.c.patch |
| `pgraph/profile.c:106` | SMOOTH of the four Sfp/Mfp/FTx/TxH fields into the stats | A | once per frame | profile.c.patch |
| `pgraph/profile.c:948` | the frame-phase print block (every 60 frames) | B (frame boundary) | `#if defined(__ANDROID__)` + `if (nv2a_perflog_on() && frame % 60 == 0)`: one check per frame. `pgraph_method_histogram_log_and_reset()` there is a plain stub (`pgraph.c:293`) outside a perflog build | profile.c.patch |
| `pgraph/profile.c:1044` | the `PHASE_TXH/FAST` fields of the phase-line format | A | format made unconditional; prints only under the check above | profile.c.patch |
| `vk/renderer.c:2465` in `fdump_poll_marker()` | the poll | B (frame boundary) | **required**: the one call to `nv2a_perflog_poll()`, at the flip, inside the frame dump's existing once-a-second limit | renderer.c.patch |
| `pfifo.c:1959` in `pfifo_run_puller()` | puller time, per-method time, lock-wait time | A | `const bool pl = nv2a_perflog_on();` once per call. **Corrected 10-18:** the pusher's word loop calls `pfifo_run_puller()` once per method command (`pfifo.c:2258`), so this is one relaxed load per method command, not "never inside the method loop". It sits beside the four atomics `pfifo_puller_should_stall()` reads on the same call, so it is class A by the same argument as `debug.h`'s sites. Every clock read in the function is behind `pl` | pfifo.c.patch |
| `pfifo.c:2422`, `2532` | pusher post-flip and push time; the idle split | B (hoisted) | flag read once per pusher pass; the idle split is gated on it | pfifo.c.patch |

`vk/surface.c` (`SURF_TIMER` at 44, the download flush/read timers at
2116/2145/2158) was in `surface.c.patch` as class A. **Dropped 10-18:**
lane.gta3instr1018 holds the file. Those timers stay perflog-build only (class C
for this PR), and under the switch the `xemu-surf` line prints 0 for them. The
patch is still in this directory.

### TCG, class A (lane files, committed)

| site (lane head) | what it records | class | why |
|---|---|---|---|
| `cputlb.c:198-208` | the `[tcg787]` counters; `HAKUX_TCG787` now follows `XBOX`, not `NV2A_PERF_LOG` | - | the counters exist in every Xbox build so the switch can fill them |
| `cputlb.c:844/877` | full-flush time (`ff`) | A | `t787 = nv2a_perflog_on() ? get_clock() : 0`; book only if `t787` |
| `cputlb.c:1025/1051` | page-flush time (`pf`) | A | same |
| `cputlb.c:1972-1990` `tlb_fill_align` | TLB fills and refills (`tf`, `tfr`, `tf_ns`) | A | off: returns the body directly after one flag read |
| `cputlb.c:378-417`, `525` | the `[tcg787]` line, once a window | B (window boundary) | printed only when on at both ends of the window (`p_on`), so a half-on window never prints |
| `translate-all.c:483-506` `tb_gen_code` | code-gen count/time/max (`gc`, `cg`, `max`) | A | `if (!nv2a_perflog_on()) return tb_gen_code_body(...)` |

### Class C: needs a rebuilt build (`-Pperflog=true`)

| site (origin/master) | what it records | why C |
|---|---|---|
| `vk/draw.c:41, 3903, 7682, 7951, 9232`; `vk/shaders.c:590, 929` | `ubosz`: UBO bytes uploaded vs changed per draw | a `memcmp`/`memcpy` of the UBO on every upload, ~1.2 ms/frame of the measured perflog cost; a flag read would not remove the shadow copy it needs |
| `vk/draw.c:942` | `opt_stats` prints | `OPT_STAT_INC` is compiled out in `vk/renderer.h:232`; switching it means a branch on every optimisation-path counter |
| `vk/draw.c:1377, 1432, 1466, 5916` | pipeline eviction tracking | needs `vk/renderer.h:299/1289` fields: struct layout |
| `vk/draw.c:4779`; `vk/renderer.c:273` | `xfr` GPU timestamps | the query pool is created only in a perflog build (`renderer.c:273`); plus `HAKUX_GPUXFR_CTRL` |
| `vk/renderer.h:58, 199, 949` | enums and struct fields for the above | layout |
| `vk/texture.c:45, 70, 318, 1502, 2745, 2850, 3110, 3205` | `TEX_PERF`, `txw`, #461/#474 bind-step attribution | per-bind clock reads inside the bind loop and per-texture fields |
| `pgraph.c:243-294, 2431` | the per-method histogram | a table indexed per method in the method loop |
| `pgraph.c:901, 907` | `LOCK474` lock attribution | per-acquisition bookkeeping on the lock path |
| `vk/surface.c:44, 2116, 2145, 2158` | `SURF_TIMER` per-surface-op timers (`xemu-surf`), download flush/read timers | class A by design (`surface.c.patch`); C in this PR only because the file is lane.gta3instr1018's |
| `vk/surface.c:797, 982-1101` | `sdrange`/`rfin` download-range attribution | per-download fields and loops |
| `vk/surface.c:1869, 1940, 2042, 3240, 5860` | `sdcall`/`upw`/`surf413` per-call attribution | per-call records; 2042's `t0` stays compile-time because its consumer is C |
| `pfifo.c:785` | `CBL`: the callback-latency split, kick to dispatch, by category (parked, per method class, `dl`, `fin`) | a clock read per method dispatch and per park, plus per-category bookkeeping under pfifo.lock |
| `accel/tcg/cpu-exec.c:1414-1572, 2375-2388` | `[tpc787]`: TB time by guest pc | a hash-table book on every TB exit, on the execution path; a flag read there is the cost the brief forbids (and the file is pmucounters') |

## What the switch gives, per defect class (goal 4)

This lane builds an instrument. It does not diagnose, and nothing here names a
cause for #998's flicker or any other defect.

| defect class | what the run-time switch gives (no rebuild) | what it does not give, and what does |
|---|---|---|
| flicker, a wrong frame, a missing or wrong draw (#998) | **when**: a `mark owner-N` on the logcat clock at the moment, plus the frame-phase breakdown around it (did a phase spike on that frame?). The Frame dump button records the per-draw state of the next 30 frames without a rebuild (the existing live frame dump) | **why**, frame-exact: which draw wrote which pixels, draw-by-draw pipeline/texture/surface state, at the exact flickering frame. Those are records, not counters, and cannot be bought with a flag read in the hot path. The frame dump is the nearest no-rebuild tool, but it starts ~1 s after resume, not on the flicker frame. Per-draw surface reads need the diag capture (per-draw `pgraph_vk_finish`) |
| a hitch, stall or slow scene | which phase took the time (surface/texture/shader/draw/finish/flip idle, Sfp/Mfp/FTx/TxH), per 60-frame window, from the press on; vCPU TLB flush/fill and code-gen time (`[tcg787]`) | per-draw/per-bind/per-upload attribution (`ubosz`, `TEX_PERF`, `txw`, `sdrange`, `sdcall`), pipeline eviction, GPU timestamps (`xfr`), per-method histogram, guest-pc time (`[tpc787]`): **a `-Pperflog=true` build** |
| a lock or wait (pfifo/vCPU contention) | puller/pusher time and lock-wait time per frame (pfifo.c; the `hakuX-cpu` line) | per-acquisition lock attribution (`LOCK474`), the callback-latency split (`CBL`): a perflog build |
| a surface-op cost (`xemu-surf`) | nothing: its timers print 0 under the switch (surface.c dropped) | a perflog build, or `surface.c.patch` applied by the file's next holder |
| a crash or hang | nothing new. A crash leaves no tombstone; the last `mark owner-N` before it dates it | a debugger |
| audio, pacing | nothing new; the always-on tier (hakuX-audio, hakuX-pace) already covers them | - |

So the owner's case: on a flicker, press **Mark this moment**, then **Perflog**
ON (or **Frame dump** for the next 30 frames), resume. The marks, phase lines
and dump land in the same logcat as the telemetry. Finding which draw flickered
and why still takes a perflog build or a diag capture replayed at that scene.

**Whether a capture keeps it.** What reaches a file depends on the recorder's
logcat filter, not on the switch. The ON block prints on seven tags: hakuX-phase,
hakuX-cpu, xemu-vsync, xemu-surf, xemu-pace, xemu-work and xemu-gpu.

| recorder | keeps | drops |
|---|---|---|
| dispatcher.sh:2516 (queued soaks) | flip line (hakuX-perf), marks (hakuX-route), `[tcg787]` (hakuX:W), hakuX-phase, hakuX-cpu, xemu-surf, xemu-work, xemu-gpu | xemu-vsync, xemu-pace |
| lane.local's `ownerplay.py` (owner sessions; `LOGCAT_SPEC` line 35, read 10-16) | flip line, marks, `[tcg787]` | **all seven ON-block tags** |
| the 10-12 unit `hakux-ownerplay-perf` (its log has only hakuX-perf/pace/stderr/unhandled/build) | flip line | marks and all seven |

So in an owner session today, the button's flip line, the marks and `[tcg787]`
are kept, but the phase breakdown is cut. That is a NEED in OUTBOX.md for
lane.local: seven tags added to `ownerplay.py`'s filter. They print nothing while
the switch is OFF.

## The default-path A/B (goal 2's proof)

Two predictions: P1 (10-16, before the patches; read, CLEARED) and P2 (10-18,
after them, with the ON leg; queued). P1's text is kept as it was registered.

### P1 (10-16)

**What P1 measured.** The 10-16 lane head carried every debug.h-gated site
(~155) and the TCG sites with the switch OFF. It could not be turned on, because
the poll was in the renderer.c patch. So A = origin/master against B = lane head
measured the OFF cost of everything except the four patches' hunks:

- pfifo.c: one flag read per puller call and per pusher pass;
- surface.c: macro-equivalent timers;
- profile.c: one check per frame;
- renderer.c: one `access()` a second.

Those are the smallest part of the risk; the ~101 draw.c sites are already in B.
After the lend lands, the same pair re-runs with B = the holder's tip carrying
the patches, and that run is also the ON leg.

**Scene.** GTA: Vice City, `gta-vc` route (state: any). Pathfound 10-11; proven
on the Nova 10-13 by x1port1012 (0-1791876042, `mark gameplay` at 115 s after
soak start, 411 gfps/[rdc] lines). An open-world on-foot scene with a moving
player (the route runs, sprints, steers and turns the camera), render-thread
busy, not a menu. Window: `mark gameplay` +20 s to +180 s; `--seconds 330`
(the mark lands ~115 s in, plus margin for the A-press trains).
Four single runs queued A, B, B, A (ABBA cancels a linear thermal drift);
4 x (330 + 90) s = 28 min, inside the 30-min pilot budget. On the 10-13 run
(0-1791876042) the reader gives tcpu 259.6 ms/s, gfps 29, Ri 23.5 ms over
80 `[rdc]` lines. GTA VC there is capped near 30 with renderer idle to spare,
so, as with Castlevania, the cost reads in headroom (tcpu, Ri), not fps.

**Prediction (P1, registered before the runs:
`docs/testing/predictions/perflog1016-defaultpath.json`).**

- Readers, present in both builds: `[rdc] tcpu` render-thread CPU ms/s
  (CLOCK_THREAD_CPUTIME_ID), and hakuX-perf `gfps` and `Ri`.
- Per run: the median over the window. Per arm: the mean of its two runs. Band:
  the larger of the within-arm spread (|A1-A2|, |B1-B2|) and alwaystelemetry's
  plain-vs-plain figure (14 ms/s tcpu, 0.2 ms Ri).
- Point estimate: B-A tcpu between 0 and +3 ms/s. The arithmetic: ~10 timed
  phases per draw, ~1000 draws a frame at 30 fps, ~1 ns per load+branch, so
  ~0.3-0.6 ms/s. A perflog build's full ON cost is +74 ms/s, and OFF skips
  every clock read.
- **SLOWDOWN (fail)**: B-A tcpu > +15 ms/s and outside the band (6% of
  alwaystelemetry's 248), or Ri lower by more than 0.3 ms/flip and outside
  the band, or gfps median lower by 1 or more in both B runs against both A
  runs.
- **CLEARED (pass)**: tcpu |B-A| <= max(15 ms/s, band), Ri |B-A| <= max(0.3,
  band), and no gfps drop as above. A pass bounds the cost below the
  instrument's floor; it does not show zero.
- **VOID**: any run without `mark gameplay`, or with fewer than 60 `[rdc]`
  lines in the window. `[rdc]` prints about once every 2 s, so a full window
  has ~80. Also void: any B run with a `[perflog] runtime tier ON`
  line (it must be OFF), or with a `[tcg787]` line.

Reader: `abread.py` in this directory, which states the band it used.

Requests (A = 4bf47129b1 origin/master, B = 644877144a lane head; emulator code
identical to the commits after it, which are docs only).

**Queue record** (10-16; requester `perflog1016`, priority arm, release tier 0.5,
pinned to the Nova, `--title 5454000F-Grand_Theft_Auto_Vice_City.xiso.iso
--route gta-vc --seconds 330`, `--expect` the prediction):

| order | arm | ref | request id |
|---|---|---|---|
| 1 | A1 | 4bf47129b1 | `1-1792169523-perflog1016-2120339` |
| 2 | B1 | 644877144a | `1-1792169529-perflog1016-2121153` |
| 3 | B2 | 644877144a | `1-1792169535-perflog1016-2121769` |
| 4 | A2 | 4bf47129b1 | `1-1792169541-perflog1016-2122978` |

Read with `python3 docs/lanes/perflog1016/abread.py --a <A1 dir> --a <A2 dir>
--b <B1 dir> --b <B2 dir> --judge docs/testing/predictions/perflog1016-defaultpath.json`.

**A confound in the design.** I found it after queuing, and wrote this before
any B result existed (10-16 10:2x PDT; only A1 had finished).

- The dispatcher clears the shader cache when the APK changes and keeps it on a
  same-APK run (dispatcher.sh:569-586).
- So in A B B A, B2 is the only run that starts warm. A1's result.json says
  `cleared`.
- A warm cache lowers B's mean. Because B2 also widens the band, both effects
  push the read toward CLEARED. That is the wrong direction for a "does not
  slow" claim.
- A1 shows no in-window warm-up. The tcpu medians in 20 s bins run 248-343
  ms/s with no early-high decay, and no frame is over 81 ms. The 1470 ms stall is
  before the mark. But a cache could lower steady-state work too, as GTA VC
  streams the world.
- The 10-13 run (warm, x1port1012 build) read 259.6 against A1's 312.1 (cold,
  master). Two variables changed, so that gap is not attributable to the cache.

Reading rule:

1. abread.py now prints each run's cache state. When both arms have a cold run,
   it also prints B-A over the cold runs only (A1, A2 against B1).
2. B1 (cold) against B2 (warm) is the same build, so |B1-B2| is the cache effect
   plus run noise.
   - If it is within the prior 14 ms/s, the registered verdict stands as read.
   - If B2 is lower by more than that, report the registered verdict alongside
     the cold-only B-A, and claim no cost bound until a warm A exists. A warm A
     means two A runs back to back, the second one warm.
3. A third A was not queued now. The queue serves ids in ASCII order, so it would
   sort behind five audio1016 Nova runs on another APK and start cold. Two back
   to back would pass the 30-min pilot gate only after B1 finishes.

No B result yet; nothing but A1 has been read (the reader's self-check).

**P1 result (all four done 10-16, read 10-18): CLEARED.** Reproduce with
`python3 docs/lanes/perflog1016/abread.py --judge
docs/testing/predictions/perflog1016-defaultpath.json --a <A1> --a <A2> --b <B1>
--b <B2>`. The dirs are under `$DISPATCH_DIR/results/`.

| arm | run | n_rdc | tcpu (ms/s) | gfps | Ri (ms) | cache |
|---|---|---|---|---|---|---|
| A1 | `1-1792169523-perflog1016-2120339` | 79 | 312.1 | 29 | 23.80 | cleared |
| A2 | `1-1792169541-perflog1016-2122978` | 80 | 283.3 | 29 | 23.50 | cleared |
| B1 | `1-1792169529-perflog1016-2121153` | 80 | 318.6 | 29 | 22.15 | cleared |
| B2 | `1-1792169535-perflog1016-2121769` | 80 | 262.7 | 29 | 23.80 | kept (warm) |

| reader | A mean | B mean | B-A | band | SE of B-A |
|---|---|---|---|---|---|
| tcpu (ms/s) | 297.70 | 290.64 | -7.05 | 55.98 | 31.49 |
| gfps | 29.00 | 29.00 | +0.00 | 0.00 | - |
| Ri (ms) | 23.65 | 22.98 | -0.67 | 1.65 | 0.84 |

- **Cold runs only** (A1, A2 against B1): B-A tcpu +20.94 ms/s, gfps 0, Ri
  -1.50 ms.
- **The reading rule.** B1-B2, the same build cold against warm, is 55.9 ms/s,
  more than the prior 14. So, per rule 2: the registered verdict, CLEARED,
  stands as read, and **no tight cost bound is claimed**. The cold-only
  figure, +20.9 ms/s, is one B run against two A runs.
- **The noise.** A1-A2, the same build cold both times, is 28.8 ms/s. That is
  about the size of the cold-only B-A, so this scene's run-to-run noise is
  around 30 ms/s of tcpu. P1 can see a slowdown of the size a perflog build
  costs (+74 ms/s). It cannot see the 0-3 ms/s point estimate.
- **No B run printed any ON-path line.** All four logs have zero hakuX-phase,
  hakuX-cpu, `[tcg787]` and runtime-tier lines. So B was OFF, and the "B must be
  OFF" rule has a clean baseline.
- B2 was warm, exactly as the confound note predicted. That is why P2
  alternates the arms.

### P2 (10-18): the full PR, plus the ON leg

`docs/testing/predictions/perflog1016-postlend.json` (sha256 `2c3c4179...4bed`),
written by `write_prediction_p2.py`. It was committed and pushed at b1ca4da762
before any request was queued.

- **A** = origin/master 7e00c7cf73.
- **B** = ce91b11b74: A merged, plus every emulator hunk of the PR (debug.h,
  TCG, pfifo.c, profile.c, renderer.c). Nothing else is in the diff, and
  surface.c is not in it.
- **ON** = B with `--env XEMU_PERFLOG_RT=1`.
- **Order: ON A1 B1 A2 B2 A3.**
  - Each run's APK differs from the one before it, and the dispatcher clears
    the shader cache on every APK change (dispatcher.sh:630-667), so every
    run starts cold.
  - A comes last, so no env of ours is left in the Nova's env_vars pref. The
    dispatcher clears it lazily, on the next request; A1 does that for the ON
    run's env.
- 6 x (330 + 90) s = 42 min, over the 30-min pilot budget. The pilot record
  is `pilots/perflog1016.ok`, citing P1's four runs.
- **Rules.**
  - The P1 thresholds stand: SLOWDOWN if B-A tcpu > +15 ms/s and outside the
    band, if Ri < -0.3 ms and outside the band, or if every B run's gfps is
    1 or more below every A run's.
  - Added `M1/cold_runs_only`: a warm run is listed and left out, and an arm
    with fewer than 2 cold runs is VOID.
  - A B run with a hakuX-phase line is VOID.
  - The band will likely be near 30 ms/s (P1's same-build spread). So a
    CLEARED here bounds the OFF cost under about that, not under the point
    estimate.
- **The ON leg, M2.** It is a HIT/MISS of its own, separate from the A/B
  verdict:
  - exactly one `runtime tier ON (frame N, by env)` line, and no other tier
    line;
  - from that line on, at least 50 hakuX-phase lines carrying
    TxH/Sfp/Mfp/FTx, with median Draw ≥ 0.1 ms;
  - hakuX-cpu medians Pull and Push ≥ 0.1 ms;
  - at least 20 `[tcg787]` lines.
  - The ON run's tcpu/gfps/Ri against the B mean are printed as the ON cost,
    one run, not judged. Expected: +5 to +60 ms/s.
- **Reader:** `abread.py --judge docs/testing/predictions/perflog1016-postlend.json
  --a <A1> --a <A2> --a <A3> --b <B1> --b <B2> --on <ON>`. Exit codes: 0
  CLEARED (and ON HIT), 1 SLOWDOWN, 2 VOID, 3 ON MISS.

**Queue record** (10-18; requester `perflog1016`, priority arm, release tier
0.5, pinned to the Nova, `--title 5454000F-Grand_Theft_Auto_Vice_City.xiso.iso
--route gta-vc --seconds 330`, `--expect` the P2 file). All six wait behind the
owner's Nova hold.

| order | arm | ref | env | request id |
|---|---|---|---|---|
| 1 | ON | ce91b11b74 | `XEMU_PERFLOG_RT=1` | `1-1792344816-perflog1016-1365941` |
| 2 | A1 | 7e00c7cf73 | - | `1-1792344821-perflog1016-1366376` |
| 3 | B1 | ce91b11b74 | - | `1-1792344826-perflog1016-1366882` |
| 4 | A2 | 7e00c7cf73 | - | `1-1792344832-perflog1016-1368963` |
| 5 | B2 | ce91b11b74 | - | `1-1792344837-perflog1016-1369630` |
| 6 | A3 | 7e00c7cf73 | - | `1-1792344843-perflog1016-1370194` |

**Not yet shown on a device:** that the pause-menu button turns the switch on
(`by marker`). The ON run proves the native path through the env pin: the same
`nv2a_perflog_set()`, the same timers and prints. The marker branch of
`nv2a_perflog_poll()` is covered by the host selftest's marker mode, which uses
the real `debug.h`. The Kotlin side (createNewFile/delete on press) needs a
person pressing the button on a device. That is the first thing to check in an
owner session after this folds: press Perflog, resume, and look for one
`runtime tier ON (frame N, by marker)`.

## Next lane: do not repeat

- `nv2a_clock_ns()` is the counter since boot, so a taken `t0` is never 0.
  END testing `t0` is therefore exact; do not add a second flag read at END.
- Do not put the poll anywhere but a frame boundary. `access()` is a syscall;
  the frame dump's once-a-second limit is the right home.
- A new logcat tag for the flip line would be dropped by the dispatcher's
  LOGCAT_SPEC. Keep it on hakuX-perf.
- The Kotlin label reads the marker file. It does not ask native, so a failed
  native poll would show ON in the menu with no `runtime tier ON` line in
  logcat. The logcat line is the truth.
- Do not wait for a lend by checking only the holder's branch. A grant can
  arrive as files on your own territory row (`origin/board:territory.toml`),
  and that is how this one came. See "Why attempt 2 did not finish".
- Do not order a same-build pair back to back on one device. The dispatcher
  keeps the shader cache on a same-APK run, so the second run starts warm. P1's
  B2 did, and was 56 ms/s under B1. Alternate the arms.
- On GTA VC (gta-vc, Nova), same-build cold runs differ by ~30 ms/s tcpu. A
  default-path cost below that needs many more runs, or a lower-noise reader,
  not a re-run of the same pair.
- `pfifo_run_puller()` runs once per method command, not once per batch. Any
  flag read placed there is per method; it is cheap (one relaxed load beside
  four atomics), but do not describe it as hoisted out of the method loop.

## Questions (for lane.local; none blocks the offline work)

1. ~~Lend~~: answered 10-18 by the hostops addendum. `profile.c`, `vk/renderer.c`
   and `pfifo.c` were granted to this row on 10-16 and applied at ce91b11b74.
   `vk/surface.c` was dropped, because lane.gta3instr1018 holds it.
2. Owner-play capture: can `ownerplay.py`'s `LOGCAT_SPEC` gain
   `hakuX-phase:I hakuX-cpu:I xemu-vsync:I xemu-surf:I xemu-pace:I xemu-work:I
   xemu-gpu:I`? Without them an owner session records that the button was
   pressed, but not what it turned on. The table is in "Whether a capture keeps
   it" above, and the NEED is in OUTBOX.md. Still open, and lane.local's call
   on its own file; it does not block this PR.
