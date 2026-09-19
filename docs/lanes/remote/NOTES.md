# lane.remote — resumed 2026-09-19 onto master

The session that ran this lane through 2026-09-18 is the same one writing this.
PR #45 merged at 23:11Z that day (fold commit `fa3d04f2`), so this branch was
re-based onto `origin/master` rather than continued: all 78 of its commits are
ancestors of master and nothing was carried forward.

## What changed underneath this lane

- **The orchestrator session is retired.** The channel is GitHub issues, tagged
  `[lane.remote]` on the first line. There is no peer session to message.
- **`[skip ci]` is retired** (`preflight.sh:338`): the repository is public and
  Actions are free, so the gate this lane pushed under for four days is gone.
- **The board is `origin/board`**, and a lane may not edit `territory.toml` or
  `nv2a_issues.toml`; `preflight.sh` checks it.
- **Seven of this lane's nine claimed issues are closed.** #138 asked where the
  lane's commits lived and walled the rest behind the answer; answered by
  containment rather than by hunting for a worktree.

## Open, and what each is actually blocked on

| issue | state |
|---|---|
| #34 | not this lane's: four findings in `vk/*`, and the device confirmation is APK packaging in `android/` |
| #60 | **the subject of this note** — see below |
| #62 | finding 2 only, and it needs `gl/surface.c` **and an NDK**; the other five are fixed and verified in master |
| #88 | filed by this lane; needs `vk/surface.c`, which this lane does not hold |

## #60: the fix landed while the issue stayed open

`a105a51a` — *"a reused surface binding now refreshes its guest format"* — is in
master and carries the `drawn_format` refresh on the `is_compatible` branch of
`update_surface_part()`. **This lane's branch never carried it**: it was one of
the fifteen campaign-branch commits in `gl/*.c` that were never in this branch,
so every measurement this lane published about #60 predates the fix it was
measuring.

What this lane did measure, on its own tree without the refresh, was that
applying it regressed exactly one capture:

| capture | without refresh | with refresh (this lane, 09-13) |
|---|---:|---:|
| `Blend_surface::DstAlpha_XA_O1A7RGB8` | 81,920 | 90,112 |

and attributed those 8,192 px to **#59's pad-alpha semantics** — a surface
rendered while the guest called it a pad format, then sampled as one where
alpha is meaningful, so the raster's raw alpha shows through where hardware
reads the pad as zero.

**#59's write side has since landed in master** (`e761ee31`, with
`dualSrcBlend` enabled in `vk/instance.c` and `surface_sampled_pad_alpha` in
`vk/draw.c`). So the named cause of the regression is gone, and the
combination has never been measured: the refresh and the pad-alpha write side
are both in master and no run of this disc has been taken since.

### Registered before measuring

**Prediction.** On master, `Blend_surface::DstAlpha_XA_O1A7RGB8` reads
**81,920** under OpenGL — the pre-refresh value — because the 8,192 px the
refresh exposed were the pad-alpha defect and that defect is now fixed at its
source.

**Kill conditions, as numbers.**

1. **90,112** means the regression is live in master: the refresh is landed,
   the pad-alpha fix did not reach this path, and #60 is a live regression
   rather than a closable issue. That is the uncomfortable outcome and it is
   the more useful one.
2. Any third value means neither model is right and both get withdrawn.
3. The three captures this lane measured as recovering under #71's filter fix —
   `ARGB8_Add_SrcA_1-SrcA` 9,547, `ARGB8_Add_SrcA_DstA` 11,521 — must still
   read those values. If they moved, something else landed in this path and the
   comparison is confounded.
