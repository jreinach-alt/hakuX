#!/usr/bin/env python3
"""Turn the rendered harness dashboard (status/index.html) into GitHub Markdown plus a standalone chart.svg.

Same data as the page, laid out for a phone: sections, goal bars, one row per title (the per-title
expansions stay in index.html), lanes as bullets. Usage: status_md.py in.html out.md out_chart.svg
"""
import re, sys
from html.parser import HTMLParser

VOID = {"br", "hr", "img", "input", "meta", "link", "col"}
DOT = {"green": "\U0001F7E2", "blue": "\U0001F535", "red": "\U0001F534", "purple": "\U0001F7E3", "amber": "\U0001F7E1", "grey": "⚪", "gray": "⚪"}


class N:
    def __init__(self, tag, attrs, parent):
        self.tag, self.a, self.p, self.kids = tag, dict(attrs), parent, []

    def cls(self):
        return (self.a.get("class") or "").split()


class T(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = N("root", [], None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = N(tag, attrs, self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(N(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.p
        if n is not None and n.p is not None:
            self.cur = n.p

    def handle_data(self, d):
        self.cur.kids.append(d)


def find(n, pred):
    if isinstance(n, str):
        return
    if pred(n):
        yield n
    for k in n.kids:
        yield from find(k, pred)


def esc(s):
    s = s.replace("\\", "\\\\").replace("*", "\\*").replace("<", "&lt;").replace("|", "\\|")
    return re.sub(r"\s+", " ", s)


def join(kids, skip=()):
    out = ""
    prev = None
    for k in kids:
        v = inline(k, skip)
        if out and v and (not isinstance(prev, str) or not isinstance(k, str)) \
                and re.search(r"[\w*`)]$", out) and re.match(r"[\w`(*]", v):
            out += " "
        out += v
        if v:
            prev = k
    return out


def inline(n, skip=()):
    if isinstance(n, str):
        return esc(n)
    if n.tag in ("script", "style", "svg") or n.tag in skip or "hidden" in n.a:
        return ""
    if n.tag == "br":
        return "<br>"
    inner = join(n.kids, skip)
    if n.tag == "code":
        t = "".join(text(k) for k in n.kids).replace("|", "\\|")
        t = re.sub(r"\s+", " ", t).strip()
        return ("`` %s ``" % t) if "`" in t else ("`%s`" % t)
    if n.tag in ("b", "strong") and inner.strip():
        return "**%s**" % inner.strip()
    if n.tag in ("i", "em") and inner.strip():
        return "_%s_" % inner.strip()
    if n.tag == "a" and n.a.get("href", "").startswith("http") and inner.strip():
        return "[%s](%s)" % (inner.strip(), n.a["href"])
    if n.tag == "span" and "bad" in n.cls() and inner.strip():
        return "**%s**" % inner.strip()
    return inner


def text(n):
    if isinstance(n, str):
        return n
    if n.tag in ("script", "style", "svg"):
        return ""
    return "".join(text(k) for k in n.kids)


def slug(s):
    s = re.sub(r"[^\w\- ]", "", s.lower())
    return s.replace(" ", "-")


def cell(n, skip=()):
    return re.sub(r"(<br>\s*)+$", "", re.sub(r"\s+", " ", inline(n, skip)).strip()).strip()


def bar(frac):
    k = max(0, min(10, round(frac * 10)))
    return "▓" * k + "░" * (10 - k)


def lanes_table(t, out):
    rows = [r for r in find(t, lambda x: x.tag == "tr")]
    for r in rows:
        tds = [k for k in r.kids if not isinstance(k, str) and k.tag == "td"]
        if not tds:
            continue
        head, rest = tds[0], []
        for td in tds[1:]:
            v = cell(td, skip=("details",))
            if v:
                rest.append("%s: %s" % (td.a.get("data-l", ""), v) if td.a.get("data-l") else v)
        notes = [n for d in find(head, lambda x: x.tag == "details") for n in [cell(d)]]
        out.append("- %s%s" % (cell(head, skip=("details",)) or "-", (" -- " + "; ".join(rest)) if rest else ""))
        for nt in notes:
            out.append("  - %s" % nt)


def plain_table(t, out):
    rows = []
    for r in find(t, lambda x: x.tag == "tr"):
        rows.append([cell(c) for c in r.kids if not isinstance(c, str) and c.tag in ("td", "th")])
    rows = [r for r in rows if r]
    if not rows:
        return
    w = max(len(r) for r in rows)
    rows = [r + [""] * (w - len(r)) for r in rows]
    out.append("| " + " | ".join(rows[0]) + " |")
    out.append("|" + "---|" * w)
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    out.append("")


def title_table(t, out):
    # Three columns (#433): the C I S B pipeline column is gone -- Copied meant
    # nothing, and Inputs/Save are replaced by reach-gameplay/soak-for-Playable.
    out += ["| Title and next step | Status | fps |", "|---|---|---|"]
    for tb in find(t, lambda x: x.tag == "tbody"):
        ct = next(find(tb, lambda x: "c-t" in x.cls()), None)
        cs = next(find(tb, lambda x: "c-s" in x.cls()), None)
        cf = next(find(tb, lambda x: "c-f" in x.cls() and x.tag == "td"), None)
        if ct is None:
            continue
        name = cell(next(find(ct, lambda x: x.tag == "summary"), ""))
        extra = [cell(k) for k in ct.kids if not isinstance(k, str) and k.tag != "details"]
        extra = [e for e in extra if e]
        chip = next(find(cs, lambda x: any(c.startswith("k-") for c in x.cls())), None) if cs is not None else None
        col = next((c[2:] for c in chip.cls() if c.startswith("k-")), "") if chip is not None else ""
        status = (DOT.get(col, "") + " " + cell(cs)).strip() if cs is not None else ""
        fps = ""
        if cf is not None:
            parts = [cell(k) for k in cf.kids if not isinstance(k, str)]
            parts = [p for p in parts if p]
            if parts:
                fps = parts[0] + (("<br>" + "<br>".join(parts[1:])) if len(parts) > 1 else "")
        out.append("| **%s**%s | %s | %s |" % (name, "".join("<br>" + e for e in extra), status, fps))
    out.append("")


def block(n, out, ids, svgs):
    if isinstance(n, str):
        return
    c = n.cls()
    if n.tag in ("script", "style", "header") or "hidden" in n.a:
        return
    if n.tag in ("h1", "h2", "h3", "h4"):
        h = cell(n)
        out += ["#" * int(n.tag[1]) + " " + h, ""]
        if n.tag == "h2" and n.p is not None and n.p.a.get("id"):
            ids[n.p.a["id"]] = slug(text(n))
        return
    if "goal" in c:
        lab = cell(next(find(n, lambda x: "gl" in x.cls()), ""))
        w = next(find(n, lambda x: x.tag == "i"), None)
        m = re.search(r"width:([\d.]+)%", (w.a.get("style") or "") if w else "")
        out += ["%s&nbsp;&nbsp;`%s`" % (lab, bar(float(m.group(1)) / 100 if m else 0)), ""]
        return
    if n.tag == "svg":
        # Two charts now (#433): "How close is 0.6?" then "How close is 1.0?".
        # The first is chart.svg (unchanged name, for anything already linking
        # it); the second is chart2.svg. Both are written by build()'s caller.
        i = svgs[0]
        svgs[0] += 1
        if i == 0:
            out += ["![Titles over time](chart.svg)", ""]
        else:
            out += ["![Titles toward 1.0](chart2.svg)", ""]
        return
    if n.tag == "table":
        if "tt" in c:
            title_table(n, out)
        elif any(td.a.get("data-l") for td in find(n, lambda x: x.tag == "td")):
            lanes_table(n, out)
            out.append("")
        else:
            plain_table(n, out)
        return
    if n.tag in ("ul", "ol"):
        for i, li in enumerate([k for k in n.kids if not isinstance(k, str) and k.tag == "li"], 1):
            out.append(("%d. " % i if n.tag == "ol" else "- ") + cell(li))
        out.append("")
        return
    if n.tag == "details":
        s = next(find(n, lambda x: x.tag == "summary"), None)
        body = []
        for k in n.kids:
            if k is s:
                continue
            if isinstance(k, str):
                if k.strip():
                    body.append(esc(k).strip())
            else:
                block(k, body, ids, svgs)
        out += ["<details><summary>%s</summary>" % (cell(s) if s else "details"), ""] + body + ["", "</details>", ""]
        return
    if n.tag == "pre":
        out += ["```", text(n).rstrip(), "```", ""]
        return
    if n.tag in ("p", "footer"):
        v = cell(n)
        if v:
            out += [("_%s_" % v) if n.tag == "footer" else v, ""]
        return
    kinds = [k for k in n.kids if not isinstance(k, str)]
    if n.tag in ("div", "section", "main", "root", "body", "html") and (kinds or any(isinstance(k, str) and k.strip() for k in n.kids)):
        loose = []
        for k in n.kids:
            if isinstance(k, str) or k.tag in ("b", "span", "i", "code", "a", "em", "strong"):
                loose.append(k)
                continue
            if loose:
                v = re.sub(r"\s+", " ", join(loose)).strip()
                if v:
                    out += [v, ""]
                loose = []
            block(k, out, ids, svgs)
        if loose:
            v = re.sub(r"\s+", " ", join(loose)).strip()
            if v:
                out += [v, ""]
        return
    v = cell(n)
    if v:
        out += [v, ""]


def chart_svg(html, index=0):
    """The `index`-th (0-based) inline chart, standalone. None past the last one."""
    starts = [m.start() for m in re.finditer(r'<svg class="chart"', html)]
    if index >= len(starts):
        return None
    i = starts[index]
    j = html.find("</svg>", i)
    svg = html[i:j + 6]
    css = html[html.find("<style>") + 7:html.find("</style>")]
    head = css.split("\n*{", 1)[0]
    rules = "".join(re.findall(r"\.chart [^{}]*\{[^}]*\}", css))
    svg = svg.replace('<svg class="chart"', '<svg class="chart" xmlns="http://www.w3.org/2000/svg" width="400" height="236"', 1)
    svg = svg.replace("</svg>", "", 1)
    return svg.replace(">", ">\n<style>%s%s svg{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}</style>"
                      '<rect width="400" height="236" rx="6" style="fill:var(--bg)"/>' % (head, rules), 1) + "</svg>\n"


def build(html):
    """Returns (markdown, charts): `charts` is the inline chart SVGs standalone,
    in page order (#433: one or two -- "How close is 0.6?" then "...1.0?")."""
    t = T()
    t.feed(html)
    main = next(find(t.root, lambda x: x.tag == "main"))
    age = next(find(main, lambda x: x.a.get("id") == "age"), None)
    gl = next(find(main, lambda x: "glance" in x.cls()), None)
    out = ["# hakuX harness", "", "_%s_" % cell(age) if age is not None else "", ""]
    ids = {}
    body = []
    svgs = [0]
    for k in main.kids:
        if isinstance(k, str) or k.tag == "header":
            continue
        block(k, body, ids, svgs)
    md = "\n".join(out + body)
    for q, s in ids.items():
        md = md.replace("(#%s)" % q, "(#%s)" % s)
    md = md.replace(" Tap a title for the rest.", " The per-title detail is in index.html.")
    md = re.sub(r"\n{3,}", "\n\n", md).rstrip() + "\n"
    charts = []
    for idx in range(svgs[0]):
        s = chart_svg(html, idx)
        if s:
            charts.append(s)
    return md, charts


if __name__ == "__main__":
    md, charts = build(open(sys.argv[1], encoding="utf-8").read())
    open(sys.argv[2], "w", encoding="utf-8").write(md)
    if charts:
        open(sys.argv[3], "w", encoding="utf-8").write(charts[0])
    if len(charts) > 1:
        p2 = re.sub(r"\.svg$", "2.svg", sys.argv[3]) if sys.argv[3].endswith(".svg") else sys.argv[3] + "2"
        open(p2, "w", encoding="utf-8").write(charts[1])
