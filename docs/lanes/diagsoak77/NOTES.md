# lane.diagsoak77 -- drive #77's frame dump at the artifact itself

Issue: #77. Base: master @ 732b97e2df (PR #143 merged, FDUMP_SCHEMA 3).
Files: `docs/lanes/diagsoak77/**` only. No source file is touched; the
instrument was released to `[free]` by lane.diagdump77 and this lane only
uses it.

## The question, and the shape an answer can take

#77 has been left suspecting the *schedule* -- draw merging, deferred
submission, a missing barrier -- because the only per-draw instrument it had
(the Debug Capture button) forces `pgraph_vk_finish` per draw and so destroys
exactly that behaviour. PR #143 built an instrument that does not. This lane
spends the device time to find out whether the schedule differs between a
stipple frame and a clean one.

Three outcomes are allowed and the brief names all three: positive, negative,
or **"not visible to this instrument"**. The last is not a hedge; §"F0" below
makes it a *measured* verdict rather than a shrug, because a counter that is
constant across every frame of a run cannot correlate with anything and the
dump says outright whether it is constant.

---

# PRE-REGISTERED, before any new dump is read

Everything from here to the `---` was written and committed before any dump
taken by this lane existed. The reconnaissance it rests on is run
`1789811606-diagdump77-4099630` -- a **different binary** (`fbf3b3f5ee`, schema
1), taken by a different lane, whose images the checker refuses to pair with
its records. It is used here to size the experiment and to choose a region and
a bar; it is not, and must not become, the run this lane draws a conclusion
from.

## R0. What the reconnaissance established (and what it did not)

**R0a -- the 120 s mark of a Galleon soak is a parked camera, not a scene
cut.** The 30 PPMs of `1789811606` show Rhama centred over sea and cliff,
performing a sword flourish, with the background essentially unchanged across
all 30 frames. That contradicts nothing in the issue -- the issue's claim is
about the *attract demo* and about **texture detail**, not about camera motion
-- but it does mean `galleon_flash_rate.py`'s "one scene, parked camera"
assumption holds in this window.

**R0b -- and that is exactly where the tool's default bar goes wrong.** Run
with `--per-frame` over those 30 consecutive frames:

```
  HF energy   median 1.20  mad 0.02  bar 1.28  (k=3.0)
  STIPPLE    4 / 30  =  13.3 per 100   [16, 17, 18, 19]
```

13.3 per 100 sits squarely inside the founding 10-14 per 100 baseline, and it
is **not the artifact**. The per-frame column shows HF climbing smoothly
1.13 -> 1.34 across frames 0..17 and falling back: that is the sword entering
frame, a continuous animation ramp of **+12%**. The founding stipple frames are
a **+45% to +93%** excursion (HF 6.80-8.96 against a median of 4.65) *and*
reverse the hatch direction (d1/d2 0.50-0.92 against 1.56-1.90). Here d1/d2
never leaves 0.97-1.07. Nothing reverses; nothing steps.

The mechanism is the MAD. Over *consecutive* frames a smooth trend makes
neighbouring frames nearly equal, so `mad` collapses to 0.02 and the k=3 bar
lands 7% above the median -- any smooth excursion clears it. Over the founding
**mosaics** (sampled frames of a moving scene) the MAD is large and the bar is
a real outlier bar. So:

> `galleon_flash_rate.py` at its default k, applied to a run of consecutive
> frames, reports a rate that is set by how SMOOTH the sequence is and not by
> whether the artifact fired. A soak-derived "stipple rate" measured that way
> is uninterpretable, and it lands in the same 10-14 per 100 bracket as the
> real thing.

This lane therefore does **not** classify on the tool's default bar. See C1.

**R0c -- the founding scenes are gameplay a soak cannot reach.**
`galleon-deck-cycle.png` is a hand-driven close-up of the ship's deck filling
the frame; `galleon-town-cycle.png` is the player walking a town path. Both are
in-game. An unattended soak boots the title and lets it idle, so neither
surface is on screen at 120 s. This is the issue's own "the obstacle is
SIGNAL" finding, now confirmed from pixels rather than inferred: HF median in
the soak window is **1.20**, against 4.65 on the founding deck set.

**R0d -- and almost every schedule counter is already constant.** Over the
3,847 draws of `1789811606`:

| counter | values seen over 3,847 draws / 30 frames |
|---|---|
| `dq`, `dq_active`, `rw`, `rw_active` | `0` -- every draw |
| `in_rp`, `cb` | `1` -- every draw |
| `submits_in_frame` | `1` -- every frame, all 30 |
| `submits - tex.submit_time` (enabled stages) | `0` -- all 4,417 samples |
| `color.dirty` | 1 on 3,787 draws, 0 on 60 |
| draws per frame | 126..131 |

