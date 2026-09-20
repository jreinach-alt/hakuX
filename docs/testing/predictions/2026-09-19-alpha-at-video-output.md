# Prediction: does the framebuffer's alpha reach the video output?

Registered 2026-09-19 on `9472a18d33` by `lane.cloud-111`, for issue #111,
**before any hardware run and before any emulator run**. Nothing in this file
has been measured.

Severity reasoning and the code-side enumeration this rests on:
[`docs/investigations/2026-09-19-alpha-at-video-output-severity.md`](../../investigations/2026-09-19-alpha-at-video-output-severity.md).

**This prediction registers no arm and queues nothing.** It names no golden,
no `a_ref` and no `b_ref`, and it is deliberately a `.md` and not a `.json`.
Every capture in this harness is a PNG the *guest* writes by reading surface
memory back; the video output is downstream of the framebuffer and the guest
cannot read back what the RAMDAC emitted — on hardware or here. A `.json`
registered for this question would queue an arm that captured **the
framebuffer twice** and reported a confident zero about a channel it never
looked at. The run this file binds needs an **external** capture on the AV
output (capture card, or a camera) and is outside `request.sh`.
`lane.cloud-110` reached the same wall for the PVIDEO overlay
(`docs/lanes/cloud-110/NOTES.md`).

---

## 0. The claim, restated so that it can fail

#111: "the NV2A's video output path discards the framebuffer's alpha channel;
what reaches the encoder is RGB."

**As written this is not directly observable, and that has to be said before
any program is designed.** The encoder emits no alpha channel, on either
model. A capture of the video output therefore cannot show alpha *arriving*;
it can only show alpha *having had an effect*. The testable form is:

> **No stage between the framebuffer and the encoder reads the framebuffer's
> alpha byte.**

The NV2A output path has four stages that touch the framebuffer word. Each is
named here with what it would show, so that a null result is attributable to
a stage rather than to the whole path:

| stage | reads alpha under the "alpha reaches" model? | observable |
|---|---|---|
| CRTC pixel unpack (32bpp) | it would have to, to pass it on | flat-field difference — **P1** |
| PVIDEO colour-key comparator | compares the framebuffer word against `NV_PVIDEO_COLOR_KEY` | overlay shows / does not show — **P2** |
| hardware cursor blend | **no** — NV-class cursor blends on the *cursor's* alpha, not the framebuffer's | none. Named so nobody spends a program on it |
| palette / gamma LUT | 8bpp indexed modes only; not reachable at 32bpp | none at the modes under test |

## 1. The run this binds

One nxdk binary, display mode **640x480 progressive, 32bpp**. No pgraph disc,
no golden, no `nxdk_pgraph_tests`. Each program holds the frame for 5 seconds
and prints its own program id in a banner in the top 32 rows, in a region
cleared under `A8R8G8B8` with alpha `0xFF` in every variant — so the banner is
a constant across variants and cannot be confused with the measurement.

For every program, **two captures**:

- **capture F (framebuffer):** the guest reads the scanout surface back and
  writes a PNG, the ordinary golden path.
- **capture V (video output):** an external capture of the AV output while
  that same frame is held.

## 2. P1 — the format pair: the brief's literal program

**Two variants, RGB identical by construction, alpha the only variable.**

| variant | surface format | pad alpha | clear |
|---|---|---|---|
| **P1z** | `SCF_X8R8G8B8_Z8R8G8B8` | `PAD_ALPHA_ZERO` → `0x00` | `0x00808080` |
| **P1o** | `SCF_X8R8G8B8_O8R8G8B8` | `PAD_ALPHA_ONE` → `0xFF` | `0x00808080` |

These are the same two formats this board already measured in the hardware
goldens, which is why this pair and not an `A8R8G8B8` surface with two clear
alphas: `Clear::TestSurfaceFmt` gives **98,342 px differ, RGB IDENTICAL,
alpha 255 against 0**, 16,368 px per clear colour across all six clear
colours (`vk/draw.c:705-726`). **So the framebuffer half of P1's positive
control is already on disk, taken on hardware.** Capture F is still taken, on
the scanout surface rather than on `Clear`'s 128x128 scratch one, but it is
confirming a known result rather than establishing a new one.

### What each model predicts

| | capture F (P1z vs P1o) | capture V (P1z vs P1o) |
|---|---|---|
| **alpha reaches the output path** | differ: alpha `0x00` vs `0xFF`, RGB identical | **differ somewhere** — any visible difference at all, in a frame whose RGB is identical by construction |
| **alpha does not reach** | differ: alpha `0x00` vs `0xFF`, RGB identical | **identical** — mid-grey in both, to within the capture's noise floor |

### P1 is the weak program, and the reason is the instrument

Capture V goes through composite/YPbPr encoding, 4:2:2 chroma subsampling and
the capture device's own quantisation. **It cannot resolve a small RGB
difference in a flat field.** P1 therefore discriminates only if the "alpha
reaches" model produces a *large* difference; a null P1 bounds the effect at
the capture's noise floor and does not exclude a small one. State the measured
noise floor with the result or P1 is uninterpretable.

