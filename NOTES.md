# lane.handback — an actor for a PR a job handed back

Base: `master` @ bdeab36f75.

## The defect, restated

`fold.sh` labels a conflicting PR `needs-rebase`, comments, and stops — which
is right; a merge resolved by a script that does not understand the code is how
a working fix was reverted on 09-12. But `needs-rebase` is set by one job,
displayed by `status.sh`, and **acted on by none**. The lane that would fix it
is a `systemd-run` transient unit that exited when its session ended.

## Where it goes, and why (the brief called this a judgement call)

(Filled in as it lands.)
