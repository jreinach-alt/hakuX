# lane.buildflags427 -- #427: host build flags: native ELF TLS

Issue: #427. Base: origin/master @ 15d9406b81. Release tracker: #433 (0.5, target 2026-09-28).
Files: android/app/build.gradle.kts, android/app/src/main/cpp/CMakeLists.txt, docs/lanes/buildflags427/**, docs/testing/predictions/buildflags427-*.json.
Needs device: yes (Nova/Thor gameplay window before and after). Needs NDK: yes.
Read first: the issue body; docs/investigations/perf-architecture.md (section 3.3, lever 4); docs/investigations/perf-baseline-2026-09.md;
docs/investigations/performance-next-three.md; docs/lanes/perfarch/NOTES.md and docs/lanes/tcgchurn/NOTES.md (method, what was refuted).

## The goal
host build flags: native ELF TLS. The lever's share is a BOUND from a profile, not a measured gain: say which. 0.5 is measured by games, so the number
that counts is fps over a gameplay window of a #397 title (Crimson Skies, Blinx), before and after, same route, same device,
same session.

## The job
1. minSdk 29 (the Nova runs Android 13; check the Thor's version with adb first and say so), -march=armv8.2-a (inline LSE), and -fvisibility=hidden or -Wl,-Bsymbolic for libxemu.so.
2. CMakeLists.txt is free (released by lane.vshcpu345 at PR #402 ready; #402 has folded).
3. Confirm the three in the symbol table (no __emutls_get_address, __aarch64_swp4_acq_rel or PLT stubs inside libxemu.so) before any device run.
Register a prediction (docs/testing/predictions/buildflags427-*.json) whose falsifier names the counter that must move
(__emutls_get_address, __aarch64_* outline-atomic and PLT stub samples in a simpleperf profile of the vCPU thread) and a must-not-move leg for the pgraph suites. Merge master before marking ready.

## Falsifier
If that counter does not move on the A/B the lever is inert here: report it, do not tune until a number moves.

## Done when
PR ready, CI green, arm verdict posted, docs/lanes/buildflags427/NOTES.md with the before/after table and run ids.
Owner's rule: no pgraph suite regresses.
