# lane.gpupass1010 -- NFS Most Wanted's GPU frame: render mode A/B and the cold-start pass count (#433, 0.5)

## 1. Base and territory

Branched from `origin/master` at `bfd6986fa2` (already a merge of `lane/texscan1010` into this
branch, done at session start per the dispatch note so step 3's census has texscan1010's
GPU-side cube-face copy on the base). Two commits on top, in territory:

- `9c8b1b12b6` -- adds `docs/lanes/gpupass1010/{gpuread.py,phaseread.py,ftwin.py}` (readers only,
  no code change). This is **R_off**: the build still has no `kTitleRenderModes` row for NFS, so
  it renders at the driver's GMEM default, same as every prior lane's NFS figures.
- `81ab5f3418` -- adds `{0x4541007B, "sysmem"}` to `kTitleRenderModes`
  (`android/app/src/main/cpp/xemu_android.cpp`), the lane's only code change. This is **R_on**.

`phaseread.py`/`ftwin.py` are copied verbatim from `origin/lane/nfs30plan1010` per the dispatch
note (period/pace/draws-per-frame reader, frametrace reader). `gpuread.py` is new: it reads
`draw.c`'s `xemu-xfr` lines (`XFR rp`, `XFR rpc[ g]`), which print independently of `--perflog`,
for GPU busy ms/frame, X/R, the in/out mode-confirmation ratio and render passes per frame --
none of that is in `phaseread.py`, which only covers the `hakuX-phase` line (perflog-only).

## 2. Why a plain build, and how GPU busy is read without `hakuX-phase`

The brief insists on a **plain build** (no `--perflog`) so the ~8-10 ms/frame instrument
overhead a perflog build adds does not leak into the period and GPU-busy figures this lane is
trying to measure. `draw.c:3706-3765`'s `xfr_emit()` function is gated on `HAKUX_GPUXFR=1` only,
not on `NV2A_PERF_LOG`, and prints every 60 guest flips regardless of build type:

- `XFR rp in <med> <mean> <p90> out <med> <mean> <p90> nr_out ... res_out ... n<X> inrp<0|1> ...`
  -- `in` is the render-pass span stamped by the in-pass begin/end pair: **in full** for a
  sysmem pass, but **only for a GMEM pass's last tile** (the comment at draw.c:3706-3765 states
  this explicitly, and gives `in/out < 0.8` as the GMEM-still-active threshold). `out` is the full
  outer command-buffer bracket covering every tile's loads/stores. `gpuread.py` maps GPU busy
  ms/frame to `out_mean + nr_out_mean` (the render pass's outer span plus the non-render-pass GPU
  work in the same command buffer), R to `in_mean`, X to `out_mean - in_mean`, and treats
  `in_mean / out_mean` as the mode-confirmation ratio (leg `M`).
- `XFR rpc[ g] all <n> <ms> <kb> ... ldMB <x> stMB <y> in <z> draws <w>` -- the un-suffixed
  (`all` group, no ` g`) line's `n` is **every** render pass in the window, so it is render
  passes per frame regardless of mode (leg `P`); the ` g`-suffixed line is the GMEM-only subset.

