# Asking the emulator what it drops on the floor

Added 2026-09-12. `docs/investigations/issue-19-isolation-2026-09-12.md` put ten
features on the board by showing which tests render another test's image. This
answers the complementary question directly, in register numbers, without
inferring anything from pixels.

## Why it was invisible

`pgraph_method`'s fallthrough calls `trace_nv2a_pgraph_method_unhandled`. That
goes through QEMU's trace framework, which **does not reach logcat on Android**
— so a method we do not implement is dropped in complete silence. For an
accuracy question that is the worst available failure mode, because "we ignore
it" and "the guest never sends it" are indistinguishable from outside.

The fallthrough now also logs to `hakuX-unhandled`, one line per distinct
(class, method) pair so a suite hammering an unimplemented method logs once
instead of thousands of times.

## First run: `Image blit`, 41 captures

```
class 0x0019 method 0x0000 param 0x00014d40   (sub 5)
class 0x0019 method 0x0300 param 0x00000000   (sub 5)
class 0x0019 method 0x0304 param 0x01000100   (sub 5)
class 0x0039 method 0x0000 param 0x00014cf0   (sub 2)
class 0x0039 method 0x0180 param 0x00011190   (sub 2)
class 0x0072 method 0x0000 param 0x00014d60   (sub 7)
class 0x009f method 0x0184..0x0198 (six)      (sub 3)
class 0x0097 methods 0x09f8 0x16bc 0x1710 0x1d80 0x1d84  (sub 0)
```

**The clip rectangle is confirmed, with its values.** Class **0x19** is the NV
clip-rectangle object; `0x300` is its point and `0x304` its size. The guest
binds the object, sets the point to **(0, 0)** and the size to **0x01000100 —
256 × 256** — and we discard all three methods. That is exactly what #19's
isolation pass pointed at from the other direction: all six `ImgBlt_Clip_*`
tests render the *unclipped* blit, 6 for 6. Two independent methods, same
answer, and this one names the registers.

No clip-rectangle class is defined in `nv2a_regs.h` at all, so this is not a
handler with a gap — the object is simply absent.

**Five 3D methods are undefined too.** `NV097` `0x09f8`, `0x16bc`, `0x1710`,
`0x1d80`, `0x1d84` do not appear in our register header under any name. They
are sent during this suite's setup with small parameters (1, 4, 0). What they
are is not established here and is not worth guessing: the point is that the
inventory exists and can be looked up deliberately.

**Class 0x39 is `NV_MEMORY_TO_MEMORY_FORMAT`**, which the header defines but
`pgraph_method` has no case for — so its object binding and `0x180` are
dropped. Class **0x72** is not in the header. And six consecutive `NV_IMAGE_BLIT`
methods, `0x184` through `0x198`, are dropped, all carrying the same parameter
`0x14d30`, which is the shape of a run of context-object bindings.

## Why this is worth keeping

One log line per pair, one run per suite, and the output is a list of things
the guest asked for and did not get — with no sampling, no statistics and
nothing to misread. Tonight three of my own mechanisms died to better
measurements; this is the opposite kind of evidence, and it should be run over
every suite in the corpus before anyone infers another mechanism from pixel
differences.

The obvious next step is exactly that: one pass per suite, collecting the
union. `Image blit` alone named fifteen dropped methods.

## Second run: `Blend tests`, and a clean negative

Ran the 2025 oracle disc with the log armed — roughly 450 of its 1,568 tests
before the timeout, across every unsigned and signed equation.

**Nothing new appeared.** The log holds exactly the startup set from the
`Image blit` run — class 0x39's two methods and the five undefined `NV097`
methods — and not one additional pair in ~450 blend tests.

So **every method the blend tests use is one we handle**, and the fifth-quad
defect is *not* a dropped method. That eliminates the whole class of
"unimplemented register" explanations for it and narrows the search to our
handling of methods we do accept: state tracking, draw batching, or the
surface and blend pipeline. Given that three mechanisms for this region have
already died, a negative that removes an entire class is worth more than
another candidate.

## A constraint on the 2025 disc worth knowing

`skip_tests_by_default` with per-test `{"skipped": false}` entries **does not
work on the 2025 XBE** — the config is newer than the binary. Naming four tests
ran all 1,568. Suite-level selection (`--suite "Blend tests"`) is honoured;
per-test selection is not. So on that disc the unit of work is a whole suite,
which also means `make_isolation_discs.py`'s single-test discs cannot target
it.

## Third pass, 2026-09-12: identification without a device

The plan was one dispatcher run per suite, collecting the union. That is
blocked on the harness (see the last section), so this pass instead does what
needs no device: identify the numbers already captured, from the test repo's
own sources. The other lane's trick generalises — a suite that tests a method
usually names it, and the constants it pushes are defined in `pbkitplusplus`.

