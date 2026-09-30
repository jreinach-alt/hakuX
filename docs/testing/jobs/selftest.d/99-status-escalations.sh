# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# status_html.py "3. What needs a person?": one owner escalation is one item (#433).
#
# WHY THIS EXISTS. The owner, 2026-09-29 ~19:05 PDT: "There's now 33 items needing
# a human and that's impossible for a fully automated harness unless it's completely
# derailed." There was ONE real item: a WSL restart to clear 258 stuck D-state `sync`
# processes. hostops wrote it to host-tools/escalations.md as two "## " heading
# blocks with unindented paragraph lines -- escalation_items() (added by lane.escitems,
# docs/lanes/escitems/NOTES.md) opened a new item on every one of those unindented
# lines, since only a "#" heading was excluded from opening one, so the page listed 32
# "decisions". A second bug surfaced fixing the first: an item closed when ANY of its
# lines contained the substring RESOLVED, and hostops's own updates say "Not marking
# RESOLVED." -- so once the heading's lines are correctly grouped into one item, that
# substring check reads the still-open WSL item as resolved and the page would show 0
# while a decision is pending, worse than 32.
#
# fixtures/escalations-20260929.md (docs/lanes/escalationparse/fixtures/) is a copy of
# host-tools/escalations.md.bak-20260929-lanelocal, hostops's own file exactly as it
# stood that evening -- not a hand-written toy.
#
# The world each leg fails in:
#   (a) an unindented, non-bullet, non-heading line inside a "## " block opens its own
#       item: the 32-count bug.
#   (b) RESOLVED is read as a substring anywhere on any line: "Not marking RESOLVED."
#       (or that same sentence hard-wrapped across two lines, as hostops's own line-wrap
#       does at 2026-09-29 18:33 PDT: "...Not marking\n  RESOLVED.") closes a still-open
#       item -- the 0-count bug.
#   (c) a genuine RESOLVED marker (leading a bullet or a continuation line, or starting a
#       new sentence after the original ask on the same line -- hostops's older style)
#       is NOT recognized: an already-closed item stays on the page forever.
#   (d) the "<timer> has no next run" alarm fires while the paired .service is still
#       mid-run (a oneshot has no next elapse for as long as it runs, by design).
# (a) and (b) are #433's own bugs; (c) and (d) are what a narrow fix for them could
# easily break (over-triggering "not a substring" on (c); under-triggering the timer
# alarm's own guard on a slow render in (d)).

echo "== status page: one owner escalation is one item, not one per line (#433)"
SE2_D="$T/status-escalations"; mkdir -p "$SE2_D/host-tools"
cp "$HERE/../../lanes/escalationparse/fixtures/escalations-20260929.md" "$SE2_D/host-tools/escalations.md" 2>/dev/null \
    || cp "$REPO/docs/lanes/escalationparse/fixtures/escalations-20260929.md" "$SE2_D/host-tools/escalations.md"

cat > "$T/status-heading.md" <<'EOF'
## 2026-09-29 13:06 PDT -- WSL restart needed: sync wedged
OWNER-LEVEL: hotel-heading-first this paragraph has no bullet and no indent.

DIAGNOSIS: hotel-heading-second another unindented paragraph, after a blank line.

  UPDATE 09-29 13:28 PDT (hostops): hotel-heading-update an indented continuation.
## 2026-09-29 15:55 PDT (hostops) -- root cause found
hotel-second-block a second heading opens a second item, not a continuation of the first.
- 2026-09-29 16:00 PDT (hostops) OWNER HANDS: hotel-bullet-after a bullet after two headings opens a third item.
  UPDATE 09-29 17:00 PDT (hostops): hotel-bullet-update still open.
EOF

cat > "$T/status-resolved.md" <<'EOF'
- 09-29 08:00 PDT (hostops) OWNER HANDS: india-wrapped-prose still needs a charger.
  UPDATE 09-29 09:00 PDT (hostops): india-wrapped-update the sentence below is
  wrapped across two lines by hostops's own line-wrap. Not marking
  RESOLVED.
