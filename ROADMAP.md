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

## What "done" looks like

**Not "every pgraph test passes."** That is the wrong target, and aiming at it
would waste most of the effort available.

Of 1,591 differing colour tests, 943 differ by under 10,000 pixels and the ones
sampled so far are precision, not logic — `Blend tests` fails all 104 with a
maximum channel error of 32/255 and images that are visually identical. Driving
those to bit-exactness is enormous work for no visible gain. Meanwhile 12 tests
differ by more than 200,000 pixels and those are the ones a player would notice.

The goal is therefore:

1. **Nothing crashes, hangs or aborts.** A hang passes every pixel test it never
   reaches, so the suite cannot see this class at all. It is still first.
2. **No catastrophic or severe divergence.** Drive the >50,000-pixel buckets to
   zero — roughly 300 tests, not 1,591.
3. **Precision differences are tracked, not chased.** They are a backlog to
   revisit once the visible faults are gone, and a guard against regression in
   the meantime.
4. **The suite becomes a gate, not a goal.** Its value is telling us when a
   change makes things worse. That requires fixing the order-dependence first
   (issue #15) or the gate will flap.

Accuracy figures quoted here are colour-only. Depth captures fail almost
universally through a readback conversion bug (issue #16) that games do not
experience; including them would overstate the problem by a wide margin.

## How the work is organised

Defects live in [GitHub issues](https://github.com/jreinach-alt/hakuX/issues),
grouped by likely shared cause rather than one issue per failing suite. Each
carries its measured evidence: which suites, how many tests, median pixel delta,
and what has already been ruled out.

Work proceeds in themed sprints against those groups. **A sprint opens with a
baseline suite run and closes with another**, so its result is a measured delta
rather than a list of commits. Two weeks is the working assumption; single root
causes have repeatedly taken more than a day to isolate.

Sprint order:

| sprint | theme | issues | why this order |
|---|---|---|---|
| 0 | Make measurement trustworthy | #15 | Fix order-dependence. Until a sweep can be diffed against another sweep, no claim about whether a change helped is worth anything. |
| 1 | Textures | #3, #4, #5, #6 | Largest cluster, worst severity, and the suspected cause of the one visible fault reported from real play. |
| 2 | Surfaces and blits | #7, #16 | `Image_blit` overlaps are the second-worst colour failures; depth readback unblocks honest depth figures. |
| 3 | Fixed-function shading | #8, #9, #10 | Fog and lighting are broad and user-visible in outdoor scenes. |
| 4 | Geometry and raster | #11, #12, #13 | Clipping, attributes, line/point rules. |
| — | Deferred | #14 | Blend precision. Revisit only when nothing visible remains. |

Bisection (issue #17) is a technique used inside sprints, not a sprint of its
own. When an issue looks like a regression, `git bisect run` over the ~139
fork-era commits touching the renderer costs under an hour and hands over the
diff that broke it. That is a much cheaper repair path than deriving hardware
behaviour from goldens — but it is worth doing per issue, on demand, rather
than as an upfront survey.

Crash and hang work is **not** on this schedule. It arrives from play, it is
found by different means, and it preempts accuracy work when it appears — but it
is tracked separately so it does not silently consume a sprint.

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

**Status: run on device; first accuracy figures measured.**
Runbook: [`docs/testing/pgraph-harness.md`](docs/testing/pgraph-harness.md).
Findings: [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md).

[`abaire/nxdk_pgraph_tests`](https://github.com/abaire/nxdk_pgraph_tests) is a
test program that runs on real Xbox hardware and on emulators, covering texture
formats, vertex shaders, surface formats, combiners and blending.
`nxdk_pgraph_tests_golden_results` holds reference framebuffers **captured from
real NV2A silicon**, and
[`xemu-nxdk_pgraph_tests_results`](https://github.com/abaire/xemu-nxdk_pgraph_tests_results)
tracks xemu against them with a comparison tool and a GitHub Action.

Hardware ground truth is the one thing that cannot be produced without an Xbox
and a devkit. It exists and is published.

- [x] Get a runnable disc image and a way to configure it. The release ships a
      built XISO, and `docs/testing/make_test_iso.py` adds the config file it
      needs — without one, results never leave the emulated hard disk.
- [x] Wire the output into the existing comparison tooling.
      `docs/testing/collect_results.py` turns an upload directory into the
      layout `compare.py` expects; validated against the hardware goldens.
- [x] Run the suite on this build, on device. 3,132 tests complete in ~4m20s
      on a Retroid Pocket Nova (Adreno 740, Vulkan). Results are extracted from
      `hdd.img` host-side by `docs/testing/extract_results.py` — no networking
      involved; the FTP path in the runbook is not required.
- [x] Measure the first accuracy figures. **1,110 of 2,702 colour tests
      (41.1%) match NV2A silicon pixel-exactly.** Depth captures are excluded
      from that figure: they fail almost universally through a conversion bug
      in the readback path, not through wrong depth behaviour, and including
      them overstates the problem (see KNOWN_ISSUES).
- [ ] Triage the 1,591 differing colour tests. 943 are under 10k pixels and
      look like precision, not logic — blend and specular top out at 32/255
      with the images visually identical. The 12 catastrophic ones are worth
      more than the other 1,579 combined.
- [ ] Add it to CI as a regression gate. The pieces exist: `make_test_iso.py`
      builds a configured disc, `extract_results.py` pulls results off the
      image, `collect_results.py` feeds `compare.py`. What is missing is a
      device in CI.

The third step is worth more than any amount of new code. It converts "textures
look wrong in some games" into a named failing test with a pixel diff.

## 3. Video

**Status: the oracle exists; divergences are filed and scheduled.**

Graphical faults live in the translation from NV2A state into Vulkan or GLES,
not in the GPU driver. NV2A's pixel stage is fixed-function register combiners,
which have no modern equivalent and must be compiled into shaders — a lossy
translation of hardware that is only partly documented. XboxDevWiki's own
combiner page records open questions about it.

- [ ] With the suite running, A/B the stock Qualcomm driver against a Turnip
      build. Output differing **between drivers** is a driver bug; output
      identical between them but diverging **from the goldens** is xemu's
      translation. That separates two layers that currently get conflated.
- [x] Work the failing tests by how often the affected feature is used. Done as
      far as grouping goes: the divergences are filed as issues #3–#14, ordered
      into sprints above by severity and by how widely the feature is used.
      Sprint 1 (textures) carries the largest cluster and the only fault so far
      traced from real play — the Crimson Skies ocean, suspected to be issue #6.
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

[`docs/investigations/freeze-analysis.md`](docs/investigations/freeze-analysis.md) documents a freeze chased through thirteen eliminated
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
