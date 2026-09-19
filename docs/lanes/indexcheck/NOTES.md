# lane.indexcheck -- #157: the index check could not tell a stale index from a stale test checkout

Base: `master @ 415dcc6997`. Files: `docs/testing/nv2a_index.py`,
`docs/testing/jobs/selftest.d/75-nv2a-index.sh`, this directory.

## What was wrong

`check --tests DIR` reported `suites differ (committed 103, tests tree 102)`
and printed one remedy for every failure: `build --tests DIR`. The count has
no sign, so that same sentence covers two opposite situations, and the remedy
is correct for only one of them. Following it from a checkout that is BEHIND
rebuilds from the smaller tree and commits the deletion of a real suite.

## What I measured before changing anything

The live tree (`/home/justin/nxdk_pgraph_tests @ 91a0de45`) is exactly the
commit the committed index records, so it is a clean baseline. I copied its
`src/tests` twice and deleted `surface_as_vertex_array_tests.{cpp,h}` from one
copy -- the same suite and the same shortfall as the incident in #157.

| arm | master's `check` said |
| --- | --- |
| tree short by one suite | `suites differ (committed 103, tests tree 102)` |
| index short by one suite | `suites differ (committed 102, tests tree 103)` |

Two opposite faults, one sentence, one (wrong for the first) remedy.

**The `build` side was worse than the issue claimed.** Master already has
`tests_provenance_gate`, which asks git whether the checkout is an ancestor of
the one the index came from. That is the right question and it returned **rc 0
on my short tree** -- because a plain directory copy has no `.git`, so
`git rev-parse HEAD` fails and the gate returns early. `build` then wrote a
102-suite index over the committed 103-suite one without a word. The
provenance gate ranks the TREE; nothing ranked the RESULT.

Do not assume that gate covers you. It is blind to three ordinary cases: a
tests tree that is not a checkout, an index with no `tests_commit`, and a
different fork whose history cannot be ranked by ancestry.

## What I changed (`nv2a_index.py` only)

- `suite_drift()` splits a disagreement into missing / extra / changed.
- `describe_suite_drift()` names the suites and the direction, and gives the
  direction's own remedy -- `git -C DIR merge --ff-only @{u}` for a short
  tree, `build` for a short index.
- `stale_headline()` -- the headline now depends on the direction. For a short
  tree it must NOT name `build`, because that is the command that loses the
  data. Extracted as a function so the selftest can assert the *absence*
  cheaply, without a 4.5s index build.
- `suite_removal_gate()` refuses to WRITE an index with fewer suites than the
  committed one; `--allow-suite-removal` overrides. Deliberately **not**
  implied by `--allow-older-tests`: "this tree is older" and "I mean to delete
  these named suites" are different claims, and only the second is worth
  reading a list before making. Exit code 4 (provenance uses 3).

Free catch: `build` with no `--tests` parses no suites at all, which is the
extreme of the same removal, so the 2026-09-13 accident (an empty suite half
written, then passed by a `check` with no `--tests` because both sides agreed
there were none) is now refused by the same gate, naming the missing flag.

`fold.sh` needs no change: on a nonzero `build` it already aborts the fold and
comments "needs a person" rather than committing. The refusal lands there as
a blocked fold, which is the outcome wanted.

`preflight.sh` needs no change either -- it `sed`s the check's own log into its
output verbatim, so the new text reaches its readers already. I did not touch
it; it is lane.toolsmith's.

## After

Short tree (index ahead) -- headline no longer says regenerate:

```
STALE INDEX - but DO NOT regenerate yet: the tests tree is
SHORT of the committed index, so a rebuild would DELETE the
suite(s) named below. Update the tests checkout first.

  suites differ (committed 103, tests tree 102)
  the tests tree is MISSING 1 suite(s) the index has: Surface as vertex array
      Your nxdk_pgraph_tests checkout is probably BEHIND the one
      the committed index was built from. Fix the TREE, not the
      index -- rebuilding from this tree DELETES those suite(s):
          git -C DIR fetch --all && git -C DIR merge --ff-only @{u}
```

Short index (index behind) -- unchanged remedy, now with the suite named:

```
STALE INDEX - regenerate with: nv2a_index.py build --tests DIR

  suites differ (committed 102, tests tree 103)
  the tests tree has 1 suite(s) the index does NOT: Surface as vertex array
      The committed index is behind the tests tree. This is
      ordinary staleness; regenerate:
          nv2a_index.py build --tests DIR --support DIR
```

`build` against the short tree now exits 4 and writes nothing, naming
`Surface as vertex array` as what would be deleted; with
`--allow-suite-removal` it proceeds and still prints the list.

## Coverage

14 checks added to `selftest.d/75-nv2a-index.sh` (313 -> 327 passing, 0
failed). They drive the four new functions on synthetic suite tables, so they
cost no index build.

`docs/lanes/indexcheck/suite_gate_mutants.py` breaks each mechanism in a copy
under /tmp and shows every mutant turns a distinct check red, and that the
unmutated file passes all four. Run it if you touch this code:

```
(unmutated)                          ok  ok  ok  ok
M1 headline always says regenerate   TRIPPED headline omits 'regenerate'
M2 removal gate never refuses        TRIPPED build refuses (rc=4)
M3 drift drops the missing branch    TRIPPED names the missing suite
```

## What the next lane should not repeat

- **Do not use `build` to make the index gate go green.** Read the direction
  line first. That was the whole of #157.
- **The falsifier tree must not be a git checkout** if you want to exercise
  the content gate. Make it one and `tests_provenance_gate` refuses first, and
  you will have proved only that the gate that already existed works.
- **Do not re-measure `check`'s control against a tree you have just built
  from.** My first control run raced a `build` in the same message and passed
  against the index that build had just written -- an agreement with itself.
  Run them serially.

## Adjacent finding, NOT fixed here (worth an issue)

`cmd_check` compares only `symbols`, `sites` and `suites`. It does **not**
compare `gaps`. Rebuilding the index on this base changes 8 `gaps` entries --
`gl/shaders.c` line numbers moved when PR #128 folded -- while `check` reports
"index matches the tree". Verified part by part against the live tree:

```
gaps DIFFERS   provenance DIFFERS   issues/method_regs/schema/sites/suites/symbols/unread SAME
```

So `query gaps` answers from stale line numbers and the gate cannot see it,
and the next legitimate rebuild will carry those 8 lines as unexplained noise
in its diff. I left it alone: fixing it means committing `nv2a_index.json`,
which is not this lane's file, and it is a different defect from #157.
