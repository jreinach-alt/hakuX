# Audit pass 2c — PR #162, `claude/docs-tooling-agentic-coding-u152m1`: the GL surface pad-bit write side (#158), and #60 re-measured

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #162, branch `claude/docs-tooling-agentic-coding-u152m1`, tip
**`0cd8363668`**, against `origin/master` **`edcc31d847`** — which is also the
merge-base, so the branch is **0 behind / 30 ahead**, `MERGEABLE`, ready (not
draft).
**Date** 2026-09-19. **Records** `2026-09-19-claude/docs-tooling-agentic-coding-u152m1-pass2c.{md,json}`.
**Prior passes** `…-pass1.md` at `44b35be1eb`, `…-pass2.md` at `e81aaca8ae`,
`…-pass2b.md` at `26754a5e7e`.

**Why 2c.** Pass 2b raised P1 (MEDIUM) and P2–P4 (LOW) in
`skip_ci_marker_check.sh` and the PR body. Those were remediated (`f734a14e`,
`0cd83636`) and the PR came back `needs-audit-2`. This pass verifies **P1–P4**,
re-confirms the pass-1 and pass-2 closures still hold at the new tip, and reads
the one code commit that has landed since and that **no pass has read**:
**`a5fdb6a7`**, one condition in `hw/xbox/nv2a/pgraph/gl/surface.c`. The lane
asked for it to be rated rather than assumed dismissed, and named the X1R5G5B5
sibling it deliberately did not take. Both are rated below.

**P1, P2, P3 and P4: CLOSED, each verified by running the reproduction and by a
mutant that restores the bug. One new MEDIUM in `a5fdb6a7`: the condition it
adds cannot execute, and the commit's central factual claim is false on this
tree.**

Disposition: **`needs-remediation`** — A1 alone. The remediation is prose in
three places plus a decision about four lines of C; it is not a re-measurement
and it needs no device. **Do not reopen** `skip_ci_marker_check.sh`,
`gles_token_check.py`, `pgraph_capture_run.sh`, `gl/draw.c`, `gl/renderer.c` or
`glsl/psh.c` — all settled, all re-checked here.

---

## Part 1 — the four pass-2b findings

### P1 (MEDIUM) — CLOSED. An unresolvable range is now a refusal, and the verdict says how much was read

Pass 2b's scenario: *a lane runs the check before pushing, in a worktree or
container where `origin/master` — the **default** range's left endpoint — is not
present (single-branch clone, a fetch that named only the lane branch, an agent
worktree off a bare mirror), or mistypes the range. `git log` writes nothing,
its error goes to `/dev/null`, `found` stays 0, the script prints `clean` and
exits 0. The lane pushes a commit carrying the retired marker, GitHub creates no
workflow run, the rollup is empty, and `fold.sh` cannot fold a head nothing has
built.*

**It cannot occur at this tip.** `skip_ci_marker_check.sh:60-69` resolves the
range with `git rev-list --count` before scanning and returns 2 on failure;
`:181` turns that into `exit 2`; `:182` and `:184` print the count on both the
scanning line and the verdict.

I ran the reproduction pass 2b measured, and then the *live* form of its
scenario rather than only the typo form:

```
$ skip_ci_marker_check.sh origin/mastr..HEAD
cannot resolve range origin/mastr..HEAD: fatal: ambiguous argument …
nothing was scanned. This is not a clean result.
                                                              # exit 2
```

```
# a fresh repo with one commit and no origin/master, DEFAULT range, no argument:
$ skip_ci_marker_check.sh
cannot resolve range origin/master..HEAD: fatal: ambiguous argument …
nothing was scanned. This is not a clean result.
                                                              # exit 2
```

That second one is the finding's own named failure mode — the default range in a
tree that lacks the endpoint — and it is the one a lane would actually hit. On
real history the script reports `scanning 30 commit bodies in origin/master..HEAD`
and then `14312cb34f`, exit 1.

