# Audit pass 1: PR #578, lane.remote: revert the #557 thermal governor core

Head: 644e189bb9. Branch: `claude/docs-tooling-agentic-coding-u152m1`. Auditor: job.cloud.

The file name carries `-pr578` because this branch name was used before, by PR #560. Its pass-1 and pass-2 audits are already at `docs/audits/2026-09-28-claude/docs-tooling-agentic-coding-u152m1-pass{1,2}.md` on master. Writing to that path would overwrite the record of a different PR.

**Verdict: no HIGH, no MEDIUM, two LOW.** The revert does what the body says. Nothing in the build still refers to the core.

## What was checked

- **The CMake revert.** `git diff 0f4002eb HEAD -- android/app/src/main/cpp/CMakeLists.txt` is empty, so the file matches its state before #560.
- **No caller is left behind.** A `git grep` for `thermal_governor` and `HAKUX_THERMAL_ADAPT` over HEAD finds them only in `docs/lanes/remote/` (the harness, the replay and NOTES), in the prediction file, and in #560's audits. Nothing in `android/`, `ui/`, the hooks or `.github/` refers to them, so removing the two files cannot break a build or a check.
- **The history reference exists.** `CORE_REF` 3a5d79e3 is an ancestor of `origin/master`, and its tree holds `android/app/src/main/cpp/thermal_governor.c` and `.h`.
- **The build from history works.** `python3 docs/lanes/remote/thermal557_replay.py --selftest` on this head builds the harness against the core written to a temp dir, and passes 17 of 17 groups.
- **Include resolution.** `#include "thermal_governor.c"` in the harness looks in `docs/lanes/remote/` first, which has no such file, and then in the `-I out_dir` that the script adds. Inside the copied core, `#include "thermal_governor.h"` resolves to the copy next to it in `out_dir`.
- **Shallow clones.** All three workflows that check out the repo use `fetch-depth: 0`, and no CI job or hook runs the replay. So `fetch_core()`'s exit path cannot turn a CI run red.
- **The prediction file** `remote-557-replay.json` is not in the diff. That is correct, because registrations are never rewritten.

## Findings

**LOW-1: a stray `thermal_governor.c` beside the harness would silently take precedence.** A quoted include searches the including file's own directory before `-I`. Scenario: someone copies the core into `docs/lanes/remote/` to edit it, and the replay then builds that copy instead of CORE_REF. The selftest would still say it tested "the core" when it had not. This is bounded: nobody does it today, and the tree has no such file. Two possible fixes: include `<thermal_governor.c>` with `-I out_dir` (then only `-I` paths are searched), or have `build()` refuse to run when `os.path.exists(os.path.join(HERE, "thermal_governor.c"))`.

**LOW-2: the lane reused a branch name whose audits are already on master.** This is process, not code. The next audit of this branch hits the same path collision described above. A new PR from lane.remote should go on a suffixed branch (`lane/<name>-<suffix>`).

## Not findings

- The branch is 58 commits behind master, but GitHub reports it MERGEABLE. The revert touches only files that no later commit changed.
- `Closes #557` in the body is the owner's directive ("the one PR that reverts #560's core"). It is not a lane closing an issue on its own authority.

## Next

Only LOWs, so the label moves to `needs-audit-2`. Neither LOW has to be fixed for the fold: LOW-1 is a hardening, and LOW-2 is advice for the next branch. Pass 2 can close both as accepted.
