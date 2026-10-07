# OUTBOX: dispatchgate1006 (harness defect, no issue)

## 2026-10-06 ~18:50 PDT: attempt 2, the 18:10 review's three items fixed; ready again; still SHADOW

1. **Blocking item fixed: a newer commit is no longer a fix.** A fix counts only from a row of
   `pm/title-fixes.tsv` (yours: `title_id, gate, fix_commit, set_by, date, why`; set_by lane.local
   or owner; template `docs/lanes/dispatchgate1006/title-fixes.template.tsv`), or when the commit
   changes the title's own `docs/testing/titles/pathknow/paths/<TID>.json`. It must also answer every
   failed gate, be newer than the verdict, and be in the build if it touches anything outside `docs/`.
   **BELOW_BAR never gets a Playable attempt.** Its fix allows TELEMETRY or VALIDATION, and a verdict
   after the fix that clears the bar moves it out of BELOW_BAR. Against the real records, DOA3, Hulk UD
   and LOTR ROTK with `fix:6cef37f426` all DENY. The fixture `DOA3 PLAYABLE_ATTEMPT citing
   fix:6cef37f426 (an unrelated fold) -> deny` is green, and its mutant (the reviewed rule) ALLOWs.
   **`pm/title-fixes.tsv` does not exist on the host.** Until you create it, a Playable attempt is
   admitted only on a fix to the title's own path file.
2. **No `gh`.** The registry reads the forge's open issues over HTTP at 127.0.0.1:3330 with
   `forge/tokens/jobs.token`. On the host that is 252 open issues, `forge=ok`. If it is unreadable, the
   header says `forge=unreadable` and every issue hold stays active. A selftest leg fails if any of the
   three files invokes `gh`, and a runtime leg records every subprocess while it builds.
3. **Re-run and quoted (NOTES section 4):** selftest `59 legs, 59 green, 0 red`; CI fragment
   `4 passed, 0 failed`; `verify_patches: all pass`; plan-check on the evening and replan plans gives
   rc 2 with 7/7 and 14/14 rows rejected; `live_incidents.py` now builds into a scratch file and reports
   `host registry ... untouched: True`.

**Fight Club / RalliSport:** after a fresh build of the host registry, 5655002F is `PLAYABLE`
(ledger 2026-10-06 18:05, new column `flicker=UNCHECKED`), and 4D53000F is `EXCLUDED`
(`flicker=HOLD:ralli-flicker-804`).

**Registry now (built 2026-10-07T01:03:19Z, forge ok, 454 sources): 951 rows.** PLAYABLE 33,
EXCLUDED 27, PENDING_OWNER 1, CRASH_OR_HANG 13, BELOW_BAR 35, FAILED_HARNESS 23, VOID 0, UNSCREENED 819.
The BELOW_BAR, EXCLUDED and CRASH_OR_HANG lists below are unchanged. The only move is Fight Club, from
FAILED_HARNESS to PLAYABLE. Every record resolved to a title id.

**Files to grant:** add `docs/lanes/dispatchgate1006/title-fixes.template.tsv` (under the lane dir).
The five `docs/testing/` files are unchanged in name. Shadow mode only; hold.sh and dispatcher.sh
were not touched.

## 2026-10-06 ~17:40 PDT: done; the gate is built, verified offline, and in SHADOW mode

Nothing refuses anything yet: `pm/dispatch-gate.mode` does not exist. No device was touched and
nothing was queued.

### Files to grant (new files under docs/testing/, literal paths)

- `docs/testing/title_registry.py`
- `docs/testing/dispatch_gate.py`
- `docs/testing/dispatch_audit.py`
- `docs/testing/dispatch_gate_selftest.py`
- `docs/testing/jobs/selftest.d/99-dispatch-gate.sh`

(plus `docs/lanes/dispatchgate1006/**`)

### Patches for lane.local to route (files this lane may not edit)