**`--selftest` is 7/7, and the fixtures discriminate.** I did not take the
lane's mutant results on trust; I built both mutants from the current file by
textual substitution and ran each one's own `--selftest`:

| mutant | what it restores | result |
|---|---|---|
| A | `resolve` call replaced by `RANGE_COUNT=unknown`, `git rev-list … 2>/dev/null` back in `scan`, verdict back to bare `clean` | **4/7** — `unresolvable range exits 2`, `never gives the clean verdict for it`, `reports how many bodies it read` red; the other four unmoved |
| B | the `git log -1 --format=%B \| grep -qF` pipe back under `pipefail` | **6/7** — `finds a marker in a body past the pipe buffer` red **alone** |

Mutant A, run in the no-`origin/master` repo with the default range, prints
`clean` and exits 0 — the pre-fix behaviour exactly. So P1's three fixtures fail
on P1's bug and nothing else, P2's one fixture fails on P2's bug and nothing
else, and pass 2b's *"this invariant currently has no failing case"* no longer
holds for either.

**One thing worth keeping in the record, because it is the finding recurring
inside its own fix and the lane caught it, not me.** The first remedy had
`resolve` call `exit 2` while the caller invoked it as `N=$(resolve …)`; the
exit killed the command-substitution subshell and the script carried on to print
`clean` and exit 0 — a guard firing and the code proceeding anyway, which is
precisely P1's shape. The comment at `:52-58` records it, and the P1 fixture
drives the **script** rather than `scan()` for exactly that reason (`:129-135`),
which is what makes the fixture able to see it at all.

### P2 (LOW) — CLOSED. The pipe is gone

`scan()` now captures the body into `msg` and matches with a `case` (`:82-91`).
No pipe, no 64 KB buffer, no SIGPIPE for `pipefail` to propagate. The 128 KB
fixture at `:157-169` passes at this tip and goes red on mutant B, so the
invariant has a failing case. `git log` failure is no longer silent either: a
body that cannot be read is `exit 2`, not a skipped commit.

### P3 (LOW) — CLOSED. The file is declared, twice

`docs/testing/skip_ci_marker_check.sh` is on the PR's `Files:` line (body `:7`)
and has its own section in `docs/lanes/remote/NOTES.md`. So is
`hw/xbox/nv2a/pgraph/gl/surface.c` (body `:5`), which was the same omission
recurring on `a5fdb6a7` and which the remediation unit took.

### P4 (LOW) — CLOSED as prose, and correctly refused as a rewrite

PR body `:60` names `14312cb34f`, says the marker sits inside a sentence
recording that it had been retired, establishes it is inert (CI has run on every
head since; `fold.sh` merges rather than squashes), and says why it must **not**
be reworded: both prediction refs `dcefe55745` and `7ffcd2bce8` are descendants.
I re-verified the two ancestry facts with `git merge-base --is-ancestor`: both
refs are ancestors of `0cd83636`, and the prediction file still hashes to
`29eb63008be367c497d943d5c7f1d91ca2b08aede2d2523feada4b2bae776cfa`, matching the
body's `Prediction:` line.

---

## Part 2 — pass-1 and pass-2 closures, re-confirmed at this tip

* **H1 (HIGH).** `grep -rn SRC1 hw/xbox/nv2a/pgraph/gl/` gives seven hits; the
  only two code references are `draw.c:169` and `:171`, both inside the
  `#ifndef __ANDROID__` opened at `:164` and closed at `:176`. The **Android**
  workflow is green on `0cd83636` (run 35467762522), which is the check that
  closes H1 rather than the desktop build. Stays closed.
* **N1 (MEDIUM).** `gles_token_check.py` on the default target: **13 files
  scanned, 0 findings**, exit 0. Stays closed.
* **N2 (MEDIUM).** `pgraph_capture_run.sh` untouched since pass 2b. Stays closed.
* **L3 / prediction.** Registered, refs are ancestors, hash matches the body,
  no rebase (the branch merges master in; merge-base == `origin/master`).
