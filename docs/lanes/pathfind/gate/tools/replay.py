# Full-chain replay on labelled stored triplets: the new routing (motion floor, ratio, letterbox veto), then the
# real confirm() question to the strong model (Sonnet 5), with a, b, c as in confirm() for the non-self-moving path.
# usage: replay.py START END   (indices into the labelled list, to keep each run under the tool time limit)
import json, os, sys, time
sys.path.insert(0, 'docs/testing/titles')
import pathfind as pf

FLOOR = 0.004
RATIO = 1.5
start, end = int(sys.argv[1]), int(sys.argv[2])
res = json.load(open('scratch/probegate/gate_results.json'))
labelled = [r for r in res if r['label'] in ('R', 'U', 'C', 'M', 'P')]
out_path = 'scratch/probegate/replay_results.json'
prev = json.load(open(out_path)) if os.path.exists(out_path) else {}
trip = {(t['run'], t['pre']): t for t in json.load(open('scratch/probegate/triplets.json'))}
model = pf.Model('scratch/probegate')

for r in labelled[start:end]:
    key = r['run'] + '/' + r['pre']
    t = trip[(r['run'], r['pre'])]
    rec = {'label': r['label'], 'run': r['run'], 'pre': r['pre'], 'set': r['set'], 'n': r['n']}
    ctrl, mov = r['n2']['ctrl'], r['n2']['moved']
    ctrl, mov = r['n1']['ctrl'], r['n1']['moved']
    rec['ctrl'], rec['moved'] = ctrl, mov
    if mov < FLOOR:
        rec['route'] = 'measure: no change'
        rec['accepted'] = False
    elif ctrl <= 0.15 and mov < RATIO * ctrl:
        rec['route'] = 'measure: change within idle change'
        rec['accepted'] = False
    elif pf.letterboxed(t['a']) or pf.letterboxed(t['c']):
        rec['route'] = 'letterbox veto'
        rec['accepted'] = False
    else:
        selfmove = ctrl > 0.15
        rec['route'] = 'model' + (' (self-moving, no steer frames: non-steer prompt)' if selfmove else '')
        head = (f"Screenshots of {r['run']}, an Xbox game, below in order. The 'FPS: NN' text at the top-left "
                f"is the emulator's overlay, not a game HUD. The previous step judged this gameplay: \"HUD on a playfield\".\n")
        tail = ('A menu cursor moving is NOT a response. Answer JSON only: '
                '{"gameplay": true|false, "responded": true|false, "why": "<one line>"}')
        q = head + (f"A, then B (1 s after A, no input), then C (taken while holding the input, ~1 s after B). "
                    "Is this real player-controlled gameplay (not a menu, not a cutscene, not an attract/demo "
                    "mode, not a replay), AND does C show the playfield responding to the input (the "
                    "player/vehicle/camera moved accordingly), beyond whatever changed on its own between A "
                    "and B? " + tail)
        imgs = [t['a'], t['b'], t['c']]
        ans = model.ask(pf.STRONG, q, 'gate', imgs) or {}
        ok = bool(ans.get('gameplay')) and bool(ans.get('responded'))
        rec['answer'] = ans
        rec['accepted'] = ok
    prev[key] = rec
    print(r['label'], key, rec['route'], rec['accepted'], (rec.get('answer') or {}).get('why', '')[:90], flush=True)
    json.dump(prev, open(out_path, 'w'), indent=1)
print('done', start, end, 'calls so far', model.calls)
