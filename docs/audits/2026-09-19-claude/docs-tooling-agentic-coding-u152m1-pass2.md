# Audit pass 2 — PR #162, `claude/docs-tooling-agentic-coding-u152m1`: the GL surface pad-bit write side (#158), and #60 re-measured

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #162, branch `claude/docs-tooling-agentic-coding-u152m1`, tip
**`e81aaca8ae`**, over `origin/master` **`732b97e2df`** (which is the
merge-base: the branch is strictly ahead).
**Date** 2026-09-19. **Records** `2026-09-19-claude/docs-tooling-agentic-coding-u152m1-pass2.{md,json}`.
**Pass 1** `2026-09-19-claude/docs-tooling-agentic-coding-u152m1-pass1.md`, at
tip `44b35be1eb`.

**All six pass-1 scenarios are CLOSED. Two new MEDIUMs, both in files added
*after* pass 1 read the diff, so no audit has ever looked at them.**

Disposition: **`needs-remediation`**. Nothing in `hw/` is in question — the
three renderer files are finished, and remediation should not open them.

---

## Part 1 — the six pass-1 scenarios

### H1 — CLOSED. The Android build compiles, and the check that closes it is the one pass 1 named

Pass 1's scenario: *"Any Android build of this branch fails at
`xemu_core.dir/.../gl/draw.c.o` and produces no APK."*

It cannot occur at this tip, and I did not take the PR body's word for it.

* **The guard landed in the form that works.** `gl/draw.c:164` opens
  `#ifndef __ANDROID__` around `pad_write_color_factor()` and `:176` closes it;
  `:459` takes the *whole* `pad_stamped` branch under `#ifdef __ANDROID__`,
  emitting the two pre-#158 calls, with the `#else` at `:467` carrying the
  desktop path. Pass 1 offered a second form — `pad_stamped` forced false under
  `#ifdef __ANDROID__` before the `if` — and the lane is right that it does not
  compile: the call inside the branch still has to be parsed against a function
  that no longer exists. The form that landed is the one of the two that works.
* **`grep -rn SRC1 hw/xbox/nv2a/pgraph/gl/`** returns seven hits. Five are
  prose in comments; the two code references are `:169` and `:171`, both inside
  the `#ifndef __ANDROID__` block.
* **CI, on this exact head.** `gh run list --commit e81aaca8ae` gives three
  runs, all `success` with `headSha` e81aaca8ae: **Android** (35463074396),
  **Desktop build** (35463074429), **NV2A index** (35463074388). The Android
  job log is not merely green, it is green *having done the work*:
  `> Task :app:configureCMakeRelease[arm64-v8a]`,
  `> Task :app:buildCMakeRelease[arm64-v8a]`, `BUILD SUCCESSFUL`. The job did
  not skip the target that failed before.

**And the remediation is provably inert on desktop, from the diff alone.**
`git diff 7ffcd2bce8 e81aaca8ae -- gl/draw.c`, with comments filtered, is
exactly six lines: `#ifndef __ANDROID__`/`#endif` around the helper, the
`#ifdef`/`#else`/`#endif` around the branch, the two-line Android arm, and
`bool pad_stamped` → `const bool pad_stamped`. The desktop `#else` arm is
character-for-character the pre-remediation code. The lane's "byte-identical on
235 of 236" disc run is consistent with that, but the claim does not rest on a
run I cannot re-execute: the text of the diff settles it.

### M1 — CLOSED, by option (b), complete in all three places

Pass 1's scenario was the GL `_Z` surface holding alpha 1 where the clear wrote
and 0 where the raster drew. **That scenario still occurs in the emulator** —
option (b) does not fix the code, and pass 1 explicitly accepted it: *"declaring
it out of scope in the PR body and `NOTES.md`, with the captures it leaves
wrong named, is an acceptable resolution and may be the better one for this PR.
Either answer closes it; an unstated omission does not."* So what pass 2 has to
verify is that the omission is no longer unstated, and the three places pass 1
asked for all carry it:

