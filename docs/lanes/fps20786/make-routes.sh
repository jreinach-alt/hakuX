#!/usr/bin/env bash
# lane.fps20786: the three routes, from pathfind's recorded runs. Run from the repo root.
# The NBA steps come from lane/pathfind's nba-live-2005-hold (not folded when this ran);
# a copy is committed beside this script as nba-live-2005-hold.steps.jsonl.
set -e
D=docs/lanes/fps20786
mkdir -p "$D/routes"
python3 "$D/steps2route.py" "$D/nba-live-2005-hold.steps.jsonl" --name "NBA Live 2005 (45410050)" \
    --gameplay 20 --loop "RT:1,STICK:up:1,A,STICK:right:1,X,STICK:left:1,B,STICK:down:1,Y" \
    --source "pathfind runs/nba-live-2005-hold (10-03, lane/pathfind)" > "$D/routes/fps786-nba2005.route"
python3 "$D/steps2route.py" docs/lanes/pathfind/runs/top-spin/steps.jsonl --name "Top Spin (4D530035)" \
    --gameplay 25 --loop "A,STICK:left:0.6,A,STICK:right:0.6" \
    --source "pathfind runs/top-spin (10-02)" > "$D/routes/fps786-topspin.route"
python3 "$D/steps2route.py" docs/lanes/pathfind/runs/counter-strike/steps.jsonl --name "Counter-Strike (4D530036)" \
    --gameplay 13 --loop "STICK:up:1.5,RT:0.4,RSTICK:right:0.6,STICK:down:1,RT:0.4,RSTICK:left:0.6" \
    --source "pathfind runs/counter-strike (10-02)" > "$D/routes/fps786-cs.route"
for f in "$D"/routes/*.route; do
    bash docs/testing/titles/route.sh --check "$f" && echo "OK $f: $(tail -1 "$f")"
done
