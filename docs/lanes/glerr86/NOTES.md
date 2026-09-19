# lane.glerr86 -- #86, the Android shader-load drain

Branch `lane/glerr86`, base `master @ a1691ae68e`, PR #128.

Remediated after audit pass 1 (`docs/audits/2026-09-19-glerr86-pass1.md`:
0 HIGH, 3 MEDIUM). M1 and M2 are why the suppression rule below is not the one
the first three commits shipped; M3 is why this file is here and not at the
branch root.

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

## Every occurrence prints, and a budget bounds the pathological case

The first version of this lane counted repeats and printed only as a per-enum
count crossed a power of ten. Both premises under that design were wrong, and
the audit on PR #128 (`docs/audits/2026-09-19-glerr86-pass1.md`, M2) is what
found them:

- **"A shader load happens many times a frame" is false.**
  `pgraph_gl_shader_load_from_memory` has one caller, `shaders.c:1003`, and it
  is guarded by `!binding->initialized`. `initialized` is cleared only in
  `shader_cache_entry_init`, i.e. when the LRU claims a fresh node, against a
  51200-entry cache. The function runs **once per shader-cache miss** --
  hundreds of times over a run, front-loaded into the first seconds. At that
  rate a line per load is affordable, and it is what keeps the per-load shader
  hash, which is the whole diagnostic. Under the old rule most counts lived in
  1..9, so the usual outcome was one line naming the *first* load's hash and
  nothing about the rest.
- **"Android had no GL-error reporting path at all" is false**, and false in
  this same file. `android_log_shader_stage_errors` (`:1025`, `:1037`),
  `android_log_apply_uniform_entry_errors` (`:901`) and
  `android_log_uniform_update_errors` (`:944`) all print `GL error 0x%X ...`
  to logcat, one line per error, with no suppression and **not** behind
  `DEBUG_NV2A_GL`. What was silent was this one site.

So every drained error now prints, with its enum, its raw code, its shader
hash and a running `report=<n>` index. A process-wide budget
(`ANDROID_GLERR_MAX_REPORTS`, 256) bounds the case this cannot reason about --
a renderer broken badly enough to leave an error pending at most loads. Past
the budget one line says reporting stopped, and nothing more is printed. **The
drain never stops**, budget or not; that is what keeps the `glProgramBinary`
check below the call site honest.

There is no per-enum table any more, and that is deliberate: a fixed set of
slots must either grow without bound or share one, and the shared slot was the
audit's M1. Two enums alternating into it re-keyed each other, so the
suppression it was supposed to buy became a line per load *reporting every one
as `occurrence=1`* -- a flood that also understated itself, arriving exactly in
the badly-broken-renderer case where the log matters most.

## What this report can and cannot see

Narrower than the first draft of these notes claimed. `apply_uniform_updates`
drains and prints the entire backlog at `:901`, and `update_shader_uniforms`
runs on every `pgraph_gl_bind_shaders` (both the `goto update_uniforms` fast
path and the full path). So by the time a cache-missing bind reaches `:1003`,
the backlog is at most one draw deep: a `[glerr]` line names an error raised
**since the previous bind's uniform updates**, not "whatever ran before the
load". An error raised earlier was already reported by the
`GL error 0x%X before apply_uniform_updates:` line and leaves no `[glerr]`
line at all.

## What was measured, and what could not be

**Could not be:** that a `[glerr]` line reaches logcat on a device, and that
the report fires on a real pending error. Both need a device; this lane has
none.

**The arm64 build is not on that list**, though the first draft of these notes
put it there (audit L2). `.github/workflows/android.yml` runs on every
`pull_request`, installs `ndk;29.0.14206865` and runs `./gradlew
assembleDebug`, which drives `android/app/src/main/cpp/CMakeLists.txt` through
`externalNativeBuild` and compiles `shaders.c` into `xemu_core` with
`__ANDROID__` defined against the real GLES headers. That check passed on this
head. It is what settles the `<android/log.h>` and GLES-header-set questions
the host selftest can only approximate: the worktree has no NDK, but the PR
does.

**Was:** `docs/testing/glerr_report_selftest.sh` slices the block out of
shaders.c by anchor -- not a copy, so it cannot drift -- and compiles it with
the host compiler against stubs, three ways:

