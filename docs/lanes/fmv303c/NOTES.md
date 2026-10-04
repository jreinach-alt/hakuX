# lane.fmv303c -- #303 Spikeout FMV green: the surface write-back probe

Continues lane.fmv303b (docs/lanes/fmv303b/NOTES.md s4, s5). What is settled
there is not re-measured here: the green (Cr=0) is already in the CPU-written
A8R8G8B8 guest buffers at 0x307d000 / 0x3163000; display, upload, PVIDEO and
Tier1 are exonerated.

## Why attempt 1 did not finish

It was stopped by hostops at about 13:4x PDT on 2026-09-26 under the 0.5
release policy (#433: the device is pointed at 0.5 issues, and #303 is not
one). The probe commit was pushed and CI went green on it; the PR was
labelled `blocked:after-0.5`. The judge (`wb_judge.py`) was written and
tested against fixtures but not committed, and no prediction was registered,
so nothing was queued. Attempt 2 (handback resume) found 0.5 still open,
merged master, committed the judge and these notes, and did not register the
arm: committing a prediction queues it on the device, which the park forbids.
Attempt 2 did finish, as blocked (PR comment `[lane.fmv303c] blocked:`); the
handback job resumed it on the quiet clock at 23:55Z. Attempt 3 found #433
still open and the `blocked:after-0.5` label still on #439; master (110
commits ahead, #396 folded) merges clean against this branch, so the merge is
left to the arm step, where it has to precede registration anyway.

