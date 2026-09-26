# #112 item 2 / #41: silicon carries the radial fog coordinate per vertex, from the last quads of the fixed-function scene

**Measured 2026-09-25 on the project console.** Registered beforehand in
[`docs/lanes/xbox/fogprime-run.md`](../lanes/xbox/fogprime-run.md)
(`45787bd1af`, pushed before the XBE ran anywhere) against
[`predictions/2026-09-19-fog-radial-carryover-priming.md`](predictions/2026-09-19-fog-radial-carryover-priming.md)
(PR #179). The dry run was on hakuX `84a67b9cf8` (Thor).

**In one paragraph:**
- **The registered models.** No model is confirmed. V2 fails, which the
  prediction says voids the single-value reading its model rows are written
  in, so the outcome is **X**. It is the X form §3 anticipated: "a carryover
  from a vertex slot this file did not name".
- **What is refuted**, whether or not the reading is single-valued:
  - **H** (hardware constant): A2 sits about 195 f8 steps from A0 on every
    pixel.
  - **T** (the label is the last vertex): A1 and A2 move, and A3 carries A0's
    values.
  - **S-first:** A0 is 30–32, not 249–252.
- **What silicon does.** Each vertex-program vertex takes its fog coordinate
  from one of **six slots**, which hold values from the priming draw's
  **last two quads**. Which slot a vertex reads is fixed by its quad's draw
  index mod 6. The cycle's starting phase persists from test to test and
  moves; the six values do not.
- **hakuX** carries one scalar, the last vertex. It lands on the same values
  as silicon's slots at a single colour, so it is right in direction and flat
  in detail.
- **The repeat** ([follow-up](xbox-fogprime-repeat-2026-09-25.md)): a second
  session with a different history reproduced all 11 priming captures bit
  for bit, so the slots and the phase are deterministic. It also showed V3
  holding in the composition it needs.

## What ran

- **The XBE.** nxdk_pgraph_tests `6743b6a` plus the `Fog radial priming`
  suite: sha256 `5dd5b6cd10d8…`, as registered.
- **The tests.** 17: the six `Fog gen::FogGen_VS-*-radial`, then the eleven
  priming tests (`A0far_FF` … `A4radial_VS`).
- **The console run.** 56 s. It logged "Testing completed normally", and the
  progress log shows the registered order: each `*_FF` test ran immediately
  before its `*_VS` test.
- **Safeguards.** Shutdown-on-completion was off, networking was off, and the
  runner checked the dashboard first.
- **Emulator dry run first:** request `0-0-x-1790388908-xbox-fogprime-dry-1122165`
  ran the same 17 tests in the same order, with no crash signal.

## The gates (§6)

| gate | silicon | |
|---|---|---|
| **V0** A0 in 29.63–35.20 | **holds.** A0's three colours, 30/31/32, all fall inside | the session is not void |
| **V1** the FF captures identical outside the label | **holds.** A1, A2 and A4 against A0: 0 px each | the rotation reordered and did nothing else |
| **V2** each VS region is one colour over 181,016 px | **fails.** 2 to 5 colours per capture (below) | voids the single-value reading |
| **V3** the six radial captures equal their goldens | **fails**, 181,016 px each. This is the run's composition and **my registration error** (below). It **holds** in the follow-up, where Fog gen's FF tests run first | not evidence that the rig moved |

**V3 is my error, not the rig's.** The golden radial captures were recorded
with Fog gen's 30 fixed-function tests running first, and the value they show
is that scene's carried coordinate. `vsh.c` says so for #41's fix: "only
reproducible on a disc with the same composition".
- **What this run did.** The six ran first in the session, with no
  fixed-function radial draw before them, so under any carryover model they
  could not reproduce their goldens.
- **What they show instead** is below, under "Unprimed". It is worth having,
  but it does not test the rig.
- **Where the rig was tested.** The same console reproduced all six goldens
  bit-exactly in PR #340's full `6743b6a` run, where the suite ran in order.
- **Since run on this binary** with Fog gen's FF tests first: all six are
  bit-identical to their goldens
  ([follow-up](xbox-fogprime-repeat-2026-09-25.md)). V3 holds.

## Silicon against the models

| capture | silicon: f8, px | S window | hakuX (one colour) |
|---|---|---|---|
| **A0** (r=0) | 30: 121 · 31: 95,600 · 32: 85,295 | 30.25–32.11 | 31 |
| **A1** (r=188) | 101: 130,981 · 102: 50,035 | 100.64–101.85 | 102 |
| **A2** (r=21) | 224: 21,446 · 225: 28,243 · 226: 71,746 · 227: 52,425 · 228: 7,156 | 223.95–226.92 | 227 |
| **A3** (r=0, label moved) | 30: 119 · 31: 96,176 · 32: 84,721 | = A0 | 31 |
| **A4pad** (r=21) | 224–228, within 0.2% of A2's counts | = A2 | 227 |
| **A4radial** (r=21, after A4pad) | 224–228, within 0.2% of A2's counts | = A2 | 227 |

The prediction's decisive reading is that S predicts three different factors
across A0/A1/A2, and H and T predict three identical ones. Read as
distributions, the three are disjoint, and they run low to high as the last
quad moves nearer: **S's row effect.**
- **The must-move legs** (A1, A2 and A4 differ from A0) all move.
- **S's must-not-move leg** requires A3 bit-identical to A0. **It is not:**
  134,374 px differ.
  - 490 of those px are the printed test name.
  - The rest differ by 1–2 levels.
  - A3 carries A0's six slot values at a phase three quads on (below).
- **The scorer as first written printed `S=True`** from each mixture's
  commonest colour. That line is not a result. It is fixed so that a failed
  V2 prints no model verdict. A mutation case caught it, and the fix is in
  this PR.

## What silicon does instead

This is from [`fogprime_slots.py`](../lanes/xbox/fogprime_slots.py). It was
mutation-tested on a planted quad shift, which it recovers exactly, and on a
scrambled capture, which it reports at 0.21 purity.

1. **Every VS quad is a gradient between four different vertex values.**
   - Each quad shows two planar triangles split on the UL–LR diagonal.
   - The planar fits leave 0.25–0.35 RMS, which is 8-bit rounding
     (1/√12 = 0.29).
2. **The four values are fixed by the quad's draw index mod 6.** That index
   decides the corner pattern of 100% of quads in A1, A2 and both A4s. In A0
   and A3 it decides 90.6% and 90.4%; those values sit on the 31/32 rounding
   edge. Each of the 24 (index mod 6, corner) slots fits to the same value on
   every quad that uses it, with sd ≤ 0.02 across 62–63 quads.
3. **The values come from the priming draw's last two quads:**

   | | slot values | last quad's vertices | last two quads' vertices |
   |---|---|---|---|
   | A0 | 30.53–32.50 | 30.25–32.11 | 30.25–33.12 |
   | A1 | 100.50–102.31 | 100.64–101.85 | 100.64–102.21 |
   | A2 | 223.78–228.21 | 223.95–226.92 | 223.95–228.43 |

   The spans are f8 through the prediction's own geometry and exp model.
   A2's 228 is outside the last quad and inside the last two.
4. **Which FF vertex fills which slot is not resolved.** I fitted "slot →
   n-th vertex from the end of the draw", one offset per slot, jointly over
   A0, A1 and A2. It leaves errors up to ±1.2 f8. Either the mapping is not a
   fixed offset, or the model's absolute f8 is off by that much at this
   multiplier (the prediction's R2: silicon's mid-range exp unit is
   uncharacterised).
5. **The phase persists across draws and moves between tests; the values do
   not.**

   | pair | shift, in quads | quads matching |
   |---|---:|---:|
   | A0 → A3 | 3 | 0.95 |
   | A2 → A4pad | 3 | 1.00 |
   | A2 → A4radial | 5 | 1.00 |
   | A4pad → A4radial | 2 | 1.00 |

   - **A3 against A0:** A3's six slot values are A0's, to the fit's second
     decimal. So A3's moved label changed only the phase: nothing like T,
     and no new value.
   - **The A4 pair:** from A4pad's start to A4radial's, the phase moved by
     2 and the values did not. In between are A4pad's own 374-quad
     programmable draw and the harness's work between tests. The priming survives an intervening
     programmable draw, which is the persistence half the prediction asked
     A4 for.

**Unprimed:** the six `FogGen_VS-*-radial` captures ran first in the session.
Each is **one colour** over all 181,016 px:

| modes | f8 | coordinate it inverts to |
|---|---:|---|
| exp and exp_abs | 210 | 7.77 |
| linear and linear_abs | 245 | 7.84 |
| exp2 and exp2_abs | 246 | not inverted |

So at the start of this session, every slot held about 7.8. That is where
hakuX would need it for an isolation disc. hakuX models the starting register
as 0, which renders f8 255, and its dry run shows exactly that. What wrote 7.8
is not known: this run gives one session and one value.

## hakuX (dry run, `84a67b9cf8`)

- **What hakuX does.** It carries one scalar, the last vertex of the last
  fixed-function draw (#41's `ff_radial_fog_coord`). Its single colours are
  31, 102, 227, 31, 227 and 227: S-shaped, with A3 = A0 and A4 = A2.
- **Against silicon, the VS captures** differ on 85,416–130,981 px each, by at
  most 1–3 levels. That is the per-vertex spread one scalar cannot draw.
- **The FF priming captures** differ on 46,759 px each, by at most 2. These
  are silicon's first mid-range samples of the exp unit (f8 about 30 to 255
  across 374 distances). They are on the host for anyone calibrating it.
- **None of this touches the corpus.** At Fog gen's multiplier (−0.00225),
  all six slot values map to a single f8, so hakuX's scalar reproduces the six
  goldens exactly, as #41 measured. The slot structure shows only at a
  multiplier where the last quads' spread exceeds one f8 step.
- **The prediction's hakuX companion legs:**
  - **E1** ("all five bit-identical, because `vsh.c` resets every
    invocation") and **E2** ("a per-quad gradient") are refuted on hakuX.
    Their premise was stale when registered: #41's carry (`906ab0395f`,
    2026-09-13) is in the prediction's own base ref, `01047cf32c`. I bound
    this run to E1–E3 without checking that premise against the tree.
  - **E3** holds outside the labels, on both renderers. The FF captures
    differ from A0's only in the printed label rows: 134–300 px, and
    1,566 px for A3, which prints in two places.

## Registration notes

- **V3** could not hold in the composition I registered (above). That is my
  error.
- **The prediction's V0 cannot admit S-first.** V0 is H's window, and S-first
  puts A0 at 249–252, so S-first could never pass V0 as registered. The
  mutation test shows it. It makes no difference here, since A0 is 30–32.
- **Rounding.** S's windows are continuous, and the prediction does not say
  how f8 rounds. Under round-to-nearest, hakuX's 102 and 227 fall inside
  windows whose tops are 101.85 and 226.92. I noticed this only after the
  dry run and have not re-scored anything with it.

## Follow-ups

1. **Done:** V3 on this binary, and the repeat
   ([follow-up](xbox-fogprime-repeat-2026-09-25.md)). V3 holds, and the slots
   and phases reproduce bit for bit. That run also found the session's first
   planar-fog test rendering with half its fog coordinate.

**Not run:**

2. **What moves the phase.** It moved 2 from A4pad to A4radial,
   and 3 between the A0 and A3 tests. A variant that changes the pad draw's
   quad count separates per-vertex, per-quad and per-draw counting. This needs
   its own registration.
3. **The session-start value**, 7.8.
4. **hakuX.** Modelling the slots would move only captures that no golden
   covers. This is for the tracker to weigh, not a defect in #41's fix.

## Files

- **The gates and models:** [`fogprime_score.py`](../lanes/xbox/fogprime_score.py).
  It was written at 19:15 on 2026-09-25, before the dry run landed at 19:29,
  and gained only the V2/V0 guard afterwards.
- **The slot structure:** [`fogprime_slots.py`](../lanes/xbox/fogprime_slots.py).
- **The captures** are on the host under
  `~/hakux-work/hardware/runs/2026-09-25-fogprime/console-run/console/`, laid
  out like the goldens. The dry run's are in the dispatcher result above.