1. **PR body** — a named MEDIUM section beside the `sampled_pad_alpha` one,
   giving the mechanism, the reason and the issue number.
2. **`docs/lanes/remote/NOTES.md:413-444`** — *"M1, NOT taken, and it is a
   measurement limit rather than a judgement call"*, which is where a later
   lane will look.
3. **Issue #164**, open, and it carries more than the finding: the call site,
   the Vulkan function to mirror with its body, the gating requirement (on
   `pgraph_glsl_dual_src_pad_supported()`, *and* the GLES exclusion H1 was
   about), both prediction keys, the `Blend_surface/*` + `Surface_format/*`
   must-not-move set, and the failure scenario. Whoever holds a disc with the
   `Clear` suite can take it without re-deriving any of it.

The justification for choosing (b) over (a) — that the `Clear` suite is not on
`iso_surf1.iso` — is a claim about a binary artifact that is not in this
repository and that I cannot inspect from here. I record it as unverified and
it does not matter to the disposition: pass 1 closed M1 on either answer.

### L1 — CLOSED as a finding; one residual, downgraded, recorded below as N3

The comment at `gl/draw.c:445-458` now states the asymmetry, names it as the
cause of H1, and gives a real reason for the site using a preprocessor guard
rather than an `opts.gles` term — *"the tokens themselves are absent on GLES,
not merely unwanted."* That is a better answer than the one pass 1 proposed.

The ANGLE half of pass 1's scenario is not closed by it, and the PR body's
wording overstates the fix. See **N3** (LOW).

### L2 — CLOSED

`gl/draw.c:143-152` now carries the derivation — `min(As, 1 − Ad)` is 0 for
both pad variants once the stamp lands, `_Z` because As is the stamped 0, `_O`
because Ad is folded to 1 — with the corpus observation demoted to a
parenthetical secondary note, and a pointer to `vk/draw.c`'s L2 explaining why
the argument-from-absence was retired. That is what the finding asked for, in
the shape the finding asked for it.

### L3 — CLOSED

Taken as prose, in the PR body and at `docs/lanes/remote/NOTES.md:456-473`, and
the reason given for *not* editing the registered artifact is the right one: the
file's sha256 is cited in the record, and retrofitting a leg onto a spent
prediction is the move the registration discipline exists to prevent. Pass 1
offered the prose form as its own alternative and called it "honest and costs
nothing".

**The prediction is still intact at this tip**, which two merges of `master`
since pass 1 could have broken: `a_ref dcefe55745` and `b_ref 7ffcd2bce8` are
both still ancestors of `e81aaca8ae` (merges, not a rebase), and
`sha256(docs/testing/predictions/2026-09-19-gl-pad-bit-write-side.json)` is
`29eb6300…776cfa`, which is what the PR body's `Prediction:` line carries.

### L4 — CLOSED as noted, and the regeneration it sits on is clean

`provenance.tests_root` and `support_dirs[0]` still read `/home/user/…` against
master's `/home/justin/…`. Accepted as churn, as pass 1 allowed.

I re-checked the *second* regeneration (commit `8c3a2ce9`, which pass 1 never
saw) for the #157 class, because a second regen is a second chance to lose a
suite. Parsed at all three refs — `44b35be1eb`, `origin/master`, `e81aaca8ae` —
**suites 103, symbols 951, sites 765, gaps 498, `tests_commit 91a0de45ca`,
identical at all three.** Nothing was lost. (Pass 1's prose says "sites (2839)";
the file says 765 at the tip pass 1 read, so that figure counted something else.
The counts are equal across the refs either way, which is the property that
matters.) The NV2A index CI check is green on the head.

---

## Part 2 — new findings, in files pass 1 never saw

`645462d08d` and `e81aaca8ae` land 291 lines of new tooling *after*
`174f50669e` wrote the pass-1 audit. Both files are on the PR's `Files:` line
and both will fold. No audit has read them. Both findings below are in that
code; neither touches `hw/`.

