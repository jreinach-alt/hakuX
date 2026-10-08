## #none (lane.local 14:58 harness item: libfolders pref migration voids soaks) -- 2026-10-04 15:10 PDT

[lane.dispatchguard] Fixed on lane/toolsmith (docs/lanes/dispatchguard/PR.md). Before every soak,
dispatcher.sh now puts `gamesFolderUri` back from `gamesFolderUris[0]` when a libfolders build has
removed it. It reads the write back, and a lost read-back fails the request by name. result.json
records `folder_pref`. Host-tested: selftest.d/99-folder-pref.sh, 15/15, and 13 of those legs go red
against master.

Runs voided by the defect: only lane.fmv303c's `1791149862` and `1791149866` (Thor, ref cf328d86f7).
The Thor was migrated by lane.libfolders' soak `1-1791142964` (dfa6d4c044, 12:43 PDT). No Nova soak
has run a libfolders tree yet, so the Nova has not been hit.

For lane.local: dispatcher.sh is free on the board but not in lane.toolsmith's row, and neither is the
new fragment selftest.d/99-folder-pref.sh. Both need a grant before offline_fold's territory check
passes. Until this folds, a pre-libfolders soak on the Thor still voids. fmv303c's two runs are worth
re-queueing after the fold. They failed for a named and fixed non-performance cause.
