#!/usr/bin/env python3
"""Render side-by-side comparisons for tests that do not match bit-for-bit.

A number cannot be scrutinised. "0.00 mean error" hid a test that differed on
1,536 pixels, and an RGB-only comparison hid 1,279 differing alpha pixels — both
were caught by looking at the images, not by reading the figure. So any result
short of bit-identical gets surfaced as pictures.

    diff_specimen.py -o out.html --goldens goldens/results \\
        --results res_dir Texture_DXT::DXT3_plasma_dxt3 [more...]

    diff_specimen.py -o out.html --goldens goldens/results \\
        --results res_dir --all-differing

Each specimen shows the hardware capture, our output, and the difference map
both unamplified and amplified — small errors are invisible at 1:1, which is
exactly how they get mistaken for a match. Metrics are differing-pixel count and
max channel delta, per channel group, because a mean cannot separate "this
format is not decoded" (max 255) from "rounding" (max 8).

Output is one self-contained HTML file with the images inlined, suitable for
attaching to a pull request. Per AGENTS.md, a PR that closes or downgrades a
test must carry this.
"""
import argparse
import base64
import datetime
import io
import os
import subprocess
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("needs numpy and pillow: pip install numpy pillow")


def load(path):
    return np.asarray(Image.open(path).convert("RGBA")).astype(int)


def png_uri(arr):
    buf = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8)).save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def diff_map(g, o, gain, alpha=False):
    d = (np.abs(g[..., 3] - o[..., 3]) if alpha
         else np.abs(g[..., :3] - o[..., :3]).max(axis=2))
    a = np.clip(d * gain, 0, 255)
    return np.stack([a, a, a], axis=2)


def measure(g, o):
    rgb = np.abs(g[..., :3] - o[..., :3])
    al = np.abs(g[..., 3] - o[..., 3])
    return {
        "rgb_px": int((rgb.max(axis=2) > 0).sum()),
        "rgb_max": int(rgb.max()),
        "a_px": int((al > 0).sum()),
        "a_max": int(al.max()),
        "total": g.shape[0] * g.shape[1],
    }


