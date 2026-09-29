# Audit pass 2: PR #595, lane/battadmit-2 (#507)

Head verified: `d51585f2ca`. That is the pass-1 file on top of `72aaffc916`,
the head pass 1 audited. No remediation commit landed between the passes. CI
on this head: build x2 and selftest (0-3) green. The PR is MERGEABLE against
`origin/master`, which is 23 commits ahead.

**Verdict: clean for fold.** Pass 1 found no HIGH and no MEDIUM, so no
blocking scenario needed to be closed. L1-L3 are still open as LOWs, with the
same scenarios. None of them justifies remediation, and they are carried
below so they are not lost.

## Pass-1 "holds" re-checked at this head

- **Fail closed before the claim.** `serve_one` calls
  `battery_admit "$req" "$id" || return 1` at `dispatcher.sh:749`, before
  `mv "$req" "$D/running/$id.req"` at `:752`. An unreadable level therefore
  leaves the request in `queue/`.
- **Empty level not cached.** `battery_level` returns before it writes
  `$f` when `$l` is empty (`[ -n "$l" ] || return 0`), so the next walk does
  read again.
- **Per-walk flag survives across requests.** `serve_queue` resets
  `BATT_WALK_UNREAD` and runs in the worker's shell (`dispatcher.sh:1753`,
  `serve_queue "${reqs[@]}" && served=1`, not inside `$(...)`), so a walk
  makes one dumpsys read.
- **Other drivers.** `51-dispatch-hardening.sh:154` exports
  `BATTERY_ADMIT=off`, and `battery_admit` returns 0 on it first
  (`:689`).
- **Floor.** `floor_for(label)` feeds both `need` and the recorded
  `floor=` in `battery.json`. `BATTERY_FLOOR_<label>` overrides it, and a
  malformed value raises inside `check`, which exits 2 (admit unchecked,
  logged).

## Pass-1 LOWs: status

| # | Scenario | Still occurs? | Disposition |
|---|---|---|---|
| L1 | One `ee317437 ... terminated` line falls in two runs' `[t0-60, t1+120]` windows and counts once for each. A line with no `MM-DD HH:MM:SS` prefix makes `m` None and raises at `m.group` (`link_floor.py:14-15`, `:42`). | Yes, the code is unchanged | LOW, carried. This is analysis only, not the gate. The floor of 30 is overridable per device. |
| L2 | A multi-hour unreadable episode logs one line and nothing more, and `status` shows `device: present`. | Yes | LOW, carried. It is an observability gap. The worker still refuses correctly. |
| L3 | A level cached within `BATTERY_CACHE_S` (60 s) admits after the link has died. | Yes. This predates the diff. | LOW, carried. Bounded to 60 s. The run then fails in `device_present`/install as it did before. |

A LOW does not send a PR to remediation, and none of these three is a
correctness defect in the gate this PR adds. The three fixes are small and
independent, and they suit a follow-up PR on `lane/battadmit-3`.

## Next state

`needs-audit-2` → `fold-ready`.
