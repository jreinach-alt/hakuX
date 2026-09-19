# lane.cloud-110 -- PVIDEO overlay size/pitch limits

Issue #110. Cloud lane, no device, no code change (the brief bars
`hw/xbox/nv2a/pvideo.c`).

## The headline, before anything else

**#110's premise is wrong, and the correction changes what the hardware run is
for.** The issue says overlay composition is "absent" and that
`hw/xbox/nv2a/pvideo.c` being 77 lines of register stubs means "any title that
relies on the overlay path is drawing something the emulator never models."

The overlay is implemented. It is not in `pvideo.c` -- it is in the renderer
display path, in both backends:

- `hw/xbox/nv2a/pgraph/gl/display.c:314` `render_display_pvideo_overlay()`
- `hw/xbox/nv2a/pgraph/vk/display.c:1339` `get_pvideo_state()`

`pvideo.c` is register plumbing by design; the composite happens at scanout,
which is why it lives with the display code. So this issue is not "implement
the overlay". It is "the overlay model contains three unsourced claims about
hardware and one guest-reachable abort", which is a smaller and much more
tractable thing.

## What that means for the deliverable

The brief asked for the registered expectation a hardware run would need. That
is still the deliverable and it is written, but the table now has a fourth
column that costs nothing: **what the incumbent emulator does**, derived from
the code rather than measured. A hardware run that disagrees with that column
names a defect in a specific line.

Files:

- `docs/investigations/2026-09-18-pvideo-overlay-limits.md` -- the candidate
  models, why these are the ones worth distinguishing, what the incumbent does
  at each limit, and what no instrument in this harness can see.
- `docs/testing/predictions/2026-09-18-pvideo-overlay-size-pitch-limits.md` --
  eight overlay programs with exact register values, each model's predicted
  clipping behaviour for each, and the information content of each program.

## What the next lane should not repeat

- **Do not grep `pvideo.c` and conclude the overlay is unmodelled.** Three
  separate greps here (`overlay`, `NV_PVIDEO`, `convert_yuy2_to_rgb`) give
  three different answers, and only the third finds the implementation.
- **Do not plan a pgraph golden for this.** The harness's captures are PNGs the
  *guest* writes from the framebuffer, extracted from the HDD image. The
  overlay is composited downstream of the framebuffer, at scanout. No golden in
  this harness can ever contain it, on hardware or in the emulator -- and the
  same is true of the guest on real silicon, which cannot read back what the
  RAMDAC composited. This is why #110 has no golden, and adding a test to
  `nxdk_pgraph_tests` does not fix it.
- **The emulator half needs no device at all.** Every program in the prediction
  can be run against the desktop build under lavapipe with a host-side
  screenshot, filling the incumbent column by measurement instead of by
  reading. That is the cheapest next unit and it is not blocked on anything
  except the `libcurl4-openssl-dev` desktop-build gap AGENTS.md already names.

## Recommend to the board

1. Rewrite #110's body: the gap is not "no overlay", it is "unverified overlay
   limit semantics". Recommend against closing -- the hardware question is real
   and unanswered.
2. Split out the abort as its own issue. `assert(offset + pitch * in_height <=
   limit)` at `gl/display.c:401` and `vk/display.c:1417` is reachable from
   guest register writes, and `-UNDEBUG` at
   `android/app/src/main/cpp/CMakeLists.txt:918` keeps asserts live in Android
   **release** builds, so it aborts rather than degrades. I did not file it
   myself: one unit per firing, and it wants its own row.
