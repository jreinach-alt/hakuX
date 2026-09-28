# Audit pass 1: PR #587, lane.battadmit (#507)

Head audited: `0601357327`. Diff against base `49c8067d24`: `dispatcher.sh`,
`battery_admit.py`, `selftest.d/99-battery-admit.sh`, `docs/lanes/battadmit/NOTES.md`.

**Verdict: needs remediation.** There are two MEDIUMs and two LOWs, and no HIGH.

The admission rule, the learning, the reservation clock and the wiring into
`serve_queue`/`serve_one` all do what the PR body says. The selftest sources
the real functions, not copies. I ran the helper read-only over the live
`dispatch/results` (1840 finished results). None raised, and it learned the
figures the body quotes: nova soak 32.37 %/h n=10 with 15.3 s overhead, thor
soak 22.53 %/h n=10 with 24.0 s. Both defects below are latent: nothing in
today's history triggers them. Each one fails closed and silently.

## MEDIUM

### M1. A helper exception reads as "does not fit", not as "helper failed"

`battery_admit.py` has no top-level handler. An uncaught Python exception exits
with status **1**, which is the helper's "does not fit" code. The shell's `*)`
branch in `battery_admit()` exists to admit unchecked when the helper fails,
but an exception never reaches it. It only catches exit 2 (usage) and signals.

Failure scenarios, both reproduced with the PR's helper:

- A request with `"seconds": "90s"` exits 1 with `ValueError` on stderr and
  nothing on stdout. The dispatcher logs an empty `BATTERY:`-less line once
  (`line` is empty) and skips the request on every tick. That request also
  becomes the tick's `BATT_HEAD`, so the rest of the queue runs as its
  "backfill".
- `learn()` walks every result of the device and kind. On the pgraph path it
  walks all of them, because test discs never yield a rate. So one result
  that makes `run_record` raise refuses **every** request of that kind on that
  device, with no diagnostic line. Example: a pre-change disc result holding a
  dangling symlink, where `getmtime` in the `listdir` fallback raises
  `FileNotFoundError`. Reproduced: a `runs:1, seconds:60` request at level 95
  exits 1 with empty stdout.

Fix: wrap `main` in a try/except that prints a one-line reason and exits with
a code the `*)` branch handles (2, say). Add a selftest case with a malformed
request, or with a history result that raises, and assert that it is admitted
unchecked with the "exited" line.

### M2. No ceiling on `need`: a head that can never fit reserves the device forever

`need = 20 + rate x runs x (seconds + overhead) / 3600` has no upper bound.
Once a head has been refused for `HEAD_WAIT_S`, every request behind it gets
exit 3. If the head's need is above the highest level the device reaches, the
handheld serves nothing until someone cancels the head. The only sign is the
`hold for head` log line.

The ceiling is 100, or lower on a device that stops charging at its limit (the
NOTES say the Thor holds 77-85 %). On today's learned nova soak rate, a
soak over about 2.47 h needs more than 100. For a disc at the 10.5 %/h
fallback with the learned 593 s per-run overhead, `--runs` 43 needs more
than 100. Neither happens today: the largest need in the 1840 historical
requests is 39.0 % (`--runs 10` discs). Nothing rejects either request,
though, and the pre-change dispatcher served both at 80 %+.

Fix, one of:

- Clamp `need` to a reachable ceiling (for example `BATTERY_CEILING`, default
  95) and admit at the ceiling.
- Or exempt a head whose need exceeds the ceiling from reserving the device,
  and log that it can never fit.

Add a selftest case: a head whose need is over the ceiling, past
`HEAD_WAIT_S`. Either the head or the short request behind it must be claimed.

## LOW

### L1. The hold line is logged every tick

The dedupe key strips `; head, refused*`, which covers the head's refusal
line. The exit-3 line `hold for head A (refused for Ns >= 1800s): not
backfilling B ...` carries its own running clock in a different shape, so its
key changes each second. While the device charges, every held request is
logged every 5 s, which is about 720 lines/h per request, for the hours a
500 mA port takes. The comment above `battery_admit` promises the opposite.
Fix: key on the line with the `(refused for ...)` clause removed.

### L2. The pgraph rate lookup scans the whole results tree

Test discs write no `thermal.jsonl`, so `history()` never fills `rates` for
pgraph. It reads every finished result, 1840 today, about 0.5 s, once per
`RATES_TTL_S` per label. The cost grows with the tree and buys nothing until
discs record capacity. Stop at `HISTORY` overheads when the kind has no
rate source, or bound the walk.

## Not findings

- The host-side `device_reality.sh` lift change (80 → 20) is out of this diff
  and is correctly routed to lane.local in the body. Until it lands, the
  per-run check only ever sees levels ≥ 80 on the Nova.
- `runs` is used for soaks, but `request.sh` refuses `--runs` on a soak, so
  it is 1 there.
