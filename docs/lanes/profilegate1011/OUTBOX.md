# lane.profilegate1011 -- OUTBOX

Patches this lane could not land itself because the target file is held by
another lane. Apply directly; this lane does not touch these files.

## FOR lane.failgate: `docs/testing/title_verdict.py` -- void a find-route run

#433's profile gate (`titlestate.py admit()`) added a `find_route` field to
`request.json` for any run queued with `--find-route` (request.sh) or run by
`pathfind.py` while proving a route blind (see `docs/lanes/profilegate1011/
NOTES.md`). Those runs are not a confirmation/screening soak of a finished
route -- they exist to discover or re-prove a path, and may play through
states (e.g. a `first-run` route not yet known to reach `mark gameplay`
cleanly) that a real Playable judgement should not score. Nothing currently
reads `find_route` outside `titlestate.py`/`titlestate_selftest.py` (checked
via `grep -rl find_route docs/testing`), so a find-route run that happens to
reach `mark gameplay` and clear the fps bar would be written up as a normal
`Playable` verdict today.

`judge()`'s existing VOID block (`title_verdict.py` lines 488-500) is the
right mechanism -- it already short-circuits `pass`/`rating_candidate` to
False/None via the `fails.append("void: " + void)` line later in the
function (line 752-753), and every downstream reader (`titles/table.py`,
`status_html.py`, `ab_compare.py`, the Playable ledger) consumes only the
written `verdict.json`'s `pass`/`rating_candidate`/`void` fields, so voiding
here is the only patch needed -- no other reader requires a change.

Patch (lines 491-500 today):

```python
    void = None
    if req.get("find_route"):
        void = "find-route: %s" % req.get("find_route")
    rframes = glob.glob(os.path.join(rdir, "route-frames", "*.png"))
    m = re.search(r"^(display-covered|display-black|not-foreground): .*$", runlog, re.M)
    render_black = re.search(r"^render-black: .*$", runlog, re.M)
    if void:
        pass
    elif m:
        void = m.group(0)
    elif render_black:
        pass    # black frames, display 0 clear and hakuX focused: hakuX's own failure
    elif rframes and all(os.path.getsize(f) < BLACK_FRAME_B for f in rframes):
        void = "display-black: all %d route frames under %d B" % (len(rframes), BLACK_FRAME_B)
```

`req` is already loaded earlier in `judge()` (line 456), before this block,
so no new read is needed. `find_route` is request.sh's/pathfind.py's free
text reason (e.g. `"proving a3-route for the first time"`), so the voided
message is self-explanatory without a lookup.

Not done by this lane: editing `title_verdict.py` itself (held by
lane.failgate), or any downstream reader (none of them need a direct change
once this lands -- confirmed by reading `titles/table.py`, `status_html.py`
and `dispatch_gate.py`'s own reads of `verdict.json`/`request.json`, all of
which key off fields `judge()` already produces).
