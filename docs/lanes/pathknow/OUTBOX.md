## #433 -- 2026-10-02 09:45 PDT

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

The hints follow in Part 2 (about 11:30): `docs/testing/titles/pathknow/hints/`.
