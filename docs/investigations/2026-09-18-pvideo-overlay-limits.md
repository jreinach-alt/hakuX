# PVIDEO overlay limits: the overlay is implemented, and its limit handling is three unsourced hardware claims

Issue #110, 2026-09-18, `lane.cloud-110`. No device, no code change. The
companion registered expectation is
[`docs/testing/predictions/2026-09-18-pvideo-overlay-size-pitch-limits.md`](../testing/predictions/2026-09-18-pvideo-overlay-size-pitch-limits.md).

## The premise this issue was filed on is wrong

#110 says:

> **State in this tree:** absent. `hw/xbox/nv2a/pvideo.c` is 77 lines of
> register read/write stubs: no overlay size cap, no pitch handling, no overlay
> composition at all.

The first clause is right about `pvideo.c` and wrong about the tree. PVIDEO
overlay composition is implemented in **both** renderers, in the display path
rather than in the device model:

| what | GL | Vulkan |
|---|---|---|
| decode the registers | `pgraph/gl/display.c:314` `render_display_pvideo_overlay()` | `pgraph/vk/display.c:1339` `get_pvideo_state()` |
| YUY2 -> RGBA | `convert_texture_data__CR8YB8CB8YA8()` `gl/display.c:287` | same name, `vk/display.c:137` |
| scale factor | `pvideo_calculate_scale()` `gl/display.c:306` | `vk/display.c:156` |
| composite | display fragment shader, `pvideo_enable` branch | `vk/display.c:350` fragment shader, same branch |

