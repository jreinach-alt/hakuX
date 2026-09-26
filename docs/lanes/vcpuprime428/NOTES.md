# lane.vcpuprime428 NOTES

Issue #428: run the emulated CPU (vCPU) thread on the X3 prime core with
`HAKUX_PLACE_VCPU=prime`, and measure it on a game's gameplay window.
Base: master @ 15d9406b81. PR #437.

## The design, and why it differs from perfarch's arm

perfarch's arm (`perfarch-vcpu-prime.json`) was refused on validity for two
reasons. Harness exits cut 3 of its 4 runs short, and Galleon at 1x sits on
its 30 fps cap. That arm did establish that the mechanism works: 100% of the
vCPU's time on the X3 and zero core changes.

- **Scene:** the Crimson Skies routed gameplay window
  (`titles/routes/crimson-skies.route`). The judge reads only the stretch from
  the route's `mark gameplay` to `soak end`, not the boot.
- **Device: the Thor.** On the Nova, Crimson's gameplay window is capped: the
  titlerun 780 s route run (apk `a00704d02eb0`) held a 29.99 fps median. On
  the Thor it is not: `0-0-y-1790433159-titleplay-p1-crimson` (apk
  `25abcaccbf45`) ran the window at 14.5 fps (flips over wall time), gfps p50
  22, G median 43.8 ms, with the renderer idle. That is guest-bound.
- **Length:** 480 s per run, about 360 s of it gameplay. 3 runs per arm on
  one binary (15d9406b81), queued A1 B1 A2 B2 A3 B3. Validity: every run
  must hold its 480 s to within 15 s.
- **Clocks and thermal (section 4.3):** `HAKUX_TOPO=200,10` runs on both
  arms. The judge prints the X3 clock (p7) and the hottest CPU zone in the
  first and last sampler window of each run's gameplay window. P4 requires
  B's last p7 to be >= 0.90 of its first.
- **Judge:** `vcpu_judge.py` (this directory). `tl.sh <id>` prints a 30 s
  timeline of gfps, the vCPU's X3 share, busy %, p7 and CPU temperature.

## The lever's share is a bound

Pinning saves s*(1-1/r) of the vCPU's busy time. Here s is the vCPU's off-X3
share in arm A, measured by this arm, and r is the X3's per-core speed over
an A715/A710, 1.1-1.5 from perfarch's survey (8.1, Nova). With s=0.28
(Galleon at perfarch's apk) the bound is 3-9%. With s=0.85 (the 09-11
Crimson capture) it is 8-28%. Neither figure is a measured gain.

## Hazard seen before queueing

In the Thor p1 run, the gameplay window collapsed from about 25 gfps to 2-7
gfps from about 150 s in, with Tq rising from 2 to 1297. That build already
had fix311. If the collapse recurs it affects both arms. P3 (the between-arm
fps delta must exceed the within-arm spread) is what says whether the arm can
still separate A from B.

## Runs

Queued 2026-09-26 on the Thor, ref 15d9406b81, `queue.sh` (A1 by hand with
the same arguments). Poll with `waitruns.py`.

| run | id | env |
|---|---|---|
| A1 | 1790454357-vcpuprime428-3938872 | HAKUX_TOPO=200,10 |
| B1 | 1790454370-vcpuprime428-3939641 | HAKUX_TOPO=200,10 HAKUX_PLACE_VCPU=prime |
| A2 | 1790454370-vcpuprime428-3939708 | HAKUX_TOPO=200,10 |
| B2 | 1790454371-vcpuprime428-3939754 | HAKUX_TOPO=200,10 HAKUX_PLACE_VCPU=prime |
| A3 | 1790454371-vcpuprime428-3939794 | HAKUX_TOPO=200,10 |
| B3 | 1790454372-vcpuprime428-3939872 | HAKUX_TOPO=200,10 HAKUX_PLACE_VCPU=prime |
