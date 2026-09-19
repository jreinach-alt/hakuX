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

Nothing above the `---` has been changed since it was committed. Where a run
made a registered choice look wrong, that is recorded here rather than by
editing the registration.

## The arms, as taken

All on the Thor, `Galleon (USA).xiso.iso`, built from `732b97e2df`
(`apk_sha f326072aa6c8`), driver `PurpleVK 26.3.0-devel (git-62ac221a33)`,
`draw_merge=false draw_reorder=false surface_scale=1 submit_frames=2`.

| arm | run id | spec | frames | draws | images |
|---|---|---|---|---|---|
| A1 | `1789844339-diagsoak77-A1-31125` | `150,after120,cap200` | 150 | 19,252 | 12 (8.0%) |
| B1 | `1789844343-diagsoak77-B1-32023` | `600,after40,noimages,cap120` | 600 | 117,248 | -- |
| C1 | `1789844674-diagsoak77-C1-97491` | `600,after120,cap200` | 600 | 82,288 | 78 (13.0%) |

Every one reads NOT SERIALISED on both columns, so PR #143's headline claim
replicates on three more runs and on 218,788 further draws.

## R1. The soak's timeline, from the dump's own pictures

C1's 600 frames (t≈120..145 s) catch the whole arc and settle the reachability
question from pixels:

- **frames 0..~485 -- the title screen.** "GALLEON / Please press the START
  button to begin", the logo fading in over a cliff-and-sea backdrop with
  Rhama performing a sword flourish. A1 and the recon run both landed here.
- **frames ~486..~500 -- `Loading...`**, a progress bar, then black.
- **frames ~500..600 -- the attract demo**, watermarked `Demo`: a lava cave,
  the character walking across a rock floor.

So an unattended soak DOES reach the attract demo, at about **t = 141 s**, and
`after120` straddles the transition. Neither the deck nor the town path is
among what it renders -- both founding sets are gameplay -- but the cave floor
is a textured ground surface, which is the nearest thing a soak can reach.

## R2. F0 PASSES, and which counters carry it

Over B1's 600 frames and 117,248 draws -- the widest sample, spanning boot,
menu and a transition:

| counter | verdict |
|---|---|
| `max_dq`, `max_dq_active`, `max_rw`, `max_rw_active` | **excluded, CONSTANT BY CONSTRUCTION** -- `draw_merge`/`draw_reorder` gate them shut and no queueable request opens them |
| `frac_not_in_rp` | excluded, constant (0.0) over every frame |
| `submits_in_frame` | **scored**, 35 distinct values, 2..105 |
| `cb_resets`, `cb_resets_per_draw` | **scored**, 34 / 351 distinct values |
| `frac_color_clean` | **scored**, 178 distinct values |
| `max_submit_lag`, `mean_submit_lag` | **scored**, `submits - tex.submit_time` takes 0, 1 and 2 |

That last row matters: over the recon window and over A1 the texture reuse key
was **0 on every one of 22,098 enabled-stage samples**, and F0 would have
excluded it. Over B1 it moves. So the reuse key is not a constant of the
build; it is a constant of the *scene*, and a correlation arm has to be taken
somewhere it varies or that leg is inert there.

**So the honest answer to "is it visible to this instrument" is: partly.**
Merging is not -- not flat, but shut. Deferred submission, command-buffer
batching, surface dirtiness and the texture reuse key are.

## R3. An instrument result PR #143 marked unmeasured: the image yield is 8-13%

PR #143's N1 remediation -- write no image when the display surface is still
`draw_dirty` after the download completion -- was committed with **Unmeasured:
no device ran this**. These are the first device runs of it, and the rate is
not a corner case:

| arm | frames | images written | refused as stale |
|---|---|---|---|
| A1 | 150 | 12 (8.0%) | 138 |
| C1 | 600 | 78 (13.0%) | 522 |

A1's gaps between imaged frames are `{1, 9, 10, 18}` -- a period of about ten
frames, not a scatter. So on this title the flip pre-records the display
download roughly once in ten flips, and the other nine frames' pixels never
leave their `VkImage`.

This is the instrument behaving **correctly and honestly** -- the old code
wrote a picture on all of them and said nothing -- but it is a hard limit on
#77's method, which is "pick the frames that show the artifact, then read those
frames' draws". One frame in ten can be picked from. `framedump_check.py`
already warns "a dump where this is most of the frames is not a dump to pick
frames from"; on this title that is every dump.

## R4. C1's four flagged frames are scene cuts, and the registered classifier cannot tell

C1, region `R_lower` (0,288,640,480): **4 / 78 = 5.1 per 100**, frames 489,
495, 566, 576.

```
  f489  HF 2.74  base 1.33  ratio 2.06  d1/d2 0.95 (local 0.94, dev 1.01)  neighbours 0.01 1.25 | 1.67 1.37
  f495  HF 2.19  base 1.32  ratio 1.67  d1/d2 0.97 (local 0.94, dev 1.03)  neighbours 1.25 2.06 | 1.37 1.20
  f566  HF 3.90  base 1.08  ratio 3.62  d1/d2 1.14 (local 0.95, dev 1.21)  neighbours 1.03 0.99 | 2.33 0.80
  f576  HF 2.53  base 1.09  ratio 2.33  d1/d2 0.95 (local 1.00, dev 0.94)  neighbours 0.99 3.62 | 0.80 0.80
```

