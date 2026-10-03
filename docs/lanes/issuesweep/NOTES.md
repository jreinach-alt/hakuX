# issuesweep: recovery pass for defects recorded since GitHub went away

## What was done
- Candidates were collected from the 2026-09-30T03:30Z-onward commits on every `origin/lane/*` branch (OUTBOX.md, NOTES.md, PR.md, and related lane docs), from `pm/lanelocal-log.md`, `host-tools/hostops-inbox.md`, `host-tools/escalations.md`, and `pm/failure-intake.tsv`. That gave 148 branch candidates and 69 PM/host candidates, 217 in all.
- Each candidate was matched against the forge (`gh issue list --state all`, 679 issues at the time). 100 were already covered by an existing issue and were skipped. The rest were reviewed by hand.
- Related candidates were grouped where they shared one mechanism. The per-title failure rows in `pm/failure-intake.tsv` were grouped by class, not filed one per title.
- 67 issues were filed (#715 to #781, label `local-only`). 5 existing issues received one comment each with new evidence (#614, #656, #662, #703, #706).
- Full row-by-row table: `sweep.tsv` (same file as `~/hakux-work/pm/issuesweep.tsv`).

## Totals
| action | candidates |
|---|---|
| filed (67 issues, #715-#781) | 104 |
| commented (5 issues) | 8 |
| skipped: already on the forge | 100 |
| skipped: resolved or owner decision | 5 |
| total | 217 |

## Skipped as resolved or not a defect
- `b-opsrebuild-01`: titleroutes fold-held; retired lane, decision 10-03 07:49.
- `b-buildstamp-02`: stale nightly ExecStartPre; the nightly unit was reinstalled (10-02).
- `b-routefix1002-01`: queue.tsv not read; the overnight runner reads it now (10-02 22:15).
- `p-thor-release-gate-routing-ask`: an owner decision, not a defect.
- `p-github-account-suspended`: account status, carried by the offline forge.

## Things the next lane should know
- `scripts/gen-license.py` `fname` is still undefined on origin/master (#760), so the bug is live.
- The forge-only gaps that bypass the shim: `status.sh` force-push to github.com (#770, high priority), and the `gh pr list --search` gap (#773).
- Per-title route and perf failures are grouped by class (#728, #729, #747, #748). Look at the title ids in each issue body before acting.
- Preflight exits 0 when the coverage gate cannot reach GitHub (#720). Do not trust a preflight pass from a branch that has not run the gate.

## Not repeated
- Nothing here changes the code. No device work and no requests were queued.
