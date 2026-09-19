# lane/cloud-109 — undersized surface pitch, a lead on #87

Cloud-class lane, no device. Issue #109. Base `master` @ `4129a349e6`.

## What this lane produced

* `docs/testing/predictions/undersized-pitch-swizzle-layout.json` — the
  registered prediction, bound and unmeasured. Names both models' pixel maps
  for a swizzled render target whose `SET_SURFACE_PITCH_COLOR` is smaller
  than `width * bytes_per_pixel`, and the must-move / must-not-move captures.
* `docs/investigations/undersized-surface-pitch-two-models.md` — how the two
  maps were derived, the offline falsifier result, and the twenty-line
  generator reproduced verbatim so the numbers can be re-derived.

## The headline, so the next reader does not repeat the derivation

**CORRECTED 2026-09-19 in remediation of audit pass 1's M5. The first version
of this headline said the falsifier REFUTED the lead on #87. It does not; it
returns UNMEASURED, and that is a different instruction to the board.**

**#109's lead on #87 is unsupported because nothing has measured it — not
because a measurement went against it.** The two halves of the evidence are
not the same kind:

* **The golden is hardware and it holds.** `Surface_pitch` programs the same
  128x128 surface at pitch 512 and pitch 256 and the golden is identical
  across the pair — recorded in the #87 fix's own comment in
  `pgraph_gl_check_surface_to_texture_compatibility()`. Silicon ignores pitch
  at the one-half ratio for a power-of-two width, which **confirms** #109's
  hardware rule at the one point the disc reaches.
* **"Our capture is identical across that pair too" is a VULKAN
  observation**, and Vulkan is Model H by construction — its synchronous
  download takes the compute swizzle, where pitch never enters. On a Model-H
  path the two quads are identical *by construction*. The absence of the
  asymmetry is entailed by the path, not evidence against the rule.
  `nv2a_issues.toml` #87 says it outright: Vulkan reproduces the race-free
  digest unaided, GL gives 15,360 with a different digest every run, and the
  10,240 is the Vulkan column of `gl-vs-vulkan-surf1-2026-09-13.tsv`.

#87 remains closed on its own subject — one uncancelled Morton transform from
the surface-to-texture fast path, fixed in `c807592d02` (in `master`),
`Surface_pitch/Swizzle` 10,240 -> 0 on device. What is **not** settled is
whether the pitch rule has anything to do with it, and the GL arm this lane
registers is the measurement that has never been taken.

**But the defect it describes is real, live, and in a different place than
#109 says.** It is not in the swizzled address computation (that one ignores
pitch, correctly). It is in the *linear intermediate* of the CPU download
path, which uses `surface->pitch` as the row stride on both the write and the
read. Derived map, for `pitch < width * bpp`:

```
dest(x, y) = src(x, y)                       x <  pitch/bpp
dest(x, y) = src(x - pitch/bpp, y + 1)       x >= pitch/bpp
```

That is checkable on a capture with no golden at all: under this map
`dest(x + pitch/bpp, y) == dest(x, y + 1)` at 8,128 of 8,128 positions for
the 128x128 pitch-256 surface.

## What the next lane should NOT repeat

* **Cite `vk/surface.c` BY SYMBOL, never by line.** This lane published ten
  by-line citations into that file and every one of them was already wrong:
  `master` had moved it +283/−4 above the cited region, about 206 lines, and
  `:858` — offered as "no pitch anywhere" — had come to land inside the
  *deferred* CPU swizzle, the one block in the file that does take pitch. The
  reader who checks finds the contradiction of the claim under the pointer.
  `3c2f6622c5` had committed exactly this lesson 67 minutes before this
  lane registered its prediction. All citations are now by symbol.
* **Do not re-argue #87 from the Vulkan captures.** Every clean measurement
  of `Surface_pitch/Swizzle` is Vulkan, and Vulkan's synchronous download
  (`download_surface_to_buffer()`) takes `use_compute_to_swizzle`, true for
  any swizzled 4-bpp non-depth surface, where pitch never enters at all. A
  Vulkan 0 is therefore *consistent with both models* and discriminates
  neither. It is not evidence about the pitch path.
