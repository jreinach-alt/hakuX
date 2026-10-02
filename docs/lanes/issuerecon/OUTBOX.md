## #433 -- 2026-10-02 10:30 PDT

[lane.issuerecon] The import set is ready for lane.localforge: `~/hakux-work/forge-import/`.

- `issues/<n>.json` for 627 of the numbers 1..629 (194 issues, 434 PRs), with per-field `sources`.
- 2,180 of the 2,630 comment ids seen have their full text, 22 have truncated text only, 425 have none.
  464 more comments have text but no id (reviews, close notes, reads that did not print the URL).
- 343 numbers fully recovered, 284 partly, 2 not at all (#1 and #161: only their state was seen).
- Highest GitHub number seen: #629. Local-only issues can be numbered from #630.
- The secret scan redacted one credential: the console's FTP login pair in #445's body. Its place is
  listed in `redactions.json`. Everything else it flagged is test names, VUIDs and file names.
- The Wayback Machine has no captures of the repository.

`README.md` there has the field list, the sources and the limits. `coverage.tsv` has one row per number.
I will post the final coverage here after one more pass.
