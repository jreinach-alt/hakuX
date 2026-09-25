#!/usr/bin/env python3
"""At-a-glance accuracy by category, across labelled runs.

The per-suite sheets answer "how is Specular doing". Nobody can hold 100 of
them in their head, and the pixel counts move for reasons that are not
progress -- a suite scored on a ninth of its oracle looks respectable, and a
shared-disc run is not comparable with a per-suite one. So this rolls the
suites into the categories the tracker already groups them by, and puts the
runs side by side with their provenance attached.

Categories come from `CATEGORIES` below rather than from the issue list on
purpose: issues open, close and get re-split (#9 closed and became #53 and #38
in one afternoon), and a scoreboard whose rows move whenever the tracker moves
cannot show a trend. Suites are stable; issues are not.

Each run is a directory of `*.tsv` written by `score_sweep.py --apk-sha
--disc-id --label`. Rows carry their own provenance, so several runs can be
concatenated and still be told apart, and a run whose rows disagree about the
binary is reported rather than averaged.

    scoreboard.py --run baseline=docs/testing/baseline \\
                  --run published=docs/testing/published \\
                  --run nightly=/home/justin/hakux-work/nightly/scores \\
                  --goldens ~/goldens/results --md docs/testing/SCOREBOARD.md
"""
import argparse
import csv
import collections
import glob
import json
import os
import sys

# Suite -> category. Adapted from how issues 3-14 grouped them, with the
# subsystem as the unit rather than the issue, plus the groups that had no
# issue of their own.
CATEGORIES = {
    "Texture addressing": ["Texture_border", "Texture_border_color",
        "TextureWrapMode", "Texture_cubemap", "Texture_2D_as_cubemap",
        "Texture_perspective", "Texture_perspective_enable",
        "Texture_anisotropy", "Texture_3D_as_2D", "Texture_Matrix",
        "Texgen", "Texgen_with_texture_matrix", "Texture_LOD_Bias"],
    "Texture formats": ["Texture_format", "Texture_DXT", "Volume_texture",
        "Texture_signed_component_tests", "Texture_palette",
        "Texture_CPU_Update", "Texture_BRDF", "Color_key"],
    "Render to texture": ["Texture_render_target", "Texture_Framebuffer_Blit",
        "Texture_render_update_in_place", "Surface_format", "Surface_pitch",
        "Null_surface", "Color_zeta_overlap", "Color_Zeta_Disable",
        "Surface_as_vertex_array"],
    "Shadow / projective": ["Texture_shadow_comparator"],
    "Lighting": ["Lighting_spotlight", "Lighting_accumulation",
        "Lighting_range", "Lighting_control", "Lighting_Two_Sided",
        "Lighting_normals", "Material_color_source", "Material_color",
        "Material_alpha",
        "Specular", "Specular_back"],
    "Bump mapping": ["Bump_map", "Bump_env_lum"],
    "Fog": ["Fog", "Fog_gen", "Fog_param", "Fog_carryover", "Fog_vsh",
        "Fog_exceptional_value", "Fog_coord_vec4", "Fog_inf_coord",
        "Fog_planar_vsh"],
    "Blend": ["Blend_tests", "Blend_surface", "Color_mask_blend",
        "Alpha_func"],
    "Depth / stencil": ["Depth_buffer", "Depth_buffer_fixed_function",
        "W_buffering", "W_param", "Depth_Clamp", "Depth_function",
        "Stencil", "Stencil_func", "ZMinMaxControl", "ZPass_pixel_count"],
    "Rasterisation": ["Line_width", "Point_size", "Point_params",
        "Point_sprite", "Swath_width", "Antialiasing_tests",
        "Smoothing_control", "Stipple_tests", "Front_face", "Shade_model",
        "3D_primitive", "Overlapping_draw_modes", "2D_Lines"],
    "Clipping / viewport": ["Window_clip", "Surface_clip", "Viewport",
        "Clear"],
    "Vertex pipeline": ["Attrib_carryover", "Attrib_float", "Attrib_setter",
        "SetVertexData", "Weight_setter", "Zero_stride",
        "Inline_array_size_mismatch", "High_vertex_count",
        "Vertex_shader_independence_tests", "Vertex_shader_swizzle_tests",
        "Vertex_shader_rounding_tests", "Degenerate_begin_end", "Combiner",
        "Pixel_shader", "Edge_flag"],
    "2D / blit": ["Image_blit", "DMA_corruption_around_surfaces",
        "Context_switch"],
}

