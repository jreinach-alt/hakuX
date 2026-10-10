# ghlive1010 -- AGENTS.md: GitHub is up; the forge is the working space by choice (#433, 0.5)

State: ready

Lane: ghlive1010          Issue: none (docs fix, #433 umbrella)
Base: master @ 1878dbf06d
Files: AGENTS.md, docs/lanes/ghlive1010/PR.md
Prediction: none: documentation only
Needs device: no    Needs NDK: no
Release note: none. Documentation only.

AGENTS.md still said GitHub was suspended (since 2026-09-29) in its overview and in the heading of "The forge", and
told readers to wait for a return procedure. GitHub has been back since 2026-10-05. The forge remains the place of
work by the owner's choice, to keep GitHub's transaction volume down, and `hakux-github-gateway.timer` mirrors it to
GitHub every 15 minutes. Every session and lane reads this file first, so the stale text led readers to treat GitHub
as unavailable.

This change states the current setup: GitHub is up; the gateway is the one job that writes to it; where its log is
and how to tell it has stopped; Actions stays off; no `gh` calls to github.com. Nothing else in the file changes.
