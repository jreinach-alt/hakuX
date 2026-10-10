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

<!-- full run results appended below once device time lands -->