# The statuses whose `differing` is a measurement. Every other status --
# `unreadable`, `size`, `no-golden`, or none at all -- writes 0 there because
# there is no number, and this file used to read that 0 as an exact capture.
# That is the false win PR #249 removed from arm verdicts, still live in the
# sweep columns: a WSL-interop pull that truncates 56 W_param PNGs would have
# scored them 56 exact. Such a row is VOID -- not exact, not structural px, not
# a capture -- and is counted per category so a column says how much of it was
# unmeasured. Keep equal to score_sweep.py's SCORED_STATUSES; selftest
# fragment 88-sweep-cover.sh fails if they drift. A copy rather than an import
# because score_sweep.py needs numpy and this must run without it.
SCORED_STATUSES = ("ok", "blank", "label-differs", "white-content")


def is_scored(r):
    return (r.get("status") or "") in SCORED_STATUSES


def load_run(d):
    """Rows from every TSV in a directory, plus the provenance they carry.

    A run directory can hold two scorings of the same test -- a suite measured
    on its own disc and again inside a multi-suite sweep. Counting both
    inflates the captures past the number of goldens, which is how this was
    noticed: 82 captures in a category with 46 goldens. Later files win, and
    the count of collisions is reported rather than absorbed.
    """
    seen, shas, discs, dupes = {}, set(), set(), 0
    for f in sorted(glob.glob(os.path.join(d, "*.tsv"))):
        for r in csv.DictReader(open(f), delimiter="\t"):
            if not r.get("suite"):
                continue
            k = (r["suite"], r.get("test", ""))
            if k in seen:
                dupes += 1
            seen[k] = r
            shas.add(r.get("apk_sha", "unknown"))
            discs.add(r.get("disc_id", "unknown"))
    return list(seen.values()), shas, discs, dupes


def summarise(rows, goldens, unscoreable=None):
    """Per category: captures, exact, one-step px, structural px, void, coverage.

    `n` counts SCORED captures only; a void row lands in `void` (and
    `void_by`, by status) and nowhere else, so exact/captures, the pixel
    figures and the coverage floor are all computed over what was measured.
    """
    cat_of = {s: c for c, ss in CATEGORIES.items() for s in ss}
    agg = collections.defaultdict(
        lambda: dict(n=0, exact=0, one=0, px=0, void=0,
                     void_by=collections.Counter(), suites=set(),
                     no_one_step=False))
    for r in rows:
        c = cat_of.get(r["suite"])
        if c is None:
            c = "(uncategorised)"
        a = agg[c]
        a["suites"].add(r["suite"])
        if not is_scored(r):
            a["void"] += 1
            a["void_by"][r.get("status") or "(no status)"] += 1
            continue
        d = int(r.get("differing") or 0)
        a["n"] += 1
        a["px"] += d
        a["exact"] += (d == 0)
        # The 2026-09-08 baseline predates the off_by_one column, so for that
        # run the structural share is not knowable -- differing pixels are all
        # we have. Report that rather than passing the total off as structural,
        # which would make every later run look like an improvement.
        if "off_by_one" in r and r["off_by_one"] not in (None, ""):
            a["one"] += int(r["off_by_one"])
        else:
            a["no_one_step"] = True
    # coverage: captures scored against goldens the category owns, less the
    # goldens no disc can produce -- they are reported, not counted, so a
    # category whose every producible golden was scored shows no floor.
    unscoreable = unscoreable or {}
    for c, a in agg.items():
        have = gone = 0
        for s in CATEGORIES.get(c, a["suites"]):
            gd = os.path.join(goldens, s)
            if os.path.isdir(gd):
                names = [f[:-4] for f in os.listdir(gd) if f.endswith(".png")]
                dead = unscoreable.get(s, set())
                have += sum(n not in dead for n in names)
                gone += sum(n in dead for n in names)
        a["goldens"] = have
        a["unscoreable"] = gone
    return agg


