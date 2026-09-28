# lane.escitems: "What needs a person?" reads escalations as items

Base: master @ 59abda3c9b. No device, no arm, no prediction.

## Defect

`status_html.py` read `host-tools/escalations.md` one line at a time and dropped
only a line containing RESOLVED. Hostops and lane.local write UPDATE, RESOLVED
and (now) `re-checked` notes on indented continuation lines under the item's
`- ` line, so:

- an item resolved on a continuation line stayed on the page (the 10:36 PDT
  Nova item and the 11:51 PDT Thor-overlay item, 09-27, until lane.local
  hand-marked their first lines at 17:06);
- every continuation line that did not say RESOLVED was listed as an ask of
  its own (UPDATE lines, and every `re-checked` stamp hostops is to append each
  tick would have been one more "owner decision").

`recovery/needs-hands.txt` had the same line-at-a-time reader. The live file has
no indented lines today, but the same shape of note would hit it, so it groups
the same way.

## Change

- `_items(text, opens)`: an opening line plus the indented lines under it is
  one item. For escalations.md any unindented, non-blank, non-`#` line opens
  one: a `- ` bullet, or the older unbulleted `OWNER ONLY, do not act
  (meta): text` line. The first cut opened items on `- ` only, as the brief and
  `harness_health.py` do, and the selftest's 16:24 fixture (65, dash432)
  lost all six of its owner decisions, which are written in the unbulleted
  format. So `harness_health.py` does not count an unbulleted item as open.
  Its escalation check is blind to that format; that file is outside this
  lane's scope, and the live file uses bullets only today.
- `escalation_items(text, now)`: skips any item with RESOLVED on any line;
  shows its first line as before; reads the newest `re-checked [MM-DD ]HH:MM
  [ZONE]` among its lines (no date = today in the display zone, a time more
  than 5 min in the future = yesterday's). The item is `unverified` when
  neither its opening stamp nor a re-check is within 2 h; the page shows
  "Re-checked HH:MM (N min ago)" or "UNVERIFIED: no re-check in the last 2 h"
  after the item (the existing `detail` slot). Unverified items are shown, not
  dropped. An item's opening stamp counts as a check so a new item is not
  unverified in its first 2 h.
- The opening stamp is now also read when it leads the line
  (`- 09-27 10:36 PDT (hostops) ...`), which is the format hostops writes;
  before, only `(meta): text` lines got an `at`.
- `_needs_hands` groups with `_items` (any non-blank unindented line opens).

## Measured

| input | master reader | this branch |
|---|---|---|
| live escalations.md (17:06 stopgap applied) | 0 | 0 |
| `escalations.md.bak-20260927-resolve` (before the stopgap) | 2: the 10:36 Nova and 11:51 Thor items, both resolved on continuation lines | 0 |
| selftest fixture escalations (3 open items) | 9 (includes the resolved alpha item, 2 UPDATE lines, 3 re-checked lines) | 3 |
| selftest fixture needs-hands (1 open ask) | 2 (includes foxtrot, resolved below) | 1 |

Selftest `99-status-escalation-items.sh`: legs (a) resolved-on-continuation,
(b) UPDATE is not its own item, (e) needs-hands resolved-on-continuation fail
on master's reader per the table above; (c) re-checked 30 min ago shows the
time and is not unverified; (d) unchecked 3 h is listed and marked UNVERIFIED;
(f) an unbulleted `OWNER ONLY` line is still an item (fails on a bullet-only
opener, which is what broke fragment 65).

## For the next lane

- Do not key anything on a single line of escalations.md: the file's unit is
  the item. If hostops changes the note format, change `_items`, not a regex
  per caller.
- The 2 h rule counts the opening stamp as a check. If the owner wants a new
  item flagged until its first re-check, drop `at` from `fresh` in
  `escalation_items`.
