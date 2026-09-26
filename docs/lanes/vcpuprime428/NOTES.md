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

At 20:37 UTC the host parked A2 B2 A3 B3 in
`dispatch/parked/vcpuprime428-20260926T203745Z` under the owner's 09-26 rule:
a device batch over 30 minutes runs a short pilot first, and the pilot is
reviewed (hostops writes `dispatch/pilots/<lane>.ok`) before the rest runs.
A1 and B1 are the pilot. The rule is in `docs/lanes/titleplay/NOTES.md`.
I queued all six without reading it.

## Pilot result (A1, B1; Thor, apk acb81bbaa1d1 = ref 15d9406b81)

Both runs held their 480 s and gave 367 to 369 s of gameplay window. The
Tq collapse seen in the titleplay p1 run did not recur.

| run | id | fps | gfps p50/p10 | vCPU X3 | rqwait ms/s | busy | p7 first->last (mean) MHz | CPU C first->last |
|---|---|---|---|---|---|---|---|---|
| A1 | 1790454357-vcpuprime428-3938872 | 28.23 | 29.0/24 | 79% NOT PINNED | 2.91 | 89% | 3115->2619 (2830) | 88.8->94.6 |
| B1 | 1790454370-vcpuprime428-3939641 | 25.56 | 27.0/19 | 100% PINNED | 50.28 | 83% | 2713->2420 (2480) | 94.6->94.3 |

Judge on the pair: P0 PASS, P1 PASS (the counter moved 20.7 points),
P2 FAIL (-9.5%), P3 PASS (n=1 per arm, so the spread is 0), P4 FAIL
(2420/2713 = 0.89).

What the pilot shows, with n=1 per arm:
- The counter moves. A already runs the vCPU on the X3 79% of the time on
  this scene, not the 15% perfarch's model assumed. The bound on the gain
  is now s*(1-1/r) with s=0.21: 2-7% of vCPU time. That is a BOUND, not a
  measurement.
- The scene sits near its 30 fps cap on this apk (A1 held 28.2; the p1 run
  at 14.5 fps had collapsed). At most about 6% of gain is visible.
- B lost fps. Two causes are confounded. (1) Runqueue wait rose 17x
  (2.9 to 50 ms/s): pinned, the vCPU can no longer leave the X3 when
  another thread holds it. (2) B1 ran right after A1 on a hot device: its X3
  clock was 12% lower (mean 2480 against 2830 MHz). A2, which follows B1,
  separates the two. If A2 also runs about 2480 MHz and still holds about
  28 fps, the loss is the pin (cause 1). If A2 drops to about 25.5, it is
  thermal order (cause 2).

## Waiting (attempt 1, 22:20 UTC)

Waiting on hostops to review the pilot (`dispatch/pilots/vcpuprime428.ok`)
and restore A2 B2 A3 B3 from the parked directory. The request is PR #437
comment 5850381031. On resume: run `waitruns.py` until all six runs are DONE,
then run the full judge. If B still loses fps after A2 controls for heat,
report the refutation: no code change and no pgraph arm. If B gains,
make the one-line default change and register the pgraph must-not-move arm.

## Why attempt 0 did not finish

The session ended with A1 and B1 (the pilot) still queued behind other
device work and the other four runs parked. No run had finished, so there
was nothing to judge. Attempt 1 resumed at 21:48 UTC with A1 running on the
Thor and B1 at the head of the queue. It merged origin/master (e08c1c0165).
The runs still use ref 15d9406b81, which is the prediction's a_ref/b_ref.

## Result: REFUTED. The default does not change (attempt 2, 23:15 UTC)

All six runs held 480 s (480 to 484) with 365 to 369 s of gameplay window,
on one device (Thor), one apk (acb81bbaa1d1 = ref 15d9406b81), in the order
A1 B1 A2 B2 A3 B3. Full judge (`vcpu_judge.py --expect
docs/testing/predictions/vcpuprime428-soak.json --a A1 A2 A3 --b B1 B2 B3`):

| run | id | fps | gfps p50/p10 | vCPU X3 | rqwait ms/s | busy | p7 first->last (mean) MHz | CPU C first->last |
|---|---|---|---|---|---|---|---|---|
| A1 | 1790454357-vcpuprime428-3938872 | 28.23 | 29/24 | 79% | 2.91 | 89% | 3115->2619 (2830) | 88.8->94.6 |
| B1 | 1790454370-vcpuprime428-3939641 | 25.56 | 27/19 | 100% | 50.28 | 83% | 2713->2420 (2480) | 94.6->94.3 |
| A2 | 1790454370-vcpuprime428-3939708 | 25.29 | 27/19 | 69% | 14.09 | 88% | 2697->2215 (2328) | 94.6->93.9 |
| B2 | 1790454371-vcpuprime428-3939754 | 18.39 | 23/8 | 71% | 129.66 | 77% | 2543->1843 (2178) | 94.3->84.0 |
| A3 | 1790454371-vcpuprime428-3939794 | 25.07 | 26/19 | 71% | 12.50 | 89% | 3076->2220 (2331) | 94.3->93.9 |
| B3 | 1790454372-vcpuprime428-3939872 | 17.74 | 23/7 | 67% | 130.46 | 77% | 2601->1843 (2182) | 90.3->83.7 |

Arm means: A 26.20 fps, B 20.56 fps (-21.5%). Legs: P0 FAIL (B2 and B3
lost the pin, see below), P0-A PASS, P1 FAIL (6.4 points over the whole
window), P2 FAIL (-21.5%), P3 FAIL, P4 FAIL (B2 and B3 end at 1843 MHz,
0.72 of their first). VERDICT: FAIL, 5 legs.

