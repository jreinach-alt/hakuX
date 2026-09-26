# Audit pass 1 -- PR #422 `host/status-escalations-open-only`

Diff: `docs/testing/jobs/status.sh` +7/-3 (the `escalation` attention item).
Result: **no HIGH, no MEDIUM; 4 LOW.** Next state: `needs-audit-2`.

## What the change does

`status.sh` raised `attn escalation` whenever `host-tools/escalations.md` was
non-empty, and counted every `-`/`*`/`#` line. Host ops marks a decided line
`RESOLVED` in place, so resolved escalations stayed on the page as urgent. The
change keeps only list lines (`^\s*[-*] `) that do not contain `RESOLVED`, counts
them, takes the latest-line text from those lines, and raises the item only if
the count is above zero.

## Checked

- The snippet from the diff, run under `set -u` (`status.sh` runs with `set -u`
  only: no `-e`, no `pipefail`) against four fixtures:
  | fixture | result |
  |---|---|
  | one blank line (today's live `escalations.md`, which `-s` treats as non-empty) | nothing raised |
  | the six archived lines in `host-tools/escalations-resolved.md`, all `- RESOLVED ...` | nothing raised |
  | those six plus `- ...watchdog...`, `  * ... second open`, `# heading` | `2 escalation line(s)`, latest = the `*` line, heading ignored |
  | one bare line with no list marker | nothing raised (see L1) |
- `grep -c` exits 1 on a zero count and prints `0`; with `|| true`, `ne` is `0` and the `-gt` test is false. No unset-variable path under `set -u`.
- Writers: `hostops_watchdog.sh` appends `- <date> watchdog: ...`; every archived hostops line starts `- `. The one other reader, `harness_health.py` (escalations check), uses the same rule: `strip().startswith('-') and 'RESOLVED' not in l`. So the two readers now agree on what counts as open.
- `[ ... ] && attn ...` as the last command in the `if` body is safe: no `set -e`, and it is top-level code, not a function's return value.

## Findings

**L1 (LOW) -- an escalation line with no list marker is now silent.** Before
the change, any non-empty file raised the item (the text came from the last
non-blank line). Now a line that does not start `- ` or `* ` is not counted.
Scenario: a hostops session follows `hostops-preamble.md` ("append a dated
line") and writes `09-26 14:00 PDT (hostops) ...` with no `- `. The owner's
page shows nothing (fixture 4). LOW because every writer seen uses `- `, and
`harness_health.py` already ignores such a line, so the harness health check
misses it too. The durable fix is in the preamble ("append a `- ` line"), which
is host-tools territory, not this PR's.

**L2 (LOW) -- `RESOLVED` anywhere in the line closes it.** An open line that
quotes the word (for example, "the watchdog item RESOLVED at 10:25 recurred")
is dropped. `harness_health.py` has the same substring rule, so behaviour
matches. Anchoring on `^\s*[-*] +RESOLVED` would be stricter, but the archived
lines put `RESOLVED` first anyway.

**L3 (LOW) -- `-` versus `*` differ between the two readers.** `status.sh`
counts `* ` lines; `harness_health.py` counts only lines that start with `-`
(and also `-` with no space after it). No writer uses `*` or a bare `-`, so the
two readers do not disagree today.

**L4 (LOW, test coverage) -- no selftest.** None of the `selftest.d/6*-status*.sh`
tests touch the escalation item. The PR body's two hand-checked fixtures are
the same as fixtures 2 and 3 above, and both pass. A fixture file in
`60-status.sh` with one resolved and one open line would pin the count.

Also in the new comment: "nothing awaiting him" gives the owner a pronoun that
has not been stated. "nothing awaiting the owner" says the same thing.

## For pass 2

There is no HIGH or MEDIUM scenario to re-verify. Pass 2 should confirm that
the head it reviews is still this diff (same `status.sh` hunk) and that CI is
green.