All four sit in or after the `Loading...` transition R1 describes, and the
neighbour ratios say so plainly: f489 is preceded by a frame at **0.01** -- a
black frame. The `draws` leg then "SEPARATES" at p=0.012, +41.3 draws on the
flagged class, which is the same fact wearing a different hat: a frame with 41
more draws is different CONTENT.

**This is the confound the persistence descriptor was added to make visible,
and it did its job.** The registered classifier is not changed to exclude cuts
-- rewriting the bar after seeing the data is exactly the curve fit it exists
to refuse. What changes is the WINDOW: arms C3 and C4 are queued at
`600,after165`, which R1 places entirely inside the attract demo, so the
classifier sees one content regime instead of a transition. C1's flags are
recorded here as **not stipple** and are not carried into any correlation.

## R4b. C2 replicated R4's false positive, which is what makes it worth a guard

C2 (`600,after120`, the C1 replicate) flagged 11 of 115 imaged frames, and
**three legs separated: `draws` +48.2 (p 0.0000), `submits_in_frame` +2.77
(p 0.0041), `cb_resets` +2.21 (p 0.0076)** -- the same three as C1, the same
sign, in an independent run. That is precisely the criterion F1-F4 registered
for implicating a leg, and it is wrong.

The split says so: **6 of C2's 9 attract-demo frames are flagged, against 5 of
its 106 title-screen frames.** The classification is mostly *"is this a demo
frame"*, and the counters that separate are the ones that tell a 216-draw cave
apart from a 127-draw title screen.

**A permutation test cannot catch this and it is important to say why.** It
guards against *random* structure by reshuffling the labels; the scene is a
property of the frame, so every reshuffle carries the scene along with the
label. The null it builds is the right null for "did some subset separate by
chance" and the wrong one for "is the subset a different scene".

So `framedump_correlate.py` now reports the flag rate by draw-count bucket
**before** any leg and marks them all `DESCRIPTIVE ONLY` when it is not flat.
On C2: `0.0, 0.0, 16.7, 20.0` per 100, monotone in draw count, with
`spearman(HF, draws) = +0.413`.

Writing the guard's selftest then found a defect **in the guard**: Spearman via
`argsort(argsort(x))` breaks ties by index, so a *constant* column ranks
`0..n-1` in frame order and correlates with anything that trends. A one-scene
fixture scored `rho +0.665` and tripped the warning it exists to stay silent
for. Ties are averaged now and a constant column returns 0, pinned in both
directions. The same one-liner also had `np.percentile` return four identical
bucket edges on a small-integer column -- three empty buckets and one holding
everything, which reads as a flat rate and is no reading at all.

## R5. A1 had no power, and says so

A1 classified 12 frames and flagged none. At the class size #77's own
documented 12 per 100 would have produced (k=1 of 12), the minimum difference
it could have separated from a permutation null was **0.91 on
`submits_in_frame`** -- nearly the counter's whole observed range -- and
`cb_resets` had **zero spread among the imaged frames** despite varying across
all 150. That is not a null result. It is an arm with no power, and it is
reported as one.

## R6. `--frames-every` returns pure black on this device, and the dump does not

Arm D1 asked for a screen frame every 5 s over a 300 s soak to map the
timeline. It returned 58 PNGs and **every one is exactly black: max pixel 0,
0.0000% non-zero, on all 58.** `start_frame_capture` deletes empty files, so
these are `adb exec-out screencap -p` calls that succeeded and returned an
all-zero image.

Bounded honestly, because this artifact cannot tell the candidates apart:

- **What is established.** On the Thor, on this title, at this moment, the
  dispatcher's screen-frame path yields no signal at all. D1 is the **only**
  soak in the whole results archive that has ever set `--frames-every` (1 of 1),
  so there is no earlier run showing it working and **nothing published rests
  on it** -- this is not a regression anyone can point at, it is a first use
  that came back empty.
- **What is not established.** Whether this is the screen fault the fleet was
  held for, whether `screencap` cannot read this app's surface, or something
  else. Three candidates, one all-zero artifact, and no way to separate them
  without touching the device -- which this lane may not do.

**What matters for #77 either way:** the frame dump reads the display surface
out of **guest VRAM**, not off the screen, and C1 and C2 returned real pictures
from the same handheld in the same minutes. So whatever blacks out `screencap`
does not touch the dump, and on this device the dump is currently the only
working way to see what the emulator renders. Every screen-derived measurement
this issue has accumulated -- the 2.25x upscale, the 0.40 modal scrim, the
25-75% detection bracket -- belongs to an instrument that is now returning
zeros here; the dump's PPMs are native, uncomposited and unaffected by all
three.
