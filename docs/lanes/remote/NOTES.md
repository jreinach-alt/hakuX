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
| #62 | finding 2 was implemented on `a5fdb6a7` and then **WITHDRAWN — reverted in `d7ef9820`** (audit pass 2c, A1): the condition it added is unreachable, because `pgraph_gl_check_surface_to_texture_compatibility()` refuses every replication-expanding texture format at `gl/surface.c:1543`, and has done since `c234c1cc`/`f0095555` on 2026-09-12 — the day *before* #62 was filed. **The device ask is withdrawn**; there is nothing here for a device lane to confirm. `gl/surface.c` is byte-identical to master on this branch. The other five findings were already fixed and verified in master. See the pass-2c section at the end of this file |
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

---

## Audit pass 1 on PR #162: what was taken, and the one finding that could not be

`job.cloud` returned **1 HIGH, 1 MEDIUM, 4 LOW** on `44b35be1`. It is a good
audit — it confirms the mechanism, the gating, the format coverage and the
control argument, so none of that needs re-deriving, and the two findings that
matter are both real.

### H1, taken — and the audit's cheaper alternative does not work

`GL_SRC1_ALPHA` and `GL_ONE_MINUS_SRC1_ALPHA` are not GLES tokens, and
`pad_write_color_factor()` named them outside any guard, so **the arm64-v8a
build did not compile**. Dead code still has to parse. The runtime exclusion
had landed in `gl/renderer.c` and in both `psh.c` gates; the compile-time one
had landed nowhere.

**I shipped this and reported the head as green.** The desktop build *was*
green and `preflight.sh` *was* green end to end — both true, and neither builds
for Android. I had also just written in the environment report that Desktop
build was green on this head, which was accurate and incomplete: I tried to
read the check runs, the tools I have did not expose them, and I moved on
instead of going after the Actions API. The green I could see is not the green
that matters.

The audit offers two forms and says either is fine: guard the branch, *or*
"make `pad_stamped` `false` under `#ifdef __ANDROID__` before the `if`". **The
second does not work** — a compile-time-false `bool` does not stop
`pad_write_color_factor(...)` inside the branch from having to be parsed, and
under the guard that function does not exist. Guarding the whole branch is the
only one of the two that compiles. Worth recording, because taking a correct
finding's incorrect remedy on trust is a way to be wrong while doing as you
were told.

Verified two ways, neither of them the desktop build alone, since the desktop
build was already green while Android was red:

* **Mechanically** — stripping the `__ANDROID__`-false branches leaves **zero**
  code references to the SRC1 tokens, while the desktop side still names them
  at the two lines that should.
* **Behaviourally** — a full disc run on desktop OpenGL, before and after,
  **byte-identical on 235 of 236**, the single mover being
  `Surface_pitch::Swizzle`, the race #71 established. A compile-only fix has to
  move no pixel, and it moves none.

The check that actually closes H1 is the Android job going green, and that is
CI's to make: **there is no NDK in this container.**

### M1, NOT taken, and it is a measurement limit rather than a judgement call

#59's write side has two halves and I ported one. `vk/draw.c:894-907` overrides
the clear colour's alpha per pad mode; the GL clear calls the shared
`pgraph_get_clear_color()` raw, whose alpha switch has no case for the four pad
formats and falls to `default: *a = 1.0f`. So as of `7ffcd2bc` a GL
`X8R8G8B8_Z8R8G8B8` surface holds alpha **0 where the raster drew** and **1
where the clear wrote**. Hardware holds 0 in both. That internal inconsistency
is new, even though no individual pixel moved away from hardware — which is
why the audit rated it MEDIUM and why the result table cannot show it.

The audit's option (a) is to take the fix *with a prediction registered first*,
bound by `Clear::SCF_X8R8G8B8_Z8R8G8B8` and `Clear::SCF_X1R5G5B5_Z1R5G5B5`, and
warns that taking it **without** one is the thing to avoid.