| patch | file | owner / when |
|---|---|---|
| `docs/lanes/dispatchgate1006/patches/request.sh.patch` | docs/testing/request.sh | grant to this lane or apply; shadow-safe now |
| `docs/lanes/dispatchgate1006/patches/hold.sh.patch` | docs/testing/jobs/hold.sh | lane.harnessfix1006 holds it until its fold after 22:00; shadow-safe |
| `docs/lanes/dispatchgate1006/patches/pathfind.py.patch` + `pathfind_selftest.py.patch` | lane.pathfind's | pathfind applies; adds `--dispatch-class/--because/--build/--order/--valid-end` and a selftest leg |
| `docs/lanes/dispatchgate1006/patches/title_verdict.py.patch` | docs/testing/title_verdict.py | `failing_all` + `fps_ok_share` always present |
| `docs/lanes/dispatchgate1006/patches/hourly_report.sh.patch` | host-tools/hourly_report.sh | lane.local; adds the DISPATCH GATE section (needs this PR folded) |

All six apply and were exercised by `tools/verify_patches.py` ("verify_patches: all pass"):
patched hold.sh takes and logs in shadow, refuses an ungated title hold with exit 3 in enforce,
exempts a `hostupd-*` tag; patched pathfind_selftest passes with its `dispatchgate` leg.

### Host files written

