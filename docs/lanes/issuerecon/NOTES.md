# lane.issuerecon: the GitHub issue log, rebuilt from what survives locally

Brief: `~/hakux-work/briefs/issuerecon.md` (owner 2026-10-02 ~09:55 PDT). Output goes to
`~/hakux-work/forge-import/` (outside the repo: it holds the owner's and agents' words). Only the
tooling is committed here.

## Run it

    python3 docs/lanes/issuerecon/recon.py scan        # ~25 s: transcripts -> scratch/events.jsonl, seen.json
    python3 docs/lanes/issuerecon/recon.py finalize    # events + board + git -> forge-import/, secret scan, README

`finalize` stops with a list if the secret scan finds a hit nobody has judged. Judge each one from the
masked context it prints (the value is never printed); add the key of a hit that is not a secret to
`secretscan-allow.json`. Hits of a redacting kind are replaced in place and listed in `redactions.json`.

## Files

- `recon.py`: the scan. One pass over every transcript (8 workers). Per transcript it tracks the files
  the session wrote (Write tool, Edit tool, heredocs, `printf/echo > f`) so a `--body-file` can be
  resolved to the text that was posted. Readers: JSON (gh `--json`, `gh api`), jq templates, `.body`
  single-field reads, `gh issue|pr list` tables. Posters: `gh issue|pr comment|create|edit|close|review`,
  `gh api -X POST|PATCH`, `deliver.sh send` (whose fixed wrapper text is unchanged since c43bdfb666).
- `jqtmpl.py`: compiles a `--jq` program whose last stage is a string template or a `+` concatenation of
  simple paths into a regex for one output record. Anything else returns None.
- `recon_build.py`: merges per number; README text; coverage.
- `secretscan.py`: the scan over the output.

## What was measured (2026-10-02, final set)

| | first set (10:30) | final set |
|---|---:|---:|
| transcripts read | 2,198 | 2,197 (this lane's own excluded) |
| numbers 1..629 | 629 | 629 |
| fully / partly / not recovered | 343 / 284 / 2 | 336 / 290 / 3 |
| title / complete body / state / labels | 627 / 502 / 605 / 440 | 626 / 490 / 598 / 530 |
| comment ids seen anywhere | 2,630 | 2,621 |
| ... with full text / truncated only / no text | 2,180 / 22 / 425 | 2,180 / 16 / 425 |
| comments without an id | 464 | 459 |

The final set has fewer bodies and states than the first because it is stricter. JSON with no URL
is now taken only from a command whose sole output is gh's. A command that also printed a game
list as JSON (`{"number": 442, "title": "25 to Life"}`) had retitled #442. A `for n in ...; do gh pr view $n`
loop beside `gh pr view 504` had given #504 three other PRs' titles. Labels went up: list templates
such as `"#\(.number) \(.state) [\([.labels[].name]|join(","))] \(.title)"` are now read for state
and labels too.

Wayback Machine CDX (`url=github.com/jreinach-alt/*`): answered 200 with zero captures on 2026-10-02
~10:20 PDT. Nothing to gain there.

Highest number seen: #629 (created 2026-09-30 03:16 UTC, about 45 min before the suspension). A #630
created in that last window would leave no trace here.

## How the parsers were checked

Where one comment id had text from two independent paths (a posting call and a later read), the texts
must agree. Each disagreement was a parser bug until shown otherwise; the ones fixed:

- a `| grep -v` after a loop's `done` removed a line from every body read in the loop (pipes after
  `done` now count);
- `head -2` on a body: the tool output drops trailing blank lines, so "fewer lines than the head" was
  wrong; now 4 lines of margin;
- two reads in one command, with templates differing only in `.body[:80]` vs `[:100]`, scanned each
  other's output; now records are exact only when no other template in the command shares the header;
- `T=$(say_time)` was read as `T=""`; a substitution is now an unknown value;
- an unquoted heredoc's `$(date ...)` was copied literally; now expanded from the transcript clock, or
  the file is unknown;
- `cat >> file <<EOF` was treated as an overwrite;
- a comment URL printed by an unrelated script (`harness_health.py`) was paired with a post whose own
  output went to `/dev/null`; a post's URL must now start its line;
- a jq-read comment object was taken for the issue (#433's body became a comment's text);
- a review template `TS + state + body` matched `gh api .../events` lines (weak header, shared output);
  weak headers are now used only when the read is the command's only output.

After the fixes: 90 agree, 3 differ, and each of the 3 is a later read of a comment edited after
posting (the later text wins).

## Not recoverable here

- #272-#297 and other issues whose creation is in no local transcript: they were filed from a session that
  did not run on this machine (cloud). Their titles come from reads and the board; their bodies were never
  read here.
- Posts whose body file was edited by python (`s.replace(old, new)` in a heredoc script) before posting:
  about 30. Replaying such scripts with `ast` (literal old/new, one file) is the one parser extension
  left that would recover agent text; it was not done.

## What the next lane should not repeat

- Do not try to recover more from `gh` text output (`gh issue view` without `--json`): agents almost
  never used it; 0 transcripts have it.
- The 425 ids with no text: about half appear only as links inside other comments or in other tools'
  output (status pages, harness_health). The comment itself was never read on this machine. The rest are
  posts whose body file was changed by `sed -i` or python before posting (dropped, not guessed) and job
  posts (`[job.fold]`, `[job.board]`) whose text only lived in the job's process.
- Do not paraphrase a missing text from the board notes or NOTES files. The brief forbids it, and the
  import marks absence explicitly.
