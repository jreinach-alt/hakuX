# Audit pass 1: PR #586, lane.energymap507 (#507)

Head audited: `41154e68e1`. Diff read: `gh pr diff 586` (10 files: NOTES.md,
seven `em_*.py` readers, one soak prediction, and `hw/xbox/nv2a/pgraph/glsl/geom.c`).

**Result: no HIGH, no MEDIUM. Five LOWs.** The only code change, the
`HAKUX_MEASURE_NO_GEOM` switch, is off by default. It does nothing unless the
environment variable is set, and when it is set it takes a render path that
already exists.

## What was checked in the code change (geom.c)

- **Default off.** When `HAKUX_MEASURE_NO_GEOM` is unset or `0`, `measure_no_geom()`
  returns 0. The new `if` then falls through to the original switch, so the
  default behaviour is the same as before. The lazy `static int on` has a race
  on first use, but it is harmless: both writers store the same value.
- **Consistency of the no-GS path.** Both callers derive every module key from
  one call. Vulkan does it in `shader_binding_build_module_keys`
  (`vk/shaders.c:867`) and GL in `gl/shaders.c:367`. The VS key's
  `prefix_outputs` follows `need_geom`, so the VS writes `vtxPos0..2 = vtxPos`
  and `triMZ = 0.0` (`glsl/vsh.c:1093-1096`). That is the path quads and points
  already take. The draw path keys the pipeline on
  `shader_binding->geom.module_info` (`vk/draw.c:2362`), and that is NULL here,
  so the two stay consistent.
- **Degenerate barycentrics.** With all three `vtxPos` equal, every `area()` is
  0 and `inv_bcsum` is inf. The shader clamps it to 0 in both depth branches
  (`glsl/psh.c:2971-2974`, `3006-3009`), so z is `vtxPos0`'s value. Depth
  comes out flat per triangle with no NaN, as the comment says. B does not
  lose fragments to NaN depth, which would have inflated the R drop.
- **Log line.** The `[nogeom507] skipped=` counter logs to `hakuX-perf`, which
  `em_extract.py` already reads, so the V leg's grep can see it. It counts
  binding builds, not draws. The V leg only asks for at least one line, so
  that is enough.
- **Arms.** The prediction has `title` set and `a_ref == b_ref`, so `arms.sh`
  skips it on structure (`arms.sh:841`, `846`) and does not refuse it. NOTES
  section 6 records the arms as queued by hand (`1224865`, `1227971`, both on
  `5af7b13ee5`), which is correct for a soak.

## LOW

**L1. NOTES section 4, P3 row, describes a different design from the one queued.**
`NOTES.md:225` says "A = master perflog; B = a measurement-only apk from master".
What is queued (section 6, `:256`, and the prediction) is one binary,
`5af7b13ee5`, with and without the env switch. Failure scenario: someone who
reads only section 4 compares B against a master-built baseline and sees a
two-binary delta. Fix: rewrite the row to say one binary, env on and off.

**L2. The prediction's window is not the window the baseline was read on.**
`window` says "`mark play` + 10 s to 10 s before the log ends, as energymap507
read Blinx's baseline ... (em_extract.py)". `em_extract.py` reads from
`mark gameplay`/`mark play` to `soak end` with no 10 s trims. So the quoted
baseline figures (R 31.4, GPU 32.9, Fen 6.7) come from a slightly wider window.
Blast radius is bounded: R is a B/A ratio over two arms read the same way
(phaseread `--from`), and the baseline is only context. Fix: make the window
text match what the judge actually runs, or add the trims to `em_extract.py`.

**L3. A stale line citation.** `NOTES.md:190` cites `glsl/geom.c:81-94` for
`pgraph_glsl_need_geom`. This PR moves it to `geom.c:106-134`.

**L4. The readers only run against uncommitted copies, and crash on a run with no data.**
Every `em_*.py` reads `scratch/runs` copies, so no figure in NOTES can be
re-derived from the repository alone. The run ids are named, so they can be
re-derived from the host's results. `em_split.py` reads `r['vcpu_share']`
without a guard, and `em_breakdown.py` indexes `ex[r]`, so a REP run with no
`[tlb68]` lines, or one that is missing from `extract.json`, raises `KeyError`
instead of printing `-`. Only the lane's own reruns are affected.

**L5. B's shader module keys persist into later default runs on the same install.**
When `cache_shaders` is on, `shader_module_key_persist` (`vk/shaders.c:1049`)
appends B's `prefix_outputs=false` VS keys to `shader_module_keys.bin`. After
that, A1 and every later run on that Nova compile those modules again during
warm-up. Pixels are not affected, because the binding recomputes `need_geom`
and never picks them. The only effects are more startup compile before
`mark play`, outside the window, and a cache file that holds modules no
default run uses. Worth one line in NOTES so the next reader of A1's startup
time knows why it is longer.

## Pass 2 should verify

- L1 to L3: the NOTES and prediction text match the queued design and the code.
- L5: noted in NOTES, or the cache is cleared between arms.
