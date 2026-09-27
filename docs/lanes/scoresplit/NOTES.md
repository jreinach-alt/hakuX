# lane.scoresplit (#500)

## What changed

`score_sweep.py --flat` mapped `score_dir` over `dirs = [args.out]`: one work
item, so one worker scored every capture of a whole-suite disc while the rest
idled and the dispatcher kept the device held. The fix (written by hostops,
installed as an interim in the dispatcher snapshot, landed here verbatim):

- `score_dir` takes an optional third element, a list of names to score
  instead of `sorted(os.listdir(run_dir))`.
- In flat mode `main()` splits the sorted file list into `--jobs` chunks.
  `ex.map` keeps order and every row depends only on its own file, so the
  captures list, the fold and the TSV come out as before.
- `chunksize` 8 -> 1 (per-run mode too; it only affects dispatch batching).

Added by this lane: one stderr line in flat mode,
`score_sweep: flat run split into N work items over M files`, so the split is
observable. It goes to `run$r.log` in the dispatcher; nothing parses it.

## Measured

Re-scored the Nova run `0-0-x-1790530526-arms-notify488-fix-2807175/captures1`
(755 files, 754 PNGs) on this host (8 CPUs), TSVs written under the worktree.

| run | work items | wall |
|---|---|---|
| `--jobs 1` (old behaviour) | 1 | 543.9 s |
| default (`--jobs 8`) | 8 | 153.9 s |

Both TSVs are byte-identical (sha256 `fc53124b...ad6c`), the stdout summaries
are identical apart from the split line, and columns 1-9 match the
dispatcher's own `scores1.tsv` for that run.

## Selftest

`jobs/selftest.d/99-score-sweep-flat-split.sh`: a flat fixture of nine
captures (colour exact and differing, one `_ZB` off by one depth step, one
with no golden, one truncated PNG) plus a non-PNG file. Asserts the summary
line and the split line (1 item at `--jobs 1`, 4 at `--jobs 4`), the TSV rows,
and `cmp` of the two TSVs. Builds a venv (or reuses 83-blank-rule's) when
numpy/PIL are absent; if that fails it prints SKIP and counts nothing.

Mutants run against the fragment (with REPO pointed at a mutated tree):
- whole list per chunk: fails "still scores each capture exactly once"
  (36 captures, 27 repeated). The fold dedups, so the TSV alone cannot see
  this mutant; the capture count is what catches it.
- master's unsplit scorer: fails both split-line checks.

## Do not repeat

- Comparing only the TSV does not catch duplicated work: the repeat-fold in
  `main()` hides it. Read the `captures, repeated` summary.