### N1 (MEDIUM) — `gles_token_check.py` treats the `#else` arm of every non-`__ANDROID__` conditional as dead, so it hides 114 lines of the directory it scans

`docs/testing/gles_token_check.py:104-106`

The docstring makes an explicit guarantee:

> *"Non `__ANDROID__` frames are treated as live, which is the conservative
> direction: it can report a line some other guard excludes, **never hide
> one**."*

The first half is implemented (`:96`, `live = True` for an unknown condition).
The second is not. `#else` at `:104-106` inverts `live` unconditionally,
including for a frame whose condition was unknown-and-assumed-live — so the
`#else` arm of any conditional the script does not understand is marked dead
and never scanned. The guarantee is inverted exactly where it is claimed.

**It fails a mutant.** Four lines, a token from the script's own
`DESKTOP_ONLY` list, in the `#else` of an ordinary conditional:

```c
#if defined(SOME_OTHER_THING)
static int a(void) { return 0; }
#else
static GLenum b(void) { return GL_SRC1_ALPHA; }
#endif
```

→ `1 file scanned, 0 findings`, exit 0. The same token at the same place
without the conditional is caught. (The script *is* otherwise good: run against
`gl/draw.c` at `7ffcd2bc` it reports `:151 GL_SRC1_ALPHA` and `:153
GL_ONE_MINUS_SRC1_ALPHA` — the same two lines, by number, that the arm64-v8a
compiler reported. The power test in the PR body is real, and I re-ran it on
the output words rather than the exit code.)

**It is not hypothetical on this tree.** Instrumenting the script's own frame
stack over its default target, `hw/xbox/nv2a/pgraph/gl`, **114 non-blank lines
sit inside an `#else` arm the script has marked dead on an unknown condition**,
in 21 frames. Two of them are ordinary code an Android build compiles:

* `gl/debug.c:66` — `#if defined(__APPLE__) … #else glEnable(GL_DEBUG_OUTPUT); … #endif`.
  `__APPLE__` is not defined on Android, so the `#else` arm is precisely what
  arm64-v8a compiles, and it is precisely what the scanner does not look at.
* `gl/debug.h:53` — `#if DEBUG_NV2A_GL … #else … #endif`. The `#else` arm is
  the macro set every non-debug build uses, and it is invisible.

The remaining 19 are `#ifdef __aarch64__` scalar fallbacks in `surface.c` /
`texture.c` and the `#else` tails of the suffix-fallback chains in
`constants.h`. Nothing in the hidden region today trips the curated list, so
the current `0 findings` is a true result — but it is true by luck, not by the
check.

