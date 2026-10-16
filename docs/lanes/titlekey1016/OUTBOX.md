# OUTBOX: lane.titlekey1016 -> lane.local

NEED: `lane/statusfix1016`'s fold has not landed on `origin/master` as of this
session (`git -C /home/justin/hakuX log --oneline origin/master -5` still
shows `15a72e10dc` -- titledb1014 -- as the tip; no `fold: lane/statusfix1016`
commit). The brief's "Order of work" says not to edit
`docs/testing/jobs/status_html.py` until that fold lands (it currently holds
that file), and to write this line rather than proceed. Everything else in
scope (items 1, 3, 4, the compat_page.py name-keyed join, the drift-check
selftest and mutant proof) is done and in this PR; `status_html.py`'s
`titles05` / `canon` / `resolve` / ledger-load name-keyed structures (the
largest piece of item 2) are the one remaining site, left name-keyed for now.

Ask: when `lane/statusfix1016` folds, move `status_html.py`'s territory row
to a lane that rebases `lane/titlekey1016` on the new master and converts
`titles05`'s `names`/`where`/`tid_of` (keyed by display name today) to
title_id keys, per `docs/lanes/titlekey1016/NOTES.md`'s "Blocked" section.
That can be a resumed titlekey1016 session or a fresh one; either way it
needs this lane's `Catalog`/`name_drift` fix already on master first, so its
own selftest fixtures can use the one real name per title_id this lane
established.
