# Measuring rendering accuracy

Notes toward roadmap item 2: giving this project an oracle.

## Why this matters more than it sounds

Emulator work has no ground truth. Correctness means "behaves as the hardware
did", and for a commercial game whose source nobody has, that cannot be proved
— only observed, usually as a failure minutes into a session. Every graphical
fault here is currently reported as "this game looks wrong", which is not
something you can bisect, regress against, or close.

For the GPU, that problem is already solved by somebody else.

## What exists

| Repository | What it holds |
|---|---|
| [`abaire/nxdk_pgraph_tests`](https://github.com/abaire/nxdk_pgraph_tests) | A test program that builds to an Xbox disc image and runs on real hardware and emulators. 100 test source files: alpha func, antialiasing, attribute carryover and setters, blending, blend surfaces, bump mapping, bump env luminance, clears, texture formats, surface formats, combiners, vertex shaders. |
| `abaire/nxdk_pgraph_tests_golden_results` | Reference framebuffers **captured from real NV2A silicon**. |
| [`abaire/xemu-nxdk_pgraph_tests_results`](https://github.com/abaire/xemu-nxdk_pgraph_tests_results) | Results tracked across xemu versions, with `dev_scripts/compare.py` driving `perceptualdiff`, and a GitHub Action that runs the hardware comparison. |
| [`abaire/nxdk_vsh_tests`](https://github.com/abaire/nxdk_vsh_tests) | Vertex shader tests specifically. |

The hardware goldens are the part that cannot be reproduced without an Xbox and
a devkit. They are published.

## Getting the disc image

**Check the releases first.** `nxdk_pgraph_tests` publishes releases with
attached assets, most recently 2026-09-01. If a built disc image is among them,
everything below about toolchains is unnecessary — download it and skip to
running.

Building from source needs, per its README:

- The nxdk, as a submodule, from `abaire/nxdk` on the `nxdk_pgraph_tester`
  branch. The suite requires pbkit modifications the upstream nxdk does not
  carry, so a stock nxdk will not do.
- `pip3 install nv2a-vsh`, which assembles some test vertex shaders.
- A bootstrap pass: `./prewarm-nxdk.sh` builds every nxdk sample project to
  produce the libraries the toolchain needs.
- `git clone --recursive`, or `git submodule update --init --recursive`.

## The harness

1. Run the disc image under this build, on device.
2. Capture the framebuffers it writes.
3. Compare against the hardware goldens with the existing `compare.py` and
   `perceptualdiff` tooling, rather than writing new comparison code.
4. Once it runs unattended, add it to CI as a regression gate.

Step 3 is the point of the exercise: it turns "textures look wrong in some
games" into a named failing test with a pixel diff, which can be bisected,
assigned and closed.

## The experiment worth running first

This build already supports loading a custom Adreno driver
(`GpuDriverHelper`, via `libadrenotools`). With the suite running, compare
three ways:

- Stock Qualcomm driver against goldens
- A Turnip build against goldens
- The two drivers against each other

Output differing **between drivers** is a driver bug. Output identical between
them but diverging **from the goldens** is this emulator's translation of NV2A
state into Vulkan. Those two are routinely conflated and the distinction
decides who can fix a given fault.

Nobody has published NV2A accuracy figures for an ARM Xbox emulator, per driver
or otherwise.

## What this cannot catch

Framebuffer comparison sees rendering divergence. It is blind to the timing and
interrupt-ordering class of bug — a hang passes every pixel test it never
reaches. `FREEZE_ANALYSIS.md` documents one such freeze, chased through
thirteen eliminated hypotheses without a fix. That needs a different oracle:
a deterministic trace of the interrupt, PFIFO and VBLANK event stream, diffed
between desktop xemu and this build. See `ROADMAP.md` item 5.