**I cannot register that prediction, because the Clear suite is not on this
disc.** `iso_surf1.iso` carries fourteen suites — Blend_surface,
Color_Zeta_Disable, Color_mask_blend, Color_zeta_overlap, Image_blit,
Null_surface, Surface_clip, Surface_format, Surface_pitch,
Texture_Framebuffer_Blit, Texture_format, Texture_perspective,
Texture_perspective_enable, Texture_render_target — and **no `Clear`**. A disc
that has it would have to be built with nxdk, which this container does not
have (environment report, question 2). So option (a) is not "harder here", it
is unavailable: I would be shipping a four-line behavioural change to a path I
have no way to observe, which is the same defect as a number nobody can re-run.

Taken as option (b), but with the work specified rather than merely declined:
the omission is named in the PR body beside the `sampled_pad_alpha` one, the
captures it leaves wrong are named, and the fix is filed as its own issue with
the call site, the Vulkan function to mirror and the two prediction keys, so
whoever holds a disc with the Clear suite can take it without re-deriving any
of this.

### L2, taken with the correction it points at

The `GL_SRC_ALPHA_SATURATE` comment had reverted to the argument-from-absence
that `vk/draw.c`'s own pass-1 audit retired as *its* L2. It now carries the
derivation instead — `min(As, 1 - Ad)` is 0 for **both** pad variants once the
stamp lands, so nothing needs substituting whatever a disc contains — with the
corpus observation kept as the secondary note it is there. A wrong comment on
right code is believed, which is the whole reason that finding is worth making
twice.

### L1, taken. L3, taken as prose. L4, noted and not acted on.

**L3** is right: the prediction's prose named `Surface_pitch::Swizzle` in a
kill condition and no leg bound it, so half of a stated kill condition could
not have fired. The reason it was unbound is good — Swizzle's GL value is not
stable run to run, moving within 13,160–15,360, so a machine leg on it would
fire on the race rather than on the change — and today's two control runs put
the same number on it again from a third and fourth direction.

**I am not editing the registered artifact to fix this.** That prediction has
already been measured and its sha256 is cited in the PR body; rewriting it now
would make the hash in the record disagree with the file, and retrofitting a
leg onto a spent prediction is exactly the move the whole registration
discipline exists to prevent. The honest form is the one the audit offers as
its alternative — say it in prose — so: **`Surface_pitch::Swizzle` was excluded
from the machine legs deliberately, because its GL value is not stable run to
run; the kill condition on it was a manual check, and it was made.**

**L4** — the index provenance now records `/home/user/…` where the sweep host
writes `/home/justin/…`, and will flip back next time it is regenerated there.
Nothing reads it; `cmd_check()` compares `symbols`, `sites` and `suites`, and
the gate reads `tests_commit`, which is unchanged. It is churn, and the field
wants to be relative or dropped rather than an absolute path from whichever
machine last built it. Not this PR's to change.

## Audit pass 2 on PR #162: both MEDIUMs were in the instruments, not the renderer

Pass 2 closed all six pass-1 scenarios and did not reopen `hw/`. Its two new
findings (N1, N2) were both in tooling added *after* pass 1 read the diff, and
both were the same defect wearing different clothes: **an instrument that
states a guarantee in prose and does not implement it.** That is the failure
mode this repository has paid for most often, so the remediation is not just
the fix -- it is a fixture per invariant, and a mutant per fixture.

### N1 -- `gles_token_check.py` hid the `#else` arm of every conditional it did not understand

The frame stack inverted `live` on `#else` even for a frame whose condition was
unknown-and-assumed-live, so that arm was marked dead and never scanned. The
docstring promised the exact opposite in as many words: it "can report a line
some other guard excludes, **never hide one**."

Fixed by recording per frame whether `__ANDROID__` decided it and inverting on
`#else` only for those; an unknown condition now leaves both arms live.

Verified rather than asserted:

* `--selftest` is **9/9**, and against a scratch copy with the one-line fix
  removed the N1 fixture **FAILS and the other eight are unmoved** -- so it
  catches that defect and is specific to it.
* The two lines pass 2 named as invisible are now scanned: `gl/debug.c:67-68`
  (the `glEnable(GL_DEBUG_OUTPUT)` arm of `#if defined(__APPLE__)`) and
  `gl/debug.h:55-61` (the macro arm of `#if DEBUG_NV2A_GL`). Both are what an
  Android build compiles. 7,341 non-blank lines are visible on the default
  target now.
