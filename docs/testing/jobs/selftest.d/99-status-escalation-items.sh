# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# status_html.py "3. What needs a person?": an escalation is an item, not a line.
#
# WHY THIS EXISTS. The owner, 2026-09-27 ~17:00 PDT: "Nothing is checking the
# section 3 needs a human for resolution. 2 is stale. 3 might be too." The reader
# walked host-tools/escalations.md one line at a time and skipped only a line
# that said RESOLVED. Hostops writes UPDATE/RESOLVED on indented continuation
# lines under the item's "- " line, so the 10:36 Nova item (resolved 14:28) and
# the 11:51 Thor-overlay item (resolved 12:13) stayed on the page as owner asks,
# and every continuation line was listed as an ask of its own. The page now
# groups an item as harness_health.py does (its "- " line plus the indented lines
# under it; resolved if any says RESOLVED) and shows hostops' newest
# "re-checked HH:MM" per open item, marking one unchecked for 2 h "unverified".
#
# The world each leg fails in:
#   (a) the reader keys RESOLVED on the line, not the item: the resolved item is listed.
#   (b) a continuation line is read as an item: the UPDATE line is listed as its own ask.
#   (c) the re-check stamp is not read, or read with the wrong day/zone: no time
#       shown, or the item marked unverified 30 min after a re-check.
#   (d) the staleness rule is missing or too loose: a 3 h old unchecked item
#       carries no visible marker (or is dropped from the list).
#   (e) recovery/needs-hands.txt keys RESOLVED on the line, as (a).
# (a), (b) and (e) fail on master at 59abda3c9b (docs/lanes/escitems/NOTES.md);
# (c) and (d) test the re-check rule this lane adds.

echo "== status page: an escalation is its '- ' line plus its continuation lines"
SE_D="$T/status-escitems"; mkdir -p "$SE_D/host-tools" "$SE_D/recovery"
cat > "$SE_D/host-tools/escalations.md" <<'EOF'
# escalations (fixture)
- 09-27 08:00 PDT (hostops) OWNER HANDS: alpha-resolved-on-a-continuation the Nova needs a charger.
  UPDATE 09-27 09:00 PDT (hostops): alpha-update still draining.
  RESOLVED 09-27 10:00 PDT (hostops): alpha-done the owner plugged it in.
- 09-27 11:00 PDT (hostops) OWNER HANDS: bravo-open-with-update the Thor overlay covers hakuX.
  UPDATE 09-27 11:10 PDT (hostops): bravo-update-line still black.
  re-checked 11:30 PDT (hostops) bravo-evidence display-0 screencap black
- 09-27 06:00 PDT (hostops) OWNER CALL: charlie-rechecked-recently decide the VHDX move.
  re-checked 09:00 PDT (hostops) older
  re-checked 11:30 PDT (hostops) charlie-evidence C: 98 GB free
- 09-27 08:30 PDT (hostops) OWNER CALL: delta-stale no re-check for three hours.
EOF
cat > "$SE_D/recovery/needs-hands.txt" <<'EOF'
(updated 11:00 PDT by lane.local: header, not an ask)
echo-open restart the xbox session
foxtrot-resolved-below re-plug the Thor
  RESOLVED 11:20 PDT (hostops): foxtrot-done replugged
EOF

cat > "$T/status-escitems.py" <<'EOF'
import os, sys
sys.path.insert(0, sys.argv[1]); import status_html as S
d, leg = sys.argv[2], sys.argv[3]
now = S._stamp("2026-09-27 12:00 PDT")          # 19:00 UTC: the same date in either zone
items = S.escalation_items(open(os.path.join(d, "host-tools/escalations.md")).read(), now)
act = [i["action"] for i in items]
def first(tag):
    return [i for i in items if tag in i["action"]]
def page():
    j = {"attention": [dict(i, kind="decision", who="owner", src="x") for i in items]}
    return S._q3(j, now)
print("items:", act)
if leg == "a":
    ok = not any("alpha" in a for a in act) and "alpha" not in page()
elif leg == "b":
    ok = len(first("bravo-open-with-update")) == 1 and not any("bravo-update-line" in a for a in act) \
        and page().count("bravo-open-with-update") == 1 and "bravo-update-line" not in page()
elif leg == "c":
    c = first("charlie-rechecked-recently")
    ok = len(c) == 1 and not c[0]["unverified"] and c[0]["checked"] == S._stamp("2026-09-27 11:30 PDT") \
        and "re-checked 11:30" in c[0]["detail"] and "UNVERIFIED" not in c[0]["detail"]
    b = first("bravo-open-with-update")
    ok = ok and len(b) == 1 and not b[0]["unverified"] and "re-checked 11:30" in b[0]["detail"]
    ok = ok and "Re-checked 11:30" in page()
elif leg == "d":
    x = first("delta-stale")
    ok = len(x) == 1 and x[0]["unverified"] and "UNVERIFIED" in x[0]["detail"] and "delta-stale" in page() \
        and page().count("UNVERIFIED") == 1
elif leg == "e":
    class F:
        W = d
        def mtime(self, p): return now - 60
        def read(self, p): return open(p).read()
    nh = S._needs_hands(F(), {"STATUS_BOOT_EPOCH": str(now - 3600)}, now, [])
    na = [x["action"] for x in nh]
    print("needs-hands:", na)
    ok = na == ["echo-open restart the xbox session"]
else:
    ok = False
print("ok" if ok else "FAIL leg " + leg)
sys.exit(0 if ok else 1)
EOF
se_leg() { python3 "$T/status-escitems.py" "$HERE" "$SE_D" "$1" > "$T/status-escitems-$1.txt" 2>&1; }
check "(a) an item RESOLVED only on a continuation line is not listed" se_leg a
check "(b) an open item with an UPDATE continuation is listed once; the UPDATE line is no item" se_leg b
check "(c) an item re-checked 30 min ago shows 're-checked 11:30' and is not unverified" se_leg c
check "(d) an item unchecked for 3 h stays listed, marked UNVERIFIED" se_leg d
check "(e) needs-hands.txt: an ask RESOLVED on its indented line is not listed" se_leg e
for se_f in "$T"/status-escitems-*.txt; do [ "$(tail -n 1 "$se_f")" = ok ] || sed 's/^/    /' "$se_f"; done