`draw_merge` and `draw_reorder` are prefs defaulting **false**, and the
dispatcher's `apply_env_pref` writes only the `env_vars` key of
`x1box_prefs.xml` -- so **no request this lane can queue can turn merging on**.
The merge columns are not "no signal found"; they are constants by
construction. Stating that up front is the point of F0.

## F0. The precondition: a counter that cannot vary cannot correlate

**Registered claim.** For the merge/barrier hypothesis to be *testable at all*
by this instrument on a default-pref build, at least one of the schedule
counters must take **two or more distinct values across the frames of a single
dump**. The candidate set is fixed here, before the data:

```
  per frame:  submits_in_frame
              max(cb_draws) - draws           (a mid-frame cb reset)
              fraction of draws with in_rp == 0
              fraction of draws with color.dirty == 0
              max(dq), max(dq_active), max(rw), max(rw_active)
              images_stale / img_sync == -2
  per draw:   submits - tex.submit_time, over enabled stages
```

**If every one of these is constant across every frame of every dump this lane
takes, the verdict is "NOT VISIBLE TO THIS INSTRUMENT", and it is a measured
verdict**: the hypothesis was not weighed and found wanting, it was found to
have no observable attached to it in this build. F1-F4 are then not run, and
reporting a null from them would be reporting an inert control.

**If one or more of them does vary**, F0 passes and the varying counters --
and only those -- are carried into F1-F4. A counter that is constant in a dump
is excluded from that dump's correlation and is named as excluded, so no leg
can pass or fail on a column that could not have moved.

## C1. The stipple classifier, fixed here

Registered because R0b shows the obvious choice is wrong. Over region `R`
(C2), grey, native resolution, on a dump whose session header says
`schema >= 3` and on frames whose `img_sync != -2`:

- `hf(f)` = `galleon_flash_rate.hf_energy` (imported, not reimplemented).
- `base(f)` = **median of `hf` over the ±10-frame window around `f`,
  excluding `f`**. A local median removes a smooth animation trend, which is
  the thing that manufactured R0b's 13.3 per 100.
- **`f` is STIPPLE iff `hf(f) >= 1.45 * base(f)`.** 1.45 is the *bottom* of
  the founding excursion bracket (6.80/4.65 = 1.46 .. 8.96/4.65 = 1.93),
  rounded down. It is an absolute magnitude anchored on the artifact, not a
  bar that moves with the data.
- `d1/d2` and its deviation from the same ±10 window's median are **reported
  for every flagged frame** but do **not** gate the classification: the
  founding direction figures are absolute ratios over a whole set, and I have
  no honest way to convert them into a local-window threshold. Gating on a
  threshold I cannot anchor would be a curve fit.

**C1 is validated before use, on the founding data.** `stipple_classify.py`'s
selftest runs the classifier over `galleon-deck-cycle.png` (8x5, region
4,4,196,84) and `galleon-town-cycle.png` (10x5, region 0,100,110,150) and must
recover the founding frames -- deck 4, 8, 13, 32 and town 3, 5, 7, 11, 22, 48,
49 -- to within the tolerance the selftest states. A classifier that cannot
find the artifact where it is known to be cannot be trusted to report its
absence anywhere else. If it fails that control, the classifier is wrong and
is fixed before any dump is classified, and the fix is recorded here.

## C2. The region, chosen before the dump exists

The tool's own docstring is emphatic that a null result is only about the
region given. Two regions are registered, both computed as fractions of the
640x480 native frame, and **both are reported** -- neither is chosen after
seeing which one flags more:

- `R_full` = the whole frame. The honest denominator; weak by construction,
  since the artifact is a few per cent of the pixels.
- `R_lower` = `x 0..640, y 288..480` -- the bottom 40%. This is where ground
  and deck sit in a third-person camera, it is where the founding town region
  (`y 100..150` of a 110x150-ish tile) sits proportionally, and it excludes
  the sky band that carries no texture detail.

A third region may be added only by naming it here *before* it is measured.

## F1-F4. The correlation legs, run only if F0 passes

Each leg is a statement about a **distribution over frames**, tested by
comparing the stipple-classified frames against the rest **within one dump**,
and each requires the same sign in **at least two independent dumps** (two
separate soaks, two separate app launches, two separate dump sessions) before
it counts. The founding history of this issue includes one conclusion
withdrawn for resting on a single run; #65's judges scored constants. Both
failure modes are addressed the same way: same sign twice, or it is not a
result.