* The check has not lost power: `gl/draw.c` at `7ffcd2bc` still reports
  **:151 and :153**, the two lines by number that the arm64-v8a compiler
  reported, and `hw/xbox/nv2a/pgraph/gl` is still `13 files scanned, 0
  findings` -- which is the regression guard on a fix that makes *more* code
  visible.

**The `#elif` half had no failing case, and now does.** Pass 2's remediation
note asked for `#elif` to stop the following `#else` inverting a value that was
never derived; the fix does that, but nothing exercised it, and an invariant
with no failing case has not been tested. Fixture
`else-after-elif-on-an-android-frame` added. Against a mutant that drops the
`decided = False` on `#elif`, that fixture alone goes red -- verified here, not
taken from the commit that added it.

**Its expectation of 1 was recorded as a deliberate FALSE positive, and that is
wrong; it is a true positive.** The claim was that on Android the `#ifndef` arm
is skipped and "the `#elif` chain is what gets compiled, so this `#else` really
is dead there". That silently assumes `SOME_OTHER_THING` is defined. It is not
-- it is a made-up token in a synthetic fixture -- so the `#elif` is not taken
and the `#else` arm is precisely what an Android build compiles. Settled with
the real preprocessor rather than by argument:

    $ gcc -E -D__ANDROID__ fixture.c
    static GLenum c(void) { return GL_SRC1_ALPHA; }

    $ gcc -E -D__ANDROID__ -DSOME_OTHER_THING=1 fixture.c
    static int b(void) { return 0; }

The code and the expectation were right; only the reasoning attached to them
was wrong. **That is pass 1's L2 recurring one level up** -- a wrong
justification on correct code, which is believed -- and here it was load
bearing in a way L2 was not: a reader told this finding is a known false
positive would be right to "correct" the fixture to expect 0, and that reopens
the `#elif` half of N1 with the fixture still green.

### N2 -- `pgraph_capture_run.sh` named the mislabelled-renderer hazard and then did not fail on it

It checked that *some* renderer was reported and never compared it to the one
requested, so a run that asked for OPENGL and came up on Vulkan printed one
informational line, exited 0, and extracted captures under the OPENGL tag.
Worth fixing on this lane rather than later because **the instrument's
silent-failure mode and this lane's headline have the same shape**: "GL is now
byte-identical to Vulkan" is both the result and what a both-on-Vulkan sweep
would manufacture. The instrument has to be the thing that refuses.

The fix is six lines and was already on the branch. What was missing is that it
had been proven **once, in a commit message** -- and a commit message is not a
fixture. `docs/testing/pgraph_capture_run_selftest.sh` now holds three cases
with every external part stubbed (no emulator, no firmware, no disc, no X
server), so it runs on a cloud container in a second:

| case | stub reports | RENDERER | must |
|---|---|---|---|
| 1 | Vulkan | OPENGL | die, naming both renderers, before extracting |
| 2 | OpenGL | OPENGL | **not** fire, and reach the extractor |
| 3 | nothing | VULKAN | hit the pre-existing never-reported-a-renderer die |

13 assertions, all pass. They are a mutant/control set on purpose: case 1 needs
the comparison to fire and case 2 needs it not to, so a blanket `die` -- the
cheapest way to pass case 1 -- fails case 2. Confirmed by deleting the six
lines from a scratch copy and pointing the fixtures at it with `RUNNER=`:
**case 1's three message assertions go red, cases 2 and 3 unmoved.**

Every assertion is on **words in the message, not the exit status**, because
the runner exits non-zero for a dozen other reasons and an exit code cannot
say which refusal happened -- or whether any did.

### Two things writing those fixtures taught, both worth not repeating

1. **The harness reproduced the runner's own `cd` bug against itself.** The
   stub directory went on `PATH` as a relative path, and the runner `cd`s into
   the binary's directory before launching, so `xvfb-run` stopped resolving.
   The runner absolutises `BIN` and `ISO` at :56 for exactly this reason; the
   fixtures now absolutise `$T` for exactly this reason too.
2. **Case 3 was green for the wrong reason first.** With `xvfb-run` missing,
   no renderer was reported, so "the emulator never reported a renderer" fired
   -- the assertion passed while nothing under test had run. Every case now
   also asserts the stub itself ran (`nv2a: init` in the log). A refusal you
   cannot distinguish from a broken harness is not evidence.

### Not done, deliberately