This is the reason P2 exists.

### The void program, named so nobody runs it

**A single flat cleared field, captured on the video output, discriminates
nothing.** Both models predict the same picture: RGB in, RGB out. It is the
obvious first program and it is worth zero. P1 is that program made
informative *only* by the second variant holding RGB byte-identical while
alpha moves, and even then it is limited by the paragraph above. A result
reported from one variant alone is void.

## 3. P2 — the colour-key program: the discriminator

Binary rather than graded, which is what makes it survive the encoder.

**Setup, identical in both variants:**
- Scanout surface `SCF_A8R8G8B8` (`PAD_ALPHA_NONE`: alpha is guest-set, not a
  pad constant, and nothing in the path substitutes for it).
- Clear the whole surface to RGB `0x2040C0`, the key colour.
- PVIDEO programmed with a solid **bright yellow** YUY2 source over the full
  640x480 output rectangle, colour keying **enabled**
  (`NV_PVIDEO_FORMAT_DISPLAY`), `NV_PVIDEO_COLOR_KEY = 0x002040C0` — alpha
  bits of the key register **zero**.

**The variable:**

| variant | framebuffer clear word | framebuffer alpha |
|---|---|---|
| **P2a** | `0x002040C0` | `0x00` — equal to the key register's alpha bits |
| **P2b** | `0xFF2040C0` | `0xFF` — differs from the key register's alpha bits |

### What each model predicts

| | capture V, P2a | capture V, P2b |
|---|---|---|
| **the comparator masks alpha** (this tree's model: `gl/display.c:221`, `vk/display.c` `& 0xFFFFFF`) | overlay shows: **full-screen yellow** | overlay shows: **full-screen yellow** |
| **the comparator compares the full 32-bit word** | overlay shows: **full-screen yellow** | overlay does **not** show: **full-screen blue** `0x2040C0` |

Yellow against blue, full screen, is far above any analogue capture's noise
floor. **P2b is the whole measurement; P2a is its positive control** — if P2a
does not show yellow, the overlay was misprogrammed and P2b says nothing
about alpha. A P2b reported without P2a is void.

### What P2 does and does not settle

P2 settles **one stage**: the colour-key comparator. It is the stage this tree
already takes an unsourced position on, at two sites, which is why it is worth
the run on its own. A null P2 (both yellow) confirms the masking those two
sites assume and is evidence *for* #111's premise — but it is evidence about
the comparator, **not** about the CRTC unpack. Do not report a null P2 as
"alpha does not reach the encoder, confirmed". Report it as "the colour-key
comparator does not read alpha; the unpack stage is bounded only by P1's noise
floor."

## 4. P3 — a non-constant alpha

`SCF_A8R8G8B8`, one clear per variant, alpha `0x00` / `0x40` / `0xC0` / `0xFF`
with RGB held at `0x2040C0` throughout, colour keying **disabled**, PVIDEO
**off**.

- **alpha does not reach:** all four capture Vs identical.
- **alpha reaches and modulates:** a monotonic ramp across the four.

P3 costs one extra minute in the same session and is the only program that
would catch an output path that *scales* RGB by alpha rather than keying on
it. Same noise-floor caveat as P1: report the floor or it is uninterpretable.

## 5. The falsifier, in the brief's own terms

- **If "alpha reaches the encoder" is TRUE:** the video-output capture shows
  the surface's actual non-`1.0` alpha having an effect somewhere — P1's two
  variants differ in a frame whose RGB is byte-identical, **or** P2b loses the
  overlay P2a keeps, **or** P3 ramps.
- **If it is FALSE:** no trace of alpha in capture V anywhere, at any alpha
  value, in any program, while capture F shows the alpha byte differing by the
  full `0x00`/`0xFF` range in the same frames.

**The conjunction is the measurement.** A run in which capture F does *not*
show the alpha difference has not confirmed anything — it has failed to
establish that the alpha was ever there, and the null capture V is then
explained by the framebuffer and not by the output path. That is this
project's impossible-row discipline applied to a capture rather than to a
prediction leg: **a leg that cannot fail discharges nothing**, and "the video
capture showed no alpha" is exactly such a leg without capture F beside it.

## 6. What this run is worth to #89, decided in advance

So that the result is not read for more than it holds:

- **Confirmed (alpha does not reach):** #89's residual is exempted from
  direct scanout **only**. It stays live on destination-alpha blending, on
  surface-as-texture readback, on alpha test downstream of that, and on guest
  CPU readback — four of five consumers, none of them downstream of the
  framebuffer. See the investigation's table. #89's severity drops by one
  bucket, not to zero.
- **Refuted (alpha reaches):** #89's residual is additionally player-visible
  through scanout, and this tree's PVIDEO colour-key masking at
  `gl/display.c:221` and `vk/display.c` is a defect of its own needing its own
  row.
- **Either way:** the 141,125 is still wrong against a framebuffer golden made
  the same way on hardware, and this run moves that number by zero. #111 says
  so itself.
