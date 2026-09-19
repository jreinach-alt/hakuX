# lane.selftestsplit — `selftest.sh` split into separately-ownable fragments

## Why attempt 1 did not finish

**It left a finished PR in draft.** The work was done, pushed and green; the
session ended without `gh pr ready 136`, and a draft is "still working", so
the board resumed the lane. The attempt cost nothing in code and one full
Opus session in bookkeeping.

The timestamps say how it happened. Attempt 1 wrote the PR body at 00:39 and
then kept going — master moved twice more, so it carried #133's block into
`96-fleet-registry.sh` at 00:47 and rewrote these notes at 00:52. The carries
were the right call; what it never did was come back to the two closing steps.
So it ended with a **body that described a four-fragment-older branch** (it
still said 65 checks and eleven fragments when the branch was at 124 and
fourteen) and the ready flag unset.

The lesson is about ordering, not diligence: this lane's design *guarantees* a
tail of re-merges, because it must fold last. Attempt 1 treated "mark ready"
as the final step after the last carry, and there is no last carry until the
session runs out. **Mark ready as soon as the branch is green and current, and
re-merge afterwards** — a ready PR that needs one more carry is a PR the board
can see and audit; a draft is invisible and costs a resume. Nothing about being
ready folds it early: the fold job only touches PRs labelled `fold-ready`, and
that label is the board's to apply.

Attempt 2 re-verified rather than assuming: pure move against the current
master (525 non-blank lines, identical, same order), CI green at the exact
head, preflight re-run — which is how the territory overlap in proof 6 below,
new since attempt 1, was caught.

## What the problem was

`docs/testing/jobs/selftest.sh` is the gate every change under
`docs/testing/jobs/` must pass, so a lane that fixes something in the harness
also writes the check that proves it. On 2026-09-19 nine harness lanes ran and
**all nine appended a block to that one file**.

The fold job folds one PR per tick, and each fold moves master. From the fold
log that night:

```
07:07:30Z #127 CONFLICT in: docs/testing/jobs/selftest.sh
07:09:30Z #132 CONFLICT in: docs/testing/jobs/fold.sh docs/testing/jobs/selftest.sh
```

Two of the first three folds attempted, both handed back. The conflict rate was
not high, it was structurally ~100%: N harness PRs in flight cost N−1
`lane.sh resume` cycles — an Opus session each, an attempt each against
`LANE_MAX_ATTEMPTS`, a queue place each — to re-land work that was already
finished, tested and green.

