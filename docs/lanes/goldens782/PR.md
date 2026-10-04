# goldens782: offline survey of the Thor-made goldens on the Nova (#782)

State: ready

Lane: goldens782          Issue: #782
Base: master (fold-time)
Files: docs/lanes/goldens782/NOTES.md, docs/lanes/goldens782/OUTBOX.md, docs/lanes/goldens782/TABLE.md, docs/lanes/goldens782/make_table.py
Prediction: none: offline survey, no emulator code and no device run

Counts over the 55 Thor-made goldens (54 open after Forza moved to a Nova golden): usable on the Nova 2, known damaged 1, likely damaged 1, unknown 51. The fix pick is (b), per-device `rejected` records through `titlestate.py record`, which needs no new code. Open: golden 4D53001E is the only run that answers a question, and lane.local schedules it.