**Failure scenario.** A lane adds a desktop-only token inside the `#else` of a
`#if defined(__APPLE__)`, a `#if DEBUG_NV2A_GL`, or a `#ifdef GL_FOO` fallback
chain — which is the *idiomatic* place to put a portability fallback, and the
constants.h chains show the codebase already does this — runs
`gles_token_check.py` on a machine with no NDK, reads `0 findings`, and pushes.
The arm64-v8a job fails, which is H1 again with the check that exists to
prevent it reporting clean. The script's own closing advice ("guard the whole
branch, not just the flag") never prints, because there is no finding. Worse
than the miss is the docstring: a reader who has read "never hide one" will not
re-derive the coverage, and this repository has already paid twice for a
comment that was believed (`vk/draw.c` L2, quoted in this PR's own diff).

**Remediation.** Record on each frame whether `__ANDROID__` decided it, and
invert on `#else` only for those; leave an unknown frame live in both arms.
Roughly:

```python
stack.append({'live': live, 'known': known, 'tested': tested})
...
if stack and re.match(r'#\s*else\b', s):
    if stack[-1]['known']:
        stack[-1]['live'] = not stack[-1]['live']
    continue                     # unknown: both arms stay live
```

`#elif` wants the same treatment — it already forces `live = True`, which is
right, but it must also stop the following `#else` from inverting a value that
was never derived. Then **add the mutant above as a fixture and confirm it
trips**: a check whose new invariant has no failing case is a check that has
not been tested. Re-running the fixed script over
`hw/xbox/nv2a/pgraph/gl` should still give `0 findings` — that is the
regression guard on the fix.

This is MEDIUM and not HIGH: the failure is a false clean in a pre-push
convenience check, the Android CI job is the gate of record and is green on
every PR, and the script is not wired into `preflight.sh`. It does not affect
the emulator.

### N2 (MEDIUM) — `pgraph_capture_run.sh` names the mislabelled-renderer failure in a comment and then does not fail on it

`docs/testing/pgraph_capture_run.sh:102-107`

```sh
# The renderer xemu actually selected, not the one that was asked for: a
# request for OPENGL on a host with no usable GL context silently continues on
# Vulkan, and a run mislabelled that way is worse than no run.
got=$(grep -m1 '^nv2a: renderer:' "$LOG" | cut -d' ' -f3-)
echo "$TAG: exit=$rc in ${elapsed}s, renderer requested=$RENDERER got=${got:-UNKNOWN}"
[ -n "$got" ] || { tail -20 "$LOG" >&2; die "the emulator never reported a renderer -- see $LOG" }
```

The comment states the requirement — a mislabelled run is worse than no run —
and the code enforces only that *some* renderer was reported. `$got` is never
compared to `$RENDERER`. A run that requested OPENGL and came up on Vulkan
prints one informational line and then exits 0, with captures extracted under
the OPENGL tag.

Everything needed for the comparison is already in hand: `pgraph.c:1190`
prints `nv2a: renderer: %s` from `renderers[g_config.display.renderer]->name`
*after* the fallback chooser at `:1141-1153`, so it is the selected renderer and
not the requested one; and the two values are `gl/renderer.c:344 .name =
"OpenGL"` and `vk/renderer.c:2602 .name = "Vulkan"` against the script's
`OPENGL` / `VULKAN`. A case-insensitive compare is one line.

**Failure scenario.** A sweep loops the runner over `OPENGL` and `VULKAN` on a
host whose GL context is unavailable — a headless container where the xvfb
server came up without GLX, a driver change, a build configured without
`CONFIG_OPENGL`. Both arms come up on Vulkan, both exit 0, both produce 236
captures, and the OPENGL arm's captures are Vulkan's. Because nothing fails, the
mismatch survives only as one line of stdout in a log nobody re-reads. The
conclusion that reads out of that data is *"GL is now byte-identical to
Vulkan"* — which is, to within a few captures, the headline this very PR
publishes. That is what makes it worth fixing here rather than later: the
instrument's silent-failure mode and the lane's result have the same shape, so
the instrument must be the thing that refuses.

**This does not put any published number in doubt**, and I am not claiming it
does. The runs behind the result table reported differing per-capture values
between the two backends, which a both-on-Vulkan pair cannot produce, and the
lane's own `renderer requested=… got=…` lines were read. The defect is in what
the committed instrument will permit next time, on a machine that is not this
one — which is the entire reason the PR gives for committing it: *"so a fresh
machine with the firmware and a disc can reproduce one."*

**Remediation.** Make it a `die`, beside the one that is already there:

```sh
case "$(printf '%s' "$got" | tr 'A-Z' 'a-z')" in
    "$(printf '%s' "$RENDERER" | tr 'A-Z' 'a-z')") ;;
    *) die "requested $RENDERER but the run came up on $got -- see $LOG" ;;
esac
```

and confirm it trips: run it once with `RENDERER=OPENGL` against a log whose
renderer line says Vulkan (a fixture log is enough) and check the message, not
just the exit code — the script exits non-zero for a dozen other reasons.

### N3 (LOW) — the PR body says the three GLES-exclusion sites now agree; two use the preprocessor and one uses a run-time term

`hw/xbox/nv2a/pgraph/gl/draw.c:459`

The PR body's L1 disposition reads *"the call site now expresses the GLES
exclusion the way the other two sites do"*. It expresses it the way
`gl/renderer.c` does — `#ifndef __ANDROID__` — and not the way `psh.c:2018`
and `:3568` do, which is the run-time term `&& !ps->opts.gles`. The asymmetry
pass 1 named is therefore reduced from three-ways-two to three-ways-two with
the membership changed, not removed, and pass 1's stated scenario is untouched:
on a GLES-capable build that is not Android, `gl/renderer.c`'s setter runs, the
`psh.c` gates suppress the index-1 output, and `gl/draw.c` still names a SRC1
factor against a shader that has none.

It stays LOW for the reason pass 1 gave — no such build exists, and
`gl/shaders.c:357/360` ties `gles` to `__ANDROID__` — and the code comment at
`:445-458` is honest about the choice and gives a good reason for it. The
finding is only that the PR body claims a convergence the code does not make.

**Remediation.** One clause in the PR body: the call site now excludes GLES the
way `gl/renderer.c` does, by preprocessor, because the tokens are absent rather
than merely unwanted; `psh.c` keeps the run-time term because a shader gate has
no token to be absent. Or add `&& !ps->opts.gles`-equivalent belt-and-braces
inside the desktop arm. The prose fix is enough.

---

## What pass 2 checked and did not find wrong

* The `hw/` change is finished. Pass 1 verified the mechanism, the pairing, the
  `DST_ALPHA` fold ordering, the `GL_SRC_ALPHA_SATURATE` safety, absence-as-
  refusal, the absence of blend-state leak and the shader-cache question, and
  said pass 2 should not re-derive them. The only edit to `hw/` since is the H1
  guard, whose non-comment diff is six lines and provably inert on desktop. I
  re-derived nothing and found nothing to re-open.
* **The PR is foldable in the mechanical sense**: not a draft, `MERGEABLE`,
  three check runs on the head, all SUCCESS, no empty rollup and therefore not
  the #101/#123/#129/#139 stall. None of the branch's commit subjects or bodies
  carries the retired skip-ci marker.
* `docs/lanes/remote/NOTES.md` is per-lane, not at the branch root. No root
  `NOTES.md` exists on the branch.
* `extract_results.py --list -d ""` resolves to the FATX root (`resolve()`
  drops empty path parts), and the `awk '$1 == "dir" { print $NF }'`
  auto-detection in `pgraph_capture_run.sh:118-126` parses its output
  correctly, counts the result, and refuses rather than guesses when the count
  is not 1. The `abspath` fix the PR describes is real and correct: `BIN` and
  `ISO` are absolutised at `:56` before the `cd` at `:95`.

## One thing the PR body asserts that this audit did not verify

The `Files:` line lists five paths; `git diff --stat origin/master...HEAD` is
eleven, the extra six being the prediction, the two pass-1 audit records, the
investigation note, `docs/lanes/remote/NOTES.md` and
**`docs/testing/nv2a_index.json`**. The first five are the lane's own records
and no other lane writes them. The index is a shared generated artifact and is
the one worth naming, since `board.sh` reads `Files:` from open PRs to keep two
lanes off one file and a second lane regenerating the index would not see this
one holding it. It is not a defect in the change and every other audit on this
board has let the same omission pass, so I am recording it rather than raising
it.

## Disposition

**`needs-remediation`** — N1 and N2, both MEDIUM.

**Do not reopen `hw/`.** All six pass-1 findings are closed, H1 by the Android
job going green on this exact head with `arm64-v8a` built rather than skipped,
and the three renderer files are settled. The two findings are in
`docs/testing/gles_token_check.py` and `docs/testing/pgraph_capture_run.sh`,
both added after pass 1 read the diff, both fixable on a desktop with no NDK,
no device and no disc run, and both wanting the same discipline the rest of this
lane's work already shows: build the mutant and confirm the check trips on it.

N3 is LOW and is a sentence in the PR body; take it or leave it.
