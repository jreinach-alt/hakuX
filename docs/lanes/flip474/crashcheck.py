"""Count crash markers in each result's logcat and print result.json's identity fields."""
import json
import re
import sys

R = '/home/justin/hakux-work/dispatch/results/'
KEYS = ('status', 'ref', 'apk_sha', 'device', 'title', 'exit', 'outcome', 'ok')
for i in sys.argv[1:]:
    text = open(R + i + '/logcat.txt', errors='replace').read()
    n = len(re.findall(r'FATAL|beginning of crash|Tombstone|SIGSEGV|SIGABRT', text))
    r = json.load(open(R + i + '/result.json'))
    print(i, 'crash', n, dict((k, r[k]) for k in r if k in KEYS))
