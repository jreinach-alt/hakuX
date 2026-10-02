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

## #433 -- 2026-10-02 11:20 PDT

[lane.issuerecon] Final coverage of `~/hakux-work/forge-import/` (rebuilt 11:15 PDT; replaces the 10:30 set, same layout):

| | count |
|---|---:|
| numbers 1..629 (195 issues, 434 PRs) | 629 |
| fully / partly / not recovered | 336 / 290 / 3 (#1, #161, #568: only their state, and #568's labels, were seen) |
| title / complete body / state / labels | 626 / 490 / 598 / 530 |
| comment ids seen | 2,621 |
| ... with full text / truncated only / no text | 2,180 / 16 / 425 |
| comments with text but no id | 459 |

- The final set has fewer bodies than the first (490, against 502) because two sources of mis-attributed titles were removed. No text in it is paraphrased. A missing text is absent and counted.
- The 425 ids with no text are mostly links to comments that were never read on this machine, and job posts whose text lived only in the job.
- Highest GitHub number: #629, so local-only issues can start at #630. #629 was created 45 minutes before the suspension, and a #630 from that window would leave no trace here.
- Secret scan: 1 redaction (#445 body, a console FTP login pair). The other hits were reviewed one by one and none is a credential.
- To rebuild: `python3 docs/lanes/issuerecon/recon.py scan && python3 docs/lanes/issuerecon/recon.py finalize` (about 30 s).
