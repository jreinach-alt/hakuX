# Prediction: PVIDEO overlay size and pitch limits

Registered 2026-09-18 on `05e25ca29b` by `lane.cloud-110`, for issue #110,
**before any hardware run and before any emulator run**. Nothing in this file
has been measured.

Mechanism, candidate models and the reason each is worth distinguishing:
[`docs/investigations/2026-09-18-pvideo-overlay-limits.md`](../../investigations/2026-09-18-pvideo-overlay-limits.md).

**This prediction registers no arm and queues nothing.** It names no golden and
no `a_ref`/`b_ref`, because no capture path in this harness can see the
overlay: the goldens are PNGs the *guest* writes from its framebuffer, and the
overlay is composited downstream of that, at scanout. The hardware run this
file binds needs an **external** capture (capture card on the AV output, or a
camera); the emulator-side companion needs a **host-side** screenshot. Both are
outside `request.sh`. It is a registered expectation, not a queued A/B.

---

## 1. The run this binds

One nxdk binary. Display mode **640x480 progressive, 32bpp**. No pgraph disc,
no golden, no `nxdk_pgraph_tests`.

**Framebuffer:** solid blue `(0,0,255)` everywhere, except a banner in the top
32 rows in which the guest prints the program id and the ten register values it
just wrote. Per the harness's own rule about reading the label before believing
the diff: a photograph that does not carry its own program id is a photograph
of an unknown program.

**Source surface:** one contiguous physical allocation, 16-byte aligned,
**640 bytes per row x 256 rows = 163,840 bytes**, filled once at startup in
YUY2 (`CR8YB8CB8YA8`), 320 pixels wide. Its physical address is `BASE`.

**Source pattern**, designed so a photograph names the row and column it is
looking at:

| rows | content |
|---|---|
| 0-191 | luma ramp; columns 16-79 carry an 8-bit black/white bar encoding the row index |
| 192-199 | solid **magenta** -- the last legal rows under P3 |
| 200-238 | solid **green** -- the impossible rows |
| 239 | solid **cyan** -- the one-row discriminator for P3b |
| 240-255 | solid **green** |

and in every row: columns 0-15 solid **yellow** (the column-zero marker), a
black stripe every 16th column.

**Green is the impossible row.** It lies past every `LIMIT` any program sets
except P3b's, so its appearance is a positive fact about the hardware reading
past a limit, and its appearance in a program that never reaches past `LIMIT`
voids the session.

### Register values

`NV_PVIDEO` is BAR0 + `0x8000`; offsets below are BAR0-relative. Held constant
in every program unless the table overrides them:

    BASE      0x8900 = phys(src)
    OFFSET    0x8920 = 0
    LIMIT     0x8908 = 0x0002_7FFF      (640*256 - 1)
    POINT_IN  0x8930 = 0
    DS_DX     0x8938 = 0x0010_0000      (unity)
    DT_DY     0x8940 = 0x0010_0000      (unity)
    FORMAT    0x8958 = 0x0001_0280      (COLOR=1, DISPLAY=0 i.e. key off, PITCH=640)
    COLOR_KEY 0x8B00 = 0
    BUFFER    0x8700 = 1                (rewritten every field -- see R1)
    STOP      0x8704 = 1                (between programs)

