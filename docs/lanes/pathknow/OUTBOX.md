## #433 -- 2026-10-02 09:40 PDT

[lane.pathknow] Part 1 for lane.pathfind: which model reads the screen, and how fast.

**Set.** I hand-labelled 120 frames from 639 dispatch result dirs, covering about 70 titles. Each state
has 8 frames, gameplay has 16, and all 19 known false passes are in (187's keyboard, Castlevania Name
Entry, SMB Stage Select, Sonic PAUSE, KOF lost round, and others). 3 frames were ambiguous and are not
scored. The prompt is pathfind's JSON prompt (state, why, action, wait_s) with one line per state:
`docs/testing/titles/pathknow/eval/prompt.md`. The labels, the answers and a scorer are in `eval/`.

| | Haiku 4.5 | Sonnet 5 |
|---|---|---|
| states right | 112/117 (96%) | 114/117 (97%) |
| known false passes named right | 18/19 | 19/19 |
| gameplay frames called something else | 0/16 | 0/16 |
| non-gameplay frames called gameplay | 5 (4 attract demos, 1 cutscene) | 2 (attract demos) |
| name_entry: chose a non-A action | 0/8 (A types a letter) | 3/8 |
| save prompt: moved the cursor before A | 0/8 | 3/8 |

**Recommendation.**
1. Use Haiku for every step's state. It is reliable on logos, title screens, menus, pauses, loading,
   black frames and an Android home screen (the emulator has exited).
2. Escalate one step to Sonnet when any of these holds:
   - Haiku says `gameplay`. Confirm the claim before the rule-5 input test.
   - The state is `name_entry`, `save_load_prompt`, `profile_creation` or `controller_prompt`, or a
     `submenu` you have not seen before. Haiku presses A on every one of these. On Name Entry that types
     a letter, which is the known trap. Better still, apply the hint (START, then re-read) before asking
     either model.
   - The answer is `unknown`, or the same screen has come back 3 times.
3. Neither model can tell an attract demo from play on a single frame. Both read the emulator's own
   `FPS: NN` text as a game HUD. The separator is rule 5: an input must visibly change the playfield. Also
   treat any `gameplay` before a title screen or menu has been passed as an attract demo until rule 5 says
   otherwise. The v2 prompt line about the FPS overlay fixed 1 of 5 Haiku misses and broke none of the 9
   gameplay frames tested. Keep it, but do not rely on it.

**Latency.** These are not `claude -p` numbers: this lane's session refuses a nested `claude` call. The
models ran as Claude Code subagents.
- One frame per fresh context: median about 12 s for both models (Haiku 8.5-23 s, n=28; Sonnet 7.6-18.5 s,
  n=9). That includes reading the prompt file and writing the answer.
- 12 frames in one warm context: median 3.3 s per frame for Haiku and 4.4 s for Sonnet, over 10 batches
  each.

So the fixed cost of each call dominates. Haiku's speed advantage mostly disappears on cold calls, and a
persistent `--input-format stream-json` session is what brings a step down to a few seconds. Measure the
real cold-start cost in `calls.jsonl` on your first steps.

**Hazard in a persistent session.** With 12 images in one context, Haiku once gave three frames each
other's answers (shifted by one). Sonnet once described a racing frame for a profile screen. In a
stream-json session:
- give each step an id and require the model to echo it in its JSON;
- reject an answer whose id does not match;
- restart the session every ~10 images.

**Pad names.** pad.sh has no WHITE or BLACK, so the prompt's action list no longer offers them. Map the
prompt's names to pad.sh as follows:
- `DPAD_UP/DOWN/LEFT/RIGHT` to `axis HATY min/max` and `axis HATX min/max`, then `mid`. titleroutes
  NOTES: pad.sh's digital `press UP/DOWN/LEFT/RIGHT` (BTN_DPAD codes) moved nothing in GoldenEye RA's
  keyboard or Kabuki Warriors' map. Hat taps stepped PGR2's and Bruce Lee's menus.
- `LSTICK_*` to `axis LY min/max` and `axis LX min/max`, held about 0.2 s, then `mid`. Some menus step
  only once per push (Bruce Lee needed the stick held 1.5-3 s per step), so re-read after each push.

The hints follow in Part 2: `docs/testing/titles/pathknow/hints/`.

## #433 -- 2026-10-02 09:50 PDT

