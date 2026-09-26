# lane.ring53 -- #53: the six-entry ring of stale FF lighting outputs under a vertex program

Base: master @ 72b77d368a. Desktop only: no build, no device, no prediction.

**Outcome: blocked, on two counts.**
1. **The phase.** The absolute phase at the start of a vertex-program draw is
   not determined by the corpus. It depends on the command stream between
   draws, beyond the vertex count, and the per-method weights are not
   separable from the captures on disk (s3). Every phase rule tried scores at
   or below chance on held-out rows (s4). A designed console run settles it in
   about a minute (s6).
2. **The files.** The mechanism needs cross-draw host state. So it needs
   `pgraph.h`, `glsl/vsh.h` and `glsl/vsh.c`, plus a method hook for the
   phase counter. The two granted glsl files hold only the consumer (s2).

Nothing is landed. The granted `vsh-ff.c` hunk is useless without the host
side, and a phase guessed now would be a fit.

## 1. Where a VS-mode lit vertex gets its colour today

- `glsl/vsh.c:658` calls `pgraph_glsl_append_vsh_prog_lighting`
  (`glsl/vsh-ff.c:590`) when a vertex program runs with `LIGHTING_ENABLE`.
- That function runs the fixed-function light loop (`append_lighting`, the
  same code the FF path uses) on **the program vertex's own inputs**:
  - `tPosition = v0 * modelViewMat0`;
  - `tNormal = v2 * invModelViewMat0`;
  - `ltDiffuse = v3`, `ltSpecular = v4`;
  - for the back side, the same with `-tNormal`.
- It then applies the SEPARATE_SPECULAR mux (`oD1 = v4`, `oB1 = v8`).
- `vsh-prog.c` has no lighting code. Its only role is the program body that
  runs before this block.

