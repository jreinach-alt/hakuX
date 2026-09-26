# lane.titleplay: gameplay frame rate under scripted input

Issue #397. Brief: drive each title into real gameplay, confirm it from the
frames, measure it (the owner, 2026-09-26). Base `a5b5b628f2`. PR #399.

## Pass 1 (queued 2026-09-26 07:32 PDT)

29 requests `0-0-y-1790433159-titleplay-p1-<label>`, ref `a5b5b628f2`
(master, includes the #382 fix), 420 s each, pinned to the device that holds
each ISO. The ids are listed in the #397 comment of 07:33 PDT and can be
regenerated with `tools/plan_p1.py`.

- Population 1, all 20 titles, run on `survey.route`.
- Population 2, the titles whose file names on a device are already proven
  by a past `done` result (`tools/isoseen.py`):
  - Nova: Ghoulies, RalliSport 2 (PAL), Tork, Fuzion Frenzy (own route).
  - Thor: Galleon, DOA3, JSRF, Spikeout (PAL), Crimson Skies (own route).
- Not queued:
  - **Conker**: a dispatcher soak of `Conker Live & Reloaded.iso` has never
    started the app (#265), and the suspect is the `&` in the name. That is
    a harness defect, not a game result.
  - **The other 13 titles of population 2** (ToeJam III, THPS2x, NG, NGB,
    Deathrow, Dino Crisis 3, Halo, Halo 2, MechAssault, Psychonauts, PDO,
    Phantom Dust, Amped 2): their exact ISO names are unknown. Guesses have
    missed before (Psychonauts, PDO and JSRF, 2026-09-12). The listing
    (`devices.sh titles`) needs adb, so it was asked for on #397.

### Why a survey route and not generic

`generic.route` takes no frame between boot and `mark play`, so a run that
stalls in a menu shows nothing of where it stalled. `survey.route` sends the
same input and takes a frame at 20/40/60 s, after every START and every A of
the 14 menu rounds, and every ~23 s of play. It never writes
`mark gameplay`: a reviewer decides from the frames.

**The scored window of a survey run starts at `mark play` (~200 s).** Only
answer `--reviewed-gameplay yes` when the frames from `mark play` onward all
show gameplay. If gameplay began later, the menu time would be counted in the
share. That title gets a pass-2 route with its own `mark gameplay` instead.

## Tools

- `tools/isoseen.py [substr]`: every soak title a past dispatch result ran,
  per device, and whether the worker found the ISO. It reads results only.
- `tools/plan_p1.py [route]`: the pass-1 plan for population 1.
- `tools/queue.py --ref R --seconds S --tag T plan.tsv`: puts each line
  through `request.sh` into a private staging queue, re-keys it
  `0-0-y-<ts>-titleplay-<tag>-<label>`, and renames it into the real queue.
  The dispatcher takes a request's id from its file name (`serve_one`).
- `tools/review.py ids [--reviewed label=yes|no]`: copies each finished run
  to `scratch/runs/`, judges the copy, and prints the marks, the fps median
  and share, and a 30 s fps timeline over the whole run.
- `tools/targets_p1.py`: the `targets.toml` entries for population 1, from
  the compat CSV and the batch TSV.

## Results

(pass 1 pending)