| id | `SIZE_IN` | `SIZE_OUT` | `POINT_OUT` | `LIMIT` | `FORMAT` | what it probes |
|---|---|---|---|---|---|---|
| **P0** | `0x00C00140` 320x192 | `0x00C00140` 320x192 | `0x009000A0` (160,144) | `0x27FFF` | `0x00010280` | validity gate |
| **P1** | `0x00C00140` | `0x00C00140` | `0x009001E0` (480,144) | `0x27FFF` | `0x00010280` | destination past the right edge |
| **P2** | `0x00C00140` 320x192 | `0x006000A0` 160x96 | `0x009000A0` | `0x27FFF` | `0x00010280` | `SIZE_IN` > `SIZE_OUT`: crop or minify |
| **P3** | `0x00F00140` 320x240 | `0x00F00140` | `0x007800A0` (160,120) | `0x1F3FF` (200 rows) | `0x00010280` | source window past `LIMIT` |
| **P3b-a** | `0x00F00140` | `0x00F00140` | `0x007800A0` | `0x257FF` (640*240-1) | `0x00010280` | is `LIMIT` inclusive? |
| **P3b-b** | `0x00F00140` | `0x00F00140` | `0x007800A0` | `0x25800` (640*240) | `0x00010280` | P3b-a's control |
| **P4** | `0x00C00140` | `0x00C00140` | `0x009000A0` | `0x27FFF` | `0x00012280` pitch **8832** | field overflow, `FORMAT_PITCH` (13 bits) |
| **P5** | `0x00C0092C` width **2348** | `0x00C00140` 320x192 | `0x009000A0` | `0x27FFF` | `0x00010280` | field overflow, `SIZE_IN_WIDTH` (11 bits) |
| **P6** | `0xFFFFFFFF` | `0x00C00140` | `0x009000A0` | `0x27FFF` | `0x00010280` | our own FIXME |

