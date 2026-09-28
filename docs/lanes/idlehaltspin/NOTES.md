# lane.idlehaltspin (#525): the spin variant against leg L

Base: master @ 23416ffb77. No emulator code changes and no new prediction.

## 1. The brief's premise, checked

The brief says nothing had measured `HAKUX_IDLE_HALT_SPIN_US`. arms.sh
SKIPPED `idlehalt-spin-{auf,blinx}.json` (`a_ref == b_ref`), and that part is
true. But lane.idlehalt had already queued all six arms directly with
`request.sh`, at 40fabbaacc, with each arm's env (its NOTES section 8). Five
had finished when this lane started. Blinx A1 (`-2124441`) was running on the
Nova at 17:4xZ; this session waited for it and read it.

C against B on one binary and one device is a real A/B. arms.sh cannot
express it, because it compares refs and not env. So this lane reads the
existing runs rather than inventing a second sha. A "fix commit" that flips
the default would only move the same env var into the source.

## 2. The read (40fabbaacc, Nova, survey, 420 s)

AUF uses `ihread.py --from 299 --to 420`, and Blinx uses `ihread.py --play`,
the windows the registrations name. J/frame comes from `title_verdict.py`
(master) on copies of each result dir.

| | AUF C (spin 100) | AUF B (halt) | AUF A (off) | Blinx C | Blinx B | Blinx A |
|---|---|---|---|---|---|---|
| result | `2124008` | `2124125` | `2124199` | `2124275` | `2124356` | `2124441` |
| windows, checks | 60 ok | 60 ok | 60 ok | 82 ok | 84 ok | 85 ok |
| gfps | 19.93 | 19.85 | 19.78 | 19.92 | 20.20 | 19.47 |
| vCPU on-CPU | 29.4% | 25.3% | 59.7% | 43.5% | 37.9% | 73.8% |
| halts/s | 483 | 492 | 0 | 601 | 543 | 0 |
| tp / xpc | 0 / 0 | 0 / 0 | | 0 / 0 | 0 / 0 | |
| sh (kicks inside the spin) | 2951 | 0 | | 19454 | 0 | |
| spinning | 4.7% | 0 | | 4.9% | 0 | |
| **pg raise-to-run >= 50 us** | **5.4%** | **7.5%** | n/a | **2.4%** | **3.3%** | n/a |
| net W | 6.14 | 6.02 | 7.27 | 6.64 | 6.49 | 8.32 |
| j_per_frame | 0.308 | 0.298 | 0.365 | 0.334 | 0.327 | 0.434 |
| thermal_status_max | 0 | 0 | 0 | 0 | 0 | 0 |

The pg kick's time from halt entry (`kpg`, in the B arms, spin 0):

| us | <20 | <50 | <100 | <200 | <500 | <1000 | >=1000 |
|---|---|---|---|---|---|---|---|
| AUF B | 107 | 221 | 1089 | 621 | 773 | 915 | 3 |
| Blinx B | 2282 | 1960 | 1971 | 1680 | 4095 | 5120 | 6 |

## 3. Legs of the spin registrations

| leg | AUF | Blinx |
|---|---|---|
| V | holds (ihread checks; C's last play shot is level play) | holds (same; C's and A's last play shots are level play) |
| **L** (C's >= 50 us share at most half of B's) | **fails**: 5.4 vs 7.5 (0.72 x) | **fails**: 2.4 vs 3.3 (0.73 x) |
| L against the first prediction's <= 1% | fails | fails |
| H (C <= B + 12 points, >= 25 under A) | holds: +4.1; 30.3 under A | holds: +5.6; 30.3 under A |
| C (tp = 0, xpc = 0, sh > 0) | holds | holds |
| F (C, B >= 0.95 x A) | holds: 1.008, 1.004 | holds: 1.023, 1.037 |
| J (C <= 0.85 x A) | holds, barely: 0.844 (B 0.815) | holds: 0.768 (B 0.752) |

The halt with a 100 us spin keeps the saving and costs no fps. It does not
fix the callback tail.

## 4. Why no other spin length fixes it (the bound)

A spin of S us catches only the pg kicks that land within S of halt entry.
`kpg` is recorded at every setting, so the B arms show which share each S
would catch. Model: C's tail = B's tail x (B's share of pg kicks with
kpg >= S).

- Checked at S = 100: the model predicts AUF 4.6% and Blinx 2.1%. The
  measurements were 5.4% and 2.4%. The model is slightly optimistic in both
  titles, so a predicted fail is a safe fail.
- S = 200: AUF 3.4%, Blinx 1.8%. **Fails** the 1% bound and the half-of-B
  leg in both titles.
- S = 500: AUF 1.8% (fails), Blinx 1.0% (the edge).
- S = 1000 (the cap, `IH_SPIN_MAX_US`): both under 1%.

The cost: at S = 100 the spin ran 4.7% and 4.9% of wall time, against a
ceiling of halts/s x S = 4.9% and 5.4%. Almost every halt spins its full S,
because 60-80% of pg kicks and most other wakes come after 100 us. The cost
scales with S until S reaches the halt's own length (AUF mean ~670 us). At
S = 500 it is ~20-25 points of a core. That breaks H (at most B + 12) in both
titles, and it is most of the 34-point saving. At S = 1000 the halt is a spin
and there is no saving left.

So L needs S >= ~500 (Blinx) and ~1000 (AUF), and H needs S <= ~200. The two
windows do not overlap. **The spin mechanism is exhausted.** I did not queue
50/200 us runs: 50 catches fewer kicks than 100 (AUF kpg < 50: 9%), and 200
is predicted to fail by a model that errs in the passing direction.

## 5. Verdict, and what the next lane should not repeat

- Idle halt stays **opt-in** (`HAKUX_IDLE_HALT=1`, `SPIN_US` default 0).
  Between this and #547 (not a heat lever at the device defaults), no flip is
  proposed.
- The broken `idlehalt-spin-{auf,blinx}.json` registrations are deleted.
  Their measurement is the table above. Re-binding them to a second sha would
  only re-measure the same env toggle.
- The remaining lever is not a spin. The pg callback comes 100-1000 us after
  the halt starts, so it has to be predicted (pushbuffer put != get, in
  nv2a.c or pfifo.c; see idlehalt NOTES section 8), not waited for.
- A flip could instead be argued from F and J: F holds in every arm on both
  builds, so the tail costs no fps that anyone has measured. That is a new
  registration with a bound argued from F, not a moved 50 us.
- Do not repeat: registering an env-only toggle for arms.sh with
  `a_ref == b_ref`. arms.sh compares refs. Queue env arms with `request.sh`,
  as lane.idlehalt did, and say so in the prediction.
- Note: A on 40fabbaacc is 59.7% on-CPU in AUF. On 6554f06175 it was 95.1%,
  so the base moved between the two batches. Compare within a batch only.