**This lane watched it happen four more times while it worked.** Master moved
under this branch four times in one session (`bc7ccef95d` #135, `642b557e77`
#126+#129, `69bacdeea9` #127, `ae3712aae1` #133), and three of those four
carried a `selftest.sh` append. One produced a genuine merge conflict. That is
the rate, measured rather than argued.

## What was done

The checks now live in `docs/testing/jobs/selftest.d/NN-<concern>.sh`, sourced
in sorted order by `selftest.sh`. `selftest.sh` keeps the entry point, the
fixture directories, the shim construction (`gh`, `systemctl`, `systemd-run`,
`adb`), the live prediction and its goldens, and the final tally. The command
CI and every brief runs is unchanged: `bash docs/testing/jobs/selftest.sh`.

A lane adding a check now creates or edits one fragment. Two lanes adding
checks touch two paths.

This is a **pure move**: not one check was rewritten, including the four blocks
carried in from master mid-session.

## The brief's "49" was stale. It was 65 when I started and 124 when I finished

The brief said the selftest reports `49 passed` and must still report 49. At
`1f7572a34c`, this lane's base, it reported **65** — `selftest.sh` is
byte-identical there and at `bc7ccef95d`, so that is not something that landed
while I worked; the brief's figure was already old when it was written. By the
end of the session other lanes' folds had taken it to **124**.

So the invariant the brief wanted is real but its number was not, and quoting
124 here would age just as badly. **The check that survives is the comparison,
not the constant**: at every ref, the split run and the unsplit run of the same
content agree check-for-check. That is what is measured below.

## Fragments, and what depends on what

Order is fixed by the numeric prefix, and it is load-bearing for 10..60.

| Fragment | Depends on |
| --- | --- |
| `10-arms-list.sh` | `selftest.sh`'s `$EXP`, the goldens tree, `arms/since`. First of the arms chain; nothing is queued when it runs. |
| `20-arms-queue.sh` | **10** (an empty queue). Leaves the pair and the two `.req` files. |
| `30-arms-error.sh` | **20** (the pair it errors). |
| `40-arms-refusal.sh` | **20/30** — runs `arms.sh` over the standing queue. Registers `$EXP2`, `$EXP3` from `selftest.sh`'s `$A`/`$B`. |
| `50-arms-requeue.sh` | **20/30**, whose markers it clears; it then drives the whole queue itself. Last of the arms chain. |
| `60-status.sh` | **10..50** — the refusal `status.sh` renders is 40's. |
| `65-fold-cloud-list.sh` | nothing |
| `70-cloud-audit.sh` | nothing (reads `cloud.sh`'s own text) |
| `75-nv2a-index.sh` | nothing (own throwaway repos under `$T/gate`) |
| `80-labels.sh` | nothing, but it **truncates `$SELFTEST_GH_LOG`** as it goes, so no later fragment may depend on what that log held before it. |
| `85-fold-ci.sh` | nothing (own `gh` shim under `$T/foldci`, own `HAKUX_WORK`) — carried from #127 |
| `90-fold-notes.sh` | nothing (own git fixtures under `$T/foldnotes`) |
| `95-affinity.sh` | nothing for its own fixtures (`$T/aff`), but its last group writes into the real `$DISPATCH_DIR/splits` and reads it back through `status.sh`, so it follows the arms fragments. Starts a `sleep 600 &` as `$LIVEPID` and kills it at the end — carried from #126 |
| `96-fleet-registry.sh` | nothing — carried from #133 |

65..96 are order-independent of each other and of 10..60, with the two caveats
noted (80's log truncation, 95's `$DISPATCH_DIR` use). The numbering leaves
`00-09`, `61-64`, `66-69`, `71-74`, `76-79`, `81-84`, `86-89`, `91-94` and
`97-99` free, so an insertion rarely needs to renumber anything — and that is
not theoretical: #127's block belonged *between* the labels and fold-notes
blocks, and `85` put it there with nothing renamed.

`NN` is **exactly two digits**, and `selftest.sh` refuses a name that is not
`NN-<concern>.sh`. Not pedantry: a glob sorts lexically, so `100-x.sh` would
run *before* `20-x.sh`, and a fragment named `check-x.sh` would simply never be
sourced. A gate that silently stops running is the failure mode this lane
exists to remove, so both are a hard `exit 2`, as is an empty `selftest.d` (a
clean run having checked nothing). The `*.md|*~` arm lets a README and an
editor backup sit in the directory.

The glob output is re-sorted through `LC_ALL=C sort`: the runner's collation is
not this box's, and the order is load-bearing.

## Proofs

**1. Pure move — byte-identical, same order, re-checked at every ref.**
`.selftest-runs/puremove.py` (scratch, not committed) reads
`<ref>:docs/testing/jobs/selftest.sh` — the *committed* file, so a working-tree
edit cannot fool it — takes its check region, strips each fragment's header
comment, concatenates the fragments *in sorted order* and compares non-blank
lines. Run after each merge:

| ref | fragments | non-blank lines | result |
| --- | --- | --- | --- |
| `bc7ccef95d` | 11 | 238 | identical |
| `69bacdeea9` | 13 | 398 | identical |
| `ae3712aae1` | 14 | 525 | identical |

Sorted-order equality is the part that matters: it proves the numeric prefixes
reproduce the original relative order, so the arms chain's fixture sequence is
preserved. The splitting script refuses to write if any non-blank line of the
region lands in no fragment or if two ranges overlap; the carry script refuses
if master's diff removes anything or spans more than one hunk; the trim script
refuses to cut a region from `selftest.sh` unless it is exactly what the named
fragment already holds.

**2. Same checks, same order, not slower.** Unsplit (a detached worktree at the
ref) and split (this branch at the same content), back to back on the same box:

| ref | | passed | failed | exit | wall clock |
| --- | --- | --- | --- | --- | --- |
| `bc7ccef95d` | unsplit | 65 | 0 | 0 | 278s |
| | split | 65 | 0 | 0 | 278s |
| `69bacdeea9` | unsplit | 97 | 0 | 0 | 164s |
| | split | 97 | 0 | 0 | 164s |
| `ae3712aae1` | unsplit | 124 | 0 | 0 | 174s |
| | split | 124 | 0 | 0 | 173s |

The totals are not the whole comparison. Reduced to `==` section headings and
`ok`/`FAIL` lines, normalised for the timestamped `.req` filenames, the two
logs of each pair diff clean:

```
IDENTICAL: 124 checks passed, same order, same sections
sections:  15
```

Timing is contended — other lane sessions share this box, which is why
`bc7ccef95d` took 278s and a later, larger run took 174s. Treat the pairs as
paired, not as absolute. The structural argument is the stronger one: the cost
is the `arms.sh` invocations, untouched, and the split adds fourteen `source`
calls.

**3. CI runs it, green, on a clean runner.** The `selftest` job on PR #136, at
two heads: `55334e78d2` **pass, 2m38s**, and the branch head `acc6fe319f`
**pass, 2m37s** — against a 15-minute timeout. That is also the end-to-end
proof the workflow still triggers on this change: the job ran at all, on a
commit that touches only `selftest.d/` and the notes.

The runner is the honest timing number. The 278s/174s local figures in proof 2
are paired measurements on a box shared with other lane sessions; CI's 2m37s
on a clean runner is what the 15-minute timeout is actually up against.

**4. A failing fragment fails the run.** The tally is shared state across
sourced files, and that is exactly the property a split like this can silently
lose. Tested for real at two different refs: wrote
`selftest.d/99-deliberate-failure.sh` with one `bad`, one failing `check` and
one passing `check`, ran the entry point, deleted it.

```
exit=1   (must be non-zero)
== deliberate failure
  FAIL a deliberately failing fragment
  FAIL a deliberately failing check in a fragment
selftest: 98 passed, 2 failed
```

98 = the 97 plus the fragment's one passing check, so the *passing* side of the
tally is shared too, not only the failing side. `set -u` is on throughout and
the fragments inherit it.

**5. The name guards trip.** Each fixture created in `selftest.d/`, run,
deleted:

| fixture | result |
| --- | --- |
| `check-foo.sh` | `exit 2`, "is not selftest.d/NN-\<concern\>.sh and would never be sourced" |
| `100-late.sh` | `exit 2`, same — it would have sorted *before* `20-` |
| an empty `selftest.d` | `exit 2`, "no fragments … nothing would be checked" |

All three exit before a single check runs, so none can be mistaken for a pass.

**6. `preflight.sh`** passes every gate it can on this branch — psh_differ,
aci_vmstate, nv2a index, coverage, board files — and fails exactly one,
`territory`, for a reason that is not this branch's to fix:

```
territory                   FAILED
  docs/testing/jobs/selftest.sh is claimed by both branchprune and selftestsplit
```

This was clean during attempt 1 and is not now, because the board added a
`[lane.branchprune]` row at wave 100 that claims `selftest.sh` as well. The
board wrote the overlap **knowingly** — its own note on my row calls it "an
accepted, fold-order-managed overlap with lane.branchprune above, not a
collision this file should try to prevent."

Worth being precise about the escape hatch, because the lane contract points
at it and it does not apply: **`--allow-tracker` does not suppress this.**
That flag licenses *editing* `territory.toml`/`nv2a_issues.toml` (preflight.sh
step 7); the territory overlap is step 3 and has no override at all. So
`preflight.sh --allow-tracker` still exits 1 here. The only thing that clears
it is an edit to `territory.toml`, which a lane may not make. Nothing in this
branch's diff can change that result, and it does not gate CI — the territory
step is explicitly "not a CI gate" (`preflight.sh:170`).

**7. CI trigger.** `.github/workflows/jobs-selftest.yml` gained
`docs/testing/jobs/selftest.d/**` in both `paths:` lists. Being precise about
what that is worth: the existing `docs/testing/jobs/**` **already** matched the
new directory — GitHub's `**` crosses directory separators — so this is
belt-and-braces rather than a fix, and a comment on the `push:` list says so.
It is there for whoever next narrows `jobs/**`. Proof 3 is the actual evidence
the gate still fires.

## What the next lane should not repeat

- **Do not edit `selftest.sh` to add a check.** Add
  `selftest.d/NN-<concern>.sh`. An append to `selftest.sh` re-creates exactly
  the collision this lane removed.
- **Mark the PR ready the moment the branch is green and current, not after
  the last re-merge.** On a lane that must fold last there is no last
  re-merge — master keeps moving until the session ends, so "finish, then mark
  ready" never reaches the second clause. That is the whole of why attempt 1
  cost a resume. Being ready does not fold anything early: `fold.sh` only
  considers PRs labelled `fold-ready`, which the board applies.
- **Do not edit a script while a long run of it is in flight.** Bash reads a
  script lazily by byte offset, so an edit that shifts bytes ahead of the
  interpreter's position makes it resume mid-token. It surfaced as
  `selftest.sh: line 125: pass: command not found`, which reads exactly like a
  defect in the change and is not. Finish every edit, *then* measure.
- **Give every run its own log filename.** `TaskStop` on the wrapper did not
  reap the `selftest.sh` child, which kept writing to the log path through its
  inherited fd. Two runs interleaved into one file and it ended
  `72 passed, 1 failed` — a number belonging to neither run. Check the
  `fake host in /tmp/hakux-selftest.XXXX` tempdir on the tally line is the one
  you expect before believing the tally.
- **Take the baseline yourself and date it.** "49" came from the brief and was
  wrong by 16 before I touched anything. The instrument that settles it is a
  throwaway `git worktree add --detach <sha>`: a pristine tree that your own
  edits cannot disturb, with its own `$T`. Re-point it with
  `git -C <wt> checkout --detach <sha>` after each merge and re-measure — an
  unsplit baseline from an older ref is not a baseline for the current one.
- **Pin the sha, not `origin/master`.** Master moved between two consecutive
  commands in this session. Every merge, diff and measurement here names an
  explicit sha, and `MERGE_HEAD` is what tells you which one you are actually
  merging.
- `git add -A` in this worktree stages the detached baseline worktree as an
  embedded git repository. Stage explicit paths.

## Sequencing

This PR moves the lines every other open `selftest.sh` PR is appending to, so
it conflicts with all of them by construction. **It must be folded last.**

Open and appending to `selftest.sh` as of the end of attempt 2 — re-read from
`gh pr list`, not carried over from attempt 1, because three of the names in
the earlier list had already folded:

| PR | lane | lines added to `selftest.sh` |
| --- | --- | --- |
| #122 | orchestration-design | 15 |
| #123 | armsskip | 72 |
| #124 | boardgate | 128 |
| #130 | auditoutlet | 104 |
| #132 | handback | 187 |
| #134 | backlogstate | 172 |
| #137 | branchprune | none yet, but `territory.toml` claims the file |

The fold job takes `--label fold-ready` and `sort_by(.number)` (`fold.sh:93`),
so among PRs labelled fold-ready together, **#136 already sorts last** behind
every one of those but #137. That is luck, not design: it holds only while no
higher-numbered PR appends to `selftest.sh`. If one does — #137 is the live
candidate — the board has to hold this PR's `fold-ready` label back until that
one lands, because number order will otherwise fold this first and conflict
the other. The ordering request is in the PR body for that reason.

Four blocks have already been carried this way (#126 → `95-affinity.sh`,
#127 → `85-fold-ci.sh`, #133 → `96-fleet-registry.sh`, plus #135's `arms.sh`
change which needed no carry). That is the whole cost of being folded last,
and it is bounded: one carry per `selftest.sh` PR that lands first, each one a
diff's worth of added lines. The recipe, for whoever does the next one:

1. `git merge <explicit sha of origin/master>`.
2. Keep this branch's `selftest.sh` (`git checkout --ours`) if it conflicts.
3. Carry master's added block into a fragment whose number puts it where it sat
   on master. Take the block from the *diff's added lines*, not a line range —
   that makes it byte-exact by construction.
4. `python3 .selftest-runs/puremove.py <sha>` must say identical.
5. Re-measure both sides at that sha and diff the logs check-for-check.
