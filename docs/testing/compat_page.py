#!/usr/bin/env python3
"""Generate docs/COMPATIBILITY.md and docs/compatibility.csv from the
playable ledger, the title registry, and the hand-written notes file.

    python3 docs/testing/compat_page.py \
        --ledger pm/playable-accepted.tsv \
        --registry <registry.tsv> \
        --notes docs/testing/compat_notes.tsv

Add --check to verify the committed files are up to date instead of
writing them (exits non-zero on any difference).

The page's "Last updated" line (read by docs_freshness.py) carries the
newest Tested date on the page, so it moves only when the data does, and
--check stays stable from one day to the next.
"""
import argparse
import csv
import io
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_MD = os.path.join(REPO_ROOT, "docs", "COMPATIBILITY.md")
DEFAULT_CSV = os.path.join(REPO_ROOT, "docs", "compatibility.csv")
GRADLE = os.path.join(REPO_ROOT, "android", "app", "build.gradle.kts")
# the "0.5.0-unknown" fallback literal, the same base version docs_freshness.py reads
GRADLE_VERSION_RE = re.compile(r'"(\d+\.\d+\.\d+)(?:-[A-Za-z0-9.]+)?"')

NOTES_COLS = ["section", "title_id", "title", "region", "region_source",
              "device", "fps_median", "time_at_bar", "gameplay_s", "tested", "notes"]

# CRASH_OR_HANG rows whose own evidence trips one of the mechanical
# left-off shapes below, but where a human-reviewed hold_detail settles
# the row the other way. Keyed by title_id; value is the reason, recorded
# here (not just in PR.md) so a registry rebuild cannot silently re-flag it.
RED_OVERRIDES = {
    "4D57001A": ("NHL Hitz Pro", "hold_detail (2026-10-06 lane.local) confirms a hang on the "
                 "post-team-select loading screen; the fps-only cause tag is stale"),
}


def read_tsv(path, skip_comments=False):
    with open(path, newline="") as f:
        lines = f.readlines()
    if skip_comments:
        lines = [l for l in lines if not l.startswith("#")]
    return list(csv.DictReader(io.StringIO("".join(lines)), delimiter="\t"))


def load_ledger(path):
    rows = read_tsv(path)
    for r in rows:
        r["title_id"] = "" if r.get("title_id") in (None, "-") else r["title_id"]
    return rows


def load_registry(path):
    return read_tsv(path, skip_comments=True)


def load_notes(path):
    rows = read_tsv(path)
    by_section = {"playable": [], "below_bar": [], "not_playable": []}
    for r in rows:
        by_section[r["section"]].append(r)
    return by_section


def below_bar_qualifies(row):
    """A BELOW_BAR row belongs on the public page only when the sole
    failing gate is fps -- any other tag (menu_time, duration,
    reached_gameplay: unconfirmed, audio, hitch, static, ...) means
    gameplay was not cleanly confirmed, per the brief's left-off list."""
    return row.get("failing_all", "") == "fps"


def crash_hang_left_off_reason(row):
    """Mechanical guard for the three shapes the brief calls out by name:
    a cause that is actually about fps and not a crash/hang, an
    unconfirmed reached_gameplay caveat, or a run voided by a thermal
    pause. Returns a short reason string, or None if nothing is tripped."""
    cause = row.get("cause", "")
    failing_all = row.get("failing_all", "")
    if row.get("void"):
        return "void: " + row["void"][:60]
    if "reached_gameplay: unconfirmed" in cause:
        return "reached_gameplay: unconfirmed"
    if failing_all == "fps":
        return "cause is fps, not crash/hang"
    return None


def build_playable_rows(ledger_rows, notes_by_title):
    out = []
    missing = []
    for lr in ledger_rows:
        title = lr["title"]
        nr = notes_by_title.get(("playable", title))
        if nr is None:
            missing.append(title)
            continue
        out.append(nr)
    if missing:
        raise SystemExit("compat_page.py: ledger titles missing from compat_notes.tsv "
                          "(section=playable): %s" % ", ".join(missing))
    return sorted(out, key=lambda r: r["title"].lower())


