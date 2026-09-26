# lane.vcpuprime428 -- #428: the emulated CPU thread on the prime core, HAKUX_PLACE_VCPU=prime

Issue: #428. Base: origin/master @ 15d9406b81. Release tracker: #433 (0.5, target 2026-09-28).
Files: android/app/src/main/cpp/xemu_android.cpp, docs/lanes/vcpuprime428/**, docs/testing/predictions/vcpuprime428-*.json.
Needs device: yes (Nova/Thor gameplay window before and after). Needs NDK: yes.
Read first: the issue body; docs/investigations/perf-architecture.md (section 4 (lever 3) and 8.3); docs/investigations/perf-baseline-2026-09.md;
docs/investigations/performance-next-three.md; docs/lanes/perfarch/NOTES.md and docs/lanes/tcgchurn/NOTES.md (method, what was refuted).

## The goal
the emulated CPU thread on the prime core, HAKUX_PLACE_VCPU=prime. The lever's share is a BOUND from a profile, not a measured gain: say which. 0.5 is measured by games, so the number
that counts is fps over a gameplay window of a #397 title (Crimson Skies, Blinx), before and after, same route, same device,
same session.

## The job
1. The earlier arm (perfarch-vcpu-prime.json) was refused on validity: its runs were cut short. Re-run with FULL-LENGTH runs of a guest-bound scene (Crimson Skies gameplay), not the boot.
2. Account for sustained clocks and thermals (section 4.3): read the clock and thermal state at the start and end of each run.
3. If the default should change, make it a one-line change in xemu_android.cpp and say why the arm supports it; otherwise report the refutation.
Register a prediction (docs/testing/predictions/vcpuprime428-*.json) whose falsifier names the counter that must move
(the vCPU thread's cpu id and clock over the run, and fps over the gameplay window) and a must-not-move leg for the pgraph suites. Merge master before marking ready.

## Falsifier
If that counter does not move on the A/B the lever is inert here: report it, do not tune until a number moves.

## Done when
PR ready, CI green, arm verdict posted, docs/lanes/vcpuprime428/NOTES.md with the before/after table and run ids.
Owner's rule: no pgraph suite regresses.
