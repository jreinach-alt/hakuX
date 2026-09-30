# lane.escalationparse -- #433: the dashboard counted one escalation as 32

## Status

PR #628 open, pushed at 9dd4b98785, waiting on CI (build + selftest shards).
Locally green: `99-status-escalation-items.sh` (unchanged, 6/6) and the new
`99-status-escalations.sh` (4/4) under the real `selftest.sh` harness, plus a
broader run of 60-67 and every 99-status-* fragment (196/197 -- the one
failure, "status shows the arms refusal in full" in `60-status.sh`, is an
artifact of running that fragment outside its normal 10-50 sequence in a
`SELFTEST_ONLY` subset; it reads `$WORK/arms/skipped/` files that only the
earlier arms fragments create, and none of this PR's files are in that path).
Will mark the PR ready once CI reports green.

## What was wrong

`status_html.py`'s `escalation_items()` grouped `host-tools/escalations.md` into
items with `_items(text, lambda l: l.strip() and not l.startswith("#"))`: only a
`"#"`-prefixed line was excluded from opening a new item. hostops's 2026-09-29
13:06 and 15:55 PDT entries are `## ` heading blocks whose body is unindented
prose (no `- ` bullet, no leading whitespace) -- every one of those paragraph
lines opened its own item, turning one WSL-restart escalation into 32 "decisions"
on the page. The 33rd (`hakux-hostops.timer ... has no next run`) is unrelated:
that one comes from `status.sh`'s bash-side `attn` mechanism (facts.tsv), not
`escalation_items()`.

Fixing (1) alone reintroduces a second, worse bug: an item was "resolved" when
*any* of its lines contained the substring `RESOLVED`. hostops's own tick
updates routinely say "Not marking RESOLVED." on a continuation line (it does,
literally, in the 2026-09-29 18:33 PDT update, and that exact sentence is also
hard-line-wrapped there as `"...Not marking\n  RESOLVED."`), which would close
the still-open WSL item the moment the heading grouping worked -- 0 items shown
while a real decision was pending, which the owner called worse than 32.

## The rule implemented (`status_html.py`)

`_items(text, opens)`: unchanged for what `opens()` matches, but now every line
that is *not* an opener -- indented **or not** -- extends the current item
instead of being silently dropped. This is what sweeps a `##` block's unindented
paragraphs into the heading's item. `_needs_hands()`'s caller is unaffected: its
`opens` is `lambda l: l.strip()`, true for every non-blank unindented line
already, so the new branch only ever fires there on a blank line, which was
already a no-op.

`escalation_items()`'s `opens()` now recognizes exactly three openers: a `"- "`/`"* "`
bullet, the older unbulleted `"OWNER ONLY"` line (**not** a bare `"OWNER"` --
first attempt matched `"OWNER-LEVEL:"` inside the WSL heading's own body and
split it into a second item; a heading block containing the word "OWNER" is not
rare, so this needed the tighter anchor), or a `"## "` heading. Everything else
belongs to whatever item is open.

**Resolved is a marker, never a bare substring**, but "starts with RESOLVED
after stripping the bullet/indent" (the brief's literal wording) is not enough
on its own: hostops writes resolutions two ways --
- a rewritten leading bullet: `"- RESOLVED <time> (source): ... Was: <original>"`
- an older style that appends a new sentence onto the *same* line as the
  original ask: `"<ask>. Nothing else possible here. RESOLVED <time> (source): ..."`
  (this is how every one of the real file's 09-27/09-28 entries resolves --
  see `fixtures/escalations-20260929.md` lines 1-16)

Both are a marker; "Not marking RESOLVED." and "Mark RESOLVED here once done."
are not, because in neither case does "RESOLVED" start a sentence. The rule:
join the item's lines back into one string with a space and search for
`(?:^|[.!?]\s+)RESOLVED\b`. Per-line matching (checking each physical line's
`^RESOLVED` independently) fails on hostops's own hard-wrap: the sentence
"Not marking RESOLVED." split across two lines as `"...Not marking"` /
`"  RESOLVED."` would read the second physical line as starting fresh with
RESOLVED and falsely close the item. Joining first, then searching, fixes that:
`"...Not marking RESOLVED."` has no `.`/`!`/`?` immediately before "RESOLVED",
so it does not match, while `"...still draining. RESOLVED <time>..."` does.

## Measured against the real file

Verified directly (not just via the selftest) against both
`/home/justin/hakux-work/host-tools/escalations.md` (live, changes every
hostops tick) and its frozen snapshot, copied into this lane as
`fixtures/escalations-20260929.md` (`host-tools/escalations.md.bak-20260929-lanelocal`,
not touched, only copied).

The brief's Proof section says the real 09-29 shape "gives exactly 2 open
items" but also separately lists the two `## ` blocks *and* the `- 16:00 OWNER
HANDS` bullet, noting the two headings "count as 2 unless one is marked" --
neither carries a RESOLVED marker, so under this rule they stay two separate
items. My rule's actual, verified yield on the frozen snapshot is **3** open
items: the 13:06 WSL heading, the 15:55 WSL heading, and the 16:00 OWNER HANDS
battery bullet. I take this as the brief's "2" being shorthand for "2 concerns"
(the WSL restart, the battery ceiling) rather than a literal item count, since
3 is what a faithful, marker-based read of the actual file produces, and it
satisfies the hard requirement ("never 32 or 0"). Watched the live file change
under me while working: by ~19:20 PDT hostops appended a leading-marker
RESOLVED to the 16:00 bullet, and a re-run against the live file at that point
correctly dropped to 2 open items (the two still-open WSL headings only).

## The timer's 33rd item

`hakux-hostops.timer is active but has no next run` comes from `status.sh`
(bash), which already guards against a mid-run service:
```
case "$(systemctl --user is-active "${u%.timer}.service")" in active|activating|reloading) continue ;; esac
```
That guard passed and the alarm still landed on the page (confirmed live: it
was sitting in `/home/justin/hakux-work/status/facts.tsv` as of this session).
The gap is time, not logic: bash checks once, when `status.sh` gathers facts;
`status_html.py build()` runs afterward to render, and hostops's tick can start
between the two. Fix: `_live_timer_attn()` re-checks the paired `.service`
*again*, right before the alarm is merged into "needs a person" in `build()`,
and drops it unless the service now reads `inactive` or `failed`. An empty/
unreadable state (no systemd user session, e.g. under test) keeps the alarm --
fail open, not closed, so a real stuck timer is never hidden by an environment
that can't be asked.

## For hostops: `harness_health.py` has the same two bugs

Out of scope to fix here (host-side, not in this repo), but named precisely
since the brief asked: `host-tools/harness_health.py` lines 2327-2341 (the
`# ---- escalations` block):
- Line 2334 only opens an item on a `"- "` bullet; a `"## "` heading's
  unindented body lines are neither an item nor a continuation (line 2336
  only appends *indented* lines), so they are silently dropped from
  harness_health's own escalation count -- not the same 32x failure mode
  (nothing multiplies), but a `##`-style escalation's body doesn't count
  toward its `escalation_min` SLO at all.
