# lane.localtime -- show Pacific to the reader, keep UTC in the data

Brief: convert the harness's human-facing timestamps to the owner's local
zone, leave the timestamps that scripts compare in UTC, and put one helper
where both halves of the harness can reach it.

The conversion itself was small. Two of the brief's premises were wrong and
one data site it does not mention would have been broken by following it, so
most of the work was establishing those three things rather than editing.

---

## 1. `Pacific/Los_Angeles` is not a timezone

The brief specifies, verbatim:

```sh
say_time() { TZ='Pacific/Los_Angeles' date '+%F %H:%M %Z'; }
```

There is no `Pacific/Los_Angeles` in the tz database. `Pacific/*` is the
Pacific *ocean* -- Auckland, Honolulu, Fiji. The United States west coast is
`America/Los_Angeles`. Measured on the host, 2026-09-19:

```
$ test -e /usr/share/zoneinfo/Pacific/Los_Angeles && echo EXISTS || echo ABSENT
ABSENT
$ test -e /usr/share/zoneinfo/America/Los_Angeles && echo EXISTS || echo ABSENT
EXISTS
```

The two halves of the harness fail differently on the bad name, and **the
shell's failure is the dangerous one**:

| | `TZ='Pacific/Los_Angeles'` | `TZ='America/Los_Angeles'` |
|---|---|---|
| `date '+%F %H:%M %Z %z'` | `2026-09-19 13:40 Pacific +0000` | `2026-09-19 06:40 PDT -0700` |
| `ZoneInfo(...)` | raises `ZoneInfoNotFoundError` | works |

glibc cannot find the file, falls back to UTC, and takes the string before the
`/` as the zone abbreviation. So the status page would have read
**`13:40 Pacific`** while the actual Pacific time was `06:40 PDT`: a
seven-hour error wearing a label that says it was converted. That is strictly
worse than leaving the timestamps as UTC, because a reader who sees `UTC` does
the subtraction and a reader who sees `Pacific` does not.

Python would have crashed instead, which is the better failure but still a
failure -- `fleet.py` would have stopped rendering.

**The fix is the correct name, and a check that the name resolves**, because
the whole hazard is that a wrong name is silent. `selftest.d/55-localtime.sh`
asks the two questions a silent UTC fallback cannot fake:

- the offset is not `+0000`;
- the abbreviation *changes with the season* -- `PDT` at 2026-07-01, `PST` at
  2026-01-01. A bad name answers `Pacific` for both. A host with no tzdata
  answers `UTC` for both.

`localtime.sh` also probes `$TZDIR/$HAKUX_TZ` at source time and, if the zone
is missing, prints **honest UTC** rather than a mislabelled fallback.

## 2. The host is already `America/Los_Angeles`, not UTC

The brief says "the host is UTC-configured". It is not, as of 2026-09-19:

```
$ readlink -f /etc/localtime
/usr/share/zoneinfo/America/Los_Angeles
$ date +'%F %H:%M %Z %z'
2026-09-19 06:37 PDT -0700
```

`timedatectl` is not in this session's permitted command set, so it was not
run; `/etc/localtime` is the file `timedatectl` reports, and `date`'s own
`%Z %z` corroborates it independently. A third corroboration was already in
the tree: `nightly_build.sh`'s header has said `00:30 America/Los_Angeles`
since it was written.

Two consequences:

- **`nightly_build.sh` was already local and never said so.** Its `DAY` and
  its `say()` used bare `date`, which follows the host. The defect there was
  not the zone, it was that `00:31:12` carried no label on a page where
  everything else printed `Z`, so a reader applied the seven-hour correction
  to a number that had already had it applied.
- **The timers are already right and are untouched**, as the brief requires.
  No `.timer` in the tree carries a `Timezone=` line, so all of them follow
  the host. `docs/testing/systemd/hakux-nightly.timer` and
  `docs/systemd/hakux-nightly.timer` are both `OnCalendar=*-*-* 00:30:00`,
  which is **00:30 Pacific**, which is the same 00:30 `nightly_build.sh`'s
  header names. They now agree in writing as well as in fact.

## 3. A data site the brief does not name, which following it would have broken

The brief lists `summarise_run.py` under "convert these", alongside
`fleet.py`, as a consumer of the Python helper. It is not a display site. Its
`ts` is **column 1 of `$WORK/logs/<job>/index.tsv`**, and `status.sh` selects
the page's 24-hour window from it:

```sh
cut=$(since_iso)                                   # UTC, from `date -u`
rows=$(awk -F'\t' -v c="$cut" '$1 >= c' "$WORK/logs/lane/index.tsv" | tail -12)
```

That is the *same* lexical-string hazard as the arms watermark the brief
correctly protects, one file over. Writing local time into `ts` would have
shifted every row seven hours against an unchanged cutoff -- rows silently
missing from the status page -- and on the November fall-back, where
01:00-02:00 occurs twice, two distinct instants would compare in the wrong
order.