Everything below is labelled, because the whole value of this document is that
it does not infer:

* **MEASURED** — read off a device run's log or a scored TSV in `docs/testing/`.
* **DOCUMENTED** — a file on disk states it literally; the path and line are
  given so it can be re-read.
* **INFERRED** — reasoning from documented facts. Not established. Says so.
* **UNKNOWN** — nothing on disk names it.

Sources searched: `/home/justin/nxdk_pgraph_tests` (the test corpus we run),
`/home/justin/pbkitplusplus` (its helper library, which defines the constants
nxdk is missing), and our own `hw/xbox/nv2a/nv2a_regs.h`.

A limit worth recording first: **`nxdk_pgraph_tests/third_party/nxdk` is an
uninitialised submodule**, and so are `pbkitplusplus`, `fpng`, `printf` and
`tiny-json` under `third_party/`. nxdk's real `pbkit/nv_regs.h` and
`nv_objects.h` — where most `NV097_*` numbers and every `GR_CLASS_*` live — are
therefore **not on disk anywhere**. The only `nv_regs.h` present is a 23-line
host-test stub. That is why several methods below are named but not numbered:
the test source pushes `NV_IMAGE_BLIT_PATTERN`, and the value is in a submodule
we never checked out. Anyone continuing this should check that submodule out
first; it is the single highest-value thing available for this question.

### The five undefined NV097 methods

| Method | Identity | Basis |
|---|---|---|
| `0x09f8` | `NV097_SET_SWATH_WIDTH` | **DOCUMENTED** twice: `nxdk_pgraph_tests/src/tests/swath_width_tests.h:10` ("Tests the behavior of NV097_SET_SWATH_WIDTH (0x09f8)") and `pbkitplusplus/src/nxdk_ext.h:175` (`#define NV097_SET_SWATH_WIDTH 0x000009f8`) |
| `0x16bc` | glEdgeFlag | **DOCUMENTED**: `nxdk_pgraph_tests/src/tests/edge_flag_tests.h:10` ("Tests behavior of 0x16BC - glEdgeFlag") |
| `0x1710` | **UNKNOWN** | No occurrence of `1710` in any form in either tree, or in `nv2a_regs.h` |
| `0x1d80` | **UNKNOWN** | idem |
| `0x1d84` | **UNKNOWN** | idem |

On the last three, one thing is worth writing down precisely so nobody has to
re-derive it and nobody mistakes it for a finding. The nearest named registers
are `NV097_SET_ZMIN_MAX_CONTROL` at `0x1D78` and `NV097_SET_SMOOTHING_CONTROL`
at `0x1D7C` (`pbkitplusplus/src/nxdk_ext.h:122`), so `0x1d80` and `0x1d84` are
the next two 4-byte slots after a register we do know. That is **adjacency, not
evidence** — there is no base-plus-offset macro anywhere that lands on either,
and an adjacent slot in this space is as likely to be an unrelated register as
a continuation. `0x1710` has no neighbour at all: the nearest defines are
`NV097_SET_WEIGHT3F` at `0x16B0` below and `NV097_SET_SCENE_AMBIENT_COLOR_BACK`
at `0x17A0` above, 0x90 away. These three stay UNKNOWN, and the honest next
step for them is the nxdk submodule or an envytools `rnndb` lookup, not a
guess.

Note also that all three arrive in the **startup** set — they appeared in both
the `Image blit` and `Blend tests` runs — and nothing in the test corpus pushes
them. So they come from pbkit's own initialisation, whose source is exactly
what the empty submodule is hiding.

### The 2D blit classes

`nxdk_pgraph_tests/src/tests/image_blit_tests.h:11-13` documents the whole
group in its class comment: *"Tests behavior of the 2D blitting commands. NV09F, NV012,
NV019, NV072."* That names three of the four classes in our capture.

* **Class 0x19 is `NV01_CONTEXT_CLIP_RECTANGLE`** — **DOCUMENTED** by use:
  `image_blit_tests.cpp:273` creates it (`pb_create_gr_ctx(channel++,
  GR_CLASS_19, &clip_rect_ctx_)`) and `:317-318` pushes
  `NV01_CONTEXT_CLIP_RECTANGLE_SET_POINT` then `..._SET_SIZE` to it. The
  numeric offsets `0x300`/`0x304` are **not** on disk, so name-to-number is
  INFERRED from that push order — but it is inference that has since been
  *tested*: implementing point at `0x300` and size at `0x304` took all six
  failing `ImgBlt_Clip_*` tests to zero differing pixels (below). A mapping
  that makes six oracle comparisons exact is no longer a guess.
