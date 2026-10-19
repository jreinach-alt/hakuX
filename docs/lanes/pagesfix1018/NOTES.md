# pagesfix1018 -- fix the stale `check --pages` falsifier fixture (#433)

## Brief

`docs/testing/jobs/selftest.d/66-status-titles.sh` runs
`docs/lanes/titledb1014/fixture/pages_check_falsifier.py` and expects `PASS`.
The brief's diagnosis: the fixture's `write_pages()` writes README.md's
Playable line in the old NUMBERED form (`"[%d Playable games](...)\n\n-
**%d games rated Playable.**..."`), which can never satisfy
`title_registry.py`'s `readme_has_numberless_line()` (added 2026-10-17,
commit 48a6db90c5), so the "agreeing fixture should PASS" case always FAILs.

## What I found reading the current code (goes beyond the brief's diagnosis)

The brief's root cause is correct but incomplete. `check --pages`'s README
handling didn't just change its expected *text* -- it changed *mechanism*.
Before 10-17, README's Playable count was presumably read numerically (the
old fixture's mutant assertion names a `"README.md (bullet)"` label and
expects a `"PAGE README.md (bullet): Playable 2, table 1"` mismatch line).
Reading `title_registry.py` as of this branch:

- `readme_has_numberless_line(p)` (line 968) is a **boolean** check: does
  README.md contain the exact literal line
  `**Games rated Playable so far:** [the list, with progress charts](https://github.com/jreinach-alt/hakuX/blob/home/STATUS.md).`
  (regex `README_NUMBERLESS`, line 964) exactly once? It carries NO number
  and is compared against nothing in the table.
- `page_playable_counts(p)` (line 979) -- the function that produces the
  `"PAGE <label>: Playable N matches/N, table M"` lines the fixture greps
  for -- has exactly 4 entries: `"status page"`, `"COMPATIBILITY.md
  (header)"`, `"COMPATIBILITY.md (table rows)"`, `"Wall"`. **There is no
  README entry at all.** README is reported separately (`check`'s `--pages`
  branch, line 1103-1107) as either `"PAGE README.md: numberless Playable
  line, as home_page.py expects (home sets the count)"` or `"PAGE README.md:
  the Playable line is not the numberless form home_page.py rewrites"` --
  never "matches the table", never naming a number.

So the old fixture's assumptions (6 numeric pages total, a `"README.md
(bullet)"` numeric mismatch line on the mutant) are not just textually stale,
they describe a comparison that no longer exists. Confirmed by running the
unfixed fixture directly against this repo before touching anything --
`exit=3` on the agreeing case every time, and the mutant assertion
("naming README.md (bullet)") was ALSO already false, independent of the
numbered-vs-numberless text bug. Both of the two assertions `66-status-titles.sh`
relies on ("PASS on agree", "names the one page a mutant disagreed on") were
broken; the brief's step 2 anticipated this ("both assertions ... must hold,
not just the one that was broken").

## The fix

`docs/lanes/titledb1014/fixture/pages_check_falsifier.py`:

1. `write_pages()`: README.md now gets the exact numberless line
   (`"**Games rated Playable so far:** [the list, with progress
   charts](https://github.com/jreinach-alt/hakuX/blob/home/STATUS.md).\n"`),
   matching `README_NUMBERLESS` byte-for-byte (read from `title_registry.py`,
   not guessed). Not parameterized on `playable` any more -- the check is a
   format match, not a number comparison, so there is nothing to vary.
2. `main()`: the agreeing-case assertion now expects `"PAGE README.md:
   numberless Playable line, as home_page.py expects"` plus exactly 4
   (not 6) `"matches the table"` lines -- one per real `page_playable_counts()`
   entry.
3. The mutant: since README can no longer "disagree by number", the mutant
   instead breaks the numberless line's exact text (`"Games rated Playable
   so far:"` -> `"Games rated Playable:"`), which is the real way this page
   can now fail. Assertion updated to expect `"PAGE README.md: the Playable
   line is not the numberless form home_page.py rewrites"` and the other 4
   numeric pages still agreeing (`"matches the table"` count stays 4).

Status page, COMPATIBILITY.md, and `.wall-synced` writes in `write_pages()`
are untouched -- their regexes in `page_playable_counts()` still match the
fixture's existing output exactly, confirmed by reading both sides.
`title_registry.py` and README.md: not touched, per the brief and the files
constraint.

## Proof

Fixture run directly, before the fix (showing the failure the brief
describes, plus the second broken assertion it didn't name):
```
agreeing fixture: exit=3
PAGE README.md: the Playable line is not the numberless form home_page.py rewrites
... (4 numeric pages all matching)
FAIL
 - the agreeing fixture ... was expected to PASS and did not
 - expected all 6 pages to report 'matches the table'; got: ... (only 4 ever print it)
 - expected the mismatch line naming README.md (bullet); got: ... (that label doesn't exist)
 - expected the other 5 pages to still match; got: ...
```

After the fix, same command:
```
agreeing fixture: exit=0
PAGE README.md: numberless Playable line, as home_page.py expects (home sets the count)
PAGE status page: Playable 1 matches the table
PAGE COMPATIBILITY.md (header): Playable 1 matches the table
PAGE COMPATIBILITY.md (table rows): Playable 1 matches the table
PAGE Wall: Playable 1 matches the table

mutant fixture (README numberless line broken): exit=3
PAGE README.md: the Playable line is not the numberless form home_page.py rewrites
... (4 numeric pages still matching)

PASS: check --pages passes when every page agrees, and fails naming the one page a mutant disagreed on
```

Full `docs/testing/jobs/selftest.sh`, all 4 shards, run to completion
(SELFTEST_SHARD=k/4 for k in 0..3), each shard's own fake host, each clean:

| shard | passed | failed |
|---|---|---|
| 0/4 | 290 | 0 |
| 1/4 | 1021 | 0 |
| 2/4 | 1219 | 0 |
| 3/4 | 1203 | 0 |

Total: 3733 passed, 0 failed across all 153 fragments. Fragment
`66-status-titles.sh` (shard 3/4) specifically shows:
```
  ok   check --pages passes when every page agrees and fails naming the one page a mutant disagreed on
```
This is the exact fragment/assertion devpushro1018 (folded just before this
lane started) reported as the one pre-existing failure in its own full-suite
run (3732 passed, 1 failed -- that failure) and explicitly left untouched,
out of its scope. Confirms this was the harness defect blocking folds all
day, as the brief said, and that it is now closed.

## For the next lane

- Nothing outstanding. The fixture and the selftest suite are both green.
- If `readme_has_numberless_line()`'s regex or `page_playable_counts()`'s
  label set changes again, re-read them before touching this fixture again --
  this file is evidence that "the brief's root cause" and "everything that
  actually drifted" are not always the same set.

## Questions

None blocking. No decision needed from the owner or another lane.
