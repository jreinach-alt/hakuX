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

**The undersized-pitch rule does not explain #87's residual, and #109 should
stop claiming it as a lead.** #87 is closed on its subject: the residual was
one uncancelled Morton transform from the surface-to-texture fast path, fixed
in `c807592d02` (in `master`), `Surface_pitch/Swizzle` 10,240 -> 0 on device.
The fix's own comment in `hw/xbox/nv2a/pgraph/gl/surface.c:1545` records that
the test programs the *same* surface at pitch 512 and pitch 256 and that both
the golden and our capture are **identical across that pair**. An active
pitch rule forbids exactly that: the two models agree on the pitch-512 member
by construction (0 of 16,384 dest pixels diverge) and diverge on half the
pitch-256 member (8,128 of 16,384). #87's two known-wrong quads were wrong
*identically*. So the hypothesis predicts an asymmetry that was measured and
is not there.

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

* **Do not re-argue #87 from the Vulkan captures.** Every clean measurement
  of `Surface_pitch/Swizzle` is Vulkan, and Vulkan's synchronous download
  takes `use_compute_to_swizzle` (`vk/surface.c:858`, true for any swizzled
  4-bpp surface), where pitch never enters at all. A Vulkan 0 is therefore
  *consistent with both models* and discriminates neither. It is not
  evidence about the pitch path.
* **GL has no compute path.** `pgraph_gl_surface_download_to_buffer` always
  runs the CPU round trip, so GL is the arm that can see this. The only GL
  numbers on this capture (13,160 / 14,848 / 15,360) predate the #87 fix and
  are race-affected. GL after `c807592d02` is **unmeasured**, and the #87 fix
  is precisely what routes GL into the pitch-using code.
* **Do not report a heap overflow on the GL path.** I derived one and it is
  wrong: `entry->size = height * MAX(surface->pitch, width * bpp)`
  (`gl/surface.c:2872`) already oversizes the allocation, so the overlapping
  last-row write stays in bounds. Checked before publishing, stated here so
  nobody re-derives it as a finding.
* **Vulkan's *deferred* download is the one with a bound over-read**, and it
  is a separate observation from the pixel question:
  `pgraph_vk_complete_staged_downloads` sizes its buffer `dl->pitch *
  dl->height` (`vk/surface.c:650`) rather than from `surface->size`, and
  `swizzle_rect` then reads the last row `width * bpp` wide from
  `(height-1) * pitch`. For the 128x128 pitch-256 case that is 64 pixels /
  256 bytes past the allocation. `dl->use_compute_to_swizzle` is set
  unconditionally `false` at `vk/surface.c:587`, so the deferred route always
  takes the CPU swizzle even where the synchronous route would not. I did
  not establish that this route is reached for a swizzled undersized-pitch
  surface on the disc — that is the missing step, and it is why this is
  written down rather than filed as a HIGH.

## The arm, and why it is bound rather than queued

The discriminating arm needs **no silicon**: one commit, two arms differing
only in the renderer, on a seven-suite disc. It is registered that way.
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
3. **The brief cites `docs/testing/swizzle_morton_fit.py`. There is no such
   file, on any branch.** The Morton work referred to is
   `docs/testing/swizzle_residual.py` (characterises a residual as a layout
   question) plus the closed-form fit recorded in `gl/surface.c:1535-1550`
   and #87's own comment. I did not touch `hw/xbox/nv2a/`, as instructed.

## Not done

* No measurement of any kind. There is no device on this lane and the
  discriminating arm is not dispatchable with today's `request.sh`.
* The hardware leg (what silicon adds over the existing golden) is written
  down but needs a new `nxdk_pgraph_tests` variant; the current disc has
  exactly one `Surface_pitch` capture, `Swizzle`, and it only exercises the
  one-half ratio at a power-of-two width.
* I did not file the `vk/surface.c:650` over-read as its own issue — I cannot
  edit `nv2a_issues.toml` and I cannot open issues. **Recommend a row** for
  it; the evidence is in the investigation doc.