### What happened: a thermal state ejects the pinned vCPU onto the little cores

In B2 and B3, about 240 s into the gameplay window, the device enters a
thermal state: p7 locks at 1843 MHz (1843-1843 over a 10 s window), p3 at
1651 and p0 at 2016. The hottest CPU zone drops from about 95 C to 84-86 C.
From that window on, the pinned vCPU (affinity mask 0x80) runs 0% on cpu7
and about 33/33/33% on cpus 0-2, the little cores. Its runqueue wait is 200
to 250 ms/s, and the gameplay 30 s gfps median falls to 4-9 for the rest of
the run. `eject.py <id> 0 100000 | grep tid=<vcpu>` shows the transition
(B2: 15:46:07 cpu%=31/9/6/0/0/0/0/54, then 0% on cpu7 to the end). No A
run entered that state: A's lowest window p7 was about 2150, and its vCPU
kept moving between cpu7 and the mid cores (X3 58-94% per 30 s). A plausible
cause, not a measured one: the pin holds cpu7 at 75-97% busy with no relief,
which drives the prime core into the mitigation that pauses it. It happened
in 2 of 3 B runs and 0 of 3 A runs.

### Before the ejection, pinning did not help either

`early.py` reads the first 240 s of each gameplay window, before any
ejection:

| run | gfps 30 s-median mean | vCPU X3 | p7 mean MHz |
|---|---|---|---|
| A1 | 28.0 | 82% | 2918 |
| B1 | 26.6 | 100% | 2508 |
| A2 | 25.9 | 70% | 2382 |
| B2 | 23.6 | 100% | 2327 |
| A3 | 25.6 | 70% | 2391 |
| B3 | 25.1 | 100% | 2344 |

At matched clocks (A2 and A3 against B2 and B3, all 2330-2390 MHz) A is 25.8
and B is 24.4. The counter moves (the vCPU goes from 70% to 100% on the X3),
but fps does not follow. Pinned, the vCPU waits 10-150 ms/s for cpu7 against
A's 3-14. A1 against B1 is thermal order: A2, run after B1 at a lower clock,
fell to the same fps unpinned.

### The bound, and why it did not show

The lever's share was a BOUND: s*(1-1/r) of vCPU time, with s = A's off-X3
share. Measured s on this scene is 0.21 to 0.31, not the 0.85 of the 09-11
Nova capture, so the bound is 2-10% of vCPU time before any runqueue cost.
That is a bound, not a measured gain, and the measured runqueue cost of the
pin is larger. Under sustained load the X3 does not hold 3.1 GHz (section
4.3). It runs at about 2.3 GHz from the second run on, which shrinks r.

### Decision

No code change. `HAKUX_PLACE_VCPU` stays opt-in, unset by default. The
falsifier does not apply as written: the counter did move (P1 passed over
the pre-ejection window and in the pilot), but fps moved the wrong way.
That is a refutation, not an inert lever. With no code change there is no
pgraph must-not-move arm to run, because nothing that ships changes. The
arms job refused `vcpuprime428-soak.json` because a_ref equals b_ref. This
verdict is `vcpu_judge.py`'s, and it is posted on PR #437.

For the next lane: a hard single-core pin on this SoC is unsafe under
sustained load. If placement is tried again, use a preference that lets the
kernel move the thread (uclamp.min or a big+prime mask), not mask 0x80. It
should run long enough (>= 300 s of gameplay, several runs back to back) to
reach the thermal state that ejected B2 and B3.

## A2 (attempt 2, 22:40 UTC)

| run | id | fps | gfps p50/p10 | vCPU X3 | rqwait ms/s | busy | p7 first->last (mean) MHz | CPU C first->last |
|---|---|---|---|---|---|---|---|---|
| A2 | 1790454370-vcpuprime428-3939708 | 25.29 | 27/19 | 69% NOT PINNED | 14.09 | 88% | 2697->2215 (2328) | 94.6->93.9 |

A2 ran after B1 on a hot device, at a lower X3 clock than B1 (mean 2328
against 2480 MHz). Unpinned, it held 25.29 fps, the same as B1's 25.56. So
the pilot's -9.5% was thermal order (cause 2), not the pin. Arm fps tracks
the X3 clock, which tracks run order: the device does not return to A1's
start state between runs.

## Why attempt 1 did not finish

It ended correctly on a wait outside the session: the pilot review. Hostops
accepted the pilot at 22:31 UTC (PR #437 comment, `[job.deliver]`), wrote
`dispatch/pilots/vcpuprime428.ok` and restored A2 B2 A3 B3. Attempt 2 resumed
at 22:32 UTC with A2 running on the Thor.

The arms job refused `vcpuprime428-soak.json` with "a_ref == b_ref, nothing to
compare". That is expected for an env-var A/B on one binary: the arms job
cannot run it, so the runs are queued by hand (`queue.sh`) and judged with
`vcpu_judge.py`. The refusal does not affect the verdict.

## Do not repeat

- Do not pin the vCPU to cpu7 alone (mask 0x80) as a default. On the Thor it
  was ejected to the little cores after about 240 s of sustained gameplay in
  2 of 3 runs (B2, B3), and fps fell to 4-9 for the rest of the run.
- Do not read A1 against B1 as a lever effect. Back-to-back runs heat the
  device, so compare runs at matched p7.
- Do not queue over 30 minutes of device time without a reviewed pilot.
  Queue one run per arm, review it, and ask hostops for the rest.
- In a titleplay `route`, `hakuX-route` `mark gameplay` is the start of the
  gameplay window. perfarch's "drop the first quarter" still counts boot on a
  route with a 105 s lead-in.
