# lane.xbox OUTBOX

ISSUE-REQUEST: Halo: Combat Evolved: the ship's rear lighting shows through the front of the ship in the opening cinematic

Evidence: owner hands-on comparison against an original Xbox, 2026-10-17 ~10:00 PDT (dispatch/board-requests/xbox.md, filed by lane.xbox 2026-10-17 10:05 PDT, item 2).

Body:

In Halo: Combat Evolved's opening cinematic, when the camera cuts from behind the ship to its front, the directional lighting on the back of the ship stays visible through the front of the ship. On an original Xbox the same shot does not show it.

Seen on the Retroid Pocket Nova on 0.5.1-rc1; compared against the console on 2026-10-17.

Not game-blocking. Priority: low. Not investigated yet.

Tracker row (board, nv2a_issues.toml), to add once the number is allocated -- same shape as [issue.939]:

```
[issue.<N>]
title = "Halo: Combat Evolved: the ship's rear lighting shows through the front of the ship in the opening cinematic"
suites = []
no_suites = "A visual defect in a commercial title, not yet identified, so no pgraph suite is known to cover it."
disposition = "defect"
status = "open"
dispatch_state = "blocked"
blocked_on = "OWNER HOLD (owner 2026-10-17 ~10:00 PDT): low priority, not game-blocking, same class as #939; do not dispatch. Release only on the owner's word."
status_note = "lighting/draw order (owner's read): the ship's rear directional light is drawn through the hull after the camera cuts from behind to the front; confirmed against the console 10-17."
```

0.5.2 text: a KNOWN_ISSUES.md player line under Games, next to #939's, with the link (needs a lane since KNOWN_ISSUES.md only moves through the fold queue -- lane.release052 folded (160728983a) without claiming #938/this one; left for the next docs lane or lane.local to pick up alongside dropping the closed #938 entry).

DONE 10:16 PDT (hostops): #938 closed (comment + close, verified-on-hardware per the owner) -- gh issue close 938 succeeded directly, no allocator needed for a close. This new issue could not be filed directly: the forge shim refuses `gh issue create` and requires this ISSUE-REQUEST line, filed through lane.local's allocator. Flagged to lane.local via SendMessage.
