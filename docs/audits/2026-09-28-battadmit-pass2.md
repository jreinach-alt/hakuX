# Audit pass 2: PR #587, lane.battadmit (#507)

Head verified: `90b763499f` (remediation of pass 1 at `0601357327`).

**Verdict: clean.** None of the four pass-1 scenarios can occur any more. I
reproduced each one against the remediated helper, and the selftest fragment
passes, mutants included. Nothing new was found.

## M1. A helper exception read as "does not fit": closed

`main` is now wrapped. Any exception prints `battery_admit.py failed: <type>:
<msg>` as line one and exits 2, and exit 2 is handled by the dispatcher's
`*)` branch (admit unchecked, log the line). `history()` also skips a single
result whose `run_record` raises, instead of failing the whole lookup.

Reproduced on the new helper:

- `{"seconds": "90s"}` → `battery_admit.py failed: ValueError: could not
  convert string to float: '90s'`, rc 2. `{"runs": "x"}` gives rc 2 the same
  way. The request is claimed unchecked and never becomes `BATT_HEAD`.
- A disc result with no `battery.json`/`thermal.jsonl` and a dangling symlink
  (the `listdir`/`getmtime` fallback raises `FileNotFoundError`), then a
  `runs:1, seconds:60` request at level 95 → `admit ... need 21.1`, rc 0. In
  pass 1 this was rc 1 with empty stdout.

An exception type outside the `history()` tuple (`KeyError`, say) still
reaches the top-level handler, so it fails open and is logged, not refused
silently. The selftest's `helper fails` cases and the `MUTANT helper-fails (no
handler)` case cover both halves.

## M2. No ceiling on `need`: closed

`need` is `min(need, CEILING)` with `BATTERY_CEILING` defaulting to 75. That is
below the Thor's 77-85 % charge stop, so every device reaches it. The line
says `need X capped at ceiling 75`, and `battery.json` records `need_uncapped`.

Reproduced with a 4 h nova soak (uncapped need 104.7):

- Level 74: skip, rc 1, and it becomes the head. With its clock backdated
  4000 s, a short request behind it gets `hold for head`, rc 3. This is the
  reservation working as designed while the device charges.
- Level 75, with or without the backdated clock: `admit long ... need 104.7
  capped at ceiling 75`, rc 0. So the head is served, and the reservation
  ends at a level the device reaches instead of never.

The selftest's `ceiling` case (need 172.6 claimed at 80) and its mutant cover
this. The remaining consequence is the one pass 1 offered as the fix: a run
admitted at the cap may drain past the floor. That is the pre-change
behaviour (serve anything at 80 %+), and the module docstring names it.

## L1. Hold line logged every tick: closed

The dedupe key now strips both clocks: `; head, refused for Ns` at the end of
the line, and ` (refused for Ns >= Ms)` in the hold line. Two hold lines at
1801 s and 2999 s produce the same key, and so do two capped head-refusal
lines at 12 s and 999 s. The `%d` formatting of `HEAD_WAIT_S` makes the
`[0-9]*s` pattern match. The selftest's `log once` case (three walks, one
line) and its mutant cover this.

## L2. pgraph lookup scanned the whole results tree: closed

Once `HISTORY` overheads are in hand, the walk stops after `SCAN_MAX` (50)
matching results even if rates are short. Measured over the live
`dispatch/results` (1883 results), old helper versus new:

| label/kind | old | new | learned (both) |
|---|---|---|---|
| nova pgraph | 1.38 s | 0.22 s | 10.5 %/h fallback, ovh 592.8 s n=10 |
| thor pgraph | 0.46 s | 0.24 s | 5.0 %/h fallback, ovh 393.0 s n=10 |
| nova soak | 0.15 s | 0.14 s | 32.37 %/h n=10, ovh 15.3 s |
| thor soak | 0.16 s | 0.18 s | 22.53 %/h n=10, ovh 42.9 s |

The learned figures are identical, so the bound changes cost and not answers.
The glob-and-stat of every `DONE` remains O(tree). That is the cheap part and
is not a finding.

## Checks run

- `SELFTEST_ONLY=99-battery-admit selftest.sh`: 41 passed, 0 failed, with
  all 11 mutants red (the 4 new ones included).
- The reproductions above, against scratch dispatch dirs, and the read-only
  `learn` over the live results tree.
- PR CI at `90b763499f`: build green and selftest shards 1-3 green. Shard 0
  was still in progress when this was written. The PR is mergeable.
