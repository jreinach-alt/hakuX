#!/bin/bash
# Every reading of the phase-2 table through condread.py, in the table's
# order. The first id per title is the reading the status page lists
# (statusrows.py, 2026-09-28 07:55 PDT); the rest are the same title's other
# runs, or the same run read another way, that bear on its conditions.
# --under F reads the counters only inside windows slower than F fps (the
# slow play, not menus or cutscenes at 60); --split S reads before/after S.
here=$(dirname "$0")
while read -r title rid rest; do
  [ -z "$title" ] && continue
  case "$title" in \#*) continue ;; esac
  echo "######## $title $rest"
  python3 "$here/condread.py" "$rid" $rest
  echo
done <<'EOF'
JSRF 1-1790497366-titleroutes-886445 --under 45
MA2 1-1790516796-lanelocal-1258823
MA2 1-1790516796-lanelocal-1258823 --under 20
MA2 1-1790516796-lanelocal-1258823 --window 540,780
MA2 1-1790492206-titleroutes-681960
MA2 0-0-x-1790557233-hostops-810152
MA2 1-1790572031-lane.sustain507-4130999 --under 10
MA2 1-1790572031-lane.sustain507-4131051 --under 10
Arctic 1-1790547557-titleroutes-979135 --under 45
Arctic 1-1790548502-titleroutes-1531400 --under 45
BloodRayne 1-1790548501-titleroutes-1530145r
BloodRayne 1-1790548501-titleroutes-1530145r --status
Alias 1-1790519290-titleroutes-2113140
DOAX y-1790481308-titlebench-2893458 --status
DOAX 0-0-y-1790433159-titleplay-p1-doax
Conker 0-0-y-1790395182-rtdbench-3 --under 45
Crash 1-1790489396-titleroutes-512742 --under 45
DOA3 0-0-y-1790433159-titleplay-p1-doa3 --status
DOA3 0-0-y-1790433159-titleplay-p1-doa3
PGR 1-1790483525-titleroutes-3587419 --split 360
Brute 1-1790510457-titleroutes-1101937
Otogi 1-1790511808-titleroutes-1129571 --under 45
Burnout 1-1790513065-titleroutes-1150288 --under 45
Black 1-1790482599-titleroutes-3358750
MM3 1-1790506491-titleroutes-1032854
Crimson 0-0-y-1790433159-titleplay-p1-crimson --split 270
Crimson 1790467153-titlebench-2601931
Crimson 1790467160-titlebench-2612149
Crimson 1-1790572033-adpf-2928981
Crimson 0-0-x-1790549042-flip474-1819312
EOF
