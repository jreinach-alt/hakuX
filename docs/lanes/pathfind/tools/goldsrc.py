"""Which device each golden save was harvested from (the save store's source image)."""
import json, os, sys, collections
sys.path.insert(0, 'docs/testing/titles')
import titlestate
g = titlestate.load_goldens()["titles"]
count = collections.Counter()
rows = []
for tid, rec in sorted(g.items()):
    gold = (rec or {}).get('golden') or {}
    save = gold.get('save')
    if not save or gold.get('status') != 'golden':
        continue
    p = os.path.join(titlestate.store_dir(tid, save), 'save.json')
    try:
        src = json.load(open(p)).get('source', {}).get('image', '')
    except Exception:
        src = '?'
    dev = 'thor' if '/thor-' in src else 'nova' if '/nova-' in src else '?'
    count[dev] += 1
    rows.append((tid, save, dev, titlestate.title_meta_name(tid) or ''))
for r in rows:
    print('\t'.join(r))
print(dict(count))
