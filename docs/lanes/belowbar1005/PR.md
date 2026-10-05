# belowbar1005: the #804 fence wait is not what holds Buffy, NG Black or DOA3 below the bar; their bounds are the vCPU, the GPU, and the GPU on one stage (#433)

State: ready

Lane: belowbar1005          Issue: #433
Base: master @ d32c35d3ce
Files: docs/lanes/belowbar1005/NOTES.md, docs/lanes/belowbar1005/OUTBOX.md, docs/lanes/belowbar1005/PR.md, docs/lanes/belowbar1005/decompose.py, docs/lanes/belowbar1005/fetch_runs.py, docs/lanes/belowbar1005/find_results.py, docs/lanes/belowbar1005/retro-buffy.steps.jsonl, docs/lanes/belowbar1005/retro-doa3.steps.jsonl, docs/lanes/belowbar1005/retro-ngb.steps.jsonl, docs/lanes/belowbar1005/routes/bb-buffy-walk.route, docs/lanes/belowbar1005/routes/bb-buffy.route, docs/lanes/belowbar1005/routes/bb-doa3.route, docs/lanes/belowbar1005/routes/bb-ngb.route, docs/lanes/belowbar1005/waitdone.py, docs/lanes/belowbar1005/xfrsurvey.py, docs/lanes/belowbar1005/xfrsurvey.tsv
Prediction: none: env A/B and telemetry soaks with no golden; the A/B's decision rule is in NOTES.md "Step 2", committed (097eb9567d) before the first request
Needs device: yes (Nova, via request.sh; 4 soaks run)    Needs NDK: no
Release note (none): analysis only; no emulator code.

**Builds first.** The Buffy and NG Black runs that screened below the bar (pathfind retro-buffy, retro-ngb, 10-04)
ran ref 39fc5d0a57, async794's head, which does not contain the #804 fix. Only retro-doa3 had it
(5e16698c99). Read from dispatcher.log's install lines; held runs record no ref.

**The fence wait, per title** (one apk, d32c35d3ce, `HAKUX_OCCL_LOG` on every run):

| title | reads occlusion queries? | wait blocks? | runs |
|---|---|---|---|
| Buffy | no (0 lines, both arms) | never runs | 1-1791212323 (WAIT=0), 1-1791212327 (WAIT=1) |
| NG Black | 1-3 in ~4% of frames | no: pend=0 on 190/190 reads | 1-1791212834 (perflog) |
| DOA3 | no (0 lines in 360 s) | never runs | 1-1791212838 (perflog) |

Buffy's pair read 0.83 vs 0.67 with the code under test executing in neither arm: the gap is where the route's
walk ended (courtyard vs forest path), which is why the share alone cannot judge an A/B on this route.

**Bounds** (near30/fps20786 decomposition, Nova, regimen default):

| title | bound | evidence |
|---|---|---|
| Buffy | vCPU | slow rows: guest busy 27-31 of 37-38 ms, renderer idle 15-24 ms; vCPU asleep 6-12 ms tracking the render thread |
| NG Black | GPU | F = GPU + ~4 ms; GPU 680 MHz in play; GPU 23.9 ms/frame, **11.7 of it outside render passes**; no surface-download finishes |
| DOA3 | GPU, dojo stage | 58.7 ms GPU/frame (render 33.2 + non-render 25.5) + one synchronous download-if-dirty per flip (Fin 30 ms); other stages 35-50 fps |

**Cross-title** (`xfrsurvey.py` over 14 days of perflog soaks): non-render GPU time is 5-18 ms/frame in ToeJam,
Agent Under Fire, DOA Ultimate, NG Black, Otogi, DOA3, Crash Twinsanity, Halo 2 and Black, ~0 in the rest. It
does not follow the render-pass count. Nothing measures what is in it yet; timestamps around uploads, copies and
conversions are the recommended next step (first by P x win).

**Device side effects** (NOTES "Side effects"): held sessions on the Nova ran this lane's builds between requests,
including the perflog apk (09:15-09:53 and from 10:44 PDT). I withdrew a third perflog soak for that reason; a
plain-master restore request is queued.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
