# Prediction: what raises the GL error that aborts the line disc

Registered 2026-09-14 on `b0059688`, before instrumenting.

## The finding

`iso_line` **aborts** on HEAD under OpenGL and produces zero captures:

    lrepro: QEMU_EXIT=134 in 13s, renderer: OpenGL
    gl/shaders.c:413: pgraph_gl_shader_load_from_memory:
        Assertion `glGetError() == GL_NO_ERROR' failed.

Reproduced twice. Seven suites on that disc cannot be measured at all.

This is the signature `predictions/issue66-surface-bind-when-absent.json`
documented, where it capped `iso_surf1` at 44 of 236 captures. **#66's fix
worked** -- `iso_surf1` gave all 236 captures today -- so this is a SECOND
source of a pending GL error, not a regression of that one.

The assertion is at the TOP of `pgraph_gl_shader_load_from_memory`, so the
shader loader is the messenger and not the culprit: some earlier GL call raised
an error that nobody consumed.

**Desktop only.** The same function drains errors in a loop under
`#ifdef __ANDROID__` and only asserts in the `#else`. So no Android arm can see
this, and it is visible only through this lane's desktop-GL capability.

## The prediction: `glLineWidth(0)`

`gl/draw.c:367,373,377` clamp only the TOP of the range:

    glLineWidth(MIN(r->supported_aliased_line_width_range[1],
                    (pg->line_width / 8.0f) * pg->surface_scale_factor));

There is no floor and no zero guard. The GL spec raises `GL_INVALID_VALUE` for
width **<= 0** (values merely below the supported range are clamped silently,
which is why only zero and negatives matter). A guest line width of 0 gives
`0 / 8.0f * scale == 0.0f`, `MIN` leaves it at 0.0, and `glLineWidth(0.0)`
raises `GL_INVALID_VALUE` (0x0501).

A suite named `Line_width` is exactly where a guest would set 0.

## Discriminator

Instrument with `glDebugMessageCallback`, NOT `glGetError`.
`issue66-surface-bind-when-absent.json` records why in as many words: glGetError
"returns and CLEARS one error per call, so it counts pendings not raises -- that
mistake is why an earlier report on this issue said 'one per run'". The callback
reports the raise at its source.

- Callback fires `GL_INVALID_VALUE` with `glLineWidth` in the message, or the
  raise is traceable to `draw.c:367/373/377` -> **prediction holds**.
- A different error or a different call -> **prediction fails**, and the
  callback names the real one anyway, which is the point of using it.

## What I will NOT do if it holds

Delete the assertion, or drain errors on desktop the way the Android branch
does. That branch is itself a workaround; copying it to desktop would hide this
defect and every future one, and the assertion is the only reason this was found
at all. The fix is to stop raising the error.

Nor will I assume `MAX(range[0], ...)` is the right floor without checking what
the hardware does at line width 0 -- a zero-width line may be specified to draw
nothing rather than to draw a thin one, and clamping up to 1.0 would then be a
visible wrong answer rather than a crash. That is a separate question and it is
flagged here so a passing measurement cannot later be read as settling it.

---

## Outcome: prediction confirmed exactly, and the probe proved causation

    HAKUXPROBE lw alias raw 0 w 0.000000 err 0x501     x7

`raw 0` is the guest line width, `w 0.000000` what reached the driver, `0x501`
is **GL_INVALID_VALUE**. Seven raises, all from the aliased branch, all at
width 0. Exactly as predicted, down to the error code and the call site.

**Causation, not correlation, and by accident.** The probe reads `glGetError()`
after the call, which CONSUMES the pending error. That one drain was the only
change, and the disc went from aborting at 0 captures to
`QEMU_EXIT=0` with **134 captures**. Nothing else was touched. So
`glLineWidth(0)` is not merely *a* source of the pending error, it is *the*
source.

## The fix, and why it is behaviour-identical

A call GL rejects is a no-op, so skipping it leaves the same line width in
effect. `set_line_width()` calls `glLineWidth` only for width > 0.

Proven rather than argued -- **134 of 134 captures byte-identical** between the
fixed arm and the drained probe arm. Compared with `cmp`, not scored.

## Controls

- `iso_line`: `QEMU_EXIT=0`, 134 captures, **0 assertions**. Was exit 134
  (SIGABRT) and 0 captures, twice.
- Probe strings absent from the shipped link (count 0).
- `iso_surf1` re-run against the clean baseline: **235 of 236 byte-identical**.
  The single mover is `Surface_pitch::Swizzle` at 32,768 -> 31,232, a delta of
  1,536 -- well inside the 6,468 spread measured TODAY on identical code
  (`9d020102`). That is the known instability and not this change.

## What the disc is worth, now that it can be scored at all

134 captures, 16 exact, 6,116,520 differing channels across seven suites that
had never been measured under GL:

    2D_Lines            13 captures   1 exact      9,371
    Line_width          61 captures   1 exact  4,514,611
    Point_params        25 captures  10 exact    457,632
    Point_size          21 captures   4 exact     61,785
    Smoothing_control    2 captures   0 exact    319,001
    Stipple_tests        6 captures   0 exact    149,416
    Swath_width          6 captures   0 exact    604,704

That is not a claim about defects -- it is the first baseline for a disc the
fleet could not run, and it wants the discriminating-power filter from
`surf1-residual-triage.md` before anyone ranks it.

## Held to, from the top of this file

The assertion was NOT deleted and desktop was NOT given the Android drain loop.
The assertion is the only reason this was found, and it is still armed.

And the fix does NOT decide what hardware draws at line width 0. Clamping up to
the minimum supported width would answer a question nothing has measured; this
changes a crash into the behaviour we already had, no more.
