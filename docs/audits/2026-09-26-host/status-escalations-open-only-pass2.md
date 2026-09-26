# Audit pass 2 -- PR #422 `host/status-escalations-open-only`

Result: **clean.** Pass 1 found no HIGH or MEDIUM, so no failure scenario had
to be fixed. The diff pass 1 read is still the diff on the branch, and the four
fixtures give the same answers when run again. Next state: `fold-ready`.

## Checked

- **The head is the diff pass 1 read.** Before this file, the PR head was
  `13a8f7a276`: the pass-1 audit commit on top of `4279cb5e91`. The code
  diff against `origin/master` is still only the `status.sh` escalation hunk
  (+7/-3). Nothing changed after pass 1. The PR is `MERGEABLE`.
- **The four pass-1 fixtures, run again** (the hunk copied verbatim, `set -u`,
  with a stub `attn`; `status.sh:45` is `set -u` only):
  | fixture | result |
  |---|---|
  | a blank line only | nothing raised |
  | `- RESOLVED` lines only | nothing raised |
  | one resolved, `- ... watchdog`, `  * second open`, `# heading` | `2 escalation line(s) ...; latest: second open` |
  | a bare line with no list marker | nothing raised (L1, as pass 1 says) |
  When nothing is raised, the `if` exits 1. There is no `set -e` and the next
  statement is a new top-level `if`, so that exit status has no effect.

## The pass-1 LOWs

They are unchanged. Each one is a limit that pass 1 already stated, and none
blocks the fold:

- L1 (a line with no marker is silent) and L3 (`*` versus `-`): both depend on
  a writer format that no writer uses today. The durable fix for L1 belongs in
  the hostops preamble (host-tools), not in this PR.
- L2 (the `RESOLVED` substring): this is the same rule `harness_health.py`
  uses.
- L4 (no selftest): still open. It is a good follow-up for `60-status.sh`.
- The new comment still says "awaiting him". Changing it to "awaiting the
  owner" costs one word. This is LOW and does not block.

## CI

When this was written, CI on `13a8f7a276` was in progress: Android, Desktop
build and jobs selftest. Pushing this file starts a new run. The fold job
gates on that run, so `fold-ready` does not skip it.
