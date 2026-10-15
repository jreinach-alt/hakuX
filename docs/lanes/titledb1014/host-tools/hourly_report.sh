#!/usr/bin/env bash
# hourly_report.sh -- model-free daytime check-in, run by hakux-hourly.timer at :45 so the report is on disk before the hour.
# Writes logs/hourly/<stamp>.txt and logs/hourly/latest.txt (atomically). No Claude session involved.
export TZ=America/Los_Angeles PATH=/home/justin/hakux-work/forge/shim/bin:/home/justin/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
H=/home/justin/hakux-work; R=/home/justin/hakuX; O=$H/logs/hourly; D=$H/dispatch
stamp=$(date +%Y%m%d-%H%M); tmp=$O/.$stamp.tmp
last=$(cat $O/.last 2>/dev/null); now=$(date +%s); since=${last:-$((now-3600))}
[ $((now-since)) -gt 21600 ] && since=$((now-3600))
mode=day; case "$(date +%u)$(date +%H)" in [1-5]05|[67]06) mode=summary;; esac
# the 6 AM recap covers everything since the last report (Friday 21:45 on a Monday), not the 6 h cap
if [ $mode = summary ]; then since=$(cat $H/logs/hourly/.last 2>/dev/null || date -d 'yesterday 21:45' +%s); fi
{
  echo "REPORT MODE: $mode ($(date '+%a %H:%M %Z'); lands for the $(date -d '+15 min' +%H:00) check-in)"
  timeout 300 bash $H/offline-git/offline_hourly.sh 0 $since 2>&1
  echo "--- active lanes and territory rows"
  git -C $R fetch -q origin 2>/dev/null
  tt=$(git -C $R show origin/board:territory.toml 2>/dev/null)
  for u in $(systemctl --user list-units --type=service --state=active --no-legend | awk '{print $1}' | grep '^hakux-lane-'); do
    l=${u#hakux-lane-}; l=${l%.service}
    printf '  %-16s row=%s\n' $l "$(grep -q "^\[lane\.$l\]" <<<"$tt" && echo yes || echo NO-ROW)"
  done
  echo "--- lane/snapdrive on master: $(git -C $R merge-base --is-ancestor origin/lane/snapdrive origin/master 2>/dev/null && echo folded || echo not-yet)"
  echo "--- GitHub contact (ghwatch: any socket to GitHub, an old-env unit, a new reference, an unserved gh call)"
  python3 -c "
import json,time
d=json.load(open('$H/host-tools/.ghwatch.json')); n=len(d['hits'])
print('  recorder up (owner 10-05: left running indefinitely as a log; no clean-hours target). %d hits logged in all; last %.1f h ago' % (n, (time.time()-d['clean_since'])/3600))
for x in d['hits'][-3:]: print('  last hit', time.strftime('%m-%d %H:%M', time.localtime(x['at'])), x['msg'][:140])
" 2>/dev/null || echo "  ghwatch state unreadable: the instrument is down"
  echo "--- open jams (idlewatch) and lane wakes (lanewaker)"
  python3 -c "import json,time; d=json.load(open('$H/host-tools/.idlewatch.json')); [print('  JAM', k, 'since', time.strftime('%H:%M', time.localtime(v))) for k,v in sorted(d.items())] or print('  none')" 2>/dev/null
  tail -5 $H/logs/lanewaker.log 2>/dev/null | sed 's/^/  /' 
  echo "--- PLAYABLE (pm/title-registry.tsv, the one table -- #433)"; python3 -c "
import csv, time
reg = [r for r in csv.DictReader((l for l in open('$H/pm/title-registry.tsv') if not l.startswith('#')), delimiter='\t')]
total = sum(1 for r in reg if r['status'] == 'PLAYABLE')
L = [l.split(chr(9)) for l in open('$H/pm/playable-accepted.tsv').read().splitlines()[1:] if l.strip()]
d = time.strftime('%Y-%m-%d'); t = [x[1] for x in L if x[0].startswith(d)]
w = open('$H/pm/.wall-synced').read().split()
print('  total %d (table); today %d (%s)' % (total, len(t), ', '.join(t) or 'none'))
if len(L) != total:
    print('  LEDGER/TABLE MISMATCH: ledger %d rows, table %d PLAYABLE -- rebuild the registry' % (len(L), total))
print('  wall: in sync (%s, %s rows)' % (w[2], w[0]) if int(w[0]) == total else '  WALL OUT OF SYNC: table %d PLAYABLE, wall %s rows (%s) -- lane.local republishes it' % (total, w[0], w[2]))
" 2>/dev/null || echo "  table unreadable"
  echo "--- harness_health (restored 10-03: the 08:32 edit dropped it from this report)"; timeout 120 python3 $H/host-tools/harness_health.py 2>&1 | grep -v '^$' 2>/dev/null | head -3 | cut -c1-220
  # Owner 10-09: disc images live on D:, never on the Linux disk. The Linux disk is a VHDX on C: that grows and never
  # shrinks; C: filled on 10-09 16:34 and the VM crashed. harness_health's C: check sat in its unread tail for a week.
  echo "--- disk (disc images live on /mnt/d/hakux-staging, never on the Linux disk: AGENTS.md, owner 10-09)"
  echo "  C: $(df -B1G --output=avail /mnt/c 2>/dev/null | tail -1 | tr -d ' ') GB free | D: $(df -B1G --output=avail /mnt/d 2>/dev/null | tail -1 | tr -d ' ') GB free | Linux disk $(df -B1G --output=used / | tail -1 | tr -d ' ') GB used"
  # lane.local 10-11 (owner: focus the scan): a whole-disk walk is 6.7M files and timed out under load. Images are written
  # by our scripts and agents, so only where they can write: home, /tmp and the few writable roots. The code trees (lane
  # worktrees, the checkout, run results, .git, the selftest's fake hosts) are 5.7M of those files and are skipped.
  imgs=$(timeout 240 ionice -c3 nice -n19 find /home/justin /tmp /root /opt /srv /var/tmp -xdev \( -path /home/justin/hakux-work/wt -o -path /home/justin/hakuX -o -path /home/justin/hakux-work/dispatch/results -o -path '/tmp/hakux-selftest.*' -o -name .git \) -prune -o -type f -size +256M \( -iname '*.iso' -o -iname '*.xiso' -o -iname '*.7z' \) -printf '%s\t%h\n' 2>/dev/null); rc=$?
  if [ $rc -eq 124 ]; then echo "  image scan TIMED OUT after 240 s: no answer this hour"
  elif [ -z "$imgs" ]; then echo "  disc images on the Linux disk: none over 256 MB (home, /tmp; code trees skipped)"
  else awk -F'\t' '{s[$2]+=$1; n[$2]++; t+=$1; c++} END{printf "  DISC IMAGES ON THE LINUX DISK: %d file(s), %.1f GB -- move them to /mnt/d/hakux-staging/<purpose>/\n", c, t/1e9; for (d in s) printf "    %6.1f GB %3d  %s\n", s[d]/1e9, n[d], d}' <<<"$imgs"; fi
  echo "--- JAMS (driver ledger pm/jams.tsv: every 5 min; opened/cleared since the last report, open rows with age, owner, last action)"
  python3 - "$since" <<'PYJ' 2>/dev/null || echo "  driver ledger unreadable: the driver is down"
import json, sys, time
since = int(sys.argv[1]); now = time.time()
rows = json.load(open('/home/justin/hakux-work/host-tools/.driver.json')).get('rows', {}).values()
age = lambda t: '%dh%02dm' % ((now - t) // 3600, (now - t) % 3600 // 60)
op = [r for r in rows if r['opened_epoch'] >= since]; cl = [r for r in rows if r['state'] == 'cleared' and r.get('cleared_epoch', 0) >= since]
print('  opened this hour: %d   cleared this hour: %d   open now: %d' % (len(op), len(cl), sum(r['state'] != 'cleared' for r in rows)))
for r in sorted([r for r in rows if r['state'] != 'cleared'], key=lambda r: r['opened_epoch']):
    print('  %-7s %-7s %-12s %-40s %s | %s' % (age(r['opened_epoch']), r['state'], r['owner'][:12], r['key'][:40], r['last_action'][:60], r['evidence'][:110]))
for r in cl: print('  cleared %s  %s (%s)' % (r['key'][:50], r['last_action'][:60], age(r['opened_epoch'])))
PYJ
  echo "--- STALLS (stallwatch: asked or decided, with no reader or no progress; owner owes the next move)"
  sed -n '3,$p' $H/pm/stalls.md 2>/dev/null | head -40 | sed 's/^/  /' || echo "  ledger missing: stallwatch is down"
  if [ $mode = summary ]; then
    echo "=== OVERNIGHT RECAP (since $(date -d @$since '+%a %H:%M'))"
    python3 $H/offline-git/offline_status.py 2>&1 | head -40
    grep -E 'PASS|PLAYABLE' $H/logs/verdicts.log | awk -v s="$(date -d @$since '+%F %T')" '$1" "$2>=s' | cut -c1-200
    systemctl --user list-units --state=failed --no-legend | head -5
  fi
  echo "--- usage / mode"; cat $H/usage/summary.txt 2>/dev/null || echo "(usage meter not built yet: lane.usagemode)"
  echo "--- ops (jams)"; cat $H/ops/summary.txt 2>/dev/null || echo "(ops layer not built yet: lane.opsrebuild; hostops interim gate 2 in force)"
  echo "--- public docs (docs_freshness.py; a docs pass every release and every 14 days)"
  docs_out=$(timeout 30 python3 $R/docs/testing/docs_freshness.py --repo $R 2>&1); docs_rc=$?
  if [ $docs_rc -eq 0 ]; then
    echo "  $(tail -1 <<<"$docs_out")"
  else
    docs_summary=$(tail -1 <<<"$docs_out")
    docs_bad=${docs_summary#*not: }
    [ "$docs_bad" = "$docs_summary" ] && docs_bad="(see below)"
    echo "  ALARM: public docs stale: $docs_bad"
    grep -v '^OK \|^public docs:' <<<"$docs_out" | sed 's/^/  /'
  fi
  echo "--- pathfind / screening verdicts since last report (held runs: wt/pathfind runs/*/verdict.json and runs/*/*/verdict.json)"
  python3 - "$since" "$H" <<'PYPF'
import glob, json, os, sys, time
since = int(sys.argv[1]); H = sys.argv[2]
rows = []
for f in glob.glob(H + '/wt/pathfind/docs/lanes/pathfind/runs/*/verdict.json') + glob.glob(H + '/wt/pathfind/docs/lanes/pathfind/runs/*/*/verdict.json'):
    if os.path.getmtime(f) < since: continue
    try: d = json.load(open(f))
    except Exception: continue
    rows.append((os.path.getmtime(f), os.path.relpath(os.path.dirname(f), H + '/wt/pathfind/docs/lanes/pathfind/runs'), d))
for t, run, d in sorted(rows):
    tl = d.get('timeline') or {}
    print('  %s %-28s %-5s fps_ok=%s play=%ss share=%s %s' % (time.strftime('%H:%M', time.localtime(t)), run[:28],
          'PASS' if d.get('pass') else 'FAIL', d.get('fps_ok_share'), d.get('gameplay_s'), tl.get('play_share'), str(d.get('failing') or '')[:90]))
if not rows: print('  (no held run finished since the last report)')
q = H + '/pm/sweep-1004.tsv'; dn = H + '/pm/sweep-1004.done'
try:
    n = sum(1 for l in open(q) if l.strip() and not l.startswith('#')); r = len(glob.glob(H + '/wt/pathfind/docs/lanes/pathfind/runs/screen-*'))
    print('  sweep list: %d titles; screen-* runs on disk: %d' % (n, r))
except Exception: pass
PYPF
  echo "--- verdicts since last report"
  awk -v s="$(date -d @$since '+%F %T')" '$1" "$2>=s' $H/logs/verdicts.log | cut -c1-220 | tail -10
  echo "--- issue mirror (hakux-issue-mirror.timer; status file + age; adds 0 GitHub reads)"
  IMS=$H/status/issue-mirror.txt
  if [ -f "$IMS" ]; then
    im_age=$(( $(date +%s) - $(stat -c %Y "$IMS") ))
    im_ec=$(grep -o 'exit=[0-9]*' "$IMS" | tail -1 | cut -d= -f2)
    sed 's/^/  /' "$IMS"
    if [ "$im_age" -gt 1800 ]; then
      echo "  ALARM: issue-mirror status is ${im_age}s old (cap 1800s)"
    fi
    # issuemirror1013: exit=76 is the gateway's day-cap refusal (reads or writes), a real condition the owner
    # should hear about but not a crash -- it is never retried within the day and clears on its own at 00:00
    # UTC, so it gets its own named line instead of falling into the generic "exit code neither 0 nor 75" one.
    # The cap itself (reads/writes) and the reset time are already in the status text above, from the tool's
    # own "ALARM: hit the GitHub <cap> cap..." line (see issue_mirror.py's _gateway_outcome_rc).
    if [ -n "$im_ec" ] && [ "$im_ec" = 76 ]; then
      echo "  ALARM: issue-mirror hit a GitHub day cap today (see the status line above for which one); resets 00:00 UTC, not retried until then"
    elif [ -n "$im_ec" ] && [ "$im_ec" != 0 ] && [ "$im_ec" != 75 ]; then
      echo "  ALARM: issue-mirror exit=$im_ec (want 0 or 75)"
    fi
  else
    echo "  status file missing: $IMS"
  fi
} > $tmp 2>&1
# next-step rule (owner 10-02 17:25): flag OUTBOX entries in this report whose "Next" has no probability
python3 - "$tmp" >> "$tmp" 2>/dev/null <<'PYNS'
import re, sys
t = open(sys.argv[1], errors='replace').read()
bad = []
for ent in re.split(r'\n(?=--- lane/)', t):
    m = re.match(r'--- lane/(\S+)\s+(#\S+)?\s*(.*)', ent)
    if not m: continue
    nx = re.search(r'(?im)^\W*\**next\b.*?(?=\n\s*\n|\Z)', ent, re.S)
    if nx and not re.search(r'(?i)\bP\s*[=~:]?\s*0?\.\d|probab|\bP\(', nx.group(0)):
        bad.append(m.group(1) + ' ' + m.group(3)[:22])
print('--- next-step rule: ' + ('OK' if not bad else 'NEXT WITHOUT P x WIN: ' + '; '.join(bad)))
PYNS
echo $now > $O/.last
mv $tmp $O/$stamp.txt; cp $O/$stamp.txt $O/latest.tmp; mv $O/latest.tmp $O/latest.txt