* **Class 0x72 is `NV072_BETA_4`, the RGBA blend factor object** —
  **DOCUMENTED** literally: `pbkitplusplus/src/nxdk_ext.h:51`, `#define
  NV072_BETA_4 0x00000072  // RGBA factor`. Its sibling on the next lines is
  `NV012_BETA 0x00000012  // Alpha factor`, and both expose `SET_BETA` at
  `0x300`. We drop class 0x72's object binding (method `0x0000`).
* **Two of the six dropped `NV_IMAGE_BLIT` methods are named.**
  `pbkitplusplus/src/nxdk_ext.h:45-46` gives `#define NV_IMAGE_BLIT_SET_BETA
  0x0194` and `#define NV_IMAGE_BLIT_SET_BETA4 0x0198` — **DOCUMENTED**, and
  they are the top two slots of the measured `0x184..0x198` run.
* **The other four are INFERRED as context-object slots, not identified.**
  `image_blit_tests.cpp` pushes exactly six context-object names to class 0x9F
  — `CLIP_RECTANGLE`, `PATTERN`, `ROP5`, `COLOR_KEY`, `BETA`, `BETA4` — and the
  measured run is six consecutive 4-byte slots whose last two are the two named
  ones. So the first four slots being the first four names, in some order, is a
  tight fit. It is still inference: no file on disk gives `0x184`, `0x188`,
  `0x18c` or `0x190` a name, and the fit does not fix the order.

  What *is* MEASURED and does support the reading: all six carried the same
  parameter `0x14d30`, which is a handle rather than a value — the shape of
  context-object binding, not of blit geometry. Consistently, `SET_BETA` and
  `SET_BETA4` take handles to the NV012 and NV072 objects, and we drop the
  NV072 binding too.
* **Class 0x39 stays as first recorded**: `nv2a_regs.h` defines
  `NV_MEMORY_TO_MEMORY_FORMAT` and `pgraph_method` has no case for it. Nothing
  in the test corpus mentions class 0x39 at all — no `NV039`, no `M2MF` — so
  this too is a startup-set drop.

Class **0x62** is worth a line for the contrast: `texture_framebuffer_blit_tests.cpp`
pushes `NV10_CONTEXT_SURFACES_2D_*` to it heavily and it **never appears in the
unhandled log**. The log distinguishes handled from dropped, which is the
property that makes it worth running.

### Cross-reference: does a suite test what we drop, and what does it score?

Two of the named methods have a dedicated suite. Both fail, and both were last
measured before today. Suite names in results use underscores; the string in
the source is `"Swath width"` / `"Edge flag"`.

| Suite | Method it tests | Last MEASURED score |
|---|---|---|
| `Swath_width` | `NV097_SET_SWATH_WIDTH` `0x09f8` | 0/6 exact, 88,788 px (`sweep-2026-09-08-scores.tsv`) |
| `Edge_flag` | glEdgeFlag `0x16bc` | 0/2 exact, 5,376 px (`sweep-2026-09-08-scores.tsv`) |
| `Image_blit` | classes 0x19 / 0x9F / 0x72 | **15/41 exact** (`run-2026-09-12-image-blit-clip.tsv`), was 9/41 |
| `Texture_Framebuffer_Blit` | class 0x19 clip rect, same pair | 0/3 exact, 44,793 px (`sweep-2026-09-08-scores.tsv`) |
| `Smoothing_control` | `0x1D7C`, the slot below `0x1d80` | 0/2 exact, 160,218 px |
| `ZMinMaxControl` | `0x1D78` | 0/32 exact, 617,241 px (`run-2026-09-12-issue19-g0-scores.tsv`) |

**`Swath_width` carries the signature of a dropped parameter.** Its six tests
sweep the swath width (`SwathWidth00` through `SwathWidth0F`) and five of the
six have *byte-identical* residuals on 2026-09-07 — 14,798 differing pixels,
`max_rgb` 163, `max_a` 61, the same in every row — while in today's
residual-class pass all six are identical (92,375 differing channels, 6,699
plus-one, 65,023 minus-one, 424 boundary-shift). Varying the parameter changes
our output not at all. That is what dropping `0x09f8` predicts, and it is
MEASURED. It does not prove the suite fails *only* because of the drop.

**`Edge_flag`'s two tests differ from each other** — 3,051 px for `Disabled`,
2,325 for `Enabled`. That is *not* evidence against the drop: each test is
scored against its own golden, so rendering one identical image for both
naturally yields two different residuals. The comparison that would settle it
is our `Enabled` capture against our `Disabled` capture, which is not something
the score TSVs hold. Recorded as undetermined rather than either answer.

**The #47 fix, measured end to end.** Six `ImgBlt_Clip_*` tests, before and
after implementing class 0x19:

```
ImgBlt_Clip_300_200_16_24     16,000 -> 0
ImgBlt_Clip_320_240_0_0       16,384 -> 0
ImgBlt_Clip_320_240_0_10      16,384 -> 0
ImgBlt_Clip_320_240_1_1       16,383 -> 0
ImgBlt_Clip_320_240_640_480   12,288 -> 0
ImgBlt_Clip_320_240_64_40     13,824 -> 0
```

`Image_blit` went 9/41 to 15/41 exact: exactly the six, nothing else moved.
`ImgBlt_Clip_0_0_640_480` was already exact before the fix, which is the
control — a clip rectangle covering the whole surface clips nothing, so
dropping it was invisible there.

**The unmeasured beneficiary.** `texture_framebuffer_blit_tests.cpp:121-123`
pushes the *identical* sequence — `NV01_CONTEXT_CLIP_RECTANGLE_SET_POINT`,
`..._SET_SIZE`, then `NV_IMAGE_BLIT_CLIP_RECTANGLE` — and every one of its
three tests takes `clip_x/clip_y/clip_width/clip_height` parameters. So
`Texture_Framebuffer_Blit` is a second consumer of the #47 fix and **has not
been re-measured since**: its last number, 0/3, predates the fix by four days.
That is the cheapest outstanding measurement in this document, and per the
stale-capture rule its old row currently reads exactly like a live defect.

## The harness cannot return this log, and that blocks the sweep

The plan — one dispatcher run per suite, collect the union — cannot be executed
as the harness stands. Recording it here rather than working around it, because
the workaround is touching the device directly and that is the one thing the
dispatcher exists to prevent.

**`docs/testing/dispatcher.sh` never invokes `adb logcat`.** `serve_one` builds
the ref, installs, then runs `make_test_iso.py` -> `run_disc.sh` ->
`score_sweep.py`, and `run_disc.sh` does not capture logcat either. A result
directory holds `captures*/`, `scores*.tsv`, `result.json`, `run*.log`,
`suites.txt` and `DONE` — verified against the two result directories that
exist, and `find` over the whole dispatch tree matches no logcat artifact at
all. So a request returns scores, and `hakuX-unhandled` is discarded with the
device state.

No request was queued. Without the log a run would only re-deliver scores
already on disk, while preempting the 4.5-hour sweep for nothing.

The precedent for the fix is already in the tree three times over:
`docs/testing/perf/run_perf.sh:66,84` clears logcat and dumps by tag,
`docs/testing/drivers/run_driver_ab.sh:19,22` does the same for
`hakuX-stderr`, and `docs/testing/boot-test.sh:36,49` for `-b all`. The
proposal, in the order it should be done:

1. **Capture in `run_disc.sh`, not in the dispatcher, and stream it.**
   `run_disc.sh` owns the device lifecycle — it starts the activity, waits, and
   force-stops in a trap — so it is the only place that knows the window. It
   should take the tags from an environment variable, default empty so existing
   behaviour is untouched, start `adb logcat -s <tags>` redirected to a file
   just after `am start`, and kill that streamer in `release()`.

   Streaming rather than a `logcat -d` dump afterwards, for a reason this
   repository has already paid for: `docs/investigations/galleon-flashing-deck.md:144`
   records the logcat ring evicting the lines of interest from a capture. A run
   here can take the full 1,800s and is followed by a ~1.5GB pull that can take
   another 600, so a dump at the end is a dump after the ring has turned over.
   The startup-set lines, which are the ones that appear first, are exactly the
   ones that would be lost.

2. **Write it into the result directory in `dispatcher.sh`**, next to
   `scores1.tsv`, and note the tags in `result.json` so a result records
   whether the log was collected. A result whose log was silently not captured
   must not be indistinguishable from a suite that dropped nothing — that is
   the same failure this whole document is about, one level up.

3. **Then raise the dedupe cap, or report when it is hit.** The log site keeps
   `static struct { uint32_t cls, method; } seen[64]` (`hw/xbox/nv2a/pgraph/pgraph.c:1951`).
   `Image blit` alone found 15 distinct pairs. A many-suite disc — the entire
   point of the sweep — can plausibly pass 64, and past that the table stops
   suppressing while the log keeps printing, so the suite that overflows it
   floods and evicts the pairs already recorded. The table is never reset, which
   is right for a per-run union; the cap is what needs attention. Cheapest
   correct fix is a one-line warning when it fills, so a flood is
   distinguishable from a genuinely large set rather than looking like noise.

Until step 1 exists, this document can grow by identification but not by
measurement, and the fifteen pairs from `Image blit` plus the clean negative
from `Blend tests` remain the entire measured corpus.