def load_unscoreable(path):
    """({suite: {test}}, {suite: entry}) from unscoreable_goldens.json.

    A missing or unreadable file is reported and read as empty: the board then
    counts every golden, which is the old behaviour and the conservative one.
    """
    try:
        doc = json.load(open(path))
    except (OSError, ValueError) as e:
        sys.stderr.write(f"scoreboard: no unscoreable list ({e}); counting "
                         "every golden\n")
        return {}, {}
    un = {s: set(e.get("tests") or [])
          for s, e in (doc.get("unscoreable") or {}).items()}
    return un, doc.get("not_captured_by_design") or {}


def cell(a):
    if a is None or (a["n"] == 0 and not a.get("void")):
        return "—"
    void = f" · {a['void']} void" if a.get("void") else ""
    if a["n"] == 0:
        return f"0/0{void}"
    if a.get("no_one_step"):
        return f"{a['exact']}/{a['n']} · {a['px']:,} diff†{void}"
    struct = a["px"] - a["one"]
    return f"{a['exact']}/{a['n']} · {struct:,}{void}"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="append", required=True, metavar="LABEL=DIR",
                    help="a labelled directory of score_sweep TSVs, repeatable "
                         "and ordered left to right")
    ap.add_argument("--goldens", required=True)
    ap.add_argument("--md", help="write the table here instead of stdout")
    ap.add_argument("--unscoreable", metavar="JSON",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "unscoreable_goldens.json"),
                    help="goldens no disc produces and suites that save "
                         "nothing (default: unscoreable_goldens.json here)")
    args = ap.parse_args()
    unscoreable, by_design = load_unscoreable(args.unscoreable)

    runs = []
    for spec in args.run:
        if "=" not in spec:
            sys.exit(f"--run wants LABEL=DIR, got {spec!r}")
        label, d = spec.split("=", 1)
        rows, shas, discs, dupes = load_run(d)
        # Written by collect_sweep.sh. Absent for columns collected before the
        # record existed, which is reported as a dash rather than as zero --
        # "not known to be stale" and "known to be current" are different
        # claims and the 2026-09-12 column is exactly why.
        prov = None
        ppath = os.path.join(d, "PROVENANCE.json")
        if os.path.exists(ppath):
            try:
                prov = json.load(open(ppath))
            except Exception:
                prov = None
        runs.append(dict(label=label, dir=d, rows=rows, shas=shas, discs=discs,
                         dupes=dupes, prov=prov,
                         agg=summarise(rows, args.goldens, unscoreable)))

    out = []
    out.append("# Accuracy scoreboard\n")
    out.append("Each cell is **exact/captures · structural px** — structural "
               "being differing pixels that are not one step out, which is the "
               "part that is a rule rather than a rounding floor. **n void** "
               "counts rows whose status is not a measurement (`unreadable`, "
               "`size`, `no-golden`): they are in neither figure, because a "
               "capture that could not be read is not an exact one.\n")

    # Provenance first. A column built from mixed binaries is not a column.
    out.append("| run | binaries | built | hw commits behind tip | discs | captures | void | rescored |")
    out.append("|---|---|---|---:|---:|---:|---:|---:|")
    for r in runs:
        shas = ", ".join(sorted(r["shas"])) or "—"
        warn = " ⚠️ mixed" if len(r["shas"]) > 1 else ""
        dup = f"{r['dupes']}" if r["dupes"] else "—"
        prov = r.get("prov") or {}
        behind = prov.get("hw_behind_tip")
        dates = sorted({i.get("date") or "" for i in prov.get("refs") or []} - {""})
        built = ", ".join(dates) if dates else "—"
        if behind is None:
            age = "—"
        elif behind == 0:
            age = "0"
        else:
            age = f"{behind} ⚠️"
        vb = collections.Counter(r2.get("status") or "(no status)"
                                 for r2 in r["rows"] if not is_scored(r2))
        void = (f"{sum(vb.values())} ⚠️ (" + ", ".join(
            f"{k} {v}" for k, v in sorted(vb.items())) + ")") if vb else "0"
        scored = len(r["rows"]) - sum(vb.values())
        out.append(f"| `{r['label']}` | {shas}{warn} | {built} | {age} | "
                   f"{len(r['discs'])} | {scored} | {void} | {dup} |")
    out.append("")

    cats = [c for c in CATEGORIES] + ["(uncategorised)"]
    header = "| category | goldens | " + " | ".join(f"`{r['label']}`" for r in runs) + " |"
    out.append(header)
    out.append("|---|---:|" + "---|" * len(runs))
    for c in cats:
        present = [r["agg"].get(c) for r in runs]
        if not any(a and (a["n"] or a["void"]) for a in present):
            continue
        g = next((a["goldens"] for a in present if a), 0)
        gone = next((a["unscoreable"] for a in present if a), 0)
        cov = ""
        first = next((a for a in present if a and (a["n"] or a["void"])), None)
        if first and g and first["n"] < g:
            cov = f" ⚠️{100.0 * first['n'] / g:.0f}%"
        gcell = f"{g} (+{gone} unscoreable)" if gone else f"{g}"
        out.append(f"| {c}{cov} | {gcell} | " +
                   " | ".join(cell(a) for a in present) + " |")

    # What the denominators leave out, by name, so a missing floor is never
    # mistaken for a suite that was simply not looked at.
    if unscoreable or by_design:
        out.append("\n**Unscoreable goldens** are in the golden set but no disc "
                   "in use emits them (renamed or compiled-out tests); they are "
                   "counted in no denominator above. **Not captured by design** "
                   "are suites that save nothing, so they have no goldens to "
                   "score. Both come from `unscoreable_goldens.json`.\n")
        for s, tests in sorted(unscoreable.items()):
            out.append(f"- unscoreable: `{s}` {len(tests)}")
        for s, e in sorted(by_design.items()):
            out.append(f"- not captured by design: `{s}` "
                       f"({e.get('tests', '?')} tests) -- {e.get('reason', '')}")

    out.append("\n† that run did not record the one-step column, so its figure "
               "is *all* differing pixels and is not comparable with a "
               "structural count. The 2026-09-08 baseline predates it.\n")
    out.append("\n**hw commits behind tip** is how many commits touching `hw/` "
               "separate the binary that produced a column from the branch tip "
               "when it was collected. `apk_sha` says which binary; this says "
               "whether it is the current one. A column collected on 2026-09-12 "
               "sat 87 commits and 2,111 `hw/` insertions behind, with every "
               "correctness fix of that day missing, and its sha was perfectly "
               "consistent throughout -- consistency is not currency. A dash "
               "means the column predates this record.\n")
    out.append("\n⚠️ on a category means the leftmost run scored fewer captures "
               "than that category has goldens: the cell is a floor, not a "
               "score. ⚠️ on a run means its rows disagree about which binary "
               "produced them.\n")
    out.append("\nA ⚠️ FLOOR IS NOT ALWAYS A LIMITATION OF THE EMULATOR, AND "
               "BLEND'S IS NOT. Blend shows the worst coverage on this board "
               "because 1,568 of its 1,722 goldens come from `TestDetailed`, "
               "which upstream marked interactive-only when `#spot_` replaced "
               "it -- so the stock disc does not run them and the sweep cannot "
               "score them. That was recorded for a day as \"behind the "
               "test-suite fork\", and it was false: on 2026-09-13 a run on a "
               "one-byte-patched disc scored **1,673 of 1,673** with "
               "`partial: false`. The 1,568 captures had also been on disk "
               "since 2026-09-12.\n\nSo this row is liftable, not stuck. "
               "`docs/testing/request.sh --base-iso "
               "/home/justin/nxdk_pgraph_tests_xiso_interactive.iso` reaches "
               "them; that disc's `disc_id` tags as `iso:85b525/...` so its "
               "figures can never be silently compared with a stock column, "
               "which is also why those 1,673 captures are NOT folded into the "
               "columns above. Anyone reading this row as a permanent ceiling "
               "should read `docs/investigations/xbe-interactive-patch.md` "
               "first.\n")
    text = "\n".join(out)
    if args.md:
        open(args.md, "w").write(text + "\n")
        print(f"wrote {args.md} ({len(runs)} run(s), "
              f"{sum(len(r['rows']) for r in runs)} rows)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
