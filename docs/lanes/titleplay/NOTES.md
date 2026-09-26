# lane.titleplay: gameplay frame rate under scripted input

Issue #397. Brief: drive each title into real gameplay, confirm it from the
frames, measure it (the owner, 2026-09-26). Base `a5b5b628f2`.

## Plan

- Pass 1: every title of population 1 (the 20 staged 2026-09-26) on the
  survey route, each on the device that holds its ISO, 420 s.
- Review each run's frames; record what each shows.
- Pass 2/3: a title route for each title not reached.

## Tools

- `tools/isoseen.py [substr]`: every soak title a past dispatch result ran,
  per device, and whether the worker found the ISO. Reads results only.