4. `Surface_pitch::Swizzle` is exempt: it is the guest/pgraph race (#44/#39)
   and moves within 13,160–15,360 on GL regardless.

**Not predicted:** Vulkan's values. The refresh is GL-only, so Vulkan is a
control for everything except the pad-alpha change, which moves both.

## Result: the prediction is REFUTED, kill condition 1 fired

Binary built from `master` at `415dcc69`; `iso_surf1`, one run per renderer,
236 captures each, zero assert lines.

| capture | GL | Vulkan | registered as |
|---|---:|---:|---|
| `Blend_surface::DstAlpha_XA_O1A7RGB8` | **90,112** | **81,920** | 81,920 predicted; **90,112 was kill condition 1** |
| `Blend_surface::ARGB8_Add_SrcA_1-SrcA` | 9,547 | 9,547 | control, held |
| `Blend_surface::ARGB8_Add_SrcA_DstA` | 11,521 | 11,521 | control, held |

**The regression is live in master, and it is GL-only.** Both controls hold at
the values registered before the run, so the comparison is not confounded, and
Vulkan reads the pre-refresh value on the same binary and the same disc.

### Why the prediction was wrong, precisely

It assumed #59's landed write side reaches both backends. It does not, and the
tree says so in its own words:

- `glsl/psh.c:225` — *"The GL renderer never calls the setter, so it keeps
  false and generates exactly the GLSL it generates today."* `g_dual_src_pad_supported`
  is a device property, and #59's write side is gated on `dualSrcBlend`, which
  `vk/instance.c` enables and the GL renderer never does.
- `gl/renderer.h:361` — *"GL has no host_fmt"*, so GL has no
  `sampled_pad_alpha` column at all; the Vulkan readback override lives in
  `kelvin_surface_color_format_vk_map`.

So the mechanism I named on 2026-09-13 was right and the remedy never reached
this backend. **#59's write side is Vulkan-only by construction.**

### What moved, measured rather than inferred

GL and Vulkan disagree on exactly **16,384 px**, one 128×128 region at
x[32..159] y[92..219]:

| | first half (8,192 px) | second half (8,192 px) |
|---|---|---|
| golden | `#2A2A2ABF` | `#000000FF` |
| Vulkan | `#555555FF` | `#000000FF` — **matches** |
| GL | `#6C6C6CE2` | `#FFFFFFFF` — **destination alpha read as one** |

GL differs from the golden on all 16,384; Vulkan on 8,192. The extra 8,192 is
exactly the half where the golden is black and GL paints white — the
destination-alpha-goes-to-one signature this lane described in September and
could not then attribute.

Worth noting against `psh.c:205`: the pad-alpha table has **no override for
`X1A7R8G8B8_{Z,O}`**, *"whose readback is not a constant"*, and this capture is
exactly that format. So this is not a missing table row; it is the case the
table deliberately excludes.

### Disposition

**#60's own fix is correct and landed.** `gl/draw.c:351` still reads the
guest-declared `pg->surface_shape.color_format` for the blend-side fold, which
is right, and the refresh repairs the surface-to-texture decisions that were
being made on a stale format. The 8,192 px it exposes are **#59's GL half**,
not #60's defect: the refresh made the decision correct, and a correct decision
reaches a path GL has never had the fix for.

That is the same shape as the question the board is already holding on #88 —
ship a correction that exposes a pre-existing defect, or hold it — with one
difference: here the correction is **already shipped** in master, so the choice
is only whether the exposed 8,192 px are chased or recorded.

## The finding #60 opened up: GL and Vulkan have diverged, 413,790 px (#158)

The same pair of runs answers a larger question than #60's. Comparing the two
renderers capture by capture on one binary, GL now trails Vulkan on **eleven**
captures. Against this lane's own September runs, still on disk:

**GL-behind total on those eleven: 4,608 px in September → 413,790 px now.** In
September the two renderers were byte-identical on ten of the eleven, the
eleventh differing only by the guest/pgraph race. Nothing regressed in absolute
terms; GL improved on several. Vulkan pulled away.

Every capture but `Surface_pitch::Swizzle` is a pad format — `X_O`, `X_Z`,
`X1R5G5B5_{Z,O}`, `X8R8G8B8_{Z,O}`, `X1A7R8G8B8_O`. One family.

The cause is structural rather than an oversight: #59's only landed code change
(`77bd2977`) touches `vk/draw.c` and no GL file; the readback override is a
column of a **vk** format table that `gl/renderer.h:361` says cannot exist on
this backend; and the write side is gated on a device feature `psh.c:225`
records the GL renderer as never enabling. Each decision was locally reasonable.
The aggregate is what nobody had measured.

`Swizzle` is the same shape from another lane: Vulkan is byte-exact at 0 where
it was 10,240, so #87's Morton fix reached `vk/texture.c`, and GL sits at
12,224 — worth confirming the GL half landed, since that lane held both files
as one claim for exactly this reason.

**The consequence worth more than the pixel count:** *"both renderers agree, so
the cause is upstream of both"* is no longer safe on this family. This lane used
that inference in #87 and was right to; on the pad formats the premise has
quietly expired, and nothing in the tooling flags it.

Filed as #158 rather than started: the fix crosses into #59's model, so it is a
routing question. The target is registered per capture if it comes back here.

## #158 implemented and measured: 9 of 9, and the Vulkan control held

Territory released #158 to this lane at wave 122, with `glsl/psh.c`,
`gl/renderer.c` and `gl/draw.c` — the three files the patch-shape analysis had
named. Implemented as that analysis specified, and **without** the constants-
table column it warned against.

Prediction registered before the run
(`docs/testing/predictions/2026-09-19-gl-pad-bit-write-side.json`), naming nine
targets at Vulkan's values, two captures pinned as **not** moving, and the
uncomfortable outcome in advance.

| capture | GL before | GL after | registered | verdict |
|---|---:|---:|---:|---|
| `1-DstAlpha_X_O1RGB5` | 65,536 | **0** | 0 | pass |
| `1-DstAlpha_X_ORGB8` | 65,536 | **0** | 0 | pass |
| `DstAlpha_X_O1RGB5` | 65,536 | **0** | 0 | pass |
| `DstAlpha_X_ORGB8` | 65,536 | **0** | 0 | pass |
| `DstAlpha_X_ZRGB8` | 65,536 | **0** | 0 | pass |
| `Fmt_X8R8G8B8_Z8R8G8B8` | 32,774 | **31** | 31 | pass |
| `Fmt_X8R8G8B8_O8R8G8B8` | 16,413 | **62** | 62 | pass |
| `Fmt_X1R5G5B5_Z1R5G5B5` | 30,197 | **15,678** | 15,678 | pass |
| `Fmt_X1R5G5B5_O1R5G5B5` | 18,564 | **16,483** | 16,483 | pass |
| `DstAlpha_XA_O1A7RGB8` | 90,112 | **90,112** | 90,112 (pinned) | pass |

**Nine moved, and exactly the nine predicted. Nothing else on the disc moved at
all** — 227 of 236 captures byte-identical to the pre-fix run, 0 worse.
**393,374 px recovered.**

### The control that makes this readable

`glsl/psh.c` is shared, so Vulkan is not automatically a control — but the gate
change is algebraically a no-op there (`opts.vulkan && flag` becomes
`flag && !gles`, and for Vulkan `gles` is false), and the measurement confirms
it: **Vulkan is byte-identical on all 236 captures.** A shared-file change that
moves one backend and provably not the other is the strongest form this
evidence takes.

GL's bit-exact count goes **123 → 128, which is Vulkan's exactly.**

### Where the renderers now stand

Differing captures between the two backends: **18 → 9**, and GL now *leads* on
six of the nine. GL trails on exactly two, and both are the captures registered
in advance as unreachable by this change:

- `Surface_pitch::Swizzle` (12,224) — not a pad capture; #87's layout question
  plus the guest/pgraph race.
- `Blend_surface::DstAlpha_XA_O1A7RGB8` (8,192) — `X1A7R8G8B8_O`, whose seven
  alpha bits are real data, excluded by design on both backends. This is #60's
  residual and it is now the *only* pad-family capture where GL trails.

12,224 + 8,192 = 20,416, and 413,790 − 393,374 = 20,416. The arithmetic closes.

### One correction to my own figure

The #158 analysis and its issue comment said the yield would be "~397,000 px".
The exact derived figure was **393,374** — the sum of the nine gaps — and I
rounded it upward in prose while the registered *values* were exact. The
registration is what was measured against; the prose estimate was loose and is
corrected here.

## #60's residual, characterised after #158 landed

`Blend_surface::DstAlpha_XA_O1A7RGB8` is now the **only** pad-family capture
where GL trails Vulkan. #158 did not touch it and was registered in advance not
to: `X1A7R8G8B8_O` returns `PSH_PAD_ALPHA_NONE`, so `pad_stamped` is false and
`gl/draw.c` takes its unchanged path. The capture read 90,112 before and after,
which is the pin holding.

**Both backends are far from the golden, and that is the larger half.** GL is
90,112 px from it and Vulkan 81,920. The 8,192 between them is the part that
belongs to this renderer; the ~82,000 they share is a model question about this
format and is not GL's to answer alone.

Where the two renderers differ, one 128×128 region at x[32..159] y[92..219],
16,384 px:

| | 8,192 px | the other 8,192 px |
|---|---|---|
| golden | `#000000FF` | `#2A2A2ABF` |
| Vulkan | `#000000FF` — **exact** | `#555555FF` |
| GL | `#FFFFFFFF` | `#6C6C6CE2` |

GL matches the golden on **0** of the 16,384; Vulkan on 8,192. So the whole
GL-minus-Vulkan gap is the half where hardware writes black and GL writes white
— destination alpha read as one, the signature this lane first described on
09-13.

**The structural finding, which is stronger than the pixel count.** Four
colours the golden holds appear **nowhere in our frame on either backend**:
`#2A2A2A`, `#4A4A4A`, `#818181`, `#B6B6B6`. Those are blend *results*, not
quantisation neighbours. A rounding or precision difference cannot produce a
frame that is missing four output values entirely; this is an equation or an
operand that is wrong, not a value that is slightly off.

Note also GL's alpha on the second row: `0xE2`, against the golden's `0xBF` and
Vulkan's `0xFF`. GL is producing a *varying* alpha where Vulkan produces a
constant — so the two backends disagree about what the alpha channel even
carries here, which is exactly what one would expect on the one format whose
seven alpha bits are real data and whose pad bit is not.

**Not this lane's to fix alone.** The remaining question is what
`X1A7R8G8B8_{Z,O}` should read back and blend with, which is #48/#59's model
and the one case both of their tables exclude by construction. Recorded so the
next actor starts from the measurement rather than from the pixel total.

---

## 2026-09-19, later: the environment report, and two things it turned up

The host asked five questions about this container, on the grounds that only
this session can see the answers and that one of them decides whether a second
desktop GL channel retires. The full reply is on PR #162. Two findings from
writing it are worth keeping here, because both correct something that was
being assumed rather than checked.

### The capture runner is now in the repo, and it reproduces its own history

`extract_results.py` was in the repo; its driver was not. A capture run could
therefore only be reproduced by someone who already had a container it had been
run in -- the same defect as a number nobody can re-run, applied to the
instrument instead of the result. `docs/testing/pgraph_capture_run.sh` is that
driver.

Writing it down found two bugs that the scratchpad original had carried
silently, both of which fail as *"the run produced nothing"* when the run was
fine:

* It `cd`s into the binary's directory, so a **relative** binary or disc path
  resolved against the wrong directory. Every call site had passed absolute
  paths, so it had never fired.
* The results directory on E: is a property of the **disc**, not the harness.
  `extract_results.py` defaults to `nxdk_pgraph_tests`; `iso_surf1.iso` writes
  to **`surf1`**. That fourth argument was passed by hand at every call site
  and written down nowhere, so it would have died with the container.
  The script now looks instead of guessing, and names what it found.

**Proof it is the same instrument, not a rewrite of it.** A fresh run through
the committed script -- relative path, no directory argument -- against
`p158gl`, produced four hours earlier by the scratchpad runner on the same
binary, same disc, same renderer:

    236 captures both; byte-identical on 235 of 236

The single mover is `Surface_pitch::Swizzle`, which is the texture-memory race
#71 established and #87 tracks. So the committed runner reproduces the
scratchpad runner exactly, and the run-to-run instability on this disc is still
exactly one capture wide -- an independent re-confirmation of #71 that cost
nothing, since the control was needed anyway.

### The goldens on this container are silicon, not a handheld

`lane.desktopchannel`'s `desktop_channel.sh` declines to score any desktop
capture against goldens, and `docs/lanes/desktopchannel/NOTES.md:249` gives the
reason: *"those goldens came off an Adreno running Vulkan."* On that premise
the refusal is right -- a desktop GL capture differing from another emulator's
output is evidence about renderers before it is evidence about xemu.

**On this container the premise does not hold.** `/tmp/goldens` is a git clone
of `abaire/nxdk_pgraph_tests_golden_results` at `6e159f1`, whose README reads:

> Output of [abaire/nxdk_pgraph_tests](...) on **XBOX 1.0 hardware**.

Those are real silicon captures -- the target, not a second emulator. Scoring
any renderer on any host against them is the accuracy question this campaign
exists to ask.

I cannot read that lane's disk, so I am not claiming their tree is this tree.
The check is one command -- `git -C <goldens> remote -v` -- and the layout is a
tell: `<root>/results/<Suite>/<capture>.png` with `perceptualdiff/` beside
`results/` is this repository's shape. If it matches, that lane's most
cautious sentence is its most interesting result: *"the capture produced here
is bit-identical to its handheld golden"* would read **bit-identical to
hardware**.

**What survives either way, and what this lane must not over-read.** A
software rasteriser and a GPU can both be correct xemu and still differ in the
last bit on filtered or interpolated output, so an **absolute** bit-exact count
is a property of the host as well as of the code. "GL bit-exact 123 -> 128" is
therefore a statement about this container. What is immune to all of it is
every number #158 actually rests on: GL-before against GL-after, and GL against
Vulkan, same binary, same disc, same host. Those are deltas on one machine, and
the host's rasteriser cancels.