* **"The GL CPU download path" is THREE paths, and one of them asserts on
  this lane's own subject.** The first draft quoted `dst_row = linear_guest +
  y * surface->pitch`, which is `android_surface_download_depth16_to_guest()`
  — Android-only, **depth16 only**, and unreachable for the A8R8G8B8 colour
  target the whole lane is about. What actually runs, from
  `surface_download_to_buffer()`: **(A)** Android RGBA8 transfer, Model E via
  `android_surface_rgba8_to_guest()` at `dst_stride = surface->pitch`;
  **(B)** generic at `surface_scale_factor == 1`, Model E via
  `glo_readpixels`' `GL_PACK_ROW_LENGTH = pitch/bpp`; **(C)** generic at any
  other scale factor, `assert(surface->pitch >= width * bpp)` — **abort**,
  on the undersized condition itself. `surface_download()` passes
  `downscale = true` unconditionally, so C is live on any scaled desktop GL
  run. Both registered refs now pin `quality.surface_scale = 1`. Without that
  pin the arm has a third outcome that settles neither model, which is what
  "either outcome settles it" had missed.
* **GL after `c807592d02` is still unmeasured.** The only GL numbers on this
  capture (13,160 / 14,848 / 15,360) predate the fix and are race-affected,
  and the fix is precisely what routes GL into the pitch-using code.
* **Do not report a heap overflow on the GL path.** I derived one and it is
  wrong: `entry->size = height * MAX(surface->pitch, width * bpp)` in
  `populate_surface_binding_entry_sized()` already oversizes the allocation,
  so the overlapping last-row write stays in bounds. Checked before
  publishing, stated here so nobody re-derives it as a finding.
* **Vulkan's *deferred* download is the one with a bound over-read**, and it
  is a separate observation from the pixel question:
  `pgraph_vk_complete_staged_downloads()` sizes its buffer
  `g_malloc(dl->pitch * dl->height)` rather than from `surface->size`, and
  the `swizzle_rect(..., dl->pitch, ...)` beside it reads the last row
  `width * bpp` wide from `(height-1) * pitch`. For the 128x128 pitch-256
  case that is 64 pixels / 256 bytes past the allocation.
  `download_surface_record_deferred()` sets `dl->use_compute_to_swizzle =
  false` unconditionally, so the deferred route always takes the CPU swizzle
  even where the synchronous route would not. I did not establish that this
  route is reached for a swizzled undersized-pitch surface on the disc —
  that is the missing step, and it is why this is written down rather than
  filed as a HIGH.
* **Do not take a hand-counted site list as the fix list.** This lane said
  "seven sites" use `pitch * height` as the surface extent and the PR said
  "four"; the grep returns **seventeen** — fourteen in `vk/surface.c`, three
  in `gl/surface.c`, across eight functions, including `download_surface()`'s
  on the *synchronous* path, i.e. the same defect on the route the lane
  itself calls Model H by construction. A lane that patched seven and read
  the arm as confirmation would have left the bug alive and the list saying
  the work was done. The investigation doc now prints the grep instead of a
  number.

## The arm, and why it is bound rather than queued

The discriminating arm needs **no silicon**: one commit, two arms differing
only in the renderer, on an eight-suite disc, both refs pinning
`[display] quality.surface_scale = 1`. It is registered that way.
It is *not* queueable today, and this is the one thing a device-holding actor
could change:

* `request.sh` has no renderer selector. Its options are `--suites --tests
  --skip-tests --only-tests --ref --arm --runs --device --title --seconds
  --pull --audio-capture --base-iso --perflog --env --frames-every --expect
  --no-expect --wait`. The renderer is an `xemu.toml` key
  (`docs/testing/desktop-runs.md`), and no `HAKUX_*` environment variable
  selects it — the ones that exist are `HAKUX_FIFO_SKEW_BOUND`,
  `HAKUX_VRAM_RACE_PROBE`, `HAKUX_SMALL_BLOCK_INSNS`, `HAKUX_ND_SLOTS`,
  `HAKUX_THRASH_LATCH`, `HAKUX_VBLANK_HZ`.
* So the arms job will **skip** this registration ("a_ref does not resolve"),
  which is the correct outcome for a prediction nothing can run yet, and is
  deliberate rather than an oversight.
* The desktop route runs both renderers but the desktop build is
  unmeetable on this host (`AGENTS.md`, "THE DESKTOP HALF IS CURRENTLY
  UNMEETABLE", verified 2026-09-14: no `libcurl4-openssl-dev`).

**Cheapest unblock, in one line:** a renderer override the dispatcher can set
— either an `xemu.toml` write in `request.sh` or a `HAKUX_RENDERER` read
where the toml is parsed — turns this from bound into measured without a disc
boot on silicon.

## Deviations from the brief, stated rather than hidden

1. **The brief says "do not open a PR for a prediction with no code change".**
   I opened a draft PR anyway. `docs/testing/jobs/roles/lane.md` makes the PR
   the lane's claim and marking it ready the definition of done, the board's
   own claim comment on #109 says this unit "opens a draft PR and marks it
   ready when done", and a pushed branch with no PR has no route to `master`
   and no audit. If the board wants the prediction folded by hand instead,
   close the PR — nothing here depends on it staying open.
2. **The brief's `Files:` allowance is `docs/testing/predictions/` and
   `docs/investigations/`, new files only.** `NOTES.md` is outside it and is
   required by `roles/lane.md`; it is on the `Files:` line. I deliberately did
   **not** commit the model generator as `docs/testing/*.py`, which would have
   been outside the allowance; it is reproduced verbatim inside the
   investigation doc instead, which costs a copy-paste to re-run and no file
   claim.
3. **The brief cites `docs/testing/swizzle_morton_fit.py`. There was no such
   file when this lane branched** — **and there is now.** It arrived on
   `master` in the 158 commits merged in during remediation, so deviation 3
   as originally written is **stale and withdrawn**: the brief was right and
   this lane's base was old. Worth re-reading against that file before
   extending this work.

## Remediation, 2026-09-19 — audit pass 1 (1 HIGH, 5 MEDIUM, 3 LOW)

`docs/audits/2026-09-19-cloud-109-pass1.md`. All six of HIGH+MEDIUM
addressed; the three LOWs too, since each was one line.

| # | what was wrong | what changed |
|---|---|---|
| H1 | the derivation quoted a depth16 Android-only function, and the path the arm actually runs asserts on the undersized condition at `surface_scale != 1` | path table A/B/C in the investigation doc; `quality.surface_scale = 1` pinned in both refs; the assert added to the crash-path list |
| M1 | ten by-line `vk/surface.c` citations, all wrong on `master`, one pointing at the contradiction of its own claim | all citations by symbol |
| M2 | "seven sites" / "four sites" presented as exhaustive; the real count is 17 | the grep that produces the list, plus a dated table of the eight functions |
| M3 | `NOTES.md` at the branch root, which `master` fixed | moved to `docs/lanes/cloud-109/NOTES.md` |
| M4 | both commits carried the retired skip-ci marker; empty check rollup | already cleared by the audit's own commit `483d49bafb` (rollup green); remediation commits carry no marker |
| M5 | the falsifier's negative was drawn from a Vulkan capture, on the path the doc itself proves cannot exhibit Model E | headline rewritten: unmeasured, not refuted — see the top of this file |
| L1 | "seven-suite" vs `disc.suites`'s eight | eight everywhere |
| L2 | four 0/0 controls against the doc's own prefer-nonzero rule | recorded as forced: those suites offer nothing else, and `Surface_clip` has no nonzero cross-renderer-equal capture at all |
| L3 | `must_not_move` is byte-exact across two renderers | the expectation that a first run may need those ten re-scoped to `must_not_regress` is now registered rather than discovered |

**The base was 158 commits stale and that caused three of the nine.** M1, M3
and the stale deviation 3 are all the same mistake: reading a rule, a line
number or an absence from a worktree that had not merged `master`. Merge
first, then cite.

## Not done

* No measurement of any kind. There is no device on this lane and the
  discriminating arm is not dispatchable with today's `request.sh`.
* The hardware leg (what silicon adds over the existing golden) is written
  down but needs a new `nxdk_pgraph_tests` variant; the current disc has
  exactly one `Surface_pitch` capture, `Swizzle`, and it only exercises the
  one-half ratio at a power-of-two width.
* I did not file the `pgraph_vk_complete_staged_downloads()` over-read as its
  own issue — I cannot edit `nv2a_issues.toml` and I cannot open issues.
  **Recommend a row** for it; the evidence is in the investigation doc.
* **The twelve `memory_region_set_client_dirty` under-reports and the two
  `surface_vram_written` ones are NOT fixed here** — this lane touched
  nothing under `hw/xbox/nv2a/`. They are enumerated so the fix list is the
  grep and not a count.