- **F1 -- submission boundary.** If a draw landing on the wrong side of a
  submit is the mechanism, stipple frames must differ in `submits_in_frame`,
  or in where inside the frame a command buffer reset falls (the draw index at
  which `cb_draws` drops). *Implicated if* the stipple class's mean
  `submits_in_frame` differs from the clean class's, same sign in two dumps,
  and the within-dump separation survives C3's permutation test.
- **F2 -- stale host binding.** `tex[i].img` is the host `VkImage` the stage
  was actually bound to; `tex[i].addr/fmt/ctl0/ctl1/fil` is what the guest
  asked for. *Implicated if* a stipple frame contains a draw whose guest
  texture state matches a draw present in the clean frames but whose `img`
  handle differs (or the converse: identical `img`, changed guest state).
  *Refuted for the draws this dump can see if* the guest-state -> `img` map is
  identical across the two classes.
- **F3 -- the `submit_time` reuse key.** Texture reuse is keyed on
  `tb->submit_time` against `submit_count` (`vk/texture.c:2074`). *Implicated
  if* the distribution of `submits - tex.submit_time` over enabled stages
  differs between the classes. R0d says this was a single value (0) over 4,417
  samples, so F0 will very likely exclude it -- and that exclusion is the
  finding, not a null.
- **F4 -- surface state at draw time.** `in_rp` and `color.dirty` per draw,
  and `img_sync` / `images_stale` per frame. *Implicated if* stipple frames
  carry `in_rp == 0` or `color.dirty == 0` draws at positions the clean frames
  do not.

## C3. Guards against finding structure that is not there

- **Permutation control.** For every leg statistic, the same statistic is
  recomputed over 10,000 random relabellings of which frames are stipple,
  holding the class sizes fixed. A leg reports its observed separation
  *against that null distribution*. This is the guard against "any statistic
  over 120 frames will separate some subset".
- **Power, stated before the result.** The report prints, for each leg, the
  smallest between-class difference that the observed class sizes could have
  distinguished from the permutation null at p < 0.05. A null result is
  reported **with that number attached**, so "we found nothing" is never
  published without "and here is what we could have found".
- **No leg may be scored on a constant.** Enforced by F0 per dump, per
  counter, in code.
- **Counters excluded by construction are named, not counted.** `dq`, `rw`,
  `dq_active`, `rw_active` under `draw_merge=false`; and the whole merging
  question with them. The report prints the header's `draw_merge` /
  `draw_reorder` and refuses to describe any merge verdict as measured.

## What this design cannot do, said before it is run

1. **It cannot reach the founding scenes.** Deck planks and town path are
   gameplay (R0c). If no dump contains a frame that clears C1, the correct
   report is "the artifact did not occur in what an unattended soak renders",
   which is a statement about reachability and **not** evidence against the
   merge/barrier hypothesis.
2. **It cannot speak about merging.** No queueable request can set
   `draw_merge` (R0d). Anything this lane says about merging is about the
   *absence of an observable*, and `docs/testing/` would need a way to write a
   pref for that to change.
3. **It cannot see clears or blits.** Their hooks are gated at call sites in
   `vk/draw.c` and `vk/blit.c` which the instrument does not hook (PR #143).
4. **It perturbs what it measures.** With images on, each frame costs one
   fence wait plus a ~900 KB PPM write on the pgraph thread. A timing-sensitive
   artifact could in principle be suppressed by the act of dumping. This is why
   the long arms below run `noimages`: the F0 question is asked at a cost of
   one buffered `fprintf` per draw and nothing else.

## The runs this registers

Thor, `Galleon (USA).xiso.iso`, 200 s, armed through
`--env XEMU_FRAME_DUMP=<spec>` and collected with `--pull 'framedump_*'`.
Sizing from the recon: a 640x480 frame costs 921,600 image bytes (charged to
the cap) plus ~134 KB of draw records, so ~1.06 MB per frame with images and
~134 KB without. `FDUMP_DEFAULT_MB` is 96 and `FDUMP_MAX_FRAMES` is 600.

| arm | spec | what it is for |
|---|---|---|
| **A1, A2** | `150,after120,cap200` | the correlation arms: 150 consecutive frames with pairable images, at the parked window the recon mapped. Two of them, because one is not a result. |
| **B1, B2** | `600,after40,noimages,cap120` / `600,after150,noimages,cap120` | the F0 witnesses: 600 consecutive frames each -- 20x the recon's window, spanning boot, menu and attract transitions -- asking only whether any schedule counter ever varies. No images, so no per-frame fence wait and no write cost. |

---

# Results

(to be filled in as the runs land; nothing above this line changes afterwards)
