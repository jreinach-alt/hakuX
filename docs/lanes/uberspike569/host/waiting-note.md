[lane.uberspike569] waiting: on seven device requests, re-queued at 16:28 PDT after the live dispatch queue and results were emptied at about 16:25 (BUILD.md section 8; possible cause flagged on #622).

- DOA soaks (Nova, 440 s, survey): A `1790724512-uberspike569-1350514`, B `1790724521-uberspike569-1353595`, H `1790724524-uberspike569-1354320`
- Kabuki soaks (Nova, 600 s): A `1790724526-uberspike569-1355381`, B2 `1790724528-uberspike569-1355882`
- E pixel arm (36 suites, 2 runs): A `1790724542-uberspike569-1360739`, H `1790724547-uberspike569-1361951`

Resolved when all seven result dirs exist. The arms job's pair for `uberspike569-gpl-pixels.json` (sha `c5c0e63aed4e`) still names the deleted ids and will not judge, so this lane judges E with `ab_compare.py` on resume. At 16:15 the Nova was at 36%, under its 38-39% admission floor for these soaks.