def gain_for(max_delta):
    """Amplify so the largest real error lands near full scale."""
    return 1 if max_delta >= 128 else max(1, min(255, 255 // max(max_delta, 1)))


CSS = """
:root{--ground:#eef0f4;--surface:#fafbfc;--edge:#cdd3de;--ink:#1b1f27;--ink-2:#4a5364;
--ink-3:#6f7889;--accent:#0f7d92;--ok:#2f7d55;--bad:#a8402f;--ok-bg:#dfeee5;--bad-bg:#f6dedb;
--mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
--sans:"IBM Plex Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ground:#0e1116;
--surface:#151a21;--edge:#2b323d;--ink:#e8ecf2;--ink-2:#a8b2c1;--ink-3:#7c8698;
--accent:#4fc3dc;--ok:#6bc490;--bad:#e2796a;--ok-bg:#16302270;--bad-bg:#3a1c1770;}}
:root[data-theme="dark"]{--ground:#0e1116;--surface:#151a21;--edge:#2b323d;--ink:#e8ecf2;
--ink-2:#a8b2c1;--ink-3:#7c8698;--accent:#4fc3dc;--ok:#6bc490;--bad:#e2796a;
--ok-bg:#16302270;--bad-bg:#3a1c1770;}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font-family:var(--sans);line-height:1.6;
-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:44px 24px 72px}
.eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;
color:var(--accent)}
h1{font-size:clamp(26px,4vw,36px);font-weight:600;letter-spacing:-.02em;margin:10px 0 8px;
text-wrap:balance}
.lede{max-width:68ch;color:var(--ink-2);margin:0 0 36px}
.spec{background:var(--surface);border:1px solid var(--edge);border-radius:10px;
overflow:hidden;margin-bottom:34px}
.spec-head{padding:20px 22px 16px;display:flex;flex-direction:column;gap:9px}
.badge{align-self:flex-start;font-family:var(--mono);font-size:11px;font-weight:600;
letter-spacing:.1em;text-transform:uppercase;padding:4px 10px;border-radius:4px}
.ok{color:var(--ok);background:var(--ok-bg)}.bad{color:var(--bad);background:var(--bad-bg)}
.spec h2{margin:0;font-family:var(--mono);font-size:15px;font-weight:500;color:var(--ink-2)}
.strip{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--edge);
border-top:1px solid var(--edge);border-bottom:1px solid var(--edge)}
figure{margin:0;background:var(--surface);padding:13px;display:flex;flex-direction:column;gap:8px}
figure img{width:100%;height:auto;display:block;border-radius:3px;background:#000;
border:1px solid var(--edge)}
figcaption{font-family:var(--mono);font-size:11.5px;color:var(--ink-2)}
figcaption em{display:block;color:var(--ink-3);font-size:11px}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--edge);margin:0}
.metric{background:var(--surface);padding:13px 22px}
.metric dt{font-family:var(--mono);font-size:11px;letter-spacing:.09em;text-transform:uppercase;
color:var(--ink-3)}
.metric dd{margin:2px 0 0;font-family:var(--mono);font-size:19px;font-weight:500;
font-variant-numeric:tabular-nums}
.build{display:flex;flex-wrap:wrap;gap:8px 24px;margin:0 0 30px;padding:13px 17px;
background:var(--surface);border:1px solid var(--edge);border-radius:8px}
.build div{display:flex;flex-direction:column;gap:1px}
.build dt{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;
text-transform:uppercase;color:var(--ink-3)}
.build dd{margin:0;font-family:var(--mono);font-size:13px;color:var(--ink)}
@media(max-width:860px){.strip,.metrics{grid-template-columns:repeat(2,1fr)}}
@media(max-width:520px){.strip{grid-template-columns:1fr}}
"""


def build_identity(results_dir):
    """Commit, time and inputs, so two comparisons can never be confused.

    A page without this is indistinguishable from the last one at a glance, and
    a client that keys on filename may not even show it. Every published
    comparison carries where it came from.
    """
    def git(*a):
        try:
            return subprocess.run(("git",) + a, capture_output=True, text=True,
                                  cwd=os.path.dirname(os.path.abspath(__file__))
                                  ).stdout.strip()
        except Exception:
            return ""
    sha = git("rev-parse", "--short", "HEAD") or "unknown"
    dirty = " +dirty" if git("status", "--porcelain") else ""
    when = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    rows = [("commit", sha + dirty), ("results", os.path.basename(results_dir.rstrip("/"))),
            ("generated", when)]
    dev = os.environ.get("SERIAL")
    if dev:
        rows.insert(2, ("device", dev))
    cells = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in rows)
    return sha, f'<dl class="build">{cells}</dl>'


def build(specs, title, identity=""):
    parts = []
    for s in specs:
        m, gain = s["m"], s["gain"]
        exact = m["rgb_px"] == 0 and m["a_px"] == 0
        badge = ('<span class="badge ok">bit-identical</span>' if exact else
                 f'<span class="badge bad">differs on {m["rgb_px"] + m["a_px"]:,} px</span>')
        amp = ("no amplification needed" if gain == 1 else f"amplified &times;{gain}")
        parts.append(f"""<article class="spec">
  <header class="spec-head">{badge}<h2>{s['name']}</h2></header>
  <div class="strip">
    <figure><img src="{s['gold']}" alt="hardware capture"><figcaption>Hardware capture</figcaption></figure>
    <figure><img src="{s['ours']}" alt="our output"><figcaption>Our output</figcaption></figure>
    <figure><img src="{s['d1']}" alt="difference"><figcaption>Difference &times;1<em>1:1, as measured</em></figcaption></figure>
    <figure><img src="{s['dn']}" alt="difference amplified"><figcaption>Difference<em>{amp}</em></figcaption></figure>
  </div>
  <dl class="metrics">
    <div class="metric"><dt>RGB pixels differing</dt><dd>{m['rgb_px']:,}</dd></div>
    <div class="metric"><dt>Max RGB delta</dt><dd>{m['rgb_max']}</dd></div>
    <div class="metric"><dt>Alpha pixels differing</dt><dd>{m['a_px']:,}</dd></div>
    <div class="metric"><dt>Max alpha delta</dt><dd>{m['a_max']}</dd></div>
  </dl>
</article>""")
    return f"""<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
  <span class="eyebrow">hakuX &middot; pgraph accuracy harness</span>
  <h1>{title}</h1>
  {identity}
  <p class="lede">Framebuffers from real XBOX 1.0 hardware
  (abaire/nxdk_pgraph_tests_golden_results) beside our output, with the difference
  shown at 1:1 and amplified. Small errors are invisible unamplified, which is how
  they get mistaken for a match.</p>
  {''.join(parts)}
</div>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tests", nargs="*", metavar="Suite::Test")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--goldens", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--all-differing", action="store_true",
                    help="every test in --results that is not bit-identical")
    ap.add_argument("--title", default="Framebuffer comparisons")
    args = ap.parse_args()

    names = list(args.tests)
    if args.all_differing:
        names = sorted(n[:-4] for n in os.listdir(args.results)
                       if n.endswith(".png") and "::" in n)
    if not names:
        sys.exit("give tests as Suite::Test, or pass --all-differing")

    specs = []
    for name in names:
        suite, test = name.split("::", 1)
        gp = os.path.join(args.goldens, suite, f"{test}.png")
        op = os.path.join(args.results, f"{suite}::{test}.png")
        if not (os.path.exists(gp) and os.path.exists(op)):
            print(f"  skip {name}: missing image", file=sys.stderr); continue
        g, o = load(gp), load(op)
        if g.shape != o.shape:
            print(f"  skip {name}: size mismatch", file=sys.stderr); continue
        m = measure(g, o)
        if args.all_differing and m["rgb_px"] == 0 and m["a_px"] == 0:
            continue
        gain = gain_for(max(m["rgb_max"], m["a_max"]))
        specs.append({"name": name, "m": m, "gain": gain,
                      "gold": png_uri(g[..., :3]), "ours": png_uri(o[..., :3]),
                      "d1": png_uri(diff_map(g, o, 1)),
                      "dn": png_uri(diff_map(g, o, gain))})

    if not specs:
        print("nothing to show — every test compared is bit-identical")
        return 0
    sha, identity = build_identity(args.results)
    out = args.output
    # Stamp the filename too: a client that keys on name will otherwise show an
    # older page when a second comparison arrives.
    root, ext = os.path.splitext(out)
    if sha != "unknown" and sha not in root:
        out = f"{root}_{sha}{ext}"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(build(specs, f"{args.title} {sha}".strip(), identity))
    args.output = out
    kb = os.path.getsize(out) // 1024
    print(f"wrote {out} ({len(specs)} specimen(s), {kb} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