`gles_token_check.py` is still **not wired into `preflight.sh`**. That is part
of why N1 is MEDIUM and not HIGH -- the Android CI job is the gate of record
and runs on every PR -- and `preflight.sh` is not this lane's file. A later
lane that owns it should add the call; the script's `--selftest` is there to
make that safe.

---

## Audit pass 2b: the marker check reported `clean` without scanning anything

Pass 2b closed N1 and N2 by building mutants rather than by reading the commit
messages that claimed them, and confirmed `cb141001`'s preprocessor correction.
It then found a **MEDIUM in the file that had landed after pass 2 and that no
audit had read** — `skip_ci_marker_check.sh`, 117 lines old at the time.

### P1 — `clean`, exit 0, having read nothing

`git log --format='%H' "$range" 2>/dev/null` sent its error to `/dev/null`, so
an unresolvable range produced no commits, the loop ran zero times, `found`
stayed 0, and the caller printed **`clean` and exited 0**. Nothing in the output
told `"I read 24 bodies and none carried it"` apart from `"I read nothing"`,
because the count was never printed. The default range's left endpoint is
`origin/master`, which a single-branch clone or a worktree off a bare mirror
need not have.

**This is the fourth instrument in one day to report success without having
done the work** — after the desktop build standing in for Android, the GLES
checker hiding the arms it could not resolve, and the capture runner scoring a
mislabelled run. Same shape every time, and this one was written in the commit
that was *about* preventing silent failure.

Fixed by resolving the range first and reporting the count, so a clean verdict
now states how many bodies it read.

**The first fix for it did not work, and the way it failed is worth more than
the fix.** `resolve()` called `exit 2`, and the caller ran it as
`N=$(resolve "$RANGE")` — where the `exit` killed the **command-substitution
subshell** and the script carried on to print `clean` and exit 0. The guard
fired and the code proceeded anyway, which is P1's own shape reproduced inside
P1's remedy. It was caught by **re-running the reproduction after fixing**,
not by reading the patch. `resolve` now returns a status and sets a global;
the caller checks it.

### P2 — `pipefail` plus `grep -q` loses a marker in a large body

`git log … | grep -qF` looks equivalent to a string test and is not: `grep -q`
exits at the first match and closes the pipe, `git log` is killed by SIGPIPE,
the pipeline's status becomes 141, and `set -o pipefail` propagates it — so a
body past the 64 KB pipe buffer reports NOT FOUND **for the one reason that it
WAS found.** Reproduced before fixing: 4/16/32/60/64 KB found, 128 KB missed.
Replaced with a `case` on a captured string: no pipe, no buffer, no SIGPIPE.

Pass 2b rated it LOW on a measurement worth keeping: the largest commit-message
body in this repository's last 3,000 commits is **10,919 bytes**, six times
under the threshold, so no commit that exists today can hit it. A latent hazard
in a new instrument, not a live miss.

### Both now have failing cases, and the fixtures are specific

`--selftest` is 7/7. Against a mutant that restores the unresolved-range
behaviour, the two P1 fixtures go red and the rest are unmoved; against one
that restores the pipe, only the large-body fixture goes red.

One fixture failed on its first run for a reason worth recording: the assertion
`grep -q 'clean'` matched the **refusal** text, which contains the sentence
*"This is not a clean result"*. The fixture was right to fail and the assertion
was wrong. Anchored to `^clean`, the verdict being the only line that starts
with it.

### P3 — the file was on no `Files:` line and in no lane record

Corrected: `skip_ci_marker_check.sh` is now on the PR's `Files:` line, and this
section is its lane record. It is **deliberately not wired into
`preflight.sh`**, which is not this lane's file — it is a standalone for
whoever owns that gate, exactly like `gles_token_check.py`.

### P4 — pass 2's record said this branch carries no marker; it does

Pass 2's "checked and did not find wrong" list stated that none of the branch's
commit bodies carries the retired marker. `14312cb34f` does, and **the
instrument this branch added is what shows it**. Already recorded on the PR
before pass 2b raised it; it stays unfixed, because both registered prediction
refs are descendants of that commit and rewording it would rewrite history a
live prediction depends on.

## #62 finding 2, landed on `a5fdb6a7` — and what no audit had read yet

