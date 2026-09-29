# Audit pass 2: PR #580, lane/litcompile569

Head verified: `a58ff1b9ae`. Auditor: job.cloud, 2026-09-28.

**Verdict: clean. The PR goes to `fold-ready`.** Pass 1 found no HIGH and no
MEDIUM. Of its two LOWs, neither can fire on this head or on current master.
LOW 1 is still unfixed; it is a hazard for a future edit, not a defect in
this change. It is noted below as a follow-up.

## What was checked

- **Head movement since pass 1.** `git diff --stat 3e24ed0fe9 a58ff1b9ae`
  shows one changed file: the pass-1 audit file.
  - `hw/xbox/nv2a/pgraph/glsl/vsh-ff.c` has not changed, so pass 1's reading
    of the shipping change still holds.
  - The re-verification that pass 1 made conditional on a moved head
    (re-running `run_lt_check.sh`, re-diffing the transcription) is not
    triggered.
- **Master since the merge base (`bf1ecde346`).**
  `git log bf1ecde346..origin/master -- hw/xbox/nv2a/pgraph/glsl/` is empty,
  so nothing on master adds a new lighting-emitter call that the fold would
  carry into the 450 block. `git merge-tree` of master and the head is clean.
  GitHub reports the PR as `MERGEABLE`, and build, build and check are
  SUCCESS.

## Pass-1 scenarios

### LOW 1: the 450 block has no `ltA`

- **Status: not fixed, and the scenario cannot occur on this head or on
  master.**
- **Why it cannot occur today.** The only `ltA(` in `hw/xbox/nv2a` is in the
  `#else` branch of `vsh-ff.c`, at lines 412-413 (the definition, and its use
  by the old `ltVA`).
  - Pass 1 listed the helpers that only the old branch defines: `ltA`,
    `ltMk`, `ltMulCore`, `ltShr`, `ltIsNan`, `ltIsInf` and `ltMsb`.
  - A grep of `origin/master` finds no call to any of them outside
    `vsh-ff.c`.
  - No Vulkan shader can reference an undefined function.
- **What remains.** The trap is still there for the next editor: a new
  emitter that calls `ltA` would fail glslang on Vulkan only.
  - This is quality, not correctness, so it does not block the fold.
  - Recommended follow-up: add `float ltA(float a, float b) { return
    ltA3(a, b, 0.0); }` to the 450 block, or a comment naming the helpers
    that both branches must define.

### LOW 2: `doa_soak_judge.py` prints PASS/FAIL on a void pair

- **Status: unchanged.** Pass 1 required no fix for the fold, and the judge
  has not been edited.
- **Scope.** It is lane tooling under `docs/lanes/litcompile569/` and does not
  ship. Its VOID line prints first.

## Outcome

There is no HIGH or MEDIUM to verify, and no pass-1 scenario fires on the
head or on master. Move `needs-audit-2` → `fold-ready`.
