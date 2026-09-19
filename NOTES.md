# lane.glerr86 -- #86, the Android shader-load drain

Branch `lane/glerr86`, base `master @ a1691ae68e`, PR #128.

## What changed

`hw/xbox/nv2a/pgraph/gl/shaders.c` only, plus a selftest under
`docs/testing/`. One call site:

```c
#ifdef __ANDROID__
-    while (glGetError() != GL_NO_ERROR) {
-        /* Clear any prior GL error to avoid aborting on Android. */
-    }
+    android_report_pending_gl_errors(binding);
#else
     assert(glGetError() == GL_NO_ERROR);
#endif
```

and the helper behind it. Nothing the shader loader compiles, links,
validates or caches was touched; the non-Android path is byte-identical.

## Why the drain stays

It would have been tidier to delete the drain and let the errors stand. That
is wrong here, and the reason is eleven lines below the call site: after
`glProgramBinary()` the loader reads `glGetError()` and treats a non-zero
result as "this binary failed to load", deleting the program and returning
false. `glGetError` reports the context's backlog, not the last call's
outcome, so an error left pending on entry would be attributed to the binary
and turn an unrelated upstream failure into a silent cache miss and a
recompile of a perfectly good shader. So the errors are still drained -- they
are simply named on the way out.

That also says what the fix is *not*: it does not give the GL renderer error
reporting at the raise site. The line says where the error was *found*, which
is the next shader load, not where it was raised. #86 notes the larger version
(install a debug callback so the driver's own message arrives at the raise
site); that remains undone and is the thing the next lane should pick up if
`[glerr]` lines start appearing and nobody can place them.

## Repeats are counted, not printed

A shader load happens many times a frame. One line per drained error per load
would have put a `[glerr]` line in logcat for every load of every frame, and a
log that floods is read no more than a log that is silent -- the failure mode
#86 was filed about, arrived at from the other side. Each distinct enum prints
the first time it is seen and then as its running count crosses a power of ten
(`occurrence=1`, `10`, `100`, ...). The table is keyed by enum, eight slots,
last slot shared; GL defines eight error codes, so only a vendor code can
reach the shared slot.

## What was measured, and what could not be

**Could not be:** this lane has no NDK, no device and no arm64 build, so the
arm that ships was not compiled by the toolchain that ships it. That is the
same limitation that had #86 filed rather than fixed, and it is unchanged.
Nothing here claims the Android build succeeds.

**Was:** `docs/testing/glerr_report_selftest.sh` slices the block out of
shaders.c by anchor -- not a copy, so it cannot drift -- and compiles it with
the host compiler against stubs, three ways:

| build | what it is | result |
|---|---|---|
| `desktop` | host header set | 18/18 legs pass |
| `gles` | `-DGLES_LIKE`: no `GL_STACK_OVERFLOW`, `GL_STACK_UNDERFLOW`, `GL_CONTEXT_LOST` -- the Android set, and why those cases are `#ifdef`-guarded | 18/18 legs pass |
| `silent` | the same slice with the report body restored to the pre-#86 drain | fails 10 legs, all of them about reporting |

The falsifier is asserted on its output words, not its exit code: the helpers
are kept so the silent variant still compiles and still runs every leg, since
a variant that merely failed to build would exit non-zero for free while
testing nothing. It must fail *by name* on the reporting legs and must still
pass `no pending error -> no [glerr] line` and `the backlog is fully drained`,
which are true in both worlds -- if those break it is the harness that broke.

Two suppression legs (`occurrences 2..9 are suppressed`, `11..99 are
suppressed`) pass vacuously against a block that prints nothing. They bound
the flood; they do not detect silence, and the harness says so where they are
written so that nobody counts them as evidence of the fix.

Anchor loss is a refusal, not a pass: pointed at a file without the block the
script exits 2 with `anchors not found ... -- the #86 block moved or was
renamed`, and the slicer additionally refuses a block with no `glGetError`,
`__android_log_print` or `[glerr]` in it. Checked by running it against
`gl/surface.c`.