> **SUPERSEDED — read this section as the record of what was believed on
> 2026-09-19 at 19:16Z, not as the state of the tree.** `a5fdb6a7` was
> **reverted** in `d7ef9820` after audit pass 2c found its condition
> unreachable; the correction, the chain that refutes it and the arithmetic
> that survives are in *"Audit pass 2c, A1"* at the end of this file. Every
> reachability claim below is wrong. The *territory* paragraph immediately
> following, and the format-table readings, are unaffected and still correct.

Written by the remediation pass, not by the commit's author, because the commit
landed **three minutes before this PR was claimed for remediation** and after
the lane's own "nothing under `hw/`" status comment. So it is recorded here
rather than left to be re-derived.

**The grant is real, and checking it needs the right copy of the file.** The
`docs/testing/territory.toml` in this worktree is **wave 94 (2026-09-18)**: it
does not list `gl/surface.c` under `[lane.remote]`, it names the file *out* of
the glob and grants it to `lane.swizzle87` at wave 86. Read that copy and this
commit looks like a territory violation. It is not one — that copy is
fold-lagged by thirty waves.

The live board is **`origin/board:territory.toml`** (repository root, not under
`docs/testing/`), and `check_territory.py` reads it from there rather than from
the tree. At **wave 124, 2026-09-19T20:06:21Z** it has
`hw/xbox/nv2a/pgraph/gl/surface.c` first in `[lane.remote].files`, absent from
`[free]`, and `lane.swizzle87` retired out of the file entirely. So the grant
is on the **machine-read field**, not only in prose, and
`check_territory.py` reports `territory ok (wave 124, 29 lanes, 75 files
claimed)` against this tree.