def build_below_bar_rows(registry_rows, ledger_title_ids, notes_below_bar):
    qualifying = []
    for rr in registry_rows:
        if rr.get("status") != "BELOW_BAR":
            continue
        if not below_bar_qualifies(rr):
            continue
        if rr.get("title_id") and rr["title_id"] in ledger_title_ids:
            continue  # ledger wins over the registry
        qualifying.append(rr)

    notes_by_id = {r["title_id"]: r for r in notes_below_bar}
    qualifying_ids = {rr["title_id"] for rr in qualifying}

    out = []
    missing = []
    for rr in qualifying:
        nr = notes_by_id.get(rr["title_id"])
        if nr is None:
            missing.append("%s (%s)" % (rr["name"], rr["title_id"]))
            continue
        out.append(nr)
    if missing:
        raise SystemExit("compat_page.py: BELOW_BAR titles qualify (failing_all=fps) but are "
                          "missing from compat_notes.tsv (section=below_bar): %s" % ", ".join(missing))

    stale = [r["title"] for r in notes_below_bar if r["title_id"] not in qualifying_ids]
    if stale:
        raise SystemExit("compat_page.py: compat_notes.tsv lists below_bar titles that no "
                          "longer qualify against the registry: %s" % ", ".join(stale))

    return sorted(out, key=lambda r: r["title"].lower())


def build_not_playable_rows(registry_rows, ledger_title_ids, notes_rows):
    registry_by_id = {rr["title_id"]: rr for rr in registry_rows}
    out = []
    for nr in notes_rows:
        tid = nr["title_id"]
        rr = registry_by_id.get(tid)
        if rr is None or rr.get("status") != "CRASH_OR_HANG":
            raise SystemExit("compat_page.py: not_playable title_id %s (%s) is not a "
                              "CRASH_OR_HANG row in the registry" % (tid, nr["title"]))
        if tid in ledger_title_ids:
            raise SystemExit("compat_page.py: not_playable title_id %s (%s) is also in the "
                              "ledger; the ledger wins, drop it from compat_notes.tsv" % (tid, nr["title"]))
        reason = crash_hang_left_off_reason(rr)
        if reason is not None and tid not in RED_OVERRIDES:
            raise SystemExit("compat_page.py: not_playable title_id %s (%s) trips a left-off "
                              "shape (%s) with no recorded override" % (tid, nr["title"], reason))
        out.append(nr)
    return sorted(out, key=lambda r: r["title"].lower())


def pct(frac):
    if frac in (None, ""):
        return ""
    return "%.0f%%" % (round(float(frac), 4) * 100)


def device_name(v):
    return (v or "").strip().capitalize()


def fps1(v):
    if v in (None, ""):
        return ""
    return "%.1f" % float(v)


DEFINITIONS = """## What "Playable" means

A title is rated Playable when a held run reaches real gameplay and stays
there for at least 10 minutes (longer for a handful of titles known to
develop problems slowly) with no crash, hang or unexpected exit; spends at
least 90% of that time in actual play rather than menus, loading screens or
cutscenes (its **play share**); holds at least 28.5 fps (the 30 fps bar,
times a 0.95 tolerance) for at least 90% of the time it is playing (the
**fps bar**); plays its audio with no more than a tiny share of starved
callbacks; and shows no hitches or flicker -- checked by reviewing the
captured frames themselves, not just the frame-rate counter (**frame
review**). The rating is tied to the handheld it was measured on, an AYN
Thor or a Retroid Pocket Nova.

A few titles were rated by a person playing them rather than by the timed
run alone, where the timed run cannot hold a representative scene. Need for
Speed: Most Wanted, for one, is rated on a full race played by hand; its
automated run covers race starts only.

Titles below run the same checks but fall short of the fps bar while
everything else about the run is clean. Titles that do not yet play either
crash, hang, or never reach gameplay in the emulator.

A rating here is not a claim that a title is free of bugs, and a title's
absence from this page is not a claim that it fails to run -- titles with
an inconclusive test run are left off rather than guessed at.
"""


def app_version():
    with open(GRADLE) as f:
        m = GRADLE_VERSION_RE.search(f.read())
    if not m:
        sys.exit("compat_page.py: no X.Y.Z version literal in %s" % GRADLE)
    return m.group(1)


def date_line(playable, below_bar, not_playable):
    tested = [r["tested"] for r in playable + below_bar + not_playable if r["tested"]]
    return "_Last updated %s, for version %s._" % (max(tested) if tested else "-", app_version())


