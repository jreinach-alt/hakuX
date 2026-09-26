# lane.statuspage: #107 in Pacific time, and a lane table that knows every lane

Brief: `briefs/statuspage.md` (owner, 2026-09-26). PR #349. Base `ff14a4580c`.

## 1. Every UTC site in the two scripts, and what happened to it

Grepped `status.sh` and `board-status.sh` at the base sha for `date -u`, `UTC`
and `%FT%TZ`, plus every place a stored UTC value is echoed.

| site (base line) | what it is | now |
|---|---|---|
| status.sh:56 `since_iso()` | `since=` for the API and the `$1 >= c` cut over index.tsv | **kept, data**: string comparison against UTC column 1 |
| status.sh:90 `due=` | "Next roll-up due by" in the comment and the body | **converted**, `local_ts "@epoch"` |
| status.sh:117 lapse line (comment) | previous tick / this tick | **converted**, `local_ts` / `say_time` |
| status.sh:160-165 window budget | `$WINDOW_WHY`, `$WINDOW_FACTS` carry `2026-09-21T00:00Z`-style instants | **converted at print** by `local_instants()`; window.sh's variables and comparisons are untouched |
| status.sh:168 limits.tsv tail | refusal records, columns 1 and 3 UTC | **converted at print**, same helper; the file is not rewritten |
| status.sh:286 arms watermark | `$WORK/arms/since` | **shown local, stored value quoted beside it**: arms.sh compares the file to registered_utc as a string |
| status.sh:337 timers line | printed `$1 $2`, which is the weekday and date, never the time | **fixed** to the time and zone systemctl prints (the host's zone, PDT) |
| status.sh:386 body "Written" | first line GitHub shows | **converted**, `say_time` |
| status.sh:392 lapse line (body) | previous tick | **converted**, `local_ts` |
| status.sh:414 title | `HH:MMZ+` | **converted** to `HH:MM PDT+`; the quantum is still epoch-aligned, so the only extra rename is the first tick after this lands |
| status.sh new lane table | index.tsv times, comment `created_at`, `retired_utc`, digest stamp | **converted at print** via `localtime.py`; the `since=` it sends is UTC |
| status.sh arms refusals (`told=...Z`) and job-error greps | a file's or a log's content quoted verbatim | **kept, data**: these are dumps of files other scripts parse |
| board-status.sh:64 arms watermark | as status.sh:286 | **shown local, stored value beside it** |
| board-status.sh:32 index.tsv tail | column 1 UTC | **converted at print** (`local_hm`) |
| board-status.sh:73 `since=` | the API query | **kept, data** |
| board-status.sh:74 `.created_at` | printed per comment | **converted at print** |

`localtime.sh`'s header, which explains the split between display and data, is
unchanged.

## 2. The lane table

`### Lanes: every row on the board` sits under the running-units table (kept:
three selftest fragments assert its heading). Source: `territory.toml` and
`nv2a_issues.toml` on `origin/board` via `git -C $REPO show`, since master's
copy lags the fold. A fixture can point `STATUS_BOARD_DIR` at a directory
instead.

State, first match wins:

1. `running`: a `hakux-lane-<name>` unit is active.
2. `waiting on device`: a queued or running `.req` whose requester is `<name>`,
   `lane.<name>`, `lane-<name>` or `arms-<name>-*`, the shapes seen in
   `$DISPATCH_DIR` today.
3. `blocked: decision-needed`: on one of its issues, or on its PR.
4. PR open and not draft: `fold-ready`, `PR needs remediation`, `PR needs rebase`,
   `PR in audit (1|2)`, else `PR ready, awaiting a label`.
5. `blocked: #N <blocked_on>`: only for an issue whose status is `open`.
   `blocked_on` is prose and often history (for #68 it begins "ANSWERED
   2026-09-14..."), so a fixed-part issue's text would read as a live block.
6. `folded (row not yet retired)`: the PR merged and the row is still `lane.*`.
7. `job (hakux-<name>.timer)`: `lane.arms` and `lane.fold` are jobs.
8. `standing, nothing in flight`: `standing = true`.
9. Otherwise, **IDLE, NO WORK**. These rows sort first, are named in a
   `[!WARNING]` above the table, and are written to `$S/idle-lanes`, which the
   issue body prints as `**Idle with no work:** ...`.

A running unit with no territory row gets its own row, and so do rows retired
in the last 24 h (newest 16, the rest counted). That keeps turnipfork and
perfbase visible for a day after they retire.

lane.xbox and lane.remote are not table rows. Each gets a line:

- xbox: last comment containing `[lane.xbox]` that is not a `[job.` or
  `[host]` comment, and whether a host answer came after it; queued or running
  requests whose id contains `xbox`; the console meter.
- remote: the same, but the body must contain the backticked marker. A
  `[job.deliver] lane.remote` delivery also contains that marker, which is why
  `[job.` comments are excluded. An answer means the same thing as in
  `host-tools/attention.sh` section 2.
- The comments come from one paginated `since=` query covering 48 h.

The console meter is `host-tools/kasa_console.py status --no-find`, keeping
only the text after the last `: ` (`ON, 66.1 W`). It runs under
`timeout 75` (the tool waits up to 60 s for its lock). Its answer is cached in
`$S/console-meter` for 60 s: every job tick ends in status.sh, and the plug
must not be read more than once a minute. If the tool is absent, the line reads
`console meter: not available`.

Host ops: the last `=== <stamp>.json` block of `$WORK/logs/hostops/digest.log`,
with its stamp and first non-blank line. If the file is absent, the line says
so.

## Measured

`status.sh --print` on the host, 2026-09-25 21:15 PDT (quoted in the PR). Three
lanes were flagged idle with no work: blankrule297, sweepcover and titlerun, all
with draft PRs. perfarch showed as `PR in audit (1)` on #308, and turnipfork as
`retired 09-25 17:35`. The xbox line showed ON, 66.1 W.

Don't run `--print` on the host and then read `$WORK/status/STATUS.md`. It
writes to the live path, and a real tick landing between the write and the
`cat` replaced my first proof with master's page. Capture `--print`'s stdout
instead.

## Not done here

- `board-status.sh`'s "what the board changed" asks for one page with `since=`
  and prints its `tail -5`, which are the oldest five on that page, not the
  newest. This was already the case before this lane and is left alone.
- The arms-refusal list prints a refusal file whole, so its `told=` line breaks
  the Markdown list item. This was also already the case.