`pvideo.c` holds no composition because the composite happens at **scanout**,
which is the display code's job. The register file it keeps is the whole of its
job, and `pvideo_vga_invalidate()` is the hook that makes the display path
re-run. The two commented-out `d->vga.enable_overlay` lines and
`nv2a.c:1302`'s commented `vga->overlay_draw_line` are the corpse of the *old*
VGA-line-callback overlay, removed upstream by `48c1720da8` ("nv2a: Support
PVIDEO overlays again", 2021-03-01) when the composite moved into the renderer.
Reading those comments as "the overlay is off" is the trap; they mark the path
that was **replaced**, not the feature that is missing.

Three greps give three different answers here, and only the third finds it:

    grep -rn overlay hw/xbox/nv2a/          -> two dead comments
    grep -rn NV_PVIDEO hw/xbox/nv2a/*.c     -> pvideo.c only
    grep -rn convert_yuy2_to_rgb --include=*.c .   -> the implementation

So #110 is not "implement the overlay". It is **"the overlay model rests on
three claims about hardware that nothing has ever checked, and one of them is
enforced with an `assert`"** -- which is a smaller, sharper and much more
answerable issue.

## What the incumbent model actually does

Both renderers agree step for step; line numbers below are GL's, and the Vulkan
equivalents are in `get_pvideo_state()` within four lines of each other.

1. **Enable.** `enabled = (BUFFER & BUFFER_0_USE) && SIZE_IN != 0xFFFFFFFF`
   (`:328`). The second clause carries a FIXME in our own source saying it
   **does not match hardware**, kept because some title (Ultimate Beach Soccer)
   hides its overlay by an unknown mechanism.
2. **Decode.** Every field through `GET_MASK`, so bits above a field's mask are
   dropped at read: `SIZE_IN` width/height 11 bits each (max 2047), `SIZE_OUT`
   width/height 12 bits (max 4095), `POINT_OUT` X/Y 12 bits,
   `FORMAT_PITCH` 13 bits (max 8191). **The write side stores all 32 bits**
   (`pvideo.c:74`), so the emulator masks at decode, not at write.
3. **Scale.** `scale = (floor(din_dout * (out - 1) / 2^20 + 0.5) + 1) / out`,
   bypassed when `DS_DX`/`DT_DY` read exactly `0x00100000`.
4. **The size cap** (`:374-379`), with the comment that is the reason this
   issue exists:

   > `// On HW, setting NV_PVIDEO_SIZE_IN larger than NV_PVIDEO_SIZE_OUT`
   > `// results in them being capped to the output size, content is not scaled.`

   No citation, no capture, no test. It is also load-bearing in a second way
   the comment admits: it is what keeps `SIZE_IN = 0xFFFFFFFF` from producing a
   2047x2047 texture upload.
5. **The asserts** (`:400-402`):

       assert(offset + in_pitch * in_height <= limit);
       hwaddr end = base + offset + in_pitch * in_height;
       assert(end <= memory_region_size(d->vram));

   and one more at `:382`, `assert(in_color == NV_PVIDEO_FORMAT_COLOR_LE_CR8YB8CB8YA8)`,
   reachable by a guest writing any other value into `FORMAT`'s 2-bit COLOR
   field -- the same register write that carries the pitch.
6. **Clipping.** There is none, as such. The fragment shader tests each screen
   fragment against the output rect (`out_Color` untouched outside it), so a
   rect extending past the display is simply not drawn there. Nothing clamps
   `POINT_OUT + SIZE_OUT` to the display.
7. **Sampling past the source.** Both samplers are `REPEAT` (GL leaves the
   default; `vk/display.c:237` sets `VK_SAMPLER_ADDRESS_MODE_REPEAT`
   explicitly), and the shader divides by `textureSize`, so when `SIZE_OUT`
   exceeds `SIZE_IN` at unity scale **the source tiles**. That is a behaviour,
   not a guard, and nothing has checked it against hardware either.

### The abort is reachable, and release builds keep it

`assert(offset + in_pitch * in_height <= limit)` is a hard abort on values a
guest writes. Android **release** builds keep it: `-UNDEBUG` is applied to
`xemu_core` for `Release`, `RelWithDebInfo` and `MinSizeRel` at
`android/app/src/main/cpp/CMakeLists.txt:918`, and `hw` is in
`XEMU_CORE_DIRS` (`:382`), so both `display.c` files compile with asserts live.

Stated at its own size, and no larger: **a guest that programs a source window
larger than its own `BASE..LIMIT` window aborts the emulator.** That is a
denial of service by a title's own register writes, in a code path the goldens
never reach. It is not a memory-safety finding -- the assert is what *stops*
the out-of-bounds read, and the second assert bounds the same expression
against VRAM size. Turning asserts off is what would make it a safety
question, and this tree deliberately does not.

I did not file that as an issue: one unit per firing, and it wants its own row.
`NOTES.md` recommends the board split it out.

## What no instrument in this harness can see

Before any of this can be measured, the capture question has to be answered,
and the answer retires a whole approach.

**The harness's captures are PNGs the guest writes.** `nxdk_pgraph_tests` saves
its framebuffer to `e:\nxdk_pgraph_tests`, and `extract_results.py` pulls them
out of the HDD image afterwards. The overlay is composited **downstream of the
framebuffer**, at scanout, into the host display surface. So:

- **No pgraph golden can ever contain the overlay**, in this emulator or on
  silicon, and adding a test to `nxdk_pgraph_tests` does not change that.
- **The guest cannot read back what it programmed**, on hardware either. The
  RAMDAC composite is not visible to the CPU. So the hardware run needs an
  **external** capture: a capture card on the composite/component output, or a
  camera on a display.
- **The emulator side needs a host-side screenshot**, not a guest-side one.

If the overlay were being composited and we looked for it in the goldens, we
would find nothing -- and nothing is also what we would find if it were not
being composited at all. That is the shape AGENTS.md warns about, and it is why
#110 reads as "absent" in the first place: the instrument that would have shown
it was never able to.

**The one part that needs no capture path** is register readback. A guest can
read `NV_PVIDEO_*` back after writing it and print the values over the debug
channel. That settles whether the hardware *stores* out-of-range bits, with no
capture card and no photo. Its blind spot, stated before it is believed: a
full-width readback proves the register holds the bits and says **nothing**
about what scanout does with them, so all three display models survive it.
Readback is decisive in one direction only -- if readback shows truncation, the
wrap model is confirmed at the register level and the clamp model is dead for
that field, for free.

## The candidate models, and why these three

The question "what does hardware do past the limit" is not one question. It is
one question per axis, and the three models are the corners of the space:

| | **C (hard clamp)** | **W (silent wrap)** | **D (disabled)** |
|---|---|---|---|
| out-of-range field value | saturate to the field maximum | take the low bits (value mod 2^n) | refuse the program, show no overlay |
| source window past `LIMIT` | repeat the last legal row | address wraps to the window start | overlay off while the program stands |
| destination past the display | rect truncated at the edge | tail reappears at the opposite edge | overlay off |

**Why these are the ones worth distinguishing.** Each is the policy a different
plausible piece of silicon would have, and each implies a different one-line
fix in our own code:

- **C** is what a hardware block with saturating field decode does, and is what
  the incumbent's `in_width > out_width` cap already assumes on one axis. If C
  holds, the emulator's `GET_MASK` decode is wrong everywhere and the fix is a
  clamp at write.
- **W** is what a hardware block that simply wires N bits to the datapath does,
  and is what `GET_MASK` already implements. If W holds, the decode is right
  and the asserts are the only thing that needs replacing.
- **D** is what a block with a validity check does, and is the model our own
  `SIZE_IN != 0xFFFFFFFF` heuristic half-implements by accident. If D holds,
  that heuristic is a special case of a general rule and Ultimate Beach
  Soccer's "unknown mechanism" may stop being unknown.

**The enumeration is probably not exhaustive, and the axes need not agree.**
Nothing requires one policy across all five axes -- a real block can truncate a
field and clamp an address in the same frame. So the prediction registers
**per axis**, and registers a fourth outcome, **X**, explicitly: any result
matching none of the three, of which the most likely concrete form is *fetch
continues past `LIMIT`* (the overlay shows whatever VRAM holds there). The
programs are designed so X is visible rather than inferred.

A fifth thing that is not a model but is settled by the same run: the
incumbent's **crop-don't-scale** claim for `SIZE_IN > SIZE_OUT`. That is a
binary question (crop vs minify) orthogonal to C/W/D, and it costs one extra
program.

### D is the model that can be confirmed by a broken test

**D's signature is "nothing on screen", which is also the signature of a wrong
`BASE` address, a test program that crashed, a capture card on the wrong input,
and a display that is off.** So D cannot be confirmed by an illegal program
alone. The prediction's run protocol therefore alternates a legal program
between every illegal one, each labelled on screen by the guest, so that "no
overlay" is only readable as D when the legal program either side of it *did*
show one in the same session. That alternation is the instrument's positive
control, and without it every ambiguous result reads as a confirmation of D.

## What this costs and what it buys

Nine programs, one nxdk binary, one capture session of a few minutes, and no
pgraph disc. It buys: the first PVIDEO measurement this project has ever had, a
citation for a comment that currently has none, a decision on whether a
guest-reachable abort should be a clamp or a wrap, and an answer to a FIXME in
our own source. The programs that would *not* buy anything are enumerated in
the prediction, because the expensive part of this run is the capture setup and
the cheap part is programs.

## Not taken

- **Color keying.** `NV_PVIDEO_COLOR_KEY` and `FORMAT_DISPLAY` are a different
  axis with their own unsourced comment (`vk/display.c:1414`, "PVIDEO color
  keying ignores alpha"). Every program here runs with the key off so it cannot
  confound the size result.
- **Non-unity `DS_DX`/`DT_DY`.** Scaling feeds the size cap arithmetic
  directly, so a non-unity scale confounds every axis at once. Unity
  everywhere; the scale rounding deserves its own run.
- **The filter divergence.** GL takes `GL_LINEAR` for both filters (min set
  explicitly, mag by default); Vulkan sets `magFilter = LINEAR` and
  `minFilter = NEAREST` (`vk/display.c:235-236`). Real, but off this issue's
  axis and invisible at unity scale.
- **Whether `BUFFER_0_USE` self-clears.** Our model is sticky:
  `pvideo_read()` returns the stored word and nothing ever clears the bit
  except an explicit `STOP`. The existence of `NV_PVIDEO_INTR_BUFFER_0`
  suggests hardware signals buffer consumption, which would mean a title
  re-arms every field. The prediction's run protocol re-arms every field
  regardless, so it is robust either way, and the readback reports the answer
  as a side effect.
