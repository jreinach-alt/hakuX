# lane.reqprio -- request.sh reads the release label itself (#432)

## What changed

`docs/testing/request.sh` now picks the `1-<epoch>` release-priority id on its
own when the request's issue carries the release label
(`HAKUX_RELEASE_LABEL`, default `0.5`). Before this, only `ab_run.sh` and
`jobs/arms.sh` read the label and passed `HAKUX_RELEASE_PRIO=1`. A lane that
queued a pilot or soak directly got a plain id. On 2026-09-27 at 19:46 PDT, 11
such requests (#474, #525, #526) waited 60-73 min behind arms that were queued
later, until the host renamed them by hand.

- The issue comes from `--issue N[,M]` (new, repeatable, comma-joined). If
  that is absent, request.sh uses the first `#N` in `--purpose`. It makes one
  `gh api repos/$GH_REPO/issues/N` read per listed issue and stops at the first
  labelled one.
- If a read fails, request.sh logs one line on stderr (`release priority: could
  not read #N's labels; queueing at normal priority`) and queues a plain id. A
  label never refuses a request.
- `HAKUX_RELEASE_PRIO=1` forces `1-`. `HAKUX_RELEASE_PRIO=0` forces a plain id.
  Set but empty also means plain with no read. That is how ab_run.sh and
  arms.sh already pass "not labelled", so they keep working unchanged and do
  not trigger a second read. Only an **unset** variable triggers the read.
- request.sh prints `priority release: '0.5' on #474` or `priority plain: ...`
  (with the reason) on stderr. stdout is still exactly `queued <id>`.
- The order of `0-*`, `0-0-x-*` and `z-*` ids is unchanged. request.sh writes
  only `1-<epoch>` or `<epoch>`, as before.

Behaviour change to note: before this, `HAKUX_RELEASE_PRIO=0` produced a `1-`
id, because `${VAR:+1-}` treats any non-empty value as true. Now it produces a
plain id. ab_run.sh still has the old reading (`PRIO="${HAKUX_RELEASE_PRIO:-}"`),
so an exported `HAKUX_RELEASE_PRIO=0` still becomes release priority there.
ab_run.sh is outside this lane's files, so that is left for a later lane.

## Proof

`docs/testing/jobs/selftest.d/99-request-release-prio.sh` uses a `gh` stub on
PATH, with each leg choosing its answer and every call logged. Each leg writes
to its own temp `DISPATCH_DIR` and asserts on the id of the `queue/*.req` file
it wrote. The legs are: labelled `#474` gets `1-`; unlabelled (`0.50` is not
`0.5`, and only the first `#N` is read) gets a plain id; an unreadable label
gets a plain id plus exactly one log line; `=0` over a label gets a plain id
with no read; set-empty gets a plain id with no read; `=1` gets `1-` with no
read; `--issue 999,474` overrides the purpose's `#12`; with no issue there is
no gh call.

Against origin/master's request.sh, the `label` leg fails (no read, so a plain
id), and so do `=0` (which gave `1-`) and `--issue` ("unknown option"). The
results are below.

## Do not repeat

- The Bash tool refuses commands containing `$?` or `${...}`. Write helpers to
  files instead.
- The full jobs selftest takes more than 10 minutes on this host. Run it
  detached and poll the log.