**Silicon instead** (PR #355, PR #351): each lit vertex takes the lighting
result of one of the preceding FF draw's last six vertices. Holders and
consumers of what that needs:

| what | where it would live | holder today |
|---|---|---|
| the last six FF-lit vertices' lighting inputs (v0, v2, v3, v4, v7, v8) | `PGRAPHState`, beside `last_ff_radial_fog_coord` (`pgraph.h:357`) | unclaimed, not granted |
| filling it from each FF-lit draw | `pgraph_glsl_set_vsh_uniform_values` (`glsl/vsh.c:1083`), beside #41's hook | unclaimed, not granted |
| the uniforms (`ringInput[36]`, `ringPhase`) | `VSH_UNIFORM_DECL_X` (`glsl/vsh.h:96`) | unclaimed, not granted |
| the phase counter's advance per command | `pgraph_method` dispatch (`pgraph.c`) | unclaimed (no row holds it on `origin/board` today), not granted |
| the consumer: light-loop inputs from ring slot `(ringPhase + vertex index) % 6` | `pgraph_glsl_append_vsh_prog_lighting` (`glsl/vsh-ff.c:590`) | **granted** |

**The inline buffer is still live when uniforms are set.** `vk/draw.c:7868`
calls `begin_pre_draw`, which updates uniforms, before anything resets
`inline_buffer_length`. So `vsh.c` can copy the draw's last six vertices from
`pg->vertex_attributes[a].inline_buffer`. Array draws have only
`inline_value`, the last vertex (the same limit #41 documents).

## 2. The design, cheapest faithful

**Carry the lighting unit's inputs, not its outputs, and run the existing
loop on them under the reading draw's state.** The goldens say the mux runs
at read time, which is what makes this faithful:
- In `Specular::ControlFlags_VS`, the diffuse row 3 quads d12 and d13
  (SEPARATE_SPECULAR set) show the **unfolded** low green (about 10), as their
  own FF quads do.
- The ring's source vertices are the FF test's d14 and d15. There,
  SEPARATE_SPECULAR is clear, so their FF output is folded (green about 22).
- So the ring holds diffuse and specular separately. The fold and the
  substitution use the **reading** quad's `LIGHT_CONTROL`.
- Recomputing from carried inputs gives exactly that, provided the light,
  material and FF-matrix registers are unchanged between the two draws. They
  are unchanged in every capture that shows the ring.

**Hunks:**
- **`pgraph.h`:** `float ff_lit_ring[6][6][4]` (slot, attribute, xyzw), and
  a `uint32_t ring_pos` counter.
- **`glsl/vsh.h`:** `DECL(S, ringInput, vec4, 36)` and
  `DECL(S, ringPhase, float, 1)`. `VSH_UNIFORM_DECL_X` declares no int
  uniform today, so the shader converts it with `int()`.
- **`glsl/vsh.c`, in `pgraph_glsl_set_vsh_uniform_values`:**
  - For an FF draw with lighting and SKINNING_OFF, copy the last `min(6, n)`
    vertices into the slots they occupy, `(ring_pos + i) % 6`.
  - For a VS draw with lighting, upload the ring and `ringPhase = ring_pos`.
  - Advance `ring_pos` by the draw's vertex count after either.
- **`pgraph.c`:** advance `ring_pos` by each method's weight (s3).
  **Unknown until s6 runs.**
- **`glsl/vsh-ff.c`:** in `pgraph_glsl_append_vsh_prog_lighting`:
  - declare `int ringSlot = (ringPhase + gl_VertexIndex) % 6` (`gl_VertexID`
    on GL);
  - build `tPosition`, `tNormal`, `ltDiffuse` and `ltSpecular` from
    `ringInput[6 * ringSlot + k]` instead of `v0`, `v2`, `v3` and `v4`;
  - leave the mux's `oD1 = v4` / `oB1 = v8` on the program vertex's own
    colours. That is the lighting-off path, which is measured separately.
  - `pgraph_prim_rewrite_sequential` keeps `gl_VertexIndex` as the vertex's
    index within the draw, including for QUADS.

**It does not fit in the two granted files.** `vsh-prog.c` needs no hunk.

## 3. What the corpus says about the phase

Reproduce with `python3 docs/lanes/ring53/ring53_price.py` (goldens). It
reads rows 1 and 3 (diffuse) and row 2's d09 (the separate specular, green).
The per-corner dump is `cf_corners.py`.

`p` is the window start into the slot word, which is the last six FF vertices
oldest first.

| draw | `Specular` p | `Specular_back` p |
|---|---:|---:|
| d04 d05 d06 d07 (row 1, diffuse) | 3 1 5 3 | 4 2 0 4 |
| d09 (row 2, separate specular) | 2 | 3 |
| d12 d13 d14 d15 (row 3, diffuse) | 4 2 0 4 | 5 3 1 5 |

**New: the separate specular output reads the ring too.** `Specular_back`
d09 reads HHLH. That is a 3-1 code, not the quad's own LHHL. `Specular`'s d09
happens to land on the window equal to its own code. So the ring carries the
specular term as well as the diffuse.

**The within-test structure is identical in the two suites.** Relative to
row 3's frame (+4 per quad):
- row 1 sits at **+1**;
- row 2 sits at **+4 (≡ −2)**;
- this holds in both suites.

Per 4-vertex quad the step is exactly +4 in each row, so the vertices alone
account for it. At the row boundaries, the pushbuffer between rows adds more
(one method per `pbkitplusplus` block):

| boundary | methods added beyond the quads | phase moved beyond +4 per quad |
|---|---|---:|
| row 1 → row 2 | `COMBINER_COLOR_ICW`, `COMBINER_ALPHA_ICW`, `SPECULAR_ENABLE` | +3 |
| row 2 → row 3 | `COMBINER_COLOR_ICW`, `COMBINER_ALPHA_ICW` | +2 |

"+1 per state method" fits both boundaries. It cannot also fit the quads:
- Each quad carries `SET_LIGHT_CONTROL` and a `BEGIN_END` pair besides its
  vertices, and moves exactly +4.
- So those three writes weigh 0 mod 6, while the combiner and
  `SPECULAR_ENABLE` writes weigh +1.
- Nothing on disk separates "LIGHT_CONTROL and BEGIN_END weigh 0" from other
  weightings that sum to 0.

**Between tests, the label text is a candidate.** `pb_draw_text_screen` draws
each glyph row run as a `pb_fill`. That is 5 method writes, and it is a
clear. `textfills.py` counts the fills exactly:
- `L0_FF` 38, `L1_FF` 35;
- `ControlFlags_FF` with its six labels, 595.
- "Each fill moves the phase −1 (≡ 5 writes at +1 each), plus a constant C = 2"
  fits L0 by construction and L1 (3 ✓). It also fits `Specular` row 1, which
  chose the weight among the odd ones.
- The fog-ring repeat (PR #346 follow-up) independently named the label as a
  candidate: "the phase is set by the work between tests".

**What stays unexplained:** `Specular_back` sits **+1** from `Specular`
throughout, with byte-identical labels and the same draw sequence. The only
in-test differences are in the VS preamble: back material alpha, back
specular params, back light colours, and `MakeBackFaceFront`. Any of those
could be the +1, and I cannot tell which.

## 4. Priced, held out

"Right" means the rule's predicted window start equals the measured one.
There are 9 ring-visible quads per suite.

| rule | fitted on | `Specular` | `Specular_back` | held-out rows right |
|---|---|---:|---:|---|
| own normal (hakuX today) | -- | 2 | 1 | -- |
| ring, start = VP vertices since the FF write | litprime L0 | 4 (row 3) | **0** | 1 of 5 (S row 3) |
| ring + label fills at −1 + C | L0, L1, S row 1 | 4 (row 1) | 4 (row 3) | 1 of 4 (B row 3) |
| ring, measured phases (ceiling) | -- | 9 | 9 | -- |

- **Chance.** With the six windows distinct, a random rule gets a row right
  1 time in 6.
- **The better rule's held-out score is at chance.** It also turns
  `Specular` d09, right today, wrong.
- **The first rule regresses `Specular_back`** from 1 to 0.

In pixels, as an estimate only: I did not re-derive the per-quad costs. They
come from #53's comment on the z-after-057/058 captures (APK `553cfffc73d3`,
older than today's master).
- A wrong lit quad costs about 7,500 to 8,500 px, and a right one about 330
  (`Specular` q31) to 2,100 (`Specular_back` q11).
- So each rule row moved from wrong to right is worth about −30,000 px.
- The oracle ceiling is roughly −64,000 px (`Specular`) and −60,000 px
  (`Specular_back`), against #53's own ~64,200 px share per suite.
- The ring's value is all in the phase. A ring at the wrong phase is no
  better than today's own-normal lighting, and on `Specular_back` it is
  worse.

## 5. Must-not-move, and what would move each

- **FF-lighting captures** (no vertex program): not reached. The consumer
  hunk is inside `pgraph_glsl_append_vsh_prog_lighting`, which only runs for
  programmable draws with `LIGHTING_ENABLE`. The FF fill in `vsh.c` changes
  no FF output.
- **`Lighting_range`, `Lighting_accumulation`, `Lighting_control` `_VS`:**
  - They have no program with lighting on (`Lighting_control`'s VS captures
    push `LIGHTING_ENABLE false`), so they are not reached.
  - Any of them moving would mean the gate in `vsh.c:658` leaked.
- **`Specular*` `ControlFlagsNoLight_VS`:** the ring holds the constant term
  only, the same in every slot, so there is no pixel change.
  - If they move, the carried v3/v4 differ from the program's own and reach
    the constant term through a colour-material source. That would be a
    design error in which inputs to carry.
- **#41 RADIAL fog:** untouched. The design leaves `carriedFogCoord` alone.
  One ring should serve both eventually. The fog scene's period 6 in quad
  index fits this model: a per-quad constant upload weighs an odd amount.
  I have not priced that here.

## 6. What unblocks it

**The phase (a console run, lane.xbox, about a minute).** PR #355's priming
design, varied along one axis per test:
1. **Priming.** FF, two quads, eight distinct N·L, exactly as `litprime`.
2. **Measure each method's weight.** Draw six single-quad VS draws, with
   exactly one extra method between draws k and k+1. Use one method per test
   from this list:
   - a NOP (`0x100`);
   - `COMBINER_COLOR_ICW`;
   - `SPECULAR_ENABLE` (same value, and toggled);
   - `LIGHT_CONTROL`;
   - one `pb_fill`;
   - one `SET_TRANSFORM_CONSTANT` vec4;
   - an empty `BEGIN_END` pair.
   Each window start reads directly, so each method's weight is the step
   minus 4.
3. **The between-test constant.** Run 0, 1 and 2 `pb_fill`s between the
   priming draw and the first VS draw, with no label text in either test
   (`pb_erase_text_screen` before `FinishDraw`).
4. **Front against back.** Run step 2 once more with `MakeBackFaceFront` and
   the back material and specular writes as the only extra methods. That
   names `Specular_back`'s +1.

**Then the files.** Grant `pgraph.h`, `glsl/vsh.h` and `glsl/vsh.c` (all
unclaimed), and `pgraph.c` for the method hook. The hunks are in s2.

**The arm, once both land:**
- mover: `Specular` and `Specular_back` `ControlFlags_VS`, toward their
  quantisation floor;
- must-not-move: the s5 list;
- check each row's `status` for `unreadable` and PARTIAL COVERAGE, because
  the labels overlap quads d04, d07, d12 and d15 (their plane-fit residuals
  run 40–140).

## Do not repeat

- **Do not fit one constant phase to these captures.** Row 1 and row 3 of
  the same test need different constants, and the two suites differ by one
  with identical sequences. A constant is right on at most one row, 4 of the
  9 quads per suite. The constant litprime L0 gives is right on 0 of 9 in
  `Specular_back`.
- **Do not carry the lighting outputs post-mux.** Row 3's d12 and d13 show the
  mux runs with the reading quad's `LIGHT_CONTROL` (s2).
- **Do not assume the specular output is own-vertex.** `Specular_back` d09
  reads a 3-1 window.
- **`Lighting_control` is not in #53's scope.** Its `_VS` captures are
  lighting-off, as #53's comment of the landed mux fix already says.

## Files

- `ring53_price.py`: the per-quad window starts and the rule scores (s3, s4).
- `cf_corners.py`: per-corner RGBA plane fits for all 16 quads of any
  ControlFlags capture.
- `textfills.py`: the exact `pb_fill` count `pb_draw_text_screen` issues for a
  label.