- Line 2338, `'RESOLVED' not in i`, is the same bare-substring bug: "Not
  marking RESOLVED." on a continuation line closes the item early here too.

## Proof

- `docs/testing/jobs/selftest.d/99-status-escalations.sh` (new): real-shape
  leg against `fixtures/escalations-20260929.md` (3 items, never 32/0, right
  identities); a synthetic heading leg (two `##` blocks' unindented paragraphs
  swept in, a second heading and a bullet each open the next item); a resolved
  leg (wrapped "Not marking\n RESOLVED." stays open; a leading `- RESOLVED`,
  an embedded ". RESOLVED", and an indented continuation `RESOLVED` line all
  close); a timer leg (`_live_timer_attn` direct: activating -> dropped,
  inactive/failed -> kept, unreadable state -> kept).
- Ran the existing `99-status-escalation-items.sh` (a-f) unchanged and green
  against this lane's code, through the real `selftest.sh` harness (not just a
  standalone script): `SELFTEST_ONLY="99-status-escalations.sh
  99-status-escalation-items.sh" bash selftest.sh` -> 10 passed, 0 failed.
- Did **not** get a clean run of `STATUS_OUT_DIR=<scratch> status.sh --print`
  in this session: the sandbox required interactive approval to run it (it
  shells out to `systemctl`/`gh`/`adb` against the live host) and that
  approval did not come through. In its place I called `escalation_items()`
  and `_live_timer_attn()` directly against the real, live
  `host-tools/escalations.md` and its frozen backup, which is the part of the
  render this lane changes; the next session with an approved shell should
  still run the `--print` local render as the brief asks, to also see it
  reflected in the actual "3. What needs a person?" HTML section end to end.

## Files touched

- `docs/testing/jobs/status_html.py`
- `docs/testing/jobs/selftest.d/99-status-escalations.sh` (new)
- `docs/lanes/escalationparse/fixtures/escalations-20260929.md` (new; a copy
  of `host-tools/escalations.md.bak-20260929-lanelocal`, not the live file)
- `docs/lanes/escalationparse/NOTES.md` (this file)

Release note (none): harness dashboard.