* **L4 / index.** `a5fdb6a7` regenerated `nv2a_index.json`, so this is not a
  no-change claim and I compared the two documents rather than the commit
  message: **suites 103 → 103, symbols 951 → 951, `tests_commit` identical
  (`91a0de45ca`), gaps 498, unread 145, suites lost NONE, suites gained NONE.**
  `sites` 2839 → 2840, which is the one line `a5fdb6a7` adds under `hw/xbox`.
  Nothing was dropped by regenerating against this container's checkout. The
  only other movement is `provenance.tests_root` / `support_dirs`, which record
  the regenerating container's paths (`/home/user/…` vs `/home/justin/…`) and
  which pass 1's L4 already noted nothing reads.
* **Territory.** `check_territory.py` reads `origin/board` and reports
  `territory ok (wave 125, 29 lanes, 76 files claimed)`. `gl/surface.c` is held
  by `lane.remote`.
* **CI.** All three workflows green on the head `0cd83636`: **Desktop build**,
  **Android**, **NV2A index**.

---

## Part 3 — the code no pass had read

`a5fdb6a7` adds one condition at `hw/xbox/nv2a/pgraph/gl/surface.c:1331`,
inside `render_surface_to_texture_slow()`'s `#ifdef __ANDROID__` block:

```c
if (pgraph_gl_surface_drawn_format(surface) !=
        NV097_SET_SURFACE_FORMAT_COLOR_LE_R5G6B5 &&
    android_surface_to_texture_rgba8_compatible(surface, texture_shape) &&
    !android_surface_to_texture_needs_guest_reinterpretation(…) &&
    texture->gl_target == GL_TEXTURE_2D) {
```

### A1 (MEDIUM) — the condition cannot execute, and the commit's premise is false on this tree

`hw/xbox/nv2a/pgraph/gl/surface.c:1331`; the record in the commit body, in the
PR body (`:66-111`) and in `docs/lanes/remote/NOTES.md:677`.

The commit states, as the fact the change rests on: *"Both gates in front of the
blit admit R5G6B5 … So the blit is taken and the expansion is wrong."* The two
gates it names are `android_surface_to_texture_rgba8_compatible()` and
`android_surface_to_texture_needs_guest_reinterpretation()`, and both readings
are correct. **There is a third gate in front of both, and it refuses.**

`render_surface_to_texture_slow()` is reached only from
`pgraph_gl_render_surface_to_texture()`, which has exactly one call site —
`gl/texture.c:927` — and that call site is guarded by `surf_to_tex`, set at
`gl/texture.c:801` from `pgraph_gl_check_surface_to_texture_compatibility()`.
That function returns false at `gl/surface.c:1543` for any texture format where
`pgraph_texture_format_is_converted()` is true, and `texture.c:143` makes that
predicate fall through to `pgraph_texture_format_expands_by_replication()` —
which is true for every 5- and 6-bit packed texture format.

Derived from the switch bodies rather than asserted — the case labels were read
out of `android_surface_to_texture_rgba8_compatible()` in `gl/surface.c` and out
of `pgraph_texture_format_expands_by_replication()` / `…_is_converted()` in
`pgraph/texture.c`, then intersected, and the two line numbers taken from the
parsed body of `check_surface_to_texture_compatibility()`. Output verbatim
(token prefixes elided for width):

```
android_surface_to_texture_rgba8_compatible() accepts, for a surface of
  LE_R5G6B5              : ['LU_IMAGE_R5G6B5', 'SZ_R5G6B5']
  LE_X1R5G5B5_Z1R5G5B5   : ['LU_IMAGE_X1R5G5B5', 'SZ_X1R5G5B5',
                            'LU_IMAGE_A1R5G5B5', 'SZ_A1R5G5B5']

R5G6B5    accepted-but-NOT-converted: NONE
X1R5G5B5  accepted-but-NOT-converted: NONE

in pgraph_gl_check_surface_to_texture_compatibility():
  the is_converted refusal is at line 1543
  the first `return true` is at line 1587
  refusal comes first: True
```

