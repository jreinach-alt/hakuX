# lane.ring53impl -- #53: six-entry ring of stale FF lighting inputs under a vertex program

Base: master @ a5b5b628f2. Continues lane.ring53 (`docs/lanes/ring53/NOTES.md`),
with the console weights of PR #394 (`docs/testing/xbox-ringw-2026-09-26.md`).

## 0. Outcome (read first): exact held out; prediction registered

**Attempt 3 (2026-09-26).** The boundary run on silicon (PR #406,
`docs/testing/xbox-ringw-boundary-2026-09-26.md`) weighed every candidate
at 0: `WAIT_FOR_IDLE`, `SET_CONTEXT_DMA_COLOR`, `SET_TRANSFORM_EXECUTION_MODE`,
`_PROGRAM_CXT_WRITE_EN`, `_PROGRAM_LOAD`, `_PROGRAM_START` and `_CONSTANT_LOAD`.
That leaves the flip pair (`FLIP_INCREMENT_WRITE`, `FLIP_STALL`) as the sole
unweighed member of the boundary set, and it carries the default +1 each.
- **The +2 is derived, not fitted.** The pair is the only unmeasured
  member left, and the old residual was exactly −2.
- **Only the pair's sum is visible.** Every boundary issues both methods once,
  and nothing else issues either.
- **The per-name label fills are accounted for.** The desktop runs the same XBE,
  so each test's printed name emits the same `pb_fill`s. The first-draw starts
  that vary by name (ringw2 N0 0, N1 3, N4 0, N6 2) come out equal to silicon's.

Re-priced on the merged tree (`b4fd40a16e`; nothing fitted on any row):

| set | rows | exact |
|---|---:|---:|
| ringw (`starts.py`, console 2026-09-26) | 15 cases × 6 draws | 15 |
| ringw2 (boundary methods) | 8 cases × 6 draws | 8 |
| Specular `ControlFlags_VS` ring-visible quads (`ring53_price.py`) | 9 | 9 (code and start) |
| Specular_back, same | 9 | 9 |

Pixel price, desktop GL (`pxprice.py`). The first figure counts pixels with
any channel off; `>1` counts those off by more than one step:

| capture | ring off | ring on | floor |
|---|---:|---:|---:|
| Specular/ControlFlags_VS | 76,531 (>1: 58,629) | 26,724 (>1: 909) | ControlFlags_FF >1: 882 |
| Specular_back/ControlFlags_VS | 89,143 (>1: 72,970) | 40,424 (>1: 8,809) | ControlFlagsNoLight_VS >1: 8,808 |

- **Every other Specular and Specular_back capture has the same count ring
  on and off.**
- **All 233 captures of 12 guard suites are byte-identical ring on vs off**
  (`onoff.py g3off g3on`). The suites: Lighting range, accumulation, control,
  spotlight, normals and Two Sided; Material color, color source and alpha;
  Fog gen, vsh and carryover.
- **How "off" was built:** the same tree with `reads_ring` forced false in
  `vsh.c`, then reverted and rebuilt.

Prediction: `docs/testing/predictions/ring53impl-ring.json`
(a `504aeee4d4` = master, b `b4fd40a16e`).
- **Movers:** `better=2`, `worse=0` over the disc.
- **Must-not-move:** the other captures, by glob.

Exact device values are not predicted: the desktop channel is GL on llvmpipe,
and its floors differ from the device's.

**Why attempt 2 did not finish.** It applied the boundary weights (`ef22e2a037`)
and re-derived all 33 rows exact. Then its session ended in the middle of the
guard-suite runs (`on-*`, 08:23). Those commits, and the master merge, were
left unpushed, and the prediction was never registered. The PR sat at
`fb06644cb1`.

### Attempt 2's blocker (superseded; kept for the record)

