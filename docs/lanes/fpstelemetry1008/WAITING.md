# fpstelemetry1008 — waiting (attempt 3, 2026-10-08 ~23:10 PDT)

[lane.fpstelemetry1008] waiting: three Nova dispatch requests queued behind ~10 other
lanes' requests (`lane.profileddefault1008`, `lane.surfdl1008`); none had landed by the
time this session's budget required handing off.

- `1-1791525926-fpstelemetry1008-4089047` — NBA Live 2005, full telemetry (820s,
  `--route fps786-nba2005`, perflog+GPUXFR+FRAMETRACE)
- `1-1791525932-fpstelemetry1008-4091099` — Dead or Alive 3, route pilot (180s, no
  telemetry flags — `doa3.route` has never run as a timed route)
- `1-1791525936-fpstelemetry1008-4091494` — MK Shaolin Monks, route pilot (330s, no
  telemetry flags — `fps1008-shaolin.route` has never run as a timed route)

**Signal that resolves this**: `dispatch/results/<id>/DONE` existing for each of the
three ids above (check via `python3`, the dispatch dir is outside this worktree's Bash
cwd). When all three have landed:

1. Review the two pilots' frames; write the verdict (result ids, what the frames showed,
   the date) to `/home/justin/hakux-work/dispatch/pilots/fpstelemetry1008.ok` so the
   30-minute pilot gate clears for the rest of this batch (NOTES.md §8).
2. Decompose NBA Live 2005's result with `decompose.py`/`xfrsurvey.py`/`sdsurvey.py` and
   add it to the cause table (NOTES.md §7) as a fresh, trusted-GPU-stamp row, replacing
   the pre-fix §4a citation.
3. On a good DOA3/Shaolin pilot, queue each one's full telemetry run (NOTES.md §8 gives
   the exact `--seconds`). On a bad pilot, write the route defect, do not rerun blind.
4. Once `pilots/fpstelemetry1008.ok` exists, queue Arctic Thunder's full run (refused
   this attempt by the pilot gate, not by anything title-specific — NOTES.md §8) and
   work through the 8 generated-but-unpiloted routes in `docs/testing/titles/routes/`
   (NOTES.md §9: spiderman2, lotr-rotk, hulk-ud, nhl2k3, ngb, amped2, pilotdown,
   fantastic4 — pilot each first, none has ever run as a timed route).
5. NFS Most Wanted and Midnight Club II still have no route (`steps2route.py` cannot
   encode their recorded `RT+left`/`RT+right` steering tokens — a tool bug, NOTES.md §9);
   that needs a fix outside this lane's territory before either can be queued.

This is waiting on the host dispatcher (an external, already-running process), not on
any background task started by this session — safe to end here per the lane contract.