So every texture format the Android predicate accepts against a 16-bit packed
surface is one the compatibility gate refuses, and it refuses **before** any
path that can return true — including the `#ifdef __ANDROID__` early return at
`:1585`, which is placed after it deliberately (`:1575`'s own comment says so
about the swizzle check immediately above). The texture comes from VRAM through
`pgraph_convert_texture_data` instead, which is where the replication lives.

This is not new code and not this lane's: `c234c1cc` and `f0095555`, both
**2026-09-12**, added the two `is_converted` refusals as part of #59's
replication work, and `docs/investigations/packed-texel-expansion.md:359` — in
this tree — already records that *"`check_surface_to_texture_compatiblity()` now
rejects every converted format outright"*.

**Consequences, in the order they will bite.**

1. **The condition is dead.** Its left operand can only be false in cases where
   the second operand is already false, so the `&&` chain is unchanged. The
   desktop run's *"byte-identical on 235 of 236"* is consistent with that and is
   not evidence against it — an `#ifdef __ANDROID__` block cannot move a desktop
   pixel either way. The Android job compiles it; nothing executes it.
2. **The stated trade does not exist.** The commit says *"THE TRADE, STATED:
   this gives up the GPU blit for R5G6B5 surface-to-texture on Android and takes
   a CPU conversion … a real throughput cost on a real device"*. There is no
   throughput cost, because there is no blit on that path to give up. A
   performance lane reading this will look for a cost that cannot appear.
3. **It hands #62's device half an unmeasurable task.** The commit closes with
   *"#62 can close once a device lane confirms it"*, and the PR body says device
   verification is the host's. A device lane will run the R5G6B5
   surface-to-texture captures, find them unchanged, and have to guess whether
   that confirms the fix or refutes the model. A change that cannot execute
   produces the same null result as a change that executed and did nothing.
4. **The sibling the lane asked me to rate cannot occur either, for the same
   reason.** PR body `:99-104` flags `LE_X1R5G5B5_Z1R5G5B5` — *"on the face of
   it the identical one-step error remains"* — and offers it to #62's device
   half. All four texture formats `rgba8_compatible()` accepts for that surface
   are replication-expanding and refused at the same line. **Rated: not a live
   defect on this tree.** The lane was right not to widen the fix; the reason it
   gives (unverifiable inference) is sound, and this is a second, stronger one.

**Failure scenario, concretely.** A lane is dispatched on #62 finding 2's device
half with this PR as its brief. It arms an A/B on `a5fdb6a7`, runs the
`Texture_render_target` and `Surface_format` 565 captures on a handheld, and
gets a byte-identical result on every one. It either closes #62 as confirmed —
recording a fix that never ran as verified silicon agreement — or opens a
regression against the ratio/replicate model that #59 measured. Either outcome
costs a device run and makes the record worse than it was. The same brief sends
a second lane at X1R5G5B5 for the same null.

**Severity.** MEDIUM, not HIGH: no incorrect behaviour is introduced, nothing
crashes, the desktop is untouched and the fix is at worst inert. What is wrong
is a factual claim in a permanent record that other work is already being
planned against.

**Remediation — prose, plus one decision, and no re-measurement.**

1. Correct the premise wherever it is stated — the commit body cannot be
   reworded (`a5fdb6a7` is an ancestor of nothing a prediction names, but it is
   published history on a branch whose rewrite rules the lane has already argued
   correctly, so leave it) but the **PR body**, **`docs/lanes/remote/NOTES.md`**
   and the **#62 comment** can: say that `pgraph_gl_check_surface_to_texture_compatibility()`
   refuses every replication-expanding texture format at `gl/surface.c:1543`,
   that this has been true since `c234c1cc`/`f0095555` on 2026-09-12, and that
   the R5G6B5 surface-to-texture blit is therefore not reachable.
2. Withdraw the device ask. #62 finding 2 has nothing for a device lane to
   confirm, and the X1R5G5B5 item offered alongside it has nothing either. Say
   so on #62 rather than leaving the offer standing.