**Blocked, as the brief directs for a table that fails held out.** The
mechanism is implemented and validated end to end on the desktop channel.
The per-method weights reproduce every within-test step on silicon
exactly. They do not reproduce the absolute phase after a test boundary:
- with the console table as given, every first draw lands **3** slots off;
- after the one correction the data identifies, it lands **2** off;
- this holds on all 15 console cases and in both Specular suites.

What is wrong, and what is not yet separable:
1. **`SET_TRANSFORM_CONSTANT_LOAD` weighs 0, not the default +1.**
   - M7's setup adds exactly one of it to M0's.
   - M7 alone was off by 2 where every other case was off by 3.
   - Now applied, so M7 is no longer held out.
2. **The remaining −2 (mod 6)** is in a fixed harness set. Every observed gap
   carries it identically, in ringw and in Specular alike (`between.py` counts):
   - `WAIT_FOR_IDLE` ×3;
   - `FLIP_INCREMENT_WRITE` and `FLIP_STALL`;
   - `SET_CONTEXT_DMA_COLOR`;
   - `SET_TRANSFORM_EXECUTION_MODE`, `_PROGRAM_CXT_WRITE_EN`, `_PROGRAM_LOAD` and
     `_PROGRAM_START`.

   **Candidates are not all equal.** `WAIT_FOR_IDLE` alone cannot be it: three of
   them at weight 0 gives −3, not −2. The most economical reading is two of the
   single-count methods at 0, like `CONSTANT_LOAD`: for example, the program
   load and start pointers, which are front-end pointers of the same kind. That
   is a guess, and the brief rules out landing a guess.

**Nothing here should fold as a fix.** At the current phase, Specular and
Specular_back `ControlFlags_VS` read 0 of 9 ring-visible quads right each.
Today's own-vertex lighting reads 2 and 1. So there is no prediction, and the PR
stays draft with a `blocked:` comment.

**What unblocks it:** a console run in ringw's shape (`docs/lanes/xbox/ringweights.patch`,
about a minute). One single-quad lit VS draw per gap, with exactly one of the
following methods between draws, each written with the value it already holds:
- `WAIT_FOR_IDLE`;
- `SET_TRANSFORM_EXECUTION_MODE`;
- `SET_TRANSFORM_PROGRAM_CXT_WRITE_EN`;
- `SET_TRANSFORM_PROGRAM_LOAD`;
- `SET_TRANSFORM_PROGRAM_START`;
- `SET_CONTEXT_DMA_COLOR`;
- `SET_TRANSFORM_CONSTANT_LOAD` (confirms the 0).

Leave the flip pair out: a `FLIP_STALL` between draws waits for a flip. Its
weight follows from the residual once the other seven are known. Then:
1. set those weights in `pgraph_ring_weigh`;
2. re-run `dc_run.py ringw …` and `ring53_price.py --root build-linux/ring53runs/deskroot`;
3. expect all 15 ringw starts and all 18 Specular quads to equal silicon's.

Only then register the arm.

## 1. The method mapping: what each measured row is at pgraph's method hook

The ring counts **methods**: one per pushbuffer word, as pgraph dispatches
them. It does not count headers or words. Every row of the console table,
mapped to the words pgraph sees:

| console row | words pgraph sees | weight | how recognised |
|---|---|---:|---|
| NOP 0x100 | `NV097_NO_OPERATION` ×1 | 0 | listed as 0 |
| LIGHT_CONTROL, same value | `NV097_SET_LIGHT_CONTROL` ×1 | 0 | listed as 0 |
| empty BEGIN_END pair | `NV097_SET_BEGIN_END` ×2 | 0 | listed as 0 |
| per-vertex back colours (B1) | `SET_VERTEX_DATA4UB` + 4×attr (pbkitplusplus `nv2astate.cpp:693`) | 0 | in the vertex-data ranges, all 0 |
| COMBINER_COLOR_ICW, same value | 1 word | +1 | default |
| SPECULAR_ENABLE, same or toggled | 1 word | +1 | default |
| SET_TRANSFORM_CONSTANT vec4 | 1 header, 4 words at 0xB80..0xB8C | +1 | +1 on the vec4's 4th word only |
| one `pb_fill` | 2 headers, 5 words: CLEAR_RECT_HORIZONTAL, _VERTICAL; ZSTENCIL_CLEAR_VALUE, COLOR_CLEAR_VALUE, CLEAR_SURFACE (nxdk `pbkit_draw.c:51-59`) | 5 ≡ −1 | 5 words at +1 |
| MATERIAL_ALPHA_BACK + 6 SPECULAR_PARAMS_BACK (B3) | 7 headers, 7 words (`ringweights.patch`: seven `PushF`) | 7 ≡ +1 | 7 words at +1 |
| a vertex | counted at the draw's END | +1 each | `pgraph_glsl_ring_fill` returns the count |
| SET_TRANSFORM_CONSTANT_LOAD | 1 word, 0x1EA4 | 0 | inferred from M7; confirmed on silicon (ringw2 N7) |
| WAIT_FOR_IDLE | 1 word, 0x0110 | 0 | ringw2 N1 |
| SET_TRANSFORM_EXECUTION_MODE | 1 word | 0 | ringw2 N2 |
| SET_TRANSFORM_PROGRAM_CXT_WRITE_EN | 1 word | 0 | ringw2 N3 |
| SET_TRANSFORM_PROGRAM_LOAD | 1 word | 0 | ringw2 N4 |
| SET_TRANSFORM_PROGRAM_START | 1 word | 0 | ringw2 N5 |
| SET_CONTEXT_DMA_COLOR | 1 word | 0 | ringw2 N6 |
| FLIP_INCREMENT_WRITE + FLIP_STALL | 2 words | +2 together (default +1 each) | the boundary residual, once every other member was measured; only the sum is visible |

**Why methods, and not headers or words.**
- If each header weighed +1, a `pb_fill` (two headers) would weigh 2. It weighs 5.
- If each word weighed +1, the vec4 constant (four words) would weigh 4. It weighs 1.
- So the transform constant is the exception, one per vec4. That is the transform unit's
  128-bit write, which is committed on the fourth component.

**The zero-weight vertex-data ranges** are `0x1500..0x16CF` (SET_VERTEX3F through
SET_WEIGHT4F), `0x1800..0x181B` (ARRAY_ELEMENT16/32, DRAW_ARRAYS, INLINE_ARRAY), and
`0x1880..0x1AFF` (SET_VERTEX_DATA*). Each quad of the console run and of Specular
carries diffuse, specular, normal, texcoord and position per vertex, and steps exactly
4 (M0). So those writes weigh 0 and the vertex weighs 1.

**Unmeasured, carried by the default +1:** every other Kelvin method.
- The transform program upload (0xB00..0xB7F) is weighed like the constants, one per
  128-bit instruction. That is by analogy; it is not measured.
- Methods on other classes (2D surfaces, blit) weigh 0: they do not reach the 3D front end.

### Specular_back's +1, from the source

Between `ControlFlags_FF`'s last draw and `ControlFlags_VS`'s first lit draw,
`Specular_back` issues these methods that `Specular` does not
(`specular_back_tests.cpp` against `specular_tests.cpp`):
- `MakeFrontFaceFront`, 2, at the end of the FF test;
- `MakeBackFaceFront`, 3;
- `MATERIAL_ALPHA` and `MATERIAL_ALPHA_BACK`, 2;
- six `SPECULAR_PARAMS_BACK` interleaved with the six `SPECULAR_PARAMS` both issue, 6.

That is 13 ≡ **+1** mod 6: the measured offset, with no weight chosen for it.
`Light::Commit` pushes the three back light colours in both suites (pbkitplusplus
`light.cpp:26-28`), so they cancel. If the face-state methods weighed 0, the
offset would be 8 ≡ 2, which is wrong.