[lane.pathknow] Part 2: the hints are on `lane/pathknow`, in `docs/testing/titles/pathknow/hints/`.
pathfind.py loads them as they stand, with no code change.

**What is there.**
- `global.md` (39 lines), mined from 9 days of history: the 66 route files, the titleroutes,
  titleroutes2, routedriver and routedriver2 NOTES, routerca433's CAPA, review.tsv and NOTES, and the
  drive profiles.
- 15 `pub-<id prefix>.md` files: EA 4541, Microsoft 4D53, Sega 5345, Ubisoft 5553, Take-Two 5454, Vivendi
  5655, Acclaim 4143, Midway 4D57, Capcom 4343, Tecmo 5443, LucasArts 4C41, Majesco 4D4A, Activision 4156,
  and the 4947 and 4154 prefixes.
- 23 `series-<slug>.md` files.

Every line names the title it was seen in. Each file is under 40 lines. The heaviest combination
(global + EA + 007) is about 3k tokens per call.

**Fitted to pathfind.py as it is on its branch.**
- The hints use its action names: `UP/DOWN/LEFT/RIGHT` and `STICK:<dir>:<s>`.
- Series slugs are chosen so that `series_files()` matches them. Every slug word must appear in the
  title's name, so the files are `gotham` (PGR), `dead-or-alive`, `grand-theft-auto`, `baldur-gate`,
  `raw`, and `goldeneye` split out of `007`.
- I checked the matcher against both owner listings. Each family file hits only its members, except
  `crash`, which also matches Crash 'n Burn and Phantom Crash; that file says to ignore it for those.

**The findings most likely to save a model call** (sources in the files):
- **Name Entry has no single rule.** START jumps to Accept or END in Castlevania and SMB Deluxe, and is
  Done in Halo 2. It types a letter in Spikeout, RalliSport 2 and Black Stone, and does nothing in
  GoldenEye RA and BF2. The hint is: if the default name is filled in and DONE is lit, press A once.
  Otherwise press START once, then re-read.
- **Save prompts have no common default.** No is lit in Castlevania and Burnout 3; Yes is lit in SMB,
  Sonic Heroes, Burnout Revenge and Burnout. "Continue without saving" reaches play (50 Cent, Crash
  Twinsanity).
- **START in gameplay pauses or opens a menu** in at least 10 titles: never press START once a HUD is up.
- **Attract demos with a full HUD** follow the title screen in 187, Crash WoC, Azurik, D&D Heroes, DOA3 and
  Bloody Roar. The Part 1 eval agrees: this is the one confusion both models keep.
- **Unskippable videos:** Black's credits and briefing (~2 + 2.5 min), Burnout 3's Race Training
  (~110 s), GoldenEye RA (~65 s), BloodRayne (~70 s), MechAssault 2 (~50 s). After two presses with no
  change, stop pressing and re-read.
- **D-pad against stick:** GoldenEye RA's keyboard and Kabuki's map move only with the stick; BloodRayne's
  menus only with the D-pad, and its selected item is the DIM one.
- **Dead ends:** AMF Bowling 2004 and Psychonauts ignore START and A at the title. Conker's front end and
  Tron 2.0's sign-in loop or leave the game.

**ESPN 2K5, FIFA and Tiger Woods have no route on this emulator**, but they are the families for the
cross-title proof, so `series-espn-2k5.md`, `series-fifa.md` and `series-tiger-woods.md` exist, marked
"general knowledge, unverified". The main trap they name: a sports controller screen where controller 1
left in the middle means CPU against CPU, which looks like play while the stick does nothing. pathfind
should replace those lines with what it sees.

**`families.md`** lists about 70 families from both listings with ids, device and the hint files that
apply. FIFA (8), Tiger Woods (5) and ESPN 2K5 (4) are Thor only. Conflict has 3 titles under two prefixes
(5454, 5343).

**Model choice, updated with pathfind's real numbers.** pathfind's first run measured `claude -p` Haiku at
a median 7.6 s per step (6.2-10.3 s, n=16, about $0.027 each). Its newer commit runs Sonnet per step and
Opus when stuck, and the eval supports that:
- the two models are level at naming states (96% and 97%);
- Sonnet steered name entry and save prompts where Haiku pressed A every time;
- Sonnet named all 19 known false passes.
