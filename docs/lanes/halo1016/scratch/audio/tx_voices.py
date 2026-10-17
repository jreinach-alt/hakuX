#!/usr/bin/env python3
"""Print the hxs_voices.py results already in this lane's transcript, per slot.

  tx_voices.py TRANSCRIPT.jsonl [VOICE ...]

Reads tool_use commands that ran hxs_voices.py on slotN.stream and the
tool_result paired with each; prints the header and the rows for the voices
asked for (all rows if none). No re-run of the tool.
"""
import json
import re
import sys

path = sys.argv[1]
want = set(int(a) for a in sys.argv[2:])
uses = {}
for line in open(path):
    try:
        o = json.loads(line)
    except ValueError:
        continue
    msg = o.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, list):
        continue
    for c in content:
        if c.get("type") == "tool_use":
            cmd = (c.get("input") or {}).get("command", "")
            m = re.search(r"hxs_voices\.py \S*(slot\d)\.stream", cmd)
            if m and m.group(1) not in uses.values():
                uses[c["id"]] = m.group(1)
        elif c.get("type") == "tool_result" and c.get("tool_use_id") in uses:
            r = c.get("content")
            if isinstance(r, list):
                r = "".join(x.get("text", "") for x in r if isinstance(x, dict))
            print("==", uses[c["tool_use_id"]])
            for row in str(r).splitlines():
                m = re.match(r"\s*(\d+)\s+[23]D", row)
                if row.startswith("v ") or not m or not want or int(m.group(1)) in want:
                    if row.startswith("v ") or m:
                        print(row)
