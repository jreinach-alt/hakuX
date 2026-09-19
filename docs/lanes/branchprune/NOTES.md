# lane.branchprune — nothing deletes a lane branch, and two jobs walk them all

## The measurement, reproduced on this branch (2026-09-19)

```
total lane refs: 25, fully merged into origin/master: 8
```

The brief's numbers reproduce exactly. The eight:

| branch | tip | local head | worktree holding it |
| --- | --- | --- | --- |
| `lane/armsperf` | `630258bad7` | yes | `$WORK/wt/armsperf` |
| `lane/cloudwt` | `fc547df32e` | yes | `$WORK/wt/cloudwt` |
| `lane/jobsfix` | `5aa5354111` | yes | `$WORK/wt/jobsfix` |
| `lane/jobslabel` | `ecbc46f416` | yes | `$WORK/wt/jobslabel` |
| `lane/notespath` | `1eee0f08da` | yes | `$WORK/wt/notespath` |
| `lane/swizzle87` | `dffcb619bd` | yes | `$WORK/wt/swizzle87` |
| `lane/tier81fix` | `b2532b9fe4` | yes | `$WORK/wt/tier81fix` |
| `lane/toolsmith` | `baa5b32698` | yes | `$WORK/wt/toolsmith` |

**8 of 8 still have a local branch held by a lane worktree.** The brief called
that an edge case to handle; it is the only case there is. A design that only
deleted the local head would have deleted nothing at all.

(Work in progress — this file is filled in as the lane runs.)