Attempt 3 did not finish for the same reason: it ended parked, by policy,
with nothing registered. Nothing failed. On 2026-10-04 the owner lifted the
park (brief addendum 3): the green is on a Playable title's pre-game screens
(Spikeout) and also on Star Wars III (#719). Attempt 4 merged origin/master
(1964 commits; one conflict in `pgraph_vk_prerecord_display_download`, where
master removed the early `display_predownload_pending` return; resolved by
keeping the `wbc` counter call first and master's body unchanged:
cf328d86f7). Master's new deferred-download batch completes through
`pgraph_vk_complete_staged_downloads()`, which the probe already covers. No
other copy into VRAM exists in `vk/`. Attempt 4 re-ran the judge's fixtures
(same four verdicts), registered
`docs/testing/predictions/fmv303c-wb-probe.json` on cf328d86f7 (86f8cace9d),
and queued both Thor runs.

Attempt 4 did not finish because both Thor runs were refused before start.
A foreign overlay covered the Thor's display (below). The session ended
waiting on `time 2026-10-04T13:40` to re-queue. Brief addendum 4 then said
two things. First, the owner left the overlay there from their own
bottom-screen test, and the lane must not ask for it to be cleared. Second,
the green was seen on the **USA** disc. The Europe disc named in the first
registration was wrong.

Attempt 5 (13:45 PDT, 2026-10-04) re-registered the prediction before any
run, on the same ref cf328d86f7, with the USA disc. It also added one M0
rule to `wb_judge.py`. The probe logs every landing only inside
0x3000000..0x3400000, and the USA build may place the FMV buffers
elsewhere. That case would read as a false EXONERATED, so the judge now
VOIDs a run where more than 10% of lit tinted frames show a buffer outside
the region. In the fmv303b control, 1 of 3100 lit tinted frames does
(0x3628000). That is why the rule is not "any". New fixture `outside` (the
control with its buffers moved to 0x1xxxxxx) gives VOID; the other four
fixtures give the same verdicts as before. Then it queued both runs again.

Attempt 5 did not finish because the USA pair was refused by the same
display cover (rows below). It parked on `WAITING: owner`. At 14:4x PDT
lane.local cleared the cover. The cause was the SYSTEM key
`dual_screen_display_mode=2`; hostops had reset only the global key.
lane.local set the system key to 0. Attempt 6 (14:38 PDT) deleted WAITING
and queued the same two runs unchanged: ref cf328d86f7, prediction sha
6b933f61..., USA disc.

Attempt 6 did not finish because it got one valid replicate of the two that
the registration needs. The second run (L2, then L2b) was heat-stopped under
100 lit tinted frames, and the session parked on `WAITING: time
2026-10-04T15:45` so the Thor could cool (rows and Next below). Nothing
failed. Attempt 7 (15:47 PDT) found the Thor idle since 14:57. It queued L2c
unchanged (same ref e2b045168a, prediction sha 3ca87cf9...):
1791154079-lane.fmv303c-3735646.

## What the branch carries

1. `hw/xbox/nv2a/pgraph/vk/surface.c`, probe hunk only (b86f91641b), gated on
   `HAKUX_FMV303_PROBE=1`. It logs
   `[fmv303] wb addr= len= color= fmt= ft= n= in= path= surf= WxH` at the
   synchronous copy in `download_surface_to_buffer()` (`sync`, `sync-part`)
   and at each staged copy in `pgraph_vk_complete_staged_downloads()`
   (`staged`, `staged-part`); `ft` is `pg->frame_time`, the guest flip count.
   Every landing in 0x3000000..0x3400000 is logged; landings elsewhere up to a
   cap of 20000 lines. One `[fmv303] wbc ft= n= in=` line per flip stall
   (`pgraph_vk_prerecord_display_download`) carries cumulative counts, so a
   zero is an observed zero and a line logd dropped shows as a gap.
   Unset, the only code that runs is `fmv303_wb_on()`, which reads the env
   once. CI green on b86f91641b.
2. `wb_judge.py`: joins the `wb`/`wbc` lines to the fmv303b `tex0 tint` lines
   by flip count. Validity per run (else VOID): probe on, `wbc` present, last
   `wbc` n > 0, >= 100 lit tinted frames, no in-region `wb` line dropped.
   Verdict pooled over two valid runs: EXONERATED (no in-region landing),
   HIT (P(join | tinted) - P(join | clean) >= 0.5 for NEAR, a region landing
   within 2 flips, or SINCE, a landing on the displayed buffer since it was
   last shown), else UNORDERED.

   Fixture check (synthetic `wb` lines injected into the fmv303b soak logcat
   `0-0-y-1790433000-1790433159-fmv303b-2432336`, 3100 tinted / 274 clean
   lit frames):

   | fixture | in-region landings | NEAR t / c | SINCE t / c | verdict |
   |---|---|---|---|---|
   | none | 0 | 0.000 / 0.000 | 0.000 / 0.000 | EXONERATED |
   | onbuf (on shown buffer before tinted only) | 3100 | 1.000 / 0.978 | 1.000 / 0.000 | HIT |
   | otherbuf (on the other buffer) | 3100 | 1.000 / 0.978 | 0.839 / 0.555 | UNORDERED |
   | all (every frame) | 3498 | 1.000 / 1.000 | 1.000 / 1.000 | UNORDERED |

   NEAR alone cannot separate states here: clean frames come singly between
   tinted runs, so a 2-flip window nearly always reaches a tinted neighbour
   (0.978 on clean). SINCE is the join that discriminates.

## Per-run table

| run id | apk_sha | lit tinted | wbc n | in-region | verdict |
|---|---|---|---|---|---|
| 1791142591-lane.fmv303c-697274 (L1) | 3ecdda7c45e7 | - | - | - | VOID: refused, display-covered |
| 1791142595-lane.fmv303c-698913 (L2) | 3ecdda7c45e7 | - | - | - | VOID: refused, display-covered |
| 1791146938-lane.fmv303c-1371607 (L1, USA disc) | 3ecdda7c45e7 | - | - | - | VOID: refused, display-covered (13:49 PDT) |
| 1791146942-lane.fmv303c-1372235 (L2, USA disc) | 3ecdda7c45e7 | - | - | - | VOID: refused, display-covered (13:50 PDT) |
| 1791149862-lane.fmv303c-2094485 (L1, USA disc) | 3ecdda7c45e7 | - | - | - | VOID: guest never booted (setup wizard, games folder not set) |
| 1791149866-lane.fmv303c-2096647 (L2, USA disc) | 3ecdda7c45e7 | - | - | - | VOID: guest never booted (setup wizard, games folder not set) |

The cover was gone in both runs (`display-clear ... no foreign overlay`).
Both runs started, and the guest never appeared in 150 s. Each logcat has 3
lines (soak start, soak end). All 72 and 70 frames show hakuX's first-run
"Welcome to hakuX / Games Folder: Not set" page with Android's "Use USB for"
dialog on top. The cause is the libfolders fold (#433, 10f14d301d).
`GamesFolders.read()` migrates the pref `gamesFolderUri` into
`gamesFolderUris` and deletes the old key. hostops ran a libfolders build
(5f6c0268e7, run 1-1791149836, Blinx booted) on the Thor two minutes before
L1, and that run did the migration. cf328d86f7 predates libfolders, so its
launcher reads only `gamesFolderUri`, finds nothing, and opens the setup
wizard. The same thing will happen to any request whose ref predates
10f14d301d, on any device where a libfolders build has run (OUTBOX `NEW
ISSUE`). The fix: merge origin/master (e2b045168a, clean, surface.c diff still
adds lines only, fixtures unchanged), re-register the prediction on
e2b045168a (sha 3ca87cf9...) before any run on it, and queue the pair again.
This allows a retest because the void cause is named and is not a
performance miss.

| run id | apk_sha | lit tinted (clean) | wbc n | in-region | NEAR t / c | SINCE t / c | M0 |
|---|---|---|---|---|---|---|---|
| 1791150498-lane.fmv303c-2353118 (L1, e2b045168a) | afb8d4ccd1e3 | 389 (36) | 2496 | 5 | 0.000 / 0.000 | 0.000 / 0.000 | OK |
| 1791150499-lane.fmv303c-2353251 (L2, e2b045168a) | afb8d4ccd1e3 | 19 (3) | 1883 | 59 | 0.053 / 0.000 | 0.000 / 0.000 | VOID: 19 < 100 |
| 1791150948-lane.fmv303c-2457692 (L2b, replaces L2) | afb8d4ccd1e3 | 96 (9) | 2028 | 65 | 0.010 / 0.000 | 0.000 / 0.000 | VOID: 96 < 100 |
| 1791154079-lane.fmv303c-3735646 (L2c, replaces L2b) | afb8d4ccd1e3 | 543 (52) | 2823 | 67 | 0.004 / 0.000 | 0.000 / 0.000 | OK |

## Verdict (L1 + L2c, 2026-10-04 15:50 PDT): UNORDERED; write-back does not reach the FMV buffers

L2c ran 61 s before the guest exited. That was the Thor's dead-fan stop, and
it was the longest run yet, after 50 min idle. It is valid, so L1 and L2c are
the registered pair. `wb_judge.py` on both logcats:

| | L1 | L2c | pooled |
|---|---|---|---|
| lit tinted / clean / middle | 389 / 36 / 46 | 543 / 52 / 63 | 932 / 88 / 109 |
| tinted / lit (P2, registered [0.3, 0.9]) | 0.826 | 0.825 | **0.826, holds** |
| last `wbc` n (write-backs seen) | 2496 | 2823 | |
| in-region landings | 5 | 67 | 72 |
| NEAR tinted / clean | 0.000 / 0.000 | 0.004 / 0.000 | 0.002 / 0.000 |
| SINCE tinted / clean | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 |

**Registered verdict: UNORDERED.** The prediction was EXONERATED, and it
misses on the letter of the rule. EXONERATED meant "no landing anywhere in
0x3000000..0x3400000", and 72 landings fall inside that range. They are all
two surfaces past the FMV buffers' end (0x3249000): a 640x480 colour surface
at 0x32a4000 (ends at 0x33d0000) and a 1280x480 zeta at 0x33d0000. The
registered region was a coarse bound, wider than the buffers. The HIT side
of the falsifier is refuted outright. It needed a tinted-minus-clean
separation of at least 0.5. The measured separation is 0.002 (NEAR) and
0.000 (SINCE). In 932 lit tinted frames, no write-back lands on the
displayed buffer, or on either FMV buffer.

Below 0x3400000 the probe logs every landing. Outside the region it logs up
to a cap of 20000, and the totals (2496, 2823) are under that cap, so every
write-back in both runs is logged. The writers that run every flip are the
game's own 640x480 targets: colour at 0x3a84000 and 0x3bb0000, zeta at
0x3958000, about 900 each per run. They land on tinted and clean frames
alike, nowhere near the FMV buffers. The rest happen once or twice per run.
So the measurement does not depend on where Sofdec keeps its Y/Cb/Cr planes.
The tint is 0.83 of lit frames and switches within shots. A writer that
lands in the region 72 times in about 1100 lit frames, and never within 2
flips of 99.8% of tinted frames, cannot produce that. **Surface write-back is
not the cause of #303.** The second surface.c hunk (the HIT branch) is not
written.

**Branch selected:** the brief's EXONERATED branch, re-ranked below,
because the outcome that matters (nothing lands on the FMV working set) is
the one EXONERATED was meant to detect.

### Next, ranked by P x win

The win is the same for every candidate: the green blocks gone from the
pre-game screens (logos, title card, story FMV, loading screen) of two titles,
Spikeout (Playable) and Star Wars III (#719). Gameplay does not change.
Candidates are ranked by P that each finds the cause.

1. **Find the colour-conversion routine and read its input (decides 2 vs
   3/4).** The existing CPU-write watch on 0x3163000 gives the guest PC of
   the writer of the ARGB buffer. Its source registers then give the Cr plane
   address. Log the zero fraction of the Cr plane per flip next to the
   `tint` line. If the Cr plane is already zero on tinted frames, the cause
   is upstream: the decoder or a writer (3, then 4). If it is intact, the
   conversion itself drops Cr (2). P that this decides: about 0.7. The risk
   is that the conversion routine is hard to pin from one PC. It needs no
   new territory beyond the probe's file set. Cost: one env-gated hunk, two
   Thor runs (each under a minute on this title). It goes first because it
   decides between the candidates, not because it is cheap.
2. **MMX/x87 register state lost across an interrupt or thread switch**
   (`target/i386`: FXSAVE/FXRSTOR, CR0.TS lazy-FPU, MMX/x87 aliasing in TCG).
   P about 0.3. The evidence is mechanism only. Sofdec's conversion is MMX.
   The fault takes out one component (Cr) and leaves Y and Cb. It switches
   per macroblock within a shot and differs between runs of one binary. That
   is the signature of register state that is correct unless an interrupt
   lands inside the loop. Fix size: one TCG path, and it may also clear other
   MMX titles.
3. **IDE/DVD and APU DMA landing sites** (fmv303b s5 items 2 and 3, the
   brief's literal next step). P about 0.1. IDE DMA writes the compressed
   bitstream, so a clobber corrupts the decode, not one clean chroma plane.
   APU DMA writes audio. Either writer would also have to land on most
   frames to give a 0.83 tint that switches within shots. Cost: hunks in
   `hw/ide` and `hw/xbox/mcpx`, which are outside this lane's row.
4. **Per-op SIMD helper falsifier** (fmv303b step 2b: packuswb, paddsw,
   pmulhw in `ops_sse.h`). P about 0.1. A wrong helper is a function of its
   inputs, so it is deterministic per clip, and the tint is not.

Do not repeat: the write-back probe on this title (two valid runs, the
verdict above); the Tier1 on/off A/B.

Device note for the next lane: on the dead-fan Thor, Spikeout USA runs 32
to 61 s before the heat stop. Only a start after 40 to 50 min idle gave more
than 100 lit tinted frames (389 and 543). Size every Thor arm on this title
for a single minute.

All three runs booted and were force-stopped early by lane.local's
`thor-suite-runner`: `HEAT STOP: xo 50/51/49 C cpu-1-9 93/93/92 C; app
force-stopped` (logs/thor-suite-runner.log 14:50:37, 14:52:11, 14:57:13).
That is the dead-fan guard (stop at cpu-1-9 >= 90 C). It is not a hakuX
crash: there is no F/libc line from the hakuX pid, and the log stops
mid-second at 59 fps. Run lengths were 53 s (start xo 42 C), 32 s (48 C) and
32 s (44 C). The hostops Blinx run at 14:39 was heat-stopped the same way.
On Spikeout USA, the Thor's die reaches 90 C in 30 to 55 s, so a "<= 480 s"
Thor soak of this title actually lasts under a minute.

What the three runs show, as data and not as the registered verdict (that
needs two valid runs; it is NONE with one): 501 lit tinted frames in total,
and no write-back lands on the FMV buffers. All 129 in-region landings are
two surfaces past the buffers' end (0x3249000): a 640x480 colour surface at
0x32a4000 and a 1280x480 zeta at 0x33d0000, both staged copies. SINCE is
0.000 on tinted frames in every run. NEAR is at most 0.053 (1 of 19), and
the surfaces it joins are not the FMV buffers. The USA build uses the same
FMV buffers (tex0 addr=3163000, 640x368).

### Next: the second valid replicate, ranked by P x win (done: A was L2c, valid)

The win is the same for both candidates: the registered verdict. EXONERATED
sends #303 to the APU and IDE DMA landing sites. HIT sends it to a second
surface.c hunk.

- A. One more Thor run, unchanged (same ref, prediction and request shape),
  queued after the Thor has idled about 40 min. P ~0.6. Evidence: the run
  that started at xo 42 C lasted 53 s and gave 389 lit tinted frames. The
  44 and 48 C starts lasted 32 s and gave 96 and 19. The tint count at 32 s
  varies by run (timing-dependent, as fmv303b found). Cost: one run of under
  4 min device time, no re-registration.
- B. The Nova, Europe disc, the full 150 s (its fan works). P ~0.6: the run
  finishes (~0.95), but the tint has been measured only on the Thor, so the
  P2 reproduction on the Nova is ~0.65. The Nova is held by hangwatch and
  busy with pathfind. It needs a re-registration naming the Nova and the
  Europe disc. Cost: one run plus an unknown queue wait.

A goes first: equal P, lower cost, no change to the registration. If A also
heat-stops under 100, B is next, re-registered before it is queued.

The first two rows were registered on the Europe disc, which was the wrong
disc, and are superseded. The USA pair was refused by the same guard
(`display-covered: ... primaryScreenTopLayout (com.odin.dualscreen.assistant,
BOOT_PROGRESS)`). Nothing was started, and no logcat or frames were
produced. The guard (`soak_title.sh` / `devices.sh display_clear`) has no
override that a request can pass. Brief addendum 4 says the overlay is the
owner's own and the lane must not ask for it to be cleared. So attempt 5
parks with `WAITING: owner`, and lane.local takes the question to the owner.
The question: either clear the overlay on the idle Thor, or let the guard
accept it when the soak draws on the top screen. Once either happens, the
same two requests can be queued again unchanged: same ref, same prediction
(sha 6b933f61...). A void whose named cause is the device state, not
performance, allows a retest.

Both refusals (2026-10-04 12:3x PDT) come from one device state, with a
named cause that is neither a performance nor a code problem. run.log says
`display-covered: a foreign full-screen overlay covers display 0 on
bdc158a5: primaryScreenTopLayout (com.odin.dualscreen.assistant,
BOOT_PROGRESS)` and `soak refused ... nothing was started`. The runs logged
0 logcat lines and one all-black 10,899 B frame. This is the 09-27 cover:
`harness_health.py`'s `covered:` check names `dual_screen_display_mode=2` as
the root cause, and hostops' fix is `device_reality.sh --fix`. The owner
hand-tested Spikeout on the Thor earlier today, which plausibly left the mode
set. The lane does not touch the device. It re-queues the same two runs (same
ref, same prediction) once the cover is cleared. The requeue is allowed
because the void cause is named and is not a performance miss.

Both runs: ref cf328d86f7, Thor (hard pin), Spikeout, 150 s, frames every 2 s,
`HAKUX_FMV303_PROBE=1`, hands-off. Prediction: EXONERATED, P about 0.65 (a
write-back lands whole surfaces, all four bytes; the green is one zeroed
chroma component).

## Next, after 0.5 ships (done 2026-10-04; superseded by the Verdict section)

1. Merge master (and `origin/lane/blinx372d` if #396 has not folded; it also
   touches surface.c). Register `docs/testing/predictions/fmv303c-wb-probe.json`
   with `ab_compare.py --register` on the post-merge refs, two Thor runs,
   hands-off, `HAKUX_FMV303_PROBE=1`; must-not-move: pgraph suites and
   Surface_* rows with the variable unset.
2. HIT: name the surface binding whose write-back lands on the shown buffer
   and why it is still dirty; fix it in a second surface.c hunk, registered
   before measuring. EXONERATED (with `wbc` showing write-backs elsewhere):
   probe the APU and IDE DMA landing sites, then fmv303b NOTES s5 step 2b.

Do not repeat: the Tier1 on/off A/B (settled, 0.688 vs 0.680).