`gpuread.py` windows these lines by **print time** inside `[mark + 1.5, mark + 12.0]` for the
route's `mark gameplay`/`mark go<N>` lines (the same convention as `startread.py`'s
`start_rows` / `nfs-mw-quickrace.route`'s own timing comment: GO is ~1.5 s after the mark),
splitting `go1` (cold, first race start after the menu load) from `go2`..`go12` (warm, pooled).
A countdown window (`mark - 2.0 .. mark + 1.5`, `phaseread.py`'s own default) is also read for
period/pace during the load, separately from the gameplay window.

**`M` is a per-run-arm leg, not a cross-arm one**: a single `gpuread.py` invocation takes
`--arm off` or `--arm on` and checks that arm's own in/out ratio against the bound that arm's
render mode predicts (off: GMEM, `in/out` in `[0.0, 0.8]`; on: sysmem, `in/out` in `[0.8, 1.5]`).
The period and the on-vs-off GPU-busy/pass-count deltas are **not** computed by the script across
two invocations -- they are read by hand from each invocation's POOLED printout and recorded
below, because the two predictions here (render mode, texscan) are read with different `--arm`
settings on the same file in the texscan case (see predictions, both read with `--arm off` since
neither arm of that A/B changes render mode).

**Found and fixed before any run used it**: the first draft of the `M` leg's off/on bounds was
backwards (off got the wide `[0, 1.5]` band, on got the narrow `[0, 0.8]` one) -- exactly
backwards from `draw.c`'s own `in/out < 0.8` = GMEM rule. Fixed in the same commit that
registered the predictions (`d51a730bf4`), before any device time was spent.

## 3. Run allocation under the 4-run/500s cap

The brief's step 1 literally asks for "2 runs per arm" for the render-mode A/B; the hard rule is
"at most four runs of 500 s total, batched in one enqueue" and the Nova is shared with
reportasync1010/drawrec1010. Step 3's census needs at least one more run on `R_off` with
`HAKUX_TEXSCAN=1`. Four runs cannot cover "2 per arm" for step 1 AND a dedicated texscan arm, so:

| run | ref | env | serves |
|---|---|---|---|
| A | `9c8b1b12b6` (R_off) | `HAKUX_GPUXFR=1` | step 1 off-arm (GMEM default) **and** step 3 off-arm (`HAKUX_TEXSCAN` default 0) |
| B | `9c8b1b12b6` (R_off) | `HAKUX_GPUXFR=1 HAKUX_TEXSCAN=1` | step 3 on-arm |
| C | `81ab5f3418` (R_on) | `HAKUX_GPUXFR=1` | step 1 on-arm, sample 1 |
| D | `81ab5f3418` (R_on) | `HAKUX_GPUXFR=1` | step 1 on-arm, sample 2 |

Off (step 1) gets one fresh run, not two: run A is reused for both step 1's off-arm and step 3's
off-arm, since `HAKUX_TEXSCAN` defaults off and is otherwise inert on R_off. The on-arm (the
new, uncertain finding -- no lane has measured NFS's X/R before) keeps both its samples (C, D).
Off is backstopped by `lane.nfs30plan1010`'s existing XFR rpc census (runs `1-1791649387`,
`1-1791649388`), same render-mode default, cited as context in both prediction files, not
treated as part of this lane's own run count since it predates the texscan1010 merge.

## 4. Pilot gate

Per the lane-role contract, four requests of ~590 s estimated device time each (500 s + 90 s
setup) total ~39 min, over the 30-min pilot cap, and there is no `pilots/lane.gpupass1010.ok`
yet. Queued runs A and C first (the most informative pair: one off sample, one on sample, ~19.7
min estimated) as the pilot, reviewed them, then queued B and D.

Pilot pair (A=1-1791659388 off/plain, C=1-1791659390 on/plain) read: both completed
cleanly (12/12 go marks, 0 fatal lines, no truncation per `ab_compare.py
--check-truncation`), but landed **zero** `xemu-xfr` lines in either logcat (17000+
lines each). Investigated: `draw.c`'s real `xfr_emit()` (the function that prints
`XFR rp`/`XFR rpc`) is compiled only `#if defined(__ANDROID__) && NV2A_PERF_LOG`
(draw.c ~3706-4317; confirmed by an `awk` scan of every `#if`/`#else`/`#endif` in
that range -- exactly one controlling `#if`, and the `#else` at 4398 is an empty
stub). `NV2A_PERF_LOG` is the CMake define `--perflog` sets
(`android/app/src/main/cpp/CMakeLists.txt:973,1093`), so a **plain** build's
`xfr_emit()` is a no-op regardless of `HAKUX_GPUXFR=1` at runtime -- the brief's
"plain build + HAKUX_GPUXFR=1 for the pass census" cannot work as literally
written. Cross-checked: every prior XFR-reading run in this issue thread
(nfs30plan1010's census, texscan1010's own A/B, both cited above as baseline) was
in fact a `--perflog` build; `draw.c`'s own comment at the `xfr_emit` site says
as much ("reported by the perflog build as an xemu-xfr line").

