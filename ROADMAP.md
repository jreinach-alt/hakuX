# Roadmap

Where this fork is going, why in that order, and what is deliberately not being
attempted.

## The problem this is organised around

Emulators are hard to improve because there is no oracle. Correctness means
"behaves as the hardware did", and for a commercial game whose source nobody
has, that cannot be proved — only observed, usually as a failure some minutes
into a session. That is why emulators take decades and why every mature one
carries per-game workarounds. `hw/xbox/game-compat.c` already contains one.

So the ordering below is not by importance. It is by what makes the next thing
measurable.

## 1. Make releases and builds repeatable

**Status: partly done.**

- [x] Persistent release signing, so releases upgrade in place instead of
      costing users their saves ([`android/RELEASING.md`](android/RELEASING.md))
- [x] Own application id, so this fork cannot damage an official install
- [x] Crash diagnostics no longer silenced by the app's own log filter
- [ ] **`subprojects/nv2a_vsh_cpu.wrap` pins a revision that does not exist
      upstream**, so a clean checkout cannot configure. This blocks CI, which
      clones fresh.
- [ ] **Android CI.** The existing workflows build Linux, macOS and Windows;
      the Android port — the reason this project exists — is never compiled.
      That is how a dead subproject pin, a machine-specific JDK path and an
      unvalidated frontend integration all shipped.

Highest value per hour on the list, and everything after it depends on knowing
the build still works.

## 2. Build the oracle

**Status: not started. The hard part is already done by someone else.**
Groundwork and open questions: [`docs/testing/pgraph-harness.md`](docs/testing/pgraph-harness.md).

[`abaire/nxdk_pgraph_tests`](https://github.com/abaire/nxdk_pgraph_tests) is a
test program that runs on real Xbox hardware and on emulators, covering texture
formats, vertex shaders, surface formats, combiners and blending.
`nxdk_pgraph_tests_golden_results` holds reference framebuffers **captured from
real NV2A silicon**, and
[`xemu-nxdk_pgraph_tests_results`](https://github.com/abaire/xemu-nxdk_pgraph_tests_results)
tracks xemu against them with a comparison tool and a GitHub Action.

Hardware ground truth is the one thing that cannot be produced without an Xbox
and a devkit. It exists and is published.

- [ ] Run the suite on this build, on device
- [ ] Wire its output into the existing comparison tooling against the goldens
- [ ] Publish the first accuracy figures for an ARM Xbox emulator — nobody has
      them
- [ ] Add it to CI as a regression gate

Step three is worth more than any amount of new code. It converts "textures
look wrong in some games" into a named failing test with a pixel diff.

## 3. Video

**Status: waiting on the oracle.**

Graphical faults live in the translation from NV2A state into Vulkan or GLES,
not in the GPU driver. NV2A's pixel stage is fixed-function register combiners,
which have no modern equivalent and must be compiled into shaders — a lossy
translation of hardware that is only partly documented. XboxDevWiki's own
combiner page records open questions about it.

- [ ] With the suite running, A/B the stock Qualcomm driver against a Turnip
      build. Output differing **between drivers** is a driver bug; output
      identical between them but diverging **from the goldens** is xemu's
      translation. That separates two layers that currently get conflated.
- [ ] Work the failing tests by how often the affected feature is used
- [ ] Establish what `shaderTessellationAndGeometryPointSize` being unavailable
      on Adreno actually costs — it is the one feature the Vulkan probe reports
      missing

## 4. Audio

**Status: under-emulated, and off by default.**

The Xbox APU is custom silicon: a voice processor plus two Motorola DSP56K-family
cores running proprietary microcode. xemu emulates the DSP by adapting Hatari's
DSP56001 implementation. `use_dsp` defaults to **false** here, so those
processors do not run at all.

- [ ] Establish *why* it is off — correctness, performance, or crashes
- [ ] Profile the DSP core on ARM
- [ ] Fix, optimise, or document as a limitation, on the evidence

## 5. Timing

**Status: hardest, deliberately last.**

`FREEZE_ANALYSIS.md` documents a freeze chased through thirteen eliminated
hypotheses without a fix. The guest parks in a kernel halt loop with no PGRAPH
interrupt pending, and the same build runs correctly on desktop xemu. It is an
interrupt delivery and ordering divergence, not a clock-rate one — running the
CPU at exactly 733 MHz would not touch it.

Framebuffer comparison cannot see this class of bug: a hang passes every pixel
test. It needs a different oracle.

- [ ] A deterministic trace harness: identical input, log the interrupt, PFIFO
      and VBLANK event stream on desktop xemu and here, diff, find the first
      divergence
- [ ] That is also the point at which real hardware would earn its cost, since
      no goldens exist for timing

## Not being attempted

**A rewrite, or a "native ARM" emulator.** hakuX already emits native ARM64:
QEMU's TCG translates x86 basic blocks to ARM64 machine code
(`tcg/aarch64/tcg-target.c.inc`). The gap against a mature emulator is JIT
*quality*, not architecture. Closing it means writing a purpose-built
x86-to-ARM64 recompiler — compiler engineering with a brutal oracle problem —
and would discard the NV2A emulation, which is the hard and valuable part.

**Anything derived from leaked material.** The XDK and Xbox source have leaked
more than once. Using them is not a grey area next to emulation: emulation
itself is settled law, and reverse engineering for interoperability has
appellate precedent behind it, while copying source nobody licensed to you does
not. Work built on a leak cannot be upstreamed, cannot be safely forked by
anyone else, and puts any project that accepts it at risk. Public
documentation, published RE, and hardware you own are sufficient.