The decision behind it is `[host.session]` on **#62 at 19:24:28Z**:
*"`hw/xbox/nv2a/pgraph/gl/surface.c` is GRANTED. Outright"* — made after
checking that `swizzle87` had retired with PR #139 merged, and **removed from
`[free]` in the same commit**, so the file is never listed both free and
claimed (the #161 repo-wide outage). Two lessons for the next reader: ask the
live board, and a grant that does not also release is not half a grant.

**The change.** One condition at `gl/surface.c:1331`: a surface whose drawn
format is `LE_R5G6B5` no longer takes the Android `render_surface_to()` blit,
because the driver's normalized conversion is the exact ratio
`round(v * 255 / (2^b - 1))` where silicon replicates bits. Excluded, it falls
through to `android_surface_guest_to_rgba8()`, whose R5G6B5 case at `:552`
already replicates. The gate is minimal and it is the right one:
`android_surface_to_texture_rgba8_compatible()` switches on
`pgraph_gl_surface_drawn_format(surface)` and admits `LE_R5G6B5` through
exactly one arm (the case at `:887`, whose only `true` returns are the
`LU_IMAGE_R5G6B5`/`SZ_R5G6B5` textures), so the new term removes that arm and
nothing else.

**What this change is NOT covered by, stated so nobody mistakes a green head
for evidence.** The whole block is `#ifdef __ANDROID__`. The desktop build
cannot execute it and the 236-capture run cannot exercise it; the Android CI
job compiles it and no more. That is H1's lesson in this same PR — the desktop
build standing in for Android — and it applies to the *behaviour* here even
though the *compile* is now gated. Behaviour on a device is unverified and is
the host's by the split agreed on the issue.

### An adjacent path the same argument reaches, NOT taken here

`rgba8_compatible()` also admits **`LE_X1R5G5B5_Z1R5G5B5`** (the case at
`:877`), and `gl/constants.h:388-391` maps both `X1R5G5B5_Z` and `_O` to
**`GL_RGB5_A1`** — read at the table itself, not from the prose comment at
`gl/surface.c:3082` that says the same thing. `GL_RGB5_A1` is
5 bits per colour channel, so `render_surface_to()` hands the driver the same
ratio expansion this commit just excluded R5G6B5 for, and on the face of it the
identical one-step error remains on X1R5G5B5 surface-to-texture on Android.

**It is recorded rather than fixed, deliberately.** #62 finding 2 is R5G6B5;
this is a different format on a path nothing in this container can build or
measure, and widening an Android-only fix on inference — the same inference
that produced the ratio/replicate model, not a measurement of this path — is
how a cheap correct change becomes an unverifiable one. It belongs to whoever
takes #62's device half. Flagged on the PR for the auditor to rate rather than
quietly taken.

---

## Audit pass 2c, A1: the #62 finding-2 fix could not execute, and the finding was stale when I filed it

Pass 2c closed P1–P4, each against a mutant it built rather than against the
commit message claiming them, and then read the one code commit no pass had
seen — `a5fdb6a7`, which I had flagged as the only unaudited code on the head.
**Its condition is unreachable and its central claim is false.**

### The chain, verified here rather than accepted

`a5fdb6a7` rested on: *"Both gates in front of the blit admit R5G6B5 … so the
blit is taken."* Both readings are correct. **There is a third gate in front of
both of them, and it refuses.**

| step | site | fact |
|---|---|---|
| the only call site | `gl/texture.c:927` | `pgraph_gl_render_surface_to_texture()` is called nowhere else in the tree |
| its guard | `gl/texture.c:801` | `surf_to_tex = pgraph_gl_check_surface_to_texture_compatibility(...)` |
| the refusal | `gl/surface.c:1543` | `if (pgraph_texture_format_is_converted(texture_fmt)) return false;` |
| ordering | `:1543` before `:1587` | the refusal precedes **every** `return true`, including the `__ANDROID__` early one |
| why R5G6B5 is caught | `pgraph/texture.c:143` | `is_converted()` falls through to `expands_by_replication()`, true for both `R5G6B5` spellings |
| why no pair escapes | `rgba8_compatible()` | an R5G6B5 **surface** is accepted only for `LU_IMAGE_R5G6B5` / `SZ_R5G6B5` **textures**, and both are converted |

So for every surface/texture pair that could have reached my condition,
`surf_to_tex` is false and `render_surface_to_texture_slow()` is never entered.
The four lines could not run.

### What I actually did wrong, which is not "missed a gate"

I re-verified the two gates the issue named, at the tip, on the day I wrote the
fix — and **never asked whether the function containing them is reached.** Local
facts checked, reachability assumed. That is the day's pattern in its purest
form: not a wrong measurement, but a correct measurement of something that does
not run.

Worse, **the finding was already dead when I filed it.** The `is_converted`
refusal landed in `c234c1cc` and `f0095555` on **2026-09-12**; #62 was filed
**2026-09-13**. So finding 2 described a path that had been closed the day
before, and neither the filing nor six days of subsequent passes over the issue
caught it. Finding 1's abort is in the same position — the `default:
g_assert_not_reached()` it fixed is equally unreachable through this route — so
that fix is inert too, though harmless.

### The decision on the four lines: REVERTED

Pass 2c offered keep-as-documented-guard or revert, and said the choice is the
lane's. Reverted, byte-identical to the pre-commit file, because **a guard that
cannot execute cannot be tested.** There is no fixture for it, no run that
exercises it, and no way to show it does the right thing when it becomes live.
Keeping untested unreachable code because it might be correct later is the same
claim-without-evidence this branch has spent the day removing from its own
instruments; relabelling it "defensive" would make the comment honest and the
code no more verifiable.

`packed-texel-expansion.md` calls the `is_converted` refusal its *"least
certain point"*, so the gate may well be relaxed. Whoever relaxes it will be
running the tests that make this path live, and can write the exclusion then
with a measurement attached — which is strictly better than inheriting four
lines written blind.

### What survives, and it is the larger half

The arithmetic is correct and is about the model, not the route:

* 5-bit channel: 4 of 32 values differ, max one step
* 6-bit channel: 10 of 64 differ
* whole pixel: **23,200 of 65,536 (35.4%)** — R 8,192, G 10,240, B 8,192
* endpoints agree in both rules, so it never shows as a black or white shift
* the 09-13 figure of 30,720 (46.9%) is reconciled: that was against the old
  **truncating** scalar tail; the GPU **rounds**. 30/64 truncating, 10/64
  rounding. Both right for what they measured.

Ratio-versus-replication is still a real divergence from silicon wherever a
5/6-bit surface is decoded by the host. It is the *surface-to-texture blit*
route that does not exist, not the discrepancy.

**The device ask is withdrawn.** #62 finding 2 has nothing for a device lane to
confirm, and the offer should not have stood after this was known.
