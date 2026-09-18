## The sign fold is complete. `fold alone = 0`, `unexplained = 0`, ring 0 restored. PRE-REGISTERED PASS on 126 checks.

Arms `d99be2b35d` → `86a1c53195`, thor, same disc, bound at queue time.

```
better 30    worse 0    same 126    noise 0    (156 compared)
exact  31 -> 31       regressed from exact 0
differing 4,644,590 -> 2,833,490   (-1,811,100)
VERDICT: PASS -- all 126 registered checks hold.

#spot_*_SADD      80,007 -> 17,024
#spot_*_SREVSUB   76,897 -> 19,140
```

### Root cause of ring 0: a cache key on a register the cache does not watch

`signed_blend_fold` was a `PshState` field set from `NV_PGRAPH_BLEND`, and `pgraph_glsl_check_shader_state_dirty()` rebuilds `ShaderState` from a **fixed register list that does not contain `NV_PGRAPH_BLEND`** — grep of that list returns 0.

`DrawQuad` calls `SetColorMask(RGB) + SetBlend(false)` for its colour half between two blended alpha draws. The folded shader was therefore reused on a draw with blending **off**, where green `0xCC` = 204 sits above the sign bit, got masked to `f1 = 0`, and reached the framebuffer unblended.

That predicts `G 204 → 0`, and ring 0 measured `G 204 → 0` against a golden of 204 on all 11,280 px, with alpha nearly untouched because the colour half's write mask excludes it. Prediction and measurement agreed on the **value**, not merely the direction.

**The fix removes the class rather than the instance.** Adding that register to the watched list would fix this field and leave the next one exposed — and that list is in `glsl/shaders.c`. So the fold no longer keys the shader cache at all: the field is gone, the masking block is emitted unconditionally and gated at run time on `signedBlendPass != 0` (uniform-valued, a predicted jump), and `set_psh_uniform_values` recomputes foldability from the **live** register at every staging. A draw with blending off stages `NONE` whatever the renderer's selector says.

### Every leg

- **W1 ring 0 restored.** `LEG 3`: `124,200 px of ring 0, 0 differing` — `ok` on **both** equations, as it was before pass 2 ever emitted.
- **W2 the bit-exact captures stayed bit-exact.** `txt_A8R8G8B8_SADD` and `_SREVSUB` still 0 differing, `exact 31 → 31`, `regressed from exact 0`. W1 and W2 were registered in tension deliberately: turning the fold off would satisfy W1 and destroy W2.
- **W3 counters hold, and show the fix.** `folds=5376 emitted=10752 empty=0 staged_high=5376` — and `staged_low` fell **36,339 → 5,376**, exactly `folds`. An unfolded draw now stages `NONE` instead of `LOW`. That was predicted in the registration as "the fix visible in a counter".
- **W4 all 124 guards hold.** This mattered more here than on any earlier arm, because the masking block now lands in *every* fragment shader, so a bad runtime gate would have corrupted unsigned draws corpus-wide. It did not.
- **W5 bound met.** Both improved and stayed above the 7,350 floor; factor-independence survived at one distinct value per equation, and `LEG 1` reports 1/1 against silicon for SADD and SREVSUB.

### The residual is the seam and nothing else

```
differ 17024 = ink 9674 + seam 7350   unexplained 0   over-predicted 87181
               [fold alone 0, both 9674, seam alone 7350]
```

**`fold alone = 0`** and **`unexplained = 0`**. `SREVSUB` lands on exactly **19,140**, the seam mask's full cardinality. So the `fold alone 54,015` I reported last time was the stale-shader bug, not a second blend defect — **the second defect I was about to file does not exist.**

What does exist, and is genuinely separate, is the rasterisation seam: filed as **#78**. It is now the entire residual of all 105 `#spot_*` captures, signed and unsigned.

### And the region tool's LEG 2 is stale, not failing

`LEG 2` reports "87,181 px that the sign fold or the seam must get wrong are exact -- the mechanism is not what is described" on all 15 captures. Read the direction: it requires those pixels to be **wrong** and they are now **right**. Its masks were derived from the factor-only state, so it is a pre-fix attribution reporting a correct fix as a failure — the same trap that made my own `7,350` leg wrong. **`ink_mask()` should be re-derived against this arm before the tool is used to judge anything again.**

### Disposition

#43's two halves are now both closed by measurement: the factor half (`ab4a829316`) and the sign fold (`86a1c53195`, on top of the two-pass construction and the pass-2 emission fix). The remaining `#spot_` residual is #78's. `Texture_signed_component_tests`, the suite built to isolate this defect, is **bit-exact on all three captures**.

---
RESCUED BY lane.triage 2026-09-18 from the session scratchpad referenced
verbatim (and unexpanded) as the entire text of #43 comment
2026-09-13T23:23:26Z. Original path:
/tmp/claude-1000/-home-justin-hakuX/afb31e59-6fc4-4685-81b2-b4db438e1cf3/scratchpad/done.md
mtime Sep 13 16:23, 4611 bytes. Post this to #43.
