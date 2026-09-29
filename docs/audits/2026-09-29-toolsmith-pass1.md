# Audit pass 1: PR #611, lane.affinitybatt (lane/toolsmith)

Diff read: `94cf8eb627..b8082131cf` (affinity.py, battery_admit.py, arms.sh,
selftest.d/99-affinity-battery.sh, docs/lanes/affinitybatt/NOTES.md).
The selftest fragment was not run by this audit. Its permission was refused
on the audit host, so the proof table in the PR body is taken as reported.

Verdict: **one MEDIUM, three LOW**. Result: `needs-remediation`.

## M1: rule 3 now reads mutable state, so a pair can split across the claim window

`affinity.py`'s module docstring gives the reason rule 3 is a hash: "No amount
of looking harder at shared state fixes a read-read race; the fix is to stop
reading. A hash needs no state, so there is no window in which two workers can
disagree." `_battery_alt` puts shared state back into rule 3: the refusal
records, `.battery_level.<label>`, and the clock. The NOTES pair argument
("an arm claimed in that minute is in running/ and rule 2 pulls its partner
after it") assumes the claim happens at the moment of the decision. It does
not. `serve_one` decides with `affinity.py`, then runs `battery_admit`, which
reads the level over adb when the 60 s cache is stale (up to
`ADB_QUICK_TIMEOUT`, 30 s), and only then does the `mv`. For that whole
interval the arm is still in `queue/`, and rule 2 cannot see it.

Failure scenario, using the incident's own shape:
1. Arms A and B of key K hash to the nova. The nova refuses both for more
   than 600 s at level 35 against a need of 49.6. The thor is at 80, so both
   arms' rule 3 answers thor.
2. The thor's worker takes arm A. `affinity.py` returns thor. Its level cache
   is stale, so `battery_level` starts a dumpsys read.
3. During that read, the nova serves some other request routed to it.
   `battery_level` rewrites `.battery_level.nova` to 50, which is at least
   49.6. `_refusing(nova)` now returns None and `_battery_alt` returns "", so
   K's answer flips back to nova.
4. The nova walks to arm B. Rule 2 finds nothing (A is still in `queue/`),
   rule 3 gives nova, the nova admits at 50 and moves B into `running/`.
5. The thor's read returns, it admits A at 80 and moves A into `running/`.
   A has run on the thor and B on the nova: a split pair.

Before this PR the only thing that could flip rule 3 was `pooled()`
changing. This PR adds a flip toward a device that can claim (the nova's
level crossing the need) that happens routinely: it is exactly how a
recharging handheld behaves. The downstream confound check (DEVICES DIFFER,
the hard-pin re-run) bounds the damage to one wasted arm pair and a re-run,
which is why this is MEDIUM and not HIGH.

Suggested remedy: make the move one-way for the pair. Once rule 3 has moved
key K off device D, follow that move. Key the note on K rather than on the
request id (`moves/<key>.battery.txt` naming the target) and have rule 3
read it back. Allow a return only when the target itself refuses, because a
refusing device cannot claim. Then the only remaining flip goes toward a
device that will not take the arm. Correct the NOTES pair paragraph and the
comment in affinity.py to match.

## L1: after a move, the refusing device's record never goes stale

After the move, the nova is never offered K, so it never refreshes its
level for K. If it has no other routed work, its `.battery_level` file ages
past 900 s, and `_refusing` falls back to the recorded level (35), which
still reads as refusing. A nova that has recharged to 90 % and is idle keeps
passing K to the thor, even when the thor has a long queue. The cost is
delay, not a wrong result. Any other work routed to the nova refreshes the
level. The comment says a device with no fresh level counts as admitting,
but that asymmetry applies only to candidates. Worth one sentence in the
comment.

## L2: `_key_ids` loads every queued and running request on every affinity call while any refusal exists

The walk calls `affinity.py` once per queued request, and each call with a
refusal on file loads every `.req` in `queue/` and `running/`. That is
quadratic per walk. Queues are tens of requests, so this is quality only.

## L3: selftest proof is local only

The PR body records 274/0 locally. The CI run on the head is the gate of
record. Nothing further is asked of this PR here.

## Not findings

- `battery_admit.py` is already in `SCRIPT_DEPS` and `snapshot_scripts`, so
  the import in a worker snapshot resolves. The fail-open `_ba = None` path
  covers lone copies.
- `need_for` is a pure extraction: `check`'s need, uncapped value and
  learned inputs are unchanged.
- `note_refusal` and `note_admission` are called only from `check`, which
  only the device's own worker runs, so the record has one writer. The
  write is atomic (tmp.pid then `os.replace`).
- The load-pin and rule-2b fall-throughs only apply while the pinned
  device is refusing, and a refusing device cannot claim. They add no
  claimable flip beyond M1's.
- arms.sh item 2 is a comment only.
