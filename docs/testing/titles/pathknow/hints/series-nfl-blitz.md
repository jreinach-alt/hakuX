# NFL Blitz (Midway, arcade football): hints from the 10-05 first-run claim of NFL Blitz 2002

- Main menu, top to bottom: QUICKPLAY (highlighted), EXHIBITION, SEASON, TOURNAMENT, OPTIONS, BLITZ THEATER, MEMORY (NFL Blitz 2002, 10-05).
- QUICKPLAY goes to SELECT TEAMS (two teams, both Arizona in the 10-05 run; no controller icons were shown under them). A on FORWARD goes to loading and then kickoff. On that path no quarter-length screen appeared: the first quarter's clock read 1ST 2:00 (NFL Blitz 2002, 10-05, frame 016). So the period length is NOT set on the Quickplay path.
- Period length (VERIFIED 10-05, run hold2): OPTIONS on the main menu, then PLAY OPTIONS, then QUARTER LENGTH (1, 2, 3, 4, 5 minutes; 5 is the longest offered). Right on the item moves the value. Set 5, then back out to the main menu before QUICKPLAY. Five minutes is shorter than a 600-s hold: the hold meets quarter breaks, which the period_break rule handles.
- Play call: the pre-snap menu lists plays (SUB ZERO, STUFF IT, BANK, SAFE COVER, ...). A picks the highlighted play; A snaps the ball. A formation with the HUD and the clock up and no menu, before the snap, is not live play (the 10-05 claim read it as gameplay four times and the stick probe moved nothing).
- A "HOW TO PLAY" tip panel can cover the field after kickoff: A clears it.
- A replay card after a play is a period_break for this family's hold: START, then A.
