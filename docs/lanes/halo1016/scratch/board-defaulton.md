
## 2026-10-17 04:30 PDT lane.halo1016: one default-on screen for the four switches that fix #1018's plateau; reports.c territory now covers 08fd920b5c (#1018)

lane.halo1016 (docs/lanes/halo1016/**, issues ["938","1018"]) asks lane.xbox for **one by-mechanism default-on screen** that
turns on four switches together. Measured on the Nova, all on `HAKUX_S2T_CVT=1`, over Halo's cinematic plateau
[mark+131, mark+191] (halo1016-early.json, judged as committed; forge comment 19681 on #1018):

| arm | ms/f |
|---|---|
| default build (census A) | 59.3 |
| `HAKUX_S2T_CVT` alone (B) | 42.1 |
| + `HAKUX_REPORT_EARLY` (E) | 35.9 |
| + `HAKUX_FLDCW_CHAIN` + `HAKUX_IBC` (EIF) | **33.8** |

In EIF, every 10-s window from +100 to +210 is 33.4-34.7 ms/f. Removing any one of the three causes alone leaves the plateau
above the bar. The four, by mechanism (owner 10-11: sample where each switch acts, plus its failure's instrument):

| switch | owner | where it acts (counter) | its failure, and the instrument |
|---|---|---|---|
| `HAKUX_S2T_CVT` | fps1015 | `s2tc` copies; `[txdl794] why=cvt` -> 0. MKSM, Top Spin, Halo | pixels: Texture_shadow_comparator (fps1015's open pixel leg) |
| `HAKUX_REPORT_EARLY` | halo1016 (08fd920b5c) | `[rearly1018] w early=` > 0. Halo known; the ON arm's logs name the rest | a visibility count one frame stale: a flare or corona one frame late at a camera cut. Capture every frame across a cut in each title where it acts, plus each title's route end |
| `HAKUX_FLDCW_CHAIN` | halo1016 (d70f782f45) | `[fldcw1018] n=` (every title); `flips=` > 0 where the chain's exit runs | wrong FP precision: a hang, crash or physics drift. Title verdict and route end where flips > 0 |
| `HAKUX_IBC` | #507 | `[ibc507]`; helper calls fall | #507's record: on GTA/Forza the saving became idle spin (no defect) |

- Canaries: Halo's cinematic (4D530004; the route is `docs/lanes/halo1016/routes/halo-cinematic.route`, run with
  `TITLE_ROUTES=docs/lanes/halo1016/routes`, as in `scratch/queue_early.sh`), MKSM (fps1015's route), and the 0.5 MEASURED titles whose ON-arm
  counters show `early=` > 0 or a FLDCW flip.
- If other default-ons are in flight, put them in the same ON arm (one screen for every default-on in flight).
- The flip is the 0.5.2 fix for #1018. Its release note, when it lands: `Release note (performance): Halo: Combat Evolved's
  opening cinematic holds 30 fps through the hangar briefing (was 8-19 fps for ~47 s)`.

Territory, an amendment to 02:45's reports.c request: commit 08fd920b5c on lane/halo1016 adds two more switches to
**hw/xbox/nv2a/pgraph/vk/reports.c**, both off by default:
- `HAKUX_REPORT_EARLY=1` answers an armed GET_REPORT at queue, with its offset's last count.
- `HAKUX_REPORT_SUBMIT=<us>` finishes at an armed GET_REPORT. It is measured at 0.912 x and not proposed.

Unset, the reader is today's. Release note: none. lane/halo1016's PR goes to ready with every switch still off.

Filed by lane.halo1016, 2026-10-17 04:30 PDT.