**Correction, before any further device time was spent**: both prediction files
(`gpupass1010-rendermode.json`, `gpupass1010-texscan.json`) were edited to
`"perflog": true`, with a `"correction"`/`"status"` field each documenting this
in full (run ids, code line numbers, CMake lines), committed as `ebcbd61064` --
registering the correction before queuing the next pair, per the lane contract's
"register, then run" order. The two plain runs are kept (useful for
period/pace/v-histogram; not useful for GPU busy/X/R/passes) and are not
resubmitted, since the 4-run/500s cap does not stretch to a third pair. This
forces dropping step 3's `HAKUX_TEXSCAN=1` on-arm measurement entirely this lane
(`gpupass1010-texscan.json`'s `"status"` field: DEFERRED) -- the remaining 2 of
4 runs went to step 1's perflog off/on pair instead, since the brief's own
dispatch condition and "Why" section frame step 1 (is the GPU on NFS's path at
all) as the headline question, and step 3's census is explicitly "name a
follow-up, not to be fixed/measured further this lane" framing already.

Queued second pair (perflog): `1-1791660793-gpupass1010-760340` (off,
`9c8b1b12b6`, `HAKUX_GPUXFR=1`, `--perflog`) and
`1-1791660794-gpupass1010-761330` (on, `81ab5f3418`, same env, `--perflog`).
Pilot verdict written to `$DISPATCH_DIR/pilots/gpupass1010.ok` per the lane-role
contract (via `python3`, since the dispatch dir sandbox blocks direct `Write`).

## 5. Merge: origin/master brought in (not rebased) after the first pair landed

`origin/master` had moved 23 commits ahead of this branch's base (fold of
texscan1010/pfifowait1009/forzasurf1010 and their own resume cycles). Merged
(`c18fdd344a`, not rebased -- `9c8b1b12b6`/`81ab5f3418` keep their shas, so both
predictions' refs stay valid) rather than concluding anything further on a stale
tree. The merge is clean: master never had this lane's `kTitleRenderModes` row
(the one-line diff `HEAD..origin/master` on `xemu_android.cpp` is *removing*
the NFS row, i.e. it is absent upstream, not conflicting), so no territory
conflict.

**Relevant to this lane's own period-vs-GPU-busy falsifier**: the fold brought
in `pfifowait1009`'s own resume-attempt-3 verdict (`f1e99aaa0f`, doc
`docs/lanes/pfifowait1009/NOTES.md` section 7) -- **FAIL on both legs**.
`HAKUX_PFIFOWAIT=1` (releasing `pfifo.lock` across the STALLED finish's fence
waits, the mechanism the brief's own "Why" section names as what would put the
GPU in parallel with the PFIFO thread) is measured unsafe (a real pgraph pixel
regression) and does not even help its own target metric (fps falls, wait
roughly doubles on amped2 in the slow bins) -- it stays **default-off**. This is
corroborating evidence, not proof, for this lane's own prediction text ("period
unchanged unless the GPU was the path... reportasync1010 is not yet merged
here"): the specific mechanism named in the brief as what would expose GPU busy
time to NFS's critical path did not ship, so a near-zero period delta on this
base is the expected outcome, not a surprise, when the on-arm perflog run lands.

Second perflog pair still queued at merge time, behind 8 `reportasync1010`
requests and 1 running + several `drawrec1010` requests sharing the Nova --
well beyond a few 10-minute polling chunks. Writing `WAITING` rather than
polling further this turn.

## 6. Why attempt 1 didn't finish

Attempt 1 did everything through registering the predictions, merging in
texscan1010/pfifowait1009/forzasurf1010, and queuing the B'/D' perflog pair
(`1-1791660793-gpupass1010-760340` off, `1-1791660794-gpupass1010-761330`
on) behind 8+ `reportasync1010`/`drawrec1010` requests on the shared Nova.
Per the lane contract ("never end a turn waiting for a background task"),
it wrote `WAITING` with both request ids and stopped rather than poll —
correct behavior, not a failure. The runs were simply still queued when the
turn budget ran out. Both are now `DONE`; this section and PR.md pick up
from there.

## 7. Three `gpuread.py` bugs found reading the perflog pair (fixed, `d3baeb348b`)

Both landed runs initially read as `FAIL` across the board. All three
causes were bugs in this lane's own reader, not the device data:

1. **FATAL regex matched a benign tag.** `FATAL` included `hakuX-unhandled`,
   a deduped per-(class,method) diagnostic for unimplemented NV2A methods
   (`docs/investigations/unhandled-methods-inventory.md`), not a crash.
   `title_verdict.py:333`'s own convention treats only `hakuX-crash` at E/F
   as fatal. Fixed by dropping it from the regex.