## 2. What is landed on the branch (the hunks)

- **`pgraph.h`:** `float ff_lit_ring[6][6][4]` (slot, attribute, xyzw) and
  `uint32_t ring_pos`, kept in 0..5. A free-running count would shift the phase
  at the 2³² wrap, since 2³² is not a multiple of 6.
- **`glsl/vsh.h`:** `DECL(S, ringInput, vec4, 36)`, `DECL(S, ringPhase, float, 1)`,
  and the prototype of `pgraph_glsl_ring_fill`.
- **`glsl/vsh.c`:**
  - `pgraph_glsl_ring_fill`, beside #41's `ff_radial_fog_coord`: an FF lit
    inline-buffer draw with no skinning writes its last `min(6, n)` vertices into
    slots `(ring_pos + i) % 6`, carrying v0, v2, v3, v4, v7 and v8. It returns the
    draw's vertex count for any draw kind.
  - The upload, beside #41's hook: `ringInput`, and `ringPhase = ring_pos` for a
    lit program draw from an inline buffer or inline array. Otherwise
    `ringPhase = -1`, and the draw keeps its own vertex's inputs. Only those two
    draw kinds index `gl_VertexIndex` from vertex 0 in both renderers
    (`vk/draw.c` inline path `vkCmdDraw(n, 1, 0, 0)`; `gl/draw.c:958-969`). An
    array or element draw's index is the guest's.
  - A `ringVertexIndex` define: `gl_VertexIndex` on Vulkan, `gl_VertexID` on GL.
- **`glsl/vsh-ff.c`, `pgraph_glsl_append_vsh_prog_lighting`:** `rV0`, `rV2`,
  `rV3` and `rV4` are taken from `ringInput[6 * ((ringPhase + ringVertexIndex) % 6) + k]`.
  They feed `tPosition`, `tNormal`, `ltDiffuse` and `ltSpecular`. The mux (`oD1 = v4`,
  `oB1 = v8`) and the constant term's alphas stay on the program vertex, and the
  fold uses the **reading** draw's `LIGHT_CONTROL` (lane.ring53 s2, Do not repeat).
- **`pgraph.c`:**
  - `pgraph_ring_weigh(pg, method)` is called for every word applied at all three
    dispatch sites: the lockless fast path, the `XEMU_OPT_METHOD_FAST_TABLE` block,
    and after each Kelvin handler, per consumed word.
  - At `SET_BEGIN_END` END: fill before `draw_end`, because `vk/draw.c` clears
    `inline_buffer_populated` while uploading. Then `ring_pos += n` after
    `draw_end`, so the draw's uniforms see the phase before its own vertices.
  - `vk/draw.c` is untouched.

State methods advance the ring **without writing a slot**. Whether silicon
overwrites a slot with a state token is not visible in any capture: every
measured window lies within one FF test's last six vertices, with nothing
weighted between them.

## 3. Priced held out, on the desktop channel

The desktop build is this worktree's (`dc_build.sh`, OpenGL on llvmpipe).
`dc_run.py` runs whole suites in order, so each FF test precedes its VS test
exactly as in the golden session. The per-draw phase was read two independent
ways, and they agree on every draw:
- a temporary method trace (`trace.patch`; `between.py` parses it);
- the **rendered images**, read with lane.ring53's `ring53_price.py`/`cf53_slots`
  and with the console run's own `ringw_score.py`.

The slot word read from our own `ControlFlags_FF` equals the golden's in both
suites (`LHHLLH`, `HLLHHL`).

**Relative structure: exact, everywhere.**
- Specular and Specular_back: every in-row step +4, and the row boundaries +2 and
  +3. Relative to row 3, row 1 sits at +1 and d09 at +4, as on silicon.
- **Specular_back = Specular + 1 falls out of the weights unaided.** The count
  in s1 is 13 ≡ 1.