So `ts` stays UTC, with the reasoning written at the site, and **the
conversion happens where `status.sh` prints the column**. That is the general
rule this lane settled on and it is worth stating plainly for the next lane:

> Convert at the point of printing, never at the point of storing. A stored
> field is somebody's sort key.

---

## What moved and what did not

**Display (now `America/Los_Angeles`, always with the zone shown):**

| site | was | is |
|---|---|---|
| `say()` in `arms/board/cloud/fold/handback.sh` | `2026-09-19T13:32:07Z` | `2026-09-19 06:32:07 PDT` |
| `nightly_build.sh` `say()` and `DAY` | `13:32:07` (local, unlabelled) | `2026-09-19 06:32:07 PDT` |
| `status.sh` `_Rewritten_` line | `13:32 UTC` | `06:32 PDT` + "every time on this page is PDT" |
| `status.sh` lane table | header `when (UTC)`, cell `09-19T13:32` | header `when (PDT)`, cell `09-18 18:10` |
| `status.sh` cloud-comment list, board/cloud TSV tails | raw UTC from the API / the file | converted at print |
| `arms.sh` verdict comment, `judged` row | `date -u` | `say_time_s` |
| `handback.sh` "Handed back" heading | `date -u` | `say_time_s` |
| `cloud.sh` audit filename `docs/audits/<date>-...` | `date -u +%F` | `local_day` |
| `fleet.py` | *(no absolute time at all)* | one `generated <time> PDT` header line |

`cloud.sh`'s audit filename is worth a word: with a Pacific host, `date -u +%F`
past 17:00 local already names **tomorrow**, so an audit written on Tuesday
evening was filed under Wednesday. Date-only names are DST-safe to sort on --
the fall-back repeats an hour, never a day -- so this one is safe to move and
was wrong before.

`fleet.py` had nothing to convert: every figure it prints is a relative
duration (`4.2h`), which needs no zone. It also never said what "4.2h ago" was
counted back *from*, so a report pasted into an issue an hour later read as
current. One absolute line fixes that and gives the Python helper its
consumer.

**Data (stays UTC, each with a comment at the site saying why):**

| site | why |
|---|---|
| `arms.sh` watermark seed and `\<` comparison | lexical compare against `registered_utc`; untouched, as the brief requires |
| `arms.sh` `queued_utc` | tie-breaks two registrations with equal timestamps -- another lexical compare |
| `arms.sh` `told=` | a stamp in a host state file; `grep -q '^told='` probes it, never compares the value |
| `summarise_run.py` `ts` | §3 above |
| `status.sh` `since_iso` | handed to the GitHub API, which specifies UTC; also the cutoff in §3 |
| `status.sh` `now=$(date +%s)` | epoch, zone-free, only ever subtracted |
| `fold.sh` handback `at=` | recorded field; `handback.sh` reads only `files=` from that file |
| `board.sh`, `cloud.sh` log/brief filenames | `%Y%m%dT%H%M%SZ` names sort; a local name jumbles across the fall-back |
| `docs/testing/predictions/**` `registered_utc` | provenance bound into a measurement, committed history. **Not touched.** |
| result ids | epoch-prefixed, already zone-free. **Not touched.** |

`nightly_build.sh`'s `SINCE=$(date -d 'yesterday 00:30' -Iseconds)` is a third
category: deliberately **local**, and already was. It has to line up with the
timer that started the run, and that timer fires at 00:30 local. Making it UTC
would have shifted the commit window seven hours off the boundary it names.
`-Iseconds` emits the offset, so the line `say()` prints is unambiguous without
going through the helper.

## The helper

`docs/testing/jobs/localtime.sh` -- `say_time`, `say_time_s`, `local_ts`,
`local_hm`, `local_day`, `tz_abbr`. Sourced beside `gh-label.sh`, which is the
idiom the five job scripts already use.

`docs/testing/jobs/localtime.py` -- `say_time`, `local_ts`, `tz`, `ZONE`.

**The zone name is written in exactly one line, and Python parses it out of
the shell file** rather than repeating it. A repeated constant is a constant
that drifts, and the drift here would present as two timestamps on one status
page disagreeing by seven hours -- precisely the confusion this lane exists to
remove. `55-localtime.sh` asserts the two halves report the same `ZONE` *and*
render one fixed instant identically.

## How the new checks were falsified

The gate requires that a new check fail against the code it replaces. Run
against `origin/master`'s files (see the PR for the transcript):

- **`arms.sh` tick-log stamp** -- the old `say()` writes
  `2026-09-19T13:32:07Z ...`. The positive check (`... PDT `) does not match;
  the negative check (no `...Z ` stamp) matches and so fails. 2 reds.