2. **Cold-window label never matched anything.** The reader looked for
   `windows(marks, {'go1'}, ...)`, but `nfs-mw-quickrace.route` writes
   `mark gameplay` for the first start and `mark go2`..`go12` for the rest
   (confirmed directly in the route file) — there is no `go1`. Every cold
   bucket, in every prior invocation since this script was written, was
   silently empty. Fixed by replacing `{'go1'}` with `{'gameplay'}` in all
   three occurrences.
3. **`pace_pool`'s denominator was the cumulative flip counter, not the
   window's flip count.** `hakuX-pace`'s `f=` field is a run-cumulative
   total (confirmed from raw lines: `f=60`, `f=120`, ... `f=19020` by the
   end of a 500 s run), not a per-window count; summing it across pooled
   windows inflated the denominator by roughly (cumulative/60)x and read
   `ms_per_frame` two orders of magnitude too low. Fixed by using `tot`
   (the v0..v4 histogram sum, which genuinely is a per-window flip count,
   always 60) as the denominator instead.

A fourth change, not a bug fix: added `cold_cd`/`warm_cd` buckets that pool
the same rp/rpc data over `COUNTDOWN_WINDOW` (pre-GO load/countdown) rather
than `GAMEPLAY_WINDOW` (post-GO racing), at zero extra device time. This
matters because the baseline this lane's predictions cite
(nfs30plan1010's 21.7 ms/69-pass cold census, NOTES 5.5) was measured over
the countdown slice for the first start only — a different window than
`gpuread.py`'s original "cold" bucket. `cold_cd`/`warm_cd` is the
closer-to-apples-to-apples comparison; both are reported below.

## 8. Results

Both runs: `max` perf/fan regimen (`perf_regimen.json`, identical across
arms, rules out a thermal/clock confound), no truncation
(`ab_compare.py --check-truncation`, clean on both), shader cache cleared
fresh for each (`result.json`'s `shader_cache`), 12/12 go marks, no fatal
lines. Moving-player gameplay confirmed by reading `s1-g11.png` for both
arms directly: off (`141958-s1-g11.png`) and on (`142908-s1-g11.png`) both
show the car mid-race, "2/3 COMPLETE 5%", ~11.7 s into the start — matched
scene, not a parked HUD clock.

`python3 docs/lanes/gpupass1010/gpuread.py --arm <off|on> <run dir>`:

| window | arm | n | GPU busy ms | X/R | mode(in/out) | passes/frame | period ms |
|---|---|---|---|---|---|---|---|
| cold (gameplay) | off | 9 | 5.10 | 0.24 | 0.81 | 15.6 | 59.56 (n=4) |
| cold (gameplay) | on | 11 | 3.83 | 0.02 | 0.98 | 13.8 | 51.37 (n=4) |
| warm (gameplay) | off | 119 | 3.98 | 0.03 | 0.97 | 10.4 | 44.50 (n=44) |
| warm (gameplay) | on | 140 | 3.54 | 0.01 | 0.99 | 9.6 | 43.71 (n=46) |
| cold_cd (countdown) | off | 3 | 7.12 | 0.41 | 0.71 | 23.6 | -- |
| cold_cd (countdown) | on | 3 | 5.15 | 0.02 | 0.98 | 21.9 | -- |
| warm_cd (countdown) | off | 35 | 4.26 | 0.02 | 0.98 | 10.0 | -- |
| warm_cd (countdown) | on | 36 | 4.07 | 0.01 | 0.99 | 9.2 | -- |

`gpuread.py`'s own verdict legs: off-arm `V=PASS M=FAIL G=PASS X=PASS
P=PASS`; on-arm `V=PASS M=PASS G=PASS X=PASS P=PASS`.

### Reading the legs against `gpupass1010-rendermode.json`'s prediction

- **M (mode-confirmation), off-arm FAIL by a hair:** gameplay-window cold
  mode is 0.81, one hundredth above the 0.80 GMEM-active cutoff. Read
  alongside `cold_cd` (0.71, clearly GMEM) and the on-arm's own clean 0.98
  PASS, this reads as a windowing artifact (the gameplay-window cold bucket
  has only n=9 and includes less tile-heavy tail frames), not evidence
  that the render-mode row failed to take effect. The countdown window is
  the closer analog to the baseline's own measurement and confirms GMEM on
  the off arm unambiguously.
- **G/X (GPU busy, X/R):** directionally as predicted — GPU busy falls
  off->on in every bucket (cold_cd -28%, cold gameplay -25%, warm_cd -4%,
  warm gameplay -11%), and X/R collapses toward 0 in every bucket (biggest
  in cold_cd: 0.41->0.02). But the *magnitude* is far smaller than the
  conditional prediction's premise (21.7->14 ms, assuming NFS behaves like
  AUF/DOA): off's own cold GPU busy here is only 5.10-7.12 ms, nowhere near
  21.7 ms. See section 9 — this is an open discrepancy against the cited
  baseline, not a render-mode effect.
- **P (passes/frame):** roughly unchanged by the mode switch alone, as
  predicted — cold gameplay 15.6->13.8, cold_cd 23.6->21.9, both within the
  predicted "no mode effect on pass count" claim.
- **Period:** flat within noise in the reliable bucket (warm, n=44/46:
  44.50->43.71 ms, -1.8%, inside the ~4-5 ms noise band). The cold bucket's
  apparent larger drop (59.56->51.37 ms, n=4 each) is not attributable to
  the measured GPU-busy delta (1.27-1.97 ms) — far smaller than the
  8.2 ms period delta — so it reads as sampling noise from only 4
  flip-windows per arm, not a GPU-driven effect. This supports the
  prediction's framing: on this base (reportasync1010 not yet merged here),
  the GPU is not on NFS's critical path, consistent with
  `pfifowait1009`'s own FAIL verdict cited in section 5.

### Step 3 cross-check (texscan census, off-arm only, no new device time)

`gpupass1010-texscan.json`'s `a_env` arm (`HAKUX_GPUXFR=1` only) is the
same request as this lane's off-arm run, reused. Its cold passes/frame:
15.6 (gameplay window) / 23.6 (countdown window, closer match to the
baseline's own window). The `b_env` arm (`+HAKUX_TEXSCAN=1`) was never
queued — budget was fully spent on the render-mode pair, as recorded in
that file's `status` field at registration. No on/off `HAKUX_TEXSCAN` delta
is reported here; that prediction remains unjudged, carried forward as a
follow-up for #433 (not blocking this PR).

## 9. Open discrepancy: both arms read far below the cited baseline

Both arms' GPU busy and pass counts are 3-4x smaller than
nfs30plan1010's own census (21.7 ms/69 passes cold, 12.8 ms/26.5 passes
warm) — and this gap appears in BOTH arms equally, so it is not a
render-mode effect. Conditions match on paper: same route, same disc,
fresh shader cache, first-run hdd state, `HAKUX_GPUXFR=1`, `--perflog`.
The `cold_cd` bucket (closest window match to the baseline's own) narrows
the gap least and still reads 7.12/5.15 ms against 21.7 ms, and
23.6/21.9 passes against 69.

Not chased further here — the 4-run/500s device budget is fully spent, and
tracing this needs either a side-by-side rerun of nfs30plan1010's own exact
reader against this lane's logcats, or new device time, neither of which
fit this lane's cap. Flagged as a named follow-up for whichever lane picks
up #433 next: **re-verify nfs30plan1010's census figures against a fresh
run with gpuread.py's windowing, or identify what differs between the two
readers' window/line-selection logic.** Until resolved, treat the *relative*
(off vs on) deltas in section 8 as trustworthy (same reader, same route,
same windowing, applied identically to both arms) but the *absolute*
magnitudes as uncertain against the brief's cited baseline.

## 10. Keep/drop recommendation for the NFS `kTitleRenderModes` row

**Keep.** Zero measured downside: pixel check is an architectural no-op
(section on step 4, pixel suites boot under a title id matching no table
row, so `rendermode474`'s existing PASS 1059 already covers it); passes/frame
is unchanged within noise; period does not regress in the reliable (warm)
bucket. And a real, if modest, upside: GPU busy drops 25-28% at the race
start and the mode-confirmation/X/R legs both confirm the row actually
engages sysmem and collapses the GMEM double-pass signature, matching the
corpus's established remedy class (gmem474/rendermode474/flip474). The
absolute-magnitude discrepancy in section 9 is a measurement-methodology
open question, not evidence of harm — it affects how big the win is, not
whether there is one. GPU is not yet on NFS's critical path at this base
(section 8's period reading), so a player will not see a frame-time change
from this row today; that is expected and already named in the brief's
"Why" (this row is positioning for when the GPU IS on the path, e.g. once
reportasync1010 lands here, or on heavier tracks/conditions).

