# Audit pass 1: PR #512 lane/slowdown462-bindtex (#474)

Head audited: `013f087a52`. Diff read against `origin/master`:
`hw/xbox/nv2a/pgraph/vk/texture.c` +109, `docs/lanes/slowdown462/NOTES.md`
+191, `txwwin.py` +46, `phasesoak.py` +27. CI: build x2 and check pass on
this head.

**Verdict: no HIGH, no MEDIUM. Three LOWs.** -> `needs-audit-2`.

## What was checked

- **Default build is unchanged.** `TXW_BEGIN`/`TXW_END` expand to
  `do { } while (0)` without `NV2A_PERF_LOG`; `txw_log_window` is only
  referenced through `TEX_PERF(...)`, whose non-perf form discards its
  arguments, so the undefined function is never named. `<android/log.h>` is
  included only under the perf build. The "Prediction: none" line holds.
- **Every exit of a timed region closes it.** `pgraph_vk_bind_textures`
  has two returns (the `!check_textures_dirty` early return, line 2918, and
  the function end, line 3078); both call `TXW_END(BT)`. Every other pair
  brackets a single call with no `return`, `goto` or `continue` inside.
- **No redeclaration in a perf build.** `TXW_BEGIN(k)` declares
  `_txw_t0_k`; each repeated key (FAF, BS, CP, UP) sits in its own braced
  block, and texture.c has no labels a declaration could follow. The device
  soaks compiled and printed the lines, so the Android perf build compiles.
- **Nesting matches the doc.** bt holds res and ct; ct holds sdl, scan, faf,
  bs, cp, up; bs holds flq and nd (both inside `bind_surface_as_texture` /
  `bind_zeta_surface_as_texture`). The header comment, the PR body and
  `txwwin.py`'s docstring agree.
- **The attribution in NOTES follows from the counters.** faf sites are the
  s2t drain and the upload drain; `up` is 0 and `cp` is 0 in both windows,
  so every faf there precedes a direct bind. Bound arithmetic checks:
  60.1 - 4.47 = 55.6 ms -> 17.98 fps; 63.4 - 2.99 = 60.4 ms -> 16.55 fps.
- **txwwin.py parses the format the C prints.** The key/value regex reads
  `bt4.57/78`, `res0.02`, `flq0.00` correctly; flips weight each line.

## Findings

### LOW 1: `bt` calls/flip printed with `%.0f`
`TXW_FMT` prints `bt%.2f/%.0f`, every other count with `%.1f` or `%.2f`.
Scenario: a title where bind_textures runs less than once per two flips
(a static menu) prints `bt.../0`, and `txwwin.py` averages that 0 as the
call rate. Not used by any figure in this PR (AUF reads 78/flip). Fix only
if the probe is kept past this lane.

### LOW 2: NOTES states the direct-bind drain "protects nothing" without checking descriptor reuse
NOTES (AUF bullet, "The direct bind writes nothing into the texture node's
image ... So the drain before it protects nothing that path writes") argues
from image writes only. The direct bind also changes what the slot's
descriptor points at (`tex_surface_direct_views`, `texture_bindings_changed`).
Scenario for the candidate fix, not for this diff: if a descriptor set that
an in-flight frame still references is rewritten in place, removing the
drain is a use-while-pending hazard that no image-write argument covers. The
fix lane should check how descriptor sets are allocated per frame before
relying on this premise; the premise should say it was checked where it is
stated.

### LOW 3: the probe's own clock reads sit inside the timed regions
Two `nv2a_clock_ns()` per step per call, and `ct` runs ~88 times per flip on
AUF, so `bt` and `ct` include the probe's overhead. At tens of ns per read
this is well under 0.05 ms/flip against a 4.47 ms `faf`, so no conclusion
moves; noted only so a later sub-0.1 ms reading of `ct` minus its children
is not read as work.

## For pass 2
Verify LOW 2 is addressed in NOTES (the premise qualified, or the
descriptor question answered) or explicitly deferred to the fix lane's
brief; LOW 1 and LOW 3 may stand as documented.