- **`status.sh` lane table** -- the old code slices `${ts:5:11}`, producing
  `09-19T01:10`. The check wants `09-18 18:10`. 1 red.
- **`status.sh` header and column head** -- old text is `13:32 UTC` and
  `| when (UTC) |`. 3 reds.
- **`board/cloud/fold/handback/nightly_build` `say()`** -- the grep is anchored
  on `$(say_time_s)` inside the `say()` body, not on any word in the
  surrounding comments, so a file that merely *mentions* the helper does not
  pass. 5 reds.
- **the zone-name checks** -- set `HAKUX_TZ=Pacific/Los_Angeles` (the brief's
  literal) and the summer/winter abbreviations both read `Pacific`, the offset
  reads `+0000`, and the sh/py renderings disagree (`13:32 Pacific` vs
  `13:32 UTC`). 5 reds.

Fifteen reds across five distinct causes, not one cause counted fifteen times.

The **data-site** checks are guards rather than falsifiers: they are green
today and exist to go red when a later lane "finishes the job". Each was
confirmed to trip by mutating its target in a scratch copy -- converting
`summarise_run.py`'s `ts` to local makes the hour check fail by seven.

## 4. `fleet.py` is run from a copy of itself, so its imports must be optional

Found by CI, not by reasoning, and worth writing down because nothing in
`fleet.py` says it.

The first CI run on this branch failed with **ten** red checks, all in
`selftest.d/93-backlog-state.sh`, none of them about timezones:

```
FAIL fleet calls exactly the available row dispatchable
FAIL ...and it is #2, by its structured field and not by its prose
FAIL nothing is unclassified on a fully classified board
...
selftest: 330 passed, 10 failed
```

`93-backlog-state.sh` builds a board fixture by copying **exactly three
files** — `check_coverage.py`, `fleet.py`, `board_files.py` — into a scratch
directory and running `fleet.py` there. There is no `jobs/` beside it. So the
`from localtime import say_time` I added raised `ModuleNotFoundError`, and
`fleet.py` died before its first `print`. Ten checks that assert on output
words all went red at once for a reason that had nothing to do with what they
test.

`board_files.py` is copied alongside *precisely because* `fleet.py` imports
it — that is the existing convention, and it is invisible unless you go
looking. **Anything `fleet.py` imports must either be one of those three
files or be optional.**

The fix guards the import and degrades to UTC, **labelled UTC**:

```
fleet.py in its own tree : fleet report generated 2026-09-19 07:04 PDT
fleet.py in a bare copy  : fleet report generated 2026-09-19 14:04 UTC
pre-fix, in a bare copy  : ModuleNotFoundError: No module named 'localtime'
```

A fallback that printed `PDT` while running on UTC would have been the exact
defect §1 is about, reintroduced by the fix for it. `jobs/` also goes *after*
`HERE` on `sys.path` rather than before it — it is a supplement to that
directory, not a shadow of it.

`55-localtime.sh` now reproduces the bare-copy layout, so the next lane to add
an import to `fleet.py` learns it from its own fragment instead of from a
CI run on somebody else's checks. Confirmed to discriminate: the pre-fix file
in that layout raises and prints no generated-at line.

## For the next lane

- The rule is *convert at the point of printing*. If you find a `date -u` and
  want to change it, first ask what reads the field. If anything sorts it,
  compares it as a string, or hands it to an API, it stays.
- Every data site now carries a comment saying why. If you are about to delete
  one of those comments, that is the signal to stop.
- `docs/testing/jobs/selftest.d/60-status.sh` (not this lane's, not changed
  here) hardcodes fixture rows dated `2026-09-19T01:00:00Z` and relies on them
  falling inside `status.sh`'s 24-hour window. **That check expires on
  2026-09-20** and will start failing for a reason unrelated to whatever
  changed. This lane's own fragment dates its fixture relative to `now` for
  exactly that reason. Worth a one-line fix by whoever next touches that file.
- `timedatectl` was not runnable in this session's permission set. If the host
  zone is ever in question, `readlink -f /etc/localtime` answers the same
  question and is permitted.
- Before adding an `import` to `docs/testing/fleet.py`, `check_coverage.py` or
  `board_files.py`, read §4. Those three travel together into a scratch
  directory and nothing else goes with them.
- A full `selftest.sh` run takes roughly 40 minutes on this box — each
  fragment that drives an `arms.sh` tick walks all 116 committed predictions,
  several times over. CI's `timeout-minutes: 15` holds because a clean runner
  is faster, but it is not a large margin. If you are iterating on one
  fragment, source it alone against a minimal fixture (`$HERE`, `$T`,
  `$HAKUX_WORK`, `ok`/`bad`/`check`) rather than paying for the whole run;
  that turned a 40-minute loop into a 3-second one here.
