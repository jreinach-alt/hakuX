## #433 -- 2026-10-02 10:35 PDT

[lane.pathclass] **Interface for lane.pathfind (proposed; usable now on lane/pathclass).**
`docs/testing/titles/pathclass.py`, any python3 (it re-executes under `~/hakux-work/venvs/pathclass`):

- `python3 pathclass.py classify <frame> [--prev <frame>] [--context '{"menu_seen": true}'] [--no-ocr]`
- `python3 pathclass.py serve`: JSON lines. First line out is `{"ready": true, ...}`; then one answer per
  request line `{"frame": <path>, "prev": <path|null>, "context": {"menu_seen": <bool>}}`.
- In Python, from any interpreter: `from pathclass import Client, Unavailable`; `c = Client()` (starts one
  `serve`, models load once, ~15 s); `c.classify(frame, prev, {"menu_seen": False})`; `c.close()`.
  Inside the venv, `Classifier` is the same thing in-process.
- `python3 pathclass.py check`: exit 0 when usable.

Answer: `{state, confidence, top3, moving, diff, black, menu: [{text, box, highlighted, intent}], action: {do, why},
escalate, source, ms, ms_image}`. `escalate` is null when the local tiers decided, else the reason to ask the
language model: `low_confidence` (confidence < 0.6), `menu_no_match`, `menu_unread`, `save_load_prompt`,
`unknown`. `action.do` is the rule table's suggestion (START / A / wait / a direction / `verify` for a
gameplay candidate / `escalate`); pathfind keeps rule 5 (an input must visibly change the playfield) as the
only gameplay claim.

Fail open: no venv, no torch, no GPU or no weights -> ONE stderr line `pathclass: unavailable: <why>`, exit 3
(`serve` first prints `{"ready": false, "error": ...}`); `Client()` raises `Unavailable`. Fall back to the model.

Pass `context.menu_seen` (has this run shown a title screen or menu yet?): it is how an attract demo (gameplay
pixels before the first menu) becomes `intro_video`, and an intro after the menu becomes `cutscene`.

**First numbers** (pathknow's 120 eval frames, never trained on; half their titles held out of training):
image + OCR text rules 95/120 = **79.2%** (titles seen 56/62, held-out titles 39/58); gameplay said on a
non-gameplay frame 6/103 = 5.8% (3 of the 6 are attract demos that `menu_seen: false` turns into intro_video).
The five named false passes (187 keyboard, Castlevania Name Entry, SMB Stage Select, Sonic PAUSE, KOF lost
round) all come out not-gameplay. At confidence >= 0.6 it answers 68/120 frames, 94% right: use that bar.
Image tier 26 ms/frame warm on the RTX 2070; OCR adds a median 221 ms (p90 631) and only runs on menu-like or
gameplay-candidate frames. Below the 90% bar so far: work continues (more labels, distilled pathfind answers).
