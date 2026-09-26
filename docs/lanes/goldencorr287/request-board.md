# board request: lane goldencorr287 (#287, PR #300)

Grant `docs/testing/golden_overrides/**` to lane goldencorr287 (new path; no
current owner, nothing in the tree writes there).

Why: #287's golden (`Texture_format::TexFmt_R6G5B5`) is from a different build
of the suite (it prints `C: 0`; ours and three console runs print `C: 1`). The
repo has no golden-override data file, and the goldens themselves are an
upstream checkout (`/home/justin/goldens`, abaire/nxdk_pgraph_tests_golden_results)
outside this repo, so an edit there would be invisible and unversioned. The data
lands as:

- `docs/testing/golden_overrides/Texture_format/TexFmt_R6G5B5.png`, a byte copy of
  console set K (sha256 07dedad9ac60aa7c36f2791bf877311f66779359912f239bb7815a704ea385f8)
- `docs/testing/golden_overrides/README.md`: one provenance row per override

It moves no score until lane.toolsmith adds the `--golden-overrides` lookup
to score_sweep.py and dispatcher.sh. That request is routed separately with
`deliver.sh send toolsmith 287`.
