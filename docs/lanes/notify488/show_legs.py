"""Print a prediction's legs and scalar fields (hand-reading aid)."""
import json
import sys

d = json.load(open(sys.argv[1]))
for k, v in d.get('legs', {}).items():
    print(k, '::', v, '\n')
for k in d:
    if k not in ('legs', 'prediction', 'only_tests', 'suites'):
        print(k, str(d[k])[:400])