- 09-29 09:30 PDT (hostops) OWNER HANDS: juliet-embedded the Nova needs a charger. Nothing else possible from here. RESOLVED 09-29 10:00 PDT (hostops): juliet-embedded-done the owner plugged it in.
- RESOLVED 09-29 11:00 PDT (hostops): kilo-leading-marker the fix already landed. Was: 09-29 10:30 PDT (hostops) OWNER HANDS: kilo-leading-marker the Thor needs a reboot.
- 09-29 12:00 PDT (hostops) OWNER HANDS: lima-indented-marker the Nova is offline.
  UPDATE 09-29 12:10 PDT (hostops): lima-indented-update still offline.
  RESOLVED 09-29 12:20 PDT (hostops): lima-indented-done it came back on its own.
EOF

cat > "$T/status-escalations.py" <<'EOF'
import os, sys
sys.path.insert(0, sys.argv[1]); import status_html as S
leg = sys.argv[2]
now = S._stamp("2026-09-29 19:05 PDT")

def items_of(path):
    return S.escalation_items(open(path, encoding="utf-8").read(), now)

if leg == "real":
    items = items_of(os.path.join(sys.argv[3], "host-tools/escalations.md"))
    act = [i["action"] for i in items]
    print("items:", [a[:60] for a in act])
    # Never 32 (every unindented paragraph read as its own item) or 0 (the open WSL
    # item read as resolved by "Not marking RESOLVED."). This lane's rule groups the
    # two "## " heading blocks (13:06, 15:55) as two items -- neither carries a RESOLVED
    # marker -- plus the "16:00 OWNER HANDS" bullet, three raw open items total.
    ok = len(items) == 3 and len(items) not in (32, 0) \
        and sum("WSL restart needed" in a for a in act) == 1 \
        and sum("258 stuck" in a for a in act) == 1 \
        and sum("OWNER HANDS (recurring" in a for a in act) == 1
elif leg == "heading":
    # action is only the item's first line, so a swept continuation (the paragraphs
    # under a heading, the line right after the second heading) never appears there;
    # this checks it never became a first line of its OWN item either, which is the
    # 32-count bug.
    items = items_of(sys.argv[3])
    act = [i["action"] for i in items]
    print("items:", act)
    ok = len(items) == 3 \
        and sum("WSL restart needed" in a for a in act) == 1 \
        and sum("root cause found" in a for a in act) == 1 \
        and sum("hotel-bullet-after" in a for a in act) == 1 \
        and not any("hotel-heading-first" in a for a in act) \
        and not any("hotel-heading-second" in a for a in act) \
        and not any("hotel-second-block" in a for a in act)
elif leg == "resolved":
    items = items_of(sys.argv[3])
    act = [i["action"] for i in items]
    print("open items:", [a[:60] for a in act])
    open_tags = {"india", "juliet", "kilo", "lima"}
    seen_open = {t for t in open_tags if any(t in a for a in act)}
    ok = seen_open == {"india"}   # only the wrapped-prose item (kept open) survives
elif leg == "timer":
    live = [{"kind": "timer", "text": "hakux-hostops.timer is active but has no next run: it will not fire again until someone restarts it"}]
    other = [{"kind": "timer", "text": "hakux-fold.timer has FAILED (systemctl --user status hakux-fold.timer)"}]
    activating = S._live_timer_attn(live, state_of=lambda u: "activating")
    inactive = S._live_timer_attn(live, state_of=lambda u: "inactive")
    failed = S._live_timer_attn(live, state_of=lambda u: "failed")
    unknown = S._live_timer_attn(live, state_of=lambda u: "")
    passthrough = S._live_timer_attn(other, state_of=lambda u: "activating")
    print("activating:", activating, "inactive:", inactive)
    ok = activating == [] and inactive == live and failed == live and unknown == live and passthrough == other
else:
    ok = False
print("ok" if ok else "FAIL leg " + leg)
sys.exit(0 if ok else 1)
EOF
se2_leg() { python3 "$T/status-escalations.py" "$HERE" "$1" "$2" > "$T/status-escalations-$1.txt" 2>&1; }
check "(real) the 09-29 escalations.md shape yields 3 open items, never 32 or 0" se2_leg real "$SE2_D"
check "(heading) a '## ' block's unindented paragraphs are one item; a second heading or bullet opens the next" se2_leg heading "$T/status-heading.md"
check "(resolved) RESOLVED closes only as a marker: a substring (incl. hard-wrapped) never does" se2_leg resolved "$T/status-resolved.md"
check "(timer) 'no next run' fires only when the paired .service reads inactive or failed" se2_leg timer x
for se2_f in "$T"/status-escalations-*.txt; do [ "$(tail -n 1 "$se2_f")" = ok ] || sed 's/^/    /' "$se2_f"; done