- ringw: every leg of `ringw_score.py` holds on our images, with every weight
  exactly the console's (C0, P1, P2, R on all 15).

**Absolute phase (first draw after a test boundary):**

| row | silicon | table as given | + `CONSTANT_LOAD` = 0 |
|---|---:|---:|---:|
| Specular d04 / d09 / d12 | 3 / 2 / 4 | 0 / 5 / 1 | 5 / 4 / 0 |
| Specular_back d04 / d09 / d12 | 4 / 3 / 5 | 1 / 0 / 2 | 0 / 5 / 1 |
| ringw B1 B2 B3 C0 C1 C2 | 2 2 2 5 4 3 | 5 5 5 2 1 0 | 4 4 4 1 0 5 |
| ringw M0 … M8 | 4 1 1 1 4 1 0 1 5 | 1 4 4 4 1 4 3 5 2 | 0 3 3 3 0 3 2 3 1 |

- In the "as given" column, every row is silicon − 3, except M7, which is
  silicon − 2 (hence `CONSTANT_LOAD`).
- In the last column, every row is silicon + 2.
- Quads right: 0 of 9 in each Specular suite, against today's 2 and 1.

## 4. Must-not-move, and what would move each

- **FF-lighting captures.** The fill only copies state, and the consumer runs
  only under `!is_fixed_function && lighting`. Only a leak in `vsh.c`'s
  `pgraph_glsl_gen_vsh` gate would move them.
- **Lighting range and accumulation, and `Lighting_control` `_VS`.** No lit
  program draws, so nothing reads the ring. The same gate is the only way in.
- **`Specular*` `ControlFlagsNoLight_VS`.** Lit program draws that do read the
  ring, but no light is enabled. The colour material is `ALL_FROM_MATERIAL`, so
  `ltDiffuse`, `ltSpecular` and `tNormal` are all unread. The constant term's
  alphas stay own-vertex. They would move only if a colour-material source
  named a vertex colour.
- **#41 RADIAL fog.** `carriedFogCoord` is untouched. A lit program draw with
  RADIAL fog does move, but none is in #41's captures.

## Do not repeat

- **Do not add a constant to fix the absolute phase.** One constant does fit
  all 33 rows here, but those rows share one harness. A game's between-draw
  stream is not this harness, and the brief is right that it would be a fit.
- **Do not read "one per pushbuffer header".** A `pb_fill` refutes it: two
  headers, weight 5. Nor "one per word": the vec4 constant, four words,
  weight 1.
- **Do not suppose the desktop run's `skip_tests_by_default` narrows a suite.**
  `dc_run.py`'s config enables the suite, and every test runs. That is what
  keeps the FF→VS order the golden's, and it is why each run takes a minute.
- **To trace:** `git apply docs/lanes/ring53impl/trace.patch`, rebuild,
  `dc_run.py <tag> <Suite> --methods`, then `between.py build-linux/ring53runs/<tag>/ring.log [gap]`.
  Revert the patch before committing.

## Files

- `dc_build.sh`: builds this worktree's desktop binary into `build-linux/`.
- `dc_run.py`: runs a suite (or another ISO) on it and extracts the captures.
- `between.py`: the FF→VS gaps' weighed words from a traced run.
- `trace.patch`: the env-gated `RING53`/`RING53M` stderr trace.
- `runall.sh <prefix>`: Specular, Specular back, ringw and ringw2 in parallel.
- `starts.py <silicon console dir> <ours out dir>`: per-case window starts,
  read with `ringw_score.py`. The silicon dir is `.../console-run/console`;
  `console-run` itself reads 0 of 0.
- `runsuites.sh <prefix> 'Suite' ...`: whole suites, four at a time.
- `pxprice.py <tag> ...`: per-capture price against the goldens.
- `onoff.py <prefixA> <prefixB>`: a byte-level diff of two `runsuites.sh` sets.
