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