## The prediction, and what the device run should show

`docs/testing/predictions/glerr86-report-inert.json`, registered after the
code commits and committed on top of them, `a_ref` master `a1691ae68e`,
`b_ref` the NOTES commit. Inertness only: `must_not_move` over
`Texture_render_target/*`, `Blend_tests/*`, `Texture_format/*`,
`Window_clip/*`, `Texture_shadow_comparator/*`, with `better=0, worse=0`.
This change cannot move a pixel: it adds no GL call, removes none, and leaves
the drained set identical.

No `disc` block is recorded, deliberately, and `--register` nudges about it.
The field records the composition the *arm* runs, which this lane does not
choose; writing the five suites above into it would state a composition I
cannot know and would make the judge print a mismatch note against whatever
disc the arm actually uses. The field's teeth are on absolutes (`expect`), and
this prediction has none -- `must_not_move` and `expect_counts` are
arm-to-arm differences and survive a composition the registrar did not
foresee. Left absent on purpose rather than filled in with a guess. A leg that moved would mean the helper is being
called somewhere it should not be, or that draining and reporting are not the
same drain.

The new evidence is the logcat. On a device run, `grep '\[glerr\]'` over the
captured log:

- **should show nothing at all** on a healthy run. #66's attachment-less
  clears were fixed in `fada1d89` on shared code, so the backlog this arm was
  added to hide is gone on Android too. An empty grep is the expected result
  and is a real result: it says no GL error was pending at any shader load in
  the run.
- **should show, if anything shows**, lines of the form
  `[glerr] GL_INVALID_FRAMEBUFFER_OPERATION (0x506) was already pending on
  entry to pgraph_gl_shader_load_from_memory shader=<hash> occurrence=<n>`,
  at most one per distinct enum per power of ten of its count -- so a handful
  of lines per run, not thousands, however often the error recurs.
- **should never show** more than about ten lines for one enum in a run
  (occurrence 1, 10, 100, ... caps it), and should never show `GL_NO_ERROR`.
- **is not** a report of where the error was raised. The shader hash names
  where it was *found*. Pairing it with `gl/surface.c` and `gl/display.c`'s
  existing (debug-logging-gated) `GL error 0x%X at %s` lines immediately
  before it in the log is how a `[glerr]` line gets placed today.

A run whose grep is empty does not prove the report works -- it is equally
what the old silent drain produced. What separates them is the selftest above,
and, on a device, deliberately provoking an error (any failing GL call before
a shader load) and seeing exactly one line for it.

## For the next lane

- Do not re-litigate keeping the drain. The `glProgramBinary` check below the
  call site is the reason; see above.
- Do not expect this lane's evidence to say the Android build compiles. It
  says the block's text compiles under both header sets with `-Werror` and
  behaves. Whoever next builds Android should watch for `<android/log.h>`
  already being included at the top of `shaders.c` (it is) and for
  `ARRAY_SIZE` coming from `qemu/osdep.h` (it does).
- The unfinished half of #86 is the debug callback at the raise site. The
  drain-to-report change does not close it, and this NOTES is the record that
  it was left open deliberately.
- `hw/xbox/nv2a/pgraph/gl/shaders.c:885` (after `glGetProgramBinary` in
  `pgraph_gl_shader_cache_to_disk`) still carries a bare
  `assert(glGetError() == GL_NO_ERROR)` with no `#ifndef __ANDROID__` around
  it, unlike the two sites at `:505` and `:949` that have one -- so on Android
  that assert is live, and it is the one place where a GL error aborts rather
  than being reported. This change neither creates nor removes that: the drain
  below it still drains, so what reaches `:885` is what reached it before. Not
  touched here (out of this brief, and changing an assert's reachability on
  the shipping platform is not a diagnostics change), but it is the next
  question in this file.
