# Audit pass 2: PR #449, lane `claude/docs-tooling-agentic-coding-u152m1` (#426 items 1, 2, 4)

Head verified: `406a195f92` (pass 1 plus nothing but the pass-1 file itself).

**Verdict: clean.** Pass 1 found no HIGH and no MEDIUM, so there was no scenario that had to be stopped from firing. Its two LOWs are documentation-only and are still open. They do not block the fold.

## The audited code is the head code

Pass 1 read `932ab471`. `git diff --stat 932ab471 406a195f92` touches none of the PR's code files (`debug.h`, `profile.c`, `vk/draw.c`, `vk/renderer.h`, `vk/texture.c`, `phase_read_split.py`, `phase_read_split_check.py`). Everything in that range is either master content brought in by the fold job's merge (`45f62ce0`), the regenerated index (`699c0e87`), or the pass-1 file. So each pass-1 "What was checked" claim was made against the code that is on the head now.

## Pass-1 findings at this head

### LOW-1 (`Tx` is not exclusive of finish): still present, does not block

`docs/testing/phase_read_split.py:40-41` still says `rest` "also carries any finish nested in a Tx bind, since Tx is not exclusive of finish". `vk/draw.c:2163` still opens `pipe_bind_tex` with `NV2A_PHASE_TIMER_BEGIN_EXCL`. The scenario can still happen: a reader who trusts the docstring attributes part of a new line's `rest` to a finish the instrument has already removed. Its blast radius is unchanged and small: it is a comment, and no number the tool prints depends on it.

### LOW-2 (older-soak caveat omits `Draw` and `BUSY`): still present, does not block

The PR body's "Not covered" still names only `Pipe`, `Setup` and `Tx`. The docstring (`phase_read_split.py:32-36`) does say that on older lines "a clear's children sit outside Draw", so a reader of the tool is told part of it. It does not say that `Draw`, and so `BUSY`, read higher on a new line from a clear-heavy title because of the instrument. The scenario can still happen, and it is still bounded to how a person reads a cross-build comparison.

## Also observed (LOW, not this PR's defect)

The audit path `docs/audits/<date>-<lane>-passN.md` is keyed on the branch name, and this branch has carried three PRs (#380, #389, #449). On `origin/master` the pass-1 path holds #380's pass 1 and the pass-2 path holds #389's pass 2. This PR's pass 1 replaced the first, and this file replaces the second. The earlier records are still in git history (`0bb332bb3e`, `734561a51f`), so nothing is lost. But after the fold, the file at the path belongs only to the latest PR. Keying the path on the PR number would stop that.

## Not verified

- The Android compile of the `pipe[...]` line, as in pass 1: the perflog APK is its first real compile, and a failure there is a loud build error, not a silent mis-measurement.
- CI on this head was still running when this was written. The fold job gates on it.