| build | what it is | result |
|---|---|---|
| `desktop` | host header set | 19/19 legs pass |
| `gles` | `-DGLES_LIKE`: no `GL_STACK_OVERFLOW`, `GL_STACK_UNDERFLOW`, `GL_CONTEXT_LOST` -- the Android set, and why those cases are `#ifdef`-guarded | 19/19 legs pass |
| `silent` | the same slice with the report body restored to the pre-#86 drain | fails 14 legs, all of them about reporting |

A second falsification, run by hand rather than committed: the **pre-audit**
block -- the eight-slot per-enum table with the shared last slot -- sliced out
of the previous commit and driven by today's harness fails 7 of the 19
legs, including `the report index counts up rather than resetting to 1` and
`past the budget the line count stops at the budget plus one`. Worth recording
which leg does *not* separate them: `40 loads alternating between two enums ->
40 lines` passes against the old code too, because 40 lines is exactly the M1
flood. The count alone was never the discriminator; the index is.

The falsifier is asserted on its output words, not its exit code: the helpers
are kept so the silent variant still compiles and still runs every leg, since
a variant that merely failed to build would exit non-zero for free while
testing nothing. It must fail *by name* on the reporting legs and must still
pass `no pending error -> no [glerr] line` and `the backlog is fully drained`,
which are true in both worlds -- if those break it is the harness that broke.

One leg (`past the budget the backlog is still drained, and silently`) passes
vacuously against a block that prints nothing: any leg about what is *not*
printed does. The harness says so where it is written so nobody counts it as
evidence of the fix. It is there because the drain outliving the budget is the
property that keeps the `glProgramBinary` check honest.

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
  and is a real result -- but a *narrow* one. It says no GL error was pending
  **at a shader-cache miss, raised since the previous bind's uniform
  updates**. It does not say the run was GL-error-free: an error raised
  anywhere else is drained and reported by
  `GL error 0x%X before apply_uniform_updates:` at `shaders.c:901` and never
  reaches a `[glerr]` line. Grep `GL error 0x` as well, always.
- **should show, if anything shows**, lines of the form
  `[glerr] GL_INVALID_FRAMEBUFFER_OPERATION (0x506) was already pending on
  entry to pgraph_gl_shader_load_from_memory shader=<hash> report=<n>`, one
  per drained error per load, `report=` counting up monotonically across the
  process. Each line's hash is a different shader load, so the hashes are the
  point: they are the set of loads that found something pending.
- **should never show** more than 257 lines in a process (256 reports plus the
  one that says reporting stopped), and should never show `GL_NO_ERROR`. If
  the `... reports printed; further pending errors are still drained, but no
  longer logged` line appears at all, the renderer is leaving an error pending
  at a large fraction of shader loads and that, not the log, is the finding.
- **is not** a report of where the error was raised. The shader hash names
  where it was *found*. Pairing it with the ungated `GL error 0x%X ...` lines
  from `shaders.c:901/944/1025/1037` immediately before it in the log, and
  with `gl/surface.c` and `gl/display.c`'s debug-logging-gated ones, is how a
  `[glerr]` line gets placed today.

A run whose grep is empty does not prove the report works -- it is equally
what the old silent drain produced. What separates them is the selftest above,
and, on a device, deliberately provoking an error (any failing GL call before
a shader load) and seeing exactly one line for it.

## For the next lane

- Do not re-litigate keeping the drain. The `glProgramBinary` check below the
  call site is the reason; see above.
- The host selftest says the block's text compiles under both header sets
  with `-Werror` and behaves; the repository's own Android CI job says it
  compiles for arm64 under the shipping NDK. Neither says a line reached
  logcat. That is the only gap left, and it needs a device.
- This report is ungated, like the other three `shaders.c` Android helpers and
  unlike `gl/surface.c` and `gl/display.c`, whose helpers return early unless
  `xemu_android_is_debug_logging_enabled()`. Ungated is what makes it useful
  on a shipping build, and `ANDROID_GLERR_MAX_REPORTS` is what makes ungated
  safe. If anyone gates it later, the budget can go with it -- but then a
  default-build run says nothing about GL errors at shader load again, which
  is #86.
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
