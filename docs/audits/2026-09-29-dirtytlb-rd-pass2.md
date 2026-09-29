# Audit pass 2: PR #575, lane/dirtytlb-rd (#548)

Head verified: `1255eaf7d0`. That is the pass-1 head `b30855c55a` plus the
pass-1 audit file. `git diff b30855c55a 1255eaf7d0` touches only
`docs/audits/2026-09-29-dirtytlb-rd-pass1.md`, so no code has changed since
pass 1. `origin/master` is two commits ahead, and both touch only
`docs/lanes/remote/NOTES.md`. Nothing under `accel/` moves at fold time.
Auditor: job.cloud, 2026-09-29.

**Result: clean. Pass 1 found no HIGH or MEDIUM, and neither LOW needs a
code change. The PR is fold-ready.**

## The three checks pass 1 asked for

- **The switch is still the JC form.** `cputlb.c:184` reads
  `getenv("HAKUX_TCG68_RD") ? hakux_tlb68_env("HAKUX_TCG68_RD") : 1`, which
  is the same form as `HAKUX_TCG68_JC` at `:194`.
- **The `c.dirty` writer set is still the three sites.** `git grep 'c\.dirty'`
  over every `*.c` and `*.h` in the tree finds exactly these writers:
  - `tlb_init` at `:575` (`= 0`).
  - `tlb_flush_by_mmuidx_async_work` at `:627-635`. It clears `to_clean`
    and flushes exactly those modes, in the same `c.lock` section.
  - `tlb_set_page_full` at `:1468` (`|=`).
  
  The other hits are reads:
  - `:257`, a `qatomic_read` that feeds a log line.
  - `:1220` and `:1298`, the two walks. Both read under `c.lock`.
  
  No file outside `cputlb.c` names the field. The exactness argument from
  pass 1 therefore still holds on this head.
- **LOW 1's decision is visible in the PR.** The body's "For the audit" line
  and the Black table both say that X FAILS and that the registered verdict
  stays FAIL. They also give the reading: `sd` tracks walks, not exactness.
  Landing over the fired falsifier remains the board's call, made in the
  open.

## Pass-1 scenarios

- **LOW 1** (a reader who trusts the registered verdict alone concludes the
  switch is inexact on Black). This is a record-keeping matter, and the PR
  states it. The code gives no path to inexactness. It stays LOW.
- **LOW 2** (a value other than a leading `1`, such as `=true`, turns the
  fix off). This is unchanged on the head: `hakux_tlb68_env` still returns
  `v[0] == '1'`. Both walks are exact, so the only cost is performance, and
  JC shares the behaviour. It stays LOW, and the fix is optional.

## Verdict

Nothing to remediate. Remove `needs-audit-2` and add `fold-ready`.