- `pm/owner-holds.tsv` (new; seeded from `docs/lanes/dispatchgate1006/owner-holds.seed.tsv`;
  **lane.local is its only writer from now on**; the owner's word goes in `released` or a new `order` row)
- `pm/title-registry.tsv` (generated; rebuilt by the gate CLI and the audit when stale)
- `pm/.dispatch-gate.key` (0600, the token HMAC key)
- `pm/dispatch-log.tsv` does not exist yet. A patched pathfind_selftest run of mine wrote 32 test rows
  (`SHADOW-DENY 00000000`) into it at 17:10-17:17; I removed the file, which held nothing else, and
  fixed the patch (NOTES section 7).

### Registry (built 2026-10-07T00:27:28Z, forge read ok, 448 sources): 951 rows

PLAYABLE 32 (= every ledger row, all resolved by id), EXCLUDED 27, PENDING_OWNER 1, CRASH_OR_HANG 13,
BELOW_BAR 35, FAILED_HARNESS 24, VOID 0, UNSCREENED 819 (the console inventory; most are on no handheld).

**EXCLUDED (27):** RalliSport Challenge 4D53000F (ralli-flicker-804); Galleon 41540004
(blocked-titles.txt); 25 by `football-last`: NFL Blitz Pro 4D570014, ESPN NFL 2K5 53450030, ESPN NFL
PrimeTime 2002 4B4E0003, NFL Fever 2003 4D530028, NFL Fever 2004 4D53004D, NFL Head Coach 4541008E,
NFL Street 45410048, NFL Street 2 45410057, Arena Football 45410094, Madden NFL 2002/2003/2004/2005/06/
07/08 and Madden 2009 (45410001 45410019 45410036 4541004D 45410075 4541009F 454100AC 4541023B),
NCAA Football 2003/2004/06/07 (4541001D 45410035 45410080 454100A2), **and four soccer titles the
football regex also matches: Club Football 434D0021, Club Football 2005 434D0045, England International
Football 2004 434D0028, FIFA Football 2004 4541003B** (same regex as pathfind.py e383da4992; lane.local
decides whether soccer is "football").

**PENDING_OWNER (1):** Marvel Nemesis 45410089 (regional 4541038A), hold marvel-851.

**CRASH_OR_HANG (13):** AMF Xtreme Bowling 42530014 (#835 #837 open; hold2 SIG_DFL 11), NHL Hitz Pro
4D57001A (#859 open), Whacked 4D530027, Whiteout 4B4E0001, Bruce Lee 56550016, Capcom Classics Vol 2
43430019, Fuzion Frenzy 4D530002, Midtown Madness 3 4D53002A, Project Gotham Racing 4D530003, PGR 2
4D53004B, Sonic Heroes 5345002B, SSX Tricky 45410004, Super Monkey Ball Deluxe 53450038.

**BELOW_BAR (35), fps_ok_share of the latest scored verdict:** 007 Agent Under Fire 0, Amped 2 0.4423,
Amped 0.0861, Arctic Thunder 0.6393, Battlefield 2 MC 0.6655, Black 0, Blinx 2 0.573, Blinx 0.0938,
Blood Wake 0.9958 (audio+hitch), Bloody Roar Extreme 0, Brute Force 0, Buffy 0.5516, Burnout 0.0704,
Burnout Revenge 0.7207, Crash Twinsanity 0, **Dead or Alive 3 0.4394**, **Dino Crisis 3 0.3793**, D&D
Heroes 0, Forza 0.4532 (a pre-#583 verdict: see below), Ghoulies 0.5897, GTA SA 0.746, MechAssault 2
0.2666, Midnight Club II 0, MK Deadly Alliance 0.9955 (hitch only), MK Shaolin Monks 0.4912, NBA Live
2005 0, NFS Most Wanted 0.1937, NHL 2K3 0.6937, Ninja Gaiden Black 0.2495, Otogi 0.3502, Spider-Man 2
0.2895, Star Wars III 0.474, Hulk UD 0.6433, LOTR RotK 0.3329, Tron 2.0 0.9199 (hitch 1064 ms).

**Status not determinable / caveats:** no ledger row, run or intake row failed to resolve to a title id
(0 UNRESOLVED). Caveats: pathfind held runs record no build (`last_run_build` = `unrecorded`); Forza's
BELOW_BAR rests on a verdict from before #583 (the gate's `forza-583-floor` makes any new Forza run
need 10fe2f59a7); Batman Begins, Fight Club and Tecmo Classic Arcade are FAILED_HARNESS "ran but
no scored window" (overnight sweep runs), so the replan's "first run" for them is wrong.

### The incidents, against the real records (tools/live_incidents.py, no log rows)

```
DENY   54430001        PLAYABLE_ATTEMPT  matrix: below the bar (fps_ok_share 0.4394, failing menu_time+fps+hitch) with no fix: TELEMETRY only
DENY   Dino Crisis 3   PLAYABLE_ATTEMPT  matrix: below the bar (fps_ok_share 0.3793, failing menu_time+fps+window_unmeasured) with no fix
DENY   4D53000F        PLAYABLE_ATTEMPT  matrix: EXCLUDED ... + hold: owner hold ralli-flicker-804 ... blocks PLAYABLE_ATTEMPT
DENY   Strike Force    PLAYABLE_ATTEMPT  plan: plan row 10 is rejected by plan_check: last failure (duration+menu_time) has no committed fix since it
DENY   Tron / 5443000D / 4D530041 / 4156002B   owner below-bar holds
DENY   NFL Blitz Pro, NBA 2K3 (ledger), AMF Xtreme (crash hold, #835 #837), Marvel (marvel-851)
ALLOW  Blowout         VALIDATION        (condition: reverse walk at the hangar corner)
```

### Selftest

`python3 docs/testing/dispatch_gate_selftest.py` -> `45 legs, 45 green, 0 red` (every mutant flips its
leg); in the CI harness `env SELFTEST_ONLY=99-dispatch-gate.sh bash docs/testing/jobs/selftest.sh` ->
`2 passed, 0 failed`. `preflight.sh --allow-tracker` -> passed.

### Last 24 h (dispatch_audit.py, 17:26 PDT)

90 title runs reached a handheld with no gate (expected: no gate existed). 462.2 Nova min went to titles
now flagged, 152.7 of them to titles already flagged before the run started (this includes
gpunonrender's telemetry on NG Black and DOA3, which a gated TELEMETRY dispatch would exempt), and
**doa3-rev: 7.8 min, KNOWN BELOW_BAR since retro-doa3**.

### For lane.local, in order

1. Grant the five files; route the patches (table above).
2. Plans: put the title id and the fix sha in each run-order row; run
   `python3 docs/testing/dispatch_gate.py plan-check pm/plan-<...>.md` before publishing. Today's 13:35
   replan rejects every row (NOTES section 6.5).
3. Owner holds: record the owner's word in `pm/owner-holds.tsv` (`released`, or a new `order` row). The
   seeded RalliSport order `owner-1006-1450-ralli` is marked spent (it ran as ralli1006.sh per the note).
4. After a day of shadow rows, set the hold exemption list from the audit's REFUSED tags, then
   `echo enforce > /home/justin/hakux-work/pm/dispatch-gate.mode`.