def render_md(playable, below_bar, not_playable):
    lines = []
    lines.append("# Compatibility")
    lines.append("")
    lines.append(date_line(playable, below_bar, not_playable))
    lines.append("")
    lines.append(
        "This lists Xbox titles tried on this project's test devices, split "
        "into three groups: titles that clear the **Playable** bar, titles "
        "that run but fall short of 30 fps, and titles that do not yet play. "
        "It is not a full compatibility list: plenty of other titles have "
        "simply not been tried yet. See [`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md) "
        "and the [issue tracker](https://github.com/jreinach-alt/hakuX/issues) "
        "for what is tracked about titles not on this page."
    )
    lines.append("")
    lines.append("%d Playable · %d run below 30 fps · %d not playable"
                 % (len(playable), len(below_bar), len(not_playable)))
    lines.append("")
    lines.append(DEFINITIONS)

    def table(rows, cols, header):
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "|".join(["---"] * len(header)) + "|")
        for r in rows:
            lines.append("| " + " | ".join(cols(r)) + " |")
        lines.append("")

    lines.append("## \U0001F7E2 Playable")
    lines.append("")
    table(playable,
          lambda r: [r["title"], r["region"] or "?", device_name(r["device"]),
                     fps1(r["fps_median"]), pct(r["time_at_bar"]), r["tested"], r["notes"]],
          ["Title", "Region", "Device", "Median fps", "Time at bar", "Tested", "Notes"])

    lines.append("## \U0001F7E1 Runs, below 30 fps")
    lines.append("")
    table(below_bar,
          lambda r: [r["title"], r["region"] or "?", device_name(r["device"]),
                     fps1(r["fps_median"]), pct(r["time_at_bar"]), r["tested"], r["notes"]],
          ["Title", "Region", "Device", "Median fps", "Time at bar", "Tested", "Notes"])

    lines.append("## \U0001F534 Not playable")
    lines.append("")
    table(not_playable,
          lambda r: [r["title"], r["title_id"], r["tested"], r["notes"]],
          ["Title", "Title ID", "Tested", "Reason"])

    lines.append(
        "A rating is not a claim of no bugs, and absence from this page is "
        "not a claim of failure -- titles with inconclusive test runs are "
        "simply not listed."
    )
    lines.append("")
    return "\n".join(lines)


def render_csv(playable, below_bar, not_playable):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["section", "title", "title_id", "region", "region_source", "device",
                "median_fps", "time_at_bar_pct", "gameplay_s", "tested", "notes_or_reason"])
    for section, rows in (("playable", playable), ("below_bar", below_bar)):
        for r in rows:
            w.writerow([section, r["title"], r["title_id"], r["region"], r["region_source"],
                        device_name(r["device"]), fps1(r["fps_median"]), pct(r["time_at_bar"]),
                        r["gameplay_s"], r["tested"], r["notes"]])
    for r in not_playable:
        w.writerow(["not_playable", r["title"], r["title_id"], "", "", "",
                     "", "", "", r["tested"], r["notes"]])
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--registry", required=True)
    ap.add_argument("--notes", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out-md", default=DEFAULT_MD)
    ap.add_argument("--out-csv", default=DEFAULT_CSV)
    args = ap.parse_args()

    ledger_rows = load_ledger(args.ledger)
    registry_rows = load_registry(args.registry)
    notes = load_notes(args.notes)

    notes_by_title = {("playable", r["title"]): r for r in notes["playable"]}

    ledger_title_ids = {r["title_id"] for r in ledger_rows if r["title_id"]}

    playable = build_playable_rows(ledger_rows, notes_by_title)
    below_bar = build_below_bar_rows(registry_rows, ledger_title_ids, notes["below_bar"])
    not_playable = build_not_playable_rows(registry_rows, ledger_title_ids, notes["not_playable"])

    md = render_md(playable, below_bar, not_playable)
    csv_text = render_csv(playable, below_bar, not_playable)

    if args.check:
        ok = True
        for path, content in ((args.out_md, md), (args.out_csv, csv_text)):
            if not os.path.isfile(path) or open(path).read() != content:
                print("compat_page.py --check: %s is stale" % path, file=sys.stderr)
                ok = False
        if not ok:
            sys.exit(1)
        print("compat_page.py --check: up to date")
        return

    with open(args.out_md, "w") as f:
        f.write(md)
    with open(args.out_csv, "w", newline="") as f:
        f.write(csv_text)
    print("wrote %s and %s" % (args.out_md, args.out_csv))


if __name__ == "__main__":
    main()
