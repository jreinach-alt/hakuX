# lane.affinitybacklog (#502)

## The defect

`affinity.py` rule 3 pinned an unpinned A/B pair by hashing its prediction
basename over the pooled live handhelds. It never read the queue. On
2026-09-27, forza414's pair (`forza414-coalesce-mnm2.json`, queued 18:34Z by
the arms job) hashed to the nova. Nine `device: nova` requests (~2 h) were
queued ahead of it, and meanwhile the thor served idle-tier `z-*` sweep legs.
The pair waited 94 min until hostops re-pinned it by hand. flip474's pair
starved the same way earlier that day.

## Alternatives priced

| Shape | Race-free? | Sees the backlog? | Cost |
|---|---|---|---|
| Rule 3 as it was (hash) | yes, stateless | no | the incident |
| Claim time: each worker computes the least-loaded device for an unpinned pair | **no**. The two arms are claimed by two workers, each reading a queue the other is about to change. This is #13's read-read race again. | yes | re-opens the split the hash closed |
| Claim time: the idle worker steals a hash-pinned pair if the other device is backlogged | **no**. The same race, with one arm stolen and the other not | yes | same |
| **Enqueue time: arms.sh picks once and writes `device` into both arms (chosen)** | yes. One writer, and both requests carry the answer before either is claimable | yes, at enqueue | stale if the queue changes after enqueue; see below |

The enqueue pick is a snapshot. Work queued later with a higher priority
(`0-*`, `0-0-x-*`) can still land ahead of the pair on the chosen device. That
cost is bounded: the pick was right when it was made, and harness_health's
90-min `[devices]` wait check still catches the rest.

## What changed

- `affinity.py`:
  - `--choose <key> <before-id>` returns the pooled device with the least
    estimated work that sorts ahead of `before-id`. Ties go to the device
    rule 3 would pick, so an empty queue changes nothing. It returns "" with
    fewer than two pooled devices, so no pin is written when nothing can be
    chosen.
  - `--backlog [<before-id>]` prints the same per-device seconds for a
    reader.
  - Work is priced with request.sh's pilot-gate estimate
    (`seconds`+90 × `runs`, or 180 s when there is no `seconds`). A running
    request counts only the estimate left since its `.owner` mtime. A queued
    request counts on the device `decide()` would send it to, with notes
    suppressed. A free request counts on neither device.
  - Rule 2b: a QUEUED sibling with the same expect basename and an explicit
    `device` pins this arm. The siblings are now read in the order a request
    moves (queue/, then running/, then results/). A sibling in running/
    whose owner file is not written yet is pinned by its own `device`. Both
    changes close the mid-claim window.
  - A load pin is a preference, not a requirement. For an `arms-*` requester
    with no title and an in-pool device, an explicit `device` that has
    stopped serving falls through to the remaining rules, and a split note
    is written. Without this, an explicit pin would turn a device outage into
    a silent stall, where the hash re-routed both arms together. Both arms
    fall through identically: 2b skips a sibling's dead load pin as well.
    Every other `device` (hand soaks, `desktop`) stays absolute.
  - `main()` is refactored into `decide()`. There is one behavioural change
    outside the above: an unreadable `results/` used to print "" before
    reaching the hash, and it now falls through to the hash.
- `jobs/arms.sh` calls `--choose` with the pair's id prefix
  (`${prio:+1-}<epoch>`) and passes `--device <pick>` to request.sh for both
  arms. The tick log line gains `device=<pick>`.

## Proof

`selftest.d/99-affinity-backlog.sh`, against fixture dispatch dirs:

- (a) The incident: nine nova soaks ahead, and a pair whose key is found to
  hash to the nova. `--backlog` reads nova 4590 s, and the thor carries only
  the remainder of its running request. The z-* leg and a later request
  (both on the thor, each 99999 s) are excluded, and counting either would
  flip the answer. `--choose` returns thor, and both arms resolve to thor.
  MUTANT: the same pair without `device`, which is what the old arms.sh
  queued, resolves to nova for both arms.
- An empty queue returns the hash's device, one pooled device returns "",
  and the desktop is never chosen.
- (b) An arm that already ran on the nova pulls its partner there (rule 2).
- (c) The race: in a hand pair with one explicit arm, both arms agree
  before either is claimed, while one is mid-claim (in running/ with no
  owner), and after the owner file is written. CONTROL: without the pin, the
  free arm hashes to the nova. A fully unpinned pair still agrees via the
  hash.
- Load pin: a pair pinned to a thor whose lane is dead does not resolve to
  thor, and both arms agree. CONTROL: a hand soak's `device: thor` still
  holds.
- Wiring: arms.sh runs for real against a private host with a backlogged
  nova, and queues both arms with `device: thor`.

Full `bash docs/testing/jobs/selftest.sh`: 2166 passed, 0 failed.
`preflight.sh` passed. The wiring mutant (arms.sh with the pin dropped) fails
the `device: thor` check. No device time was used.

## Next lane: do not repeat

- Do not move the choice to claim time. See the table: it is the #13 race.
- dispatcher.sh walks `"$D"/queue/*.req` in the locale's glob order, while
  request.sh documents ASCII order. affinity.py uses byte order. If the
  dispatcher's locale collation ever puts `1-…` after `17…`, the "ahead"
  set is slightly wrong. This is not changed here because dispatcher.sh is
  not in this lane's files.
