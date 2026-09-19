# lane.selftestsplit — `selftest.sh` split into separately-ownable fragments

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

**3. CI runs it, green, on a clean runner.** The `selftest` job on PR #136 at
`55334e78d2`: **pass, 2m38s**, against a 15-minute timeout. That is also the
end-to-end proof the workflow still triggers on this change.

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

**6. `preflight.sh`** passes clean on this branch — psh_differ, aci_vmstate,
nv2a index, territory, coverage, board files — with no `--allow-tracker`.

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
it conflicts with all of them by construction. **It must be folded last.** Open
and touching `selftest.sh` at the time of writing: #122, #130, #132, #134.

Four blocks have already been carried in this way (#126 → `95-affinity.sh`,
#127 → `85-fold-ci.sh`, #133 → `96-fleet-registry.sh`, plus #135's `arms.sh`
change which needed no carry). The recipe, for whoever does the next one:

1. `git merge <explicit sha of origin/master>`.
2. Keep this branch's `selftest.sh` (`git checkout --ours`) if it conflicts.
3. Carry master's added block into a fragment whose number puts it where it sat
   on master. Take the block from the *diff's added lines*, not a line range —
   that makes it byte-exact by construction.
4. `python3 .selftest-runs/puremove.py <sha>` must say identical.
5. Re-measure both sides at that sha and diff the logs check-for-check.