The two overflow values are chosen so their **truncations are non-zero and
below the output size**: `8832 & 0x1FFF = 640` (the correct pitch),
`2348 & 0x7FF = 300` (below `SIZE_OUT`'s 320). Section 4 explains why any other
choice makes the program carry no information.

**Run protocol.** Each program is held for 3 seconds with its banner on screen,
and **P0 is re-applied between every pair**:

    P0, P1, P0, P2, P0, P3, P0, P3b-a, P0, P3b-b, P0, P4, P0, P5, P0, P6, P0

That alternation is not tidiness. Model **D**'s signature is "no overlay",
which is also the signature of a crashed test program, a wrong `BASE`, a
capture card on the wrong input and a dark display. A blank frame is only
readable as D when the P0 either side of it, in the same session, showed the
pattern.

**P7 -- readback, and it needs no capture path at all.** After writing each
program and again at the end of its 3 seconds, read all ten registers back and
print them over the debug channel, `BUFFER` included.

---

## 2. What each candidate model predicts, per program

**C** = hard clamp (saturate to the largest legal value, overlay still shown).
**W** = silent wrap (low bits only; addresses wrap within `BASE..LIMIT`).
**D** = disabled (the illegal program shows no overlay at all).
**X** = none of the three; the named concrete form is *fetch continues past
`LIMIT`*.
**M0** = what this tree does today, derived from the code at
`gl/display.c:314` / `vk/display.c:1339`, not measured.

| | **C** | **W** | **D** | **X** | **M0 (incumbent)** |
|---|---|---|---|---|---|
| **P0** | pattern at (160,144), rows 0-191, no green | same | same | same | same |
| **P1** | source cols 0-159 at x=480-639; **nothing at x=0-159** | same, **plus cols 160-319 at x=0-159** | no overlay | -- | as C |
| **P2** | *(this axis is crop-vs-minify, not C/W/D)* -- crop: source rows 0-95 cols 0-159 at 1:1, yellow marker 16 px | -- | no overlay | minify: all 192 rows in 96, yellow marker 8 px | **crop** |
| **P3** | rows 200-239 repeat source row 199: the **magenta band grows from 8 to 48 rows** | rows 200-239 show source rows 0-39: **the row bars restart at 0** | no overlay | rows 200-239 are **green** | **abort** (assert `gl/display.c:400`) |
| **P3b-a** | `LIMIT` inclusive -> 240 rows, bottom row cyan. `LIMIT` exclusive -> row 239 per this column's P3 rule | same split | same split | same split | **abort** (implements `LIMIT` as exclusive) |
| **P3b-b** | 240 rows, bottom row cyan | same | same | same | 240 rows, bottom row cyan |
| **P4** | pitch 8191: rows step 8191 B, image **sheared**, and past `LIMIT` by row 20 -> this column's P3 rule compounds | **byte-identical to P0** | no overlay | pitch 8832: sheared differently | **identical to P0** |
| **P5** | width 2047 -> capped to `SIZE_OUT` -> **plain 320-wide crop, no yellow at the right edge** | width 300 across 320 destination columns -> destination columns 300-319 re-sample source columns 0-19, so **the yellow column-zero marker reappears at screen x=460-475** | no overlay | width 2348 -> capped -> **same picture as C** | as W |
| **P6** | 2047x2047 -> capped -> **identical to P0** | same as C | no overlay | -- | **no overlay** |

Two entries in that table are the reason it is worth running:

- **P4's W cell is "identical to P0"**, and no other model predicts that. It is
  the cleanest single discriminator in the set, because its *correct-looking*
  picture is the positive result.
- **P3 splits all four ways**, with four visually unmistakable outcomes
  (magenta band / bars restart / blank / green). If only one program can be
  captured, capture P3.

---

## 3. Confirmation criteria -- what the capture must show

A model is **confirmed** only by the whole row, not by one agreeing cell.

| model | confirmed only if |
|---|---|
| **C** | P3 shows a 48-row magenta band **and** P4 is sheared **and** P5 is a plain 320 crop **and** P1 has no left-edge tail |
| **W** | P3's row bars restart at 0 **and** P4 is indistinguishable from P0 **and** P5 repeats the yellow marker at screen x=460-475 **and** P1 shows the tail at x=0-159 |
| **D** | P3, P4 and P5 all blank, **with the flanking P0 showing the pattern in the same session and its banner legible in the same frame** |
| **X** | anything else. The named concrete form is green in P3 |

**A mixture is an expected outcome, not a failed run.** Nothing requires one
policy on all axes: "field decode truncates, address handling clamps" is a
perfectly ordinary piece of silicon, and would read as P4 -> W with P3 -> C.
Registering the three as exclusive would be the mistake -- so they are
registered per axis, and the honest report of a mixture is the mixture.

**And these three may not be exhaustive.** X is registered as a first-class
outcome with its own visible signature precisely so that "none of the above"
cannot be quietly rounded to the nearest model.

### Emulator-side predictions, derived from the code and device-free

These need no hardware at all -- a desktop build under lavapipe with a
host-side screenshot settles every one, and that is the cheapest next unit on
this issue. They are derived by reading, not measured, and are registered so
that reading can be scored.

| | prediction |
|---|---|
| **E1** | P3 and P3b-a **abort the emulator** at `assert(offset + in_pitch * in_height <= limit)` (`gl/display.c:400`, `vk/display.c:1417`). Registered as a process death, not a picture. Asserts are live in Android release builds: `-UNDEBUG` at `android/app/src/main/cpp/CMakeLists.txt:918` |
| **E2** | P4's screenshot is **byte-identical** to P0's, both renderers |
| **E3** | P6 shows **no overlay**, both renderers |
| **E4** | P5 repeats the yellow marker at screen x=460-475, **both** renderers (GL takes the default `GL_REPEAT`, Vulkan sets `VK_SAMPLER_ADDRESS_MODE_REPEAT` at `vk/display.c:237`) |
| **E5** | P2 shows the **crop**, not the minify |
| **E6** | P1 shows **no** tail at x=0-159 |

E2 and E4 are the ones that would be surprising if they failed: both follow
from `GET_MASK` and the sampler address mode with no arithmetic in between.

### Readback (P7): what it can and cannot settle

| readback shows | conclusion |
|---|---|
| `SIZE_IN` reads `0x00C0012C` after P5 wrote `0x00C0092C` | the register drops bits above the field. **W confirmed at the register level; C and "more bits than documented" are dead for that field**, with no capture at all |
| `SIZE_IN` reads back `0x00C0092C` unchanged | the register stores all 32 bits. **This settles nothing about the display**: C, W, D and X all survive it |

Stated before it is believed, per the harness's own rule: a full-width readback
proves the register *holds* the bits and says nothing about what scanout does
with them. Readback is decisive in one direction only.

---

## 4. Falsifier: which programs carry no information, and why

The expensive part of this run is the capture rig. Programs are nearly free.
So the question worth answering in advance is which programmed sizes would
**agree across all candidate models** and therefore buy nothing.

1. **Any fully legal program.** P0 and, say, a 640x480 fullscreen overlay are
   predicted identically by C, W, D, X and M0. P0 earns its place as the
   validity gate and nothing else does. *Do not spend capture time on a second
   legal program.*

2. **Any `SIZE_IN` width whose truncation is at or above `SIZE_OUT` width.**
   This retires the obvious family -- the one #110's own text implies. Program
   width 2048, 3000, 4095 or 0xFFFF against `SIZE_OUT` = 320 and **C, W and
   "more bits than documented" all produce the same 320-wide crop**, because
   every one of those values exceeds the output size and the `IN > OUT` rule
   collapses them. On a 640-wide display, **no programmed source width above
   640 is distinguishable from any other**. The value has to truncate *below*
   the output size to say anything, which is why P5 uses 2348 and not 2048.

3. **Any value whose truncation is exactly zero.** `SIZE_IN` width 2048 ->
   0: a zero-width overlay and a disabled overlay are the same blank screen, so
   **W and D coincide**. Round powers of two are the worst possible choice for
   an overflow probe here, and they are the first thing anyone reaches for.

4. **`SIZE_OUT` past the display with `POINT_OUT` = 0.** Clamp-to-display and
   clip-at-the-edge produce the same picture when the rect starts at the
   origin. The discriminating form needs a non-zero `POINT_OUT` so a wrapped
   tail has somewhere else to appear -- which is P1, and is the only reason P1
   sets x=480.

5. **P3b-b.** Predicted identically by every model and by both readings of
   `LIMIT`. It exists solely as P3b-a's control and carries nothing on its own.
   It is also the cheapest program in the set and must not be dropped: without
   it, P3b-a's blank or short overlay has no reference.

6. **Anything with the color key on or a non-unity `DS_DX`/`DT_DY`.** Not
   uninformative -- *confounded*. Both move the same pixels the size rule
   moves, and the scale factor feeds the `IN > OUT` cap arithmetic directly, so
   a non-unity scale makes every axis ambiguous at once. They deserve their own
   session.

So the capture budget is: **P3 first** (four-way split), **P4 second**
(the only model that predicts "looks correct"), **P5 and P2 third** (one bit
each, and P2 settles a comment in our source), then P1, P6, P3b as the
cheap remainder. P0 is not optional at any point.

---

## 5. Validity gates -- what voids the session

| | gate |
|---|---|
| **V0** | P0 must show the pattern at **every** alternation. If any P0 is blank, every "no overlay" reading in that session is void: a dead instrument and model D are indistinguishable |
| **V1** | P7's readback must show the programmed values still standing at the moment of capture. If the kernel or any other code re-programmed PVIDEO underneath the test, the photograph is of a different program than the banner claims |
| **V2** | **Green must not appear in P0, P1, P2, P4, P5 or P6.** None of those reaches past `LIMIT` under any model. Green there means the source pattern or `BASE` is wrong, and the whole session is void rather than interesting |

## 6. Known risk to the run

**R1 -- `BUFFER_0_USE` may self-clear on hardware.** Our model is sticky:
`pvideo_read()` returns the stored word and nothing clears the bit but an
explicit `STOP`. The existence of `NV_PVIDEO_INTR_BUFFER_0` suggests hardware
raises an interrupt when it consumes a buffer, which would mean a real title
re-arms every field and a one-shot write shows the overlay for a single field
-- indistinguishable, in a photograph, from model D.

Mitigation: the test program writes `BUFFER` every field regardless, so it is
robust either way, and P7 reports whether the bit cleared. **If it does clear
on hardware, that is a finding about our device model** independent of
everything else in this file.

---

## 7. Outcome

Not run. No hardware, no capture path, no emulator run. This section is left
for whoever runs it, and the rule that applies is the one that applies to every
prediction here: score against the table above rather than rewriting the table
to match what came back.
