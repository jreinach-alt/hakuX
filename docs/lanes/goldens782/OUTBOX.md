# goldens782 OUTBOX (#782)

Offline result, no device time used. Full reasoning is in `NOTES.md`; the generator is `make_table.py`.

## Result

- **54 Thor-made goldens still open** (Forza moved to a Nova-made golden on 10-03, so the 55 in #782 is now 54).
- Usable on the Nova, frame-confirmed: **2** (Castlevania `4B4E002D`, Spikeout `53450029`).
- Known to read damaged: **1** (Forza, replaced by its Nova golden `5725499d3c7f`; the Thor golden is no longer in use).
- Likely damaged: **1** (`4D53001E`, `.sig` files in the golden; not frame-tested).
- Unknown: **51**.

No `rejected` record exists for any title on either device, so the composer's rejection path has never run.

## Fix pick (P x titles, see NOTES)

| option | P | titles cleared | P x titles | status |
|---|---|---|---|---|
| (a) re-sign | ~0.1 | up to 54 | ~5 | blocked: the signature algorithm did not reproduce (75 combinations against the Thor key, no hit), and the Nova key is not on disk |
| (b) per-device `rejected`, first-run fallback | ~0.9 | up to 51 | ~46 | runnable now; needs per-title `rejected` records |
| (c) one `eeprom.bin` | ~0.9 | 54 fixed, up to 30 broken | ~49 gross | device decision; proposed to lane.local |

I did not run (a), because it has no reference to check against. (b) is the next step, and it needs no new code:
`titlestate.py record <dev> <tid> rejected <run>` already removes a golden from the composer.

## Verify on the Nova (step 3)

- **Forza, returning on a re-composed golden: loads.** Run `docs/lanes/pathfind/runs/forza-run2` (held run 2): PROFILE
  SELECT, "Default" lit, no damaged message, A to the main menu. Golden `5725499d3c7f`, Nova-made. Recorded in pathfind
  OUTBOX 10-03 13:55.
- I did not queue a new device run, because that criterion is already met by run 2 and a repeat would spend Nova time
  without a new question. The one open question that a run would answer is `4D53001E`'s status (the "likely" row),
  which I've left for lane.local to schedule.

## The table

| title | title id | golden | signs with HDD key | evidence |
|---|---|---|---|---|
| Burnout | 41430006 | bc52aa2f6fd8 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Alias | 41430016 | 5db249c6ee24 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Petit Copter | 41510001 | 8b6326b1bfc8 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Shin Megami Tensei: Nine | 41540002 | 2b6c57485f1e | unknown | no .sig in the golden; not frame-tested on the Nova |
| Galleon | 41540004 | 169dc045ed29 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Tony Hawk's Pro Skater 2x | 41560001 | eb5a77c99ffd | unknown | no .sig in the golden; not frame-tested on the Nova |
| Tony Hawk's Pro Skater 3 | 41560004 | 02ceef03a100 | unknown | no .sig in the golden; not frame-tested on the Nova |
| AMF Bowling 2004 | 42530009 | 1b96f2b25d76 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Capcom Classics Collection Vol. 2 | 43430019 | ebc9d653fa70 | unknown | no .sig in the golden; not frame-tested on the Nova |
| SSX Tricky | 45410004 | d72c8ec33898 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Buffy the Vampire Slayer | 45410012 | c6b6ec3cb8be | unknown | no .sig in the golden; not frame-tested on the Nova |
| Burnout 3: Takedown | 4541005B | 3853ca5a2387 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Battlefield 2: Modern Combat | 45410062 | dcf7307455f0 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Black | 45410083 | 46308c8d9a70 | unknown | no .sig in the golden; not frame-tested on the Nova |
| 25 to Life | 45530018 | c623e1b7bc4a | unknown | no .sig in the golden; not frame-tested on the Nova |
| Otogi: Myth of Demons | 46530002 | 247ba69fcbc2 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Dungeons & Dragons: Heroes | 49470013 | 8cb83326dc54 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Castlevania: Curse of Darkness | 4B4E002D | 20235e93867b | **no** | frame-confirmed: lane.local returning run 1-1791056447-lanelocal-2267406 reached play on the Nova |
| Mercenaries | 4C410015 | d17c32a300cf | unknown | no .sig in the golden; not frame-tested on the Nova |
| BloodRayne | 4D4A0001 | 208af578e883 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Psychonauts | 4D4A0012 | f978f6019d40 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Project Gotham Racing | 4D530003 | c151b9a02c1b | unknown | no .sig in the golden; not frame-tested on the Nova |
| Azurik: Rise of Perathia | 4D530007 | 3a92dca37ccf | unknown | no .sig in the golden; not frame-tested on the Nova |
| Blinx: The Time Sweeper | 4D530013 | bad5c9e7e167 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Brute Force | 4D53001E | 6e97d00a8a46 | **yes (likely)** | `global-data.sig`, `global-gameflags.sig`; same kind as Forza's `CarIcons.sig`. Not frame-tested |
| Crimson Skies: High Road to Revenge | 4D530021 | 42b0f68410a3 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Midtown Madness 3 | 4D53002A | 424a68037d87 | unknown | no .sig in the golden; not frame-tested on the Nova |
| RalliSport Challenge 2 | 4D530039 | e84d24bb437c | unknown | no .sig in the golden; not frame-tested on the Nova |
| Amped 2 | 4D530041 | f90786b6e0f5 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Phantom Dust | 4D530046 | 20d56308a665 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Project Gotham Racing 2 | 4D53004B | 7e22330b1935 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Conker: Live & Reloaded | 4D530051 | d18aa0a71b74 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Grabbed by the Ghoulies | 4D530053 | 55758513a9e3 | unknown | no .sig in the golden; not frame-tested on the Nova |
| MechAssault 2: Lone Wolf | 4D53006B | aeffd81ffd76 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Arctic Thunder | 4D570002 | 493866247e6b | unknown | no .sig in the golden; not frame-tested on the Nova |
| Gauntlet: Dark Legacy | 4D57000E | f393e74eb225 | unknown | no .sig in the golden; not frame-tested on the Nova |
| (not in CSV) | 5345000A | 8552a01fbd57 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Spikeout: Battle Street | 53450029 | c714fbc41e16 | **no** | frame-confirmed: pathfind runs/spikeout-hold, returning on the Thor-made golden, PASS on the Nova |
| Sonic Heroes | 5345002B | 7077776b9746 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Super Monkey Ball Deluxe | 53450038 | 291732127556 | unknown | no .sig in the golden; not frame-tested on the Nova |
| KOF: Maximum Impact: Maniax | 534E0007 | 97bb36646cf1 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Bistro Cupid | 53550001 | 0becb04b1221 | unknown | no .sig in the golden; not frame-tested on the Nova |
| (not in CSV) | 54430001 | 220536a66fe2 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Ninja Gaiden | 54430003 | ea05ebe518c2 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Dead or Alive 1 Ultimate | 54430006 | 3b8e57389755 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Plus Plumb 2 | 544B0004 | ed7d0165f40b | unknown | no .sig in the golden; not frame-tested on the Nova |
| Barbarian | 54530002 | eea65ed861a2 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Grand Theft Auto: San Andreas | 54540082 | 7da19befd45b | unknown | no .sig in the golden; not frame-tested on the Nova |
| Family Guy: Video Game! | 545400B0 | fc1555366ead | unknown | no .sig in the golden; not frame-tested on the Nova |
| Deathrow | 55530004 | c6cef35af601 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Tork: Prehistoric Punk | 55530040 | 6cb2e3c07c9e | unknown | no .sig in the golden; not frame-tested on the Nova |
| Bruce Lee: Quest of the Dragon | 56550016 | 71080c6c5dec | unknown | no .sig in the golden; not frame-tested on the Nova |
| Crash Twinsanity | 56550036 | e089ebabfb72 | unknown | no .sig in the golden; not frame-tested on the Nova |
| Alien Hominid | 5A440004 | c50c0ad5b571 | unknown | no .sig in the golden; not frame-tested on the Nova |

Counts: yes (likely) 1, no 2, unknown 51. "No `.sig`" is not proof of unsigned: Forza's signature also sits in a 20-byte
trailer of `Garage.bin`, which the `.sig` test cannot see.