3. Decide about the four lines of C, and say which you chose. Either is
   defensible and the choice is the lane's:
   - **Keep**, with the comment rewritten to say it is a belt-and-braces guard
     that becomes live only if the `is_converted` refusal is relaxed — which is
     a live direction of travel, since `packed-texel-expansion.md` calls that
     guard its *"least certain point"*. A guard documented as defensive is
     honest; a guard documented as a fix is not.
   - **Revert it**, leaving the blit exclusion to be written by whoever relaxes
     the gate, with the analysis kept in `NOTES.md`.
4. The measured arithmetic in the commit — 4/32, 10/64, 23,200/65,536, and the
   reconciliation of the 09-13 30,720 figure as truncating-vs-rounding — is
   correct and worth keeping. It is the reachability claim that is wrong, not
   the model. Keep the numbers; move them to where they describe the VRAM
   round-trip that actually runs.

### A2 (LOW) — `docs/investigations/gl-pad-bit-write-side-patch-shape.md` is on no `Files:` line

`docs/investigations/gl-pad-bit-write-side-patch-shape.md`, added by `cb57880d`.

`git diff --name-only origin/master...HEAD` lists 18 files. The body's `Files:`
line covers nine, and the prediction is declared on its own line; the audit
records and `docs/lanes/remote/NOTES.md` are per-lane paths that cannot collide.
That leaves this one undeclared. It is **LOW and predates every pass** — a new
file with a lane-specific name in a directory of 100-odd such files, so a
collision would be a visible create/create conflict rather than a silent
overwrite, which is exactly why pass 2b rated the same shape LOW for
`skip_ci_marker_check.sh`. Add it to `Files:` while editing the body for A1;
it does not justify a pass on its own.

---

## What this pass checked and did not find wrong

* The fall-through `a5fdb6a7` describes is correctly *described*: were the path
  reachable, an excluded R5G6B5 surface would reach the second `#ifdef
  __ANDROID__` block at `:1409`, where `rgba8_compatible()` is still true and
  `needs_guest_reinterpretation()` still false, so it would land in
  `android_surface_guest_to_rgba8()`'s R5G6B5 case at `:552`, which replicates
  through `android_expand_5_to_8()` / `android_expand_6_to_8()`. The mechanism
  is right; only the reachability is wrong.
* The commit's refusal to implement this by making
  `android_surface_to_texture_needs_guest_reinterpretation()` return true is
  correct and for the reason given: that would route to
  `android_surface_guest_to_texture_rgba8()`, the reinterpretation converter,
  and would also change the second `#ifdef __ANDROID__` block.
* `render_surface_to()` has no format-specific handling to hide behind — it
  samples `surface->gl_buffer` through a shader (`:1253`) and the driver's
  normalized conversion is the ratio, so the mechanism named is the real one.
* `pgraph_gl_render_surface_to_texture()` has exactly one call site in the whole
  tree, and no function-pointer or renderer-ops indirection reaches it.
* `gles_token_check.py` re-run at this tip because `a5fdb6a7` added an
  `#ifdef __ANDROID__` block to a file it scans: 13 files, **0 findings**.
* The branch is 0 behind master, never rebased, and the PR is ready rather than
  draft.
* The `Base: master @ bb4b7868` line in the PR body is now two merges stale
  (the branch has since merged `edcc31d8`). Not a finding — the line records
  what it was opened over and says so — but it is worth refreshing while the
  body is open for A1.

## Disposition

**`needs-remediation`** — **A1** (MEDIUM) alone forces it; **A2** is LOW and
rides along. P1, P2, P3 and P4 are all closed and verified against mutants; the
six pass-1 scenarios and both pass-2 scenarios still hold.

The whole remediation is the PR body, one `NOTES.md` section, one comment on
#62, and a decision about four lines of C. **Nothing needs re-measuring and
nothing needs a device.** `skip_ci_marker_check.sh`, `gles_token_check.py`,
`pgraph_capture_run.sh`, `gl/draw.c`, `gl/renderer.c` and `glsl/psh.c` are
settled — do not reopen them.
