#!/usr/bin/env python3
"""pathclass: a local screen-state classifier for pathfind (tiers 1 and 2), on the host GPU.

    python3 pathclass.py classify <frame> [--prev <frame>] [--context '{"menu_seen": true}'] [--no-ocr]
    python3 pathclass.py serve        JSON lines: {"frame": .., "prev": .., "context": {..}} in, one answer out
    python3 pathclass.py check        exit 0 when the venv, the GPU and the weights are usable

Any python3 may run it: it re-executes itself under the venv ($PATHCLASS_VENV, default
~/hakux-work/venvs/pathclass). In-process, `Classifier` needs the venv; `Client` works from any python
and keeps one `serve` process (models loaded once).

Each answer:
    {state, confidence, top3: [[state, p], ..], moving, diff, black, menu: [{text, box, highlighted, intent}],
     action: {do, why}, escalate: <reason or null>, source, ms}

Fail open: when the venv, torch, the GPU or the weights are missing, `classify`/`serve`/`check` print ONE line
starting `pathclass: unavailable:` on stderr and exit 3, and `Client` raises `Unavailable`, so the caller
falls back to the language model and never stops.

Tiers. (1) free checks: black (mean luma, FPS corner masked, or a flat fade; classify.py's thresholds) and
moving (changed fraction against --prev, classify.py's motion). (2) a SigLIP2 image embedding scored by a
trained linear head (docs/testing/titles/pathknow/classifier/head.npz) or, without one, zero-shot text
prompts; then the temporal rule below, the OCR menu reader on menu-like states, and the rule table.

Temporal separation (the image alone cannot tell an attract demo from play, or an intro from a cutscene):
the caller passes context.menu_seen (has this run shown a title screen or menu yet?). Before the first menu,
cutscene and gameplay-looking frames are intro_video (an attract demo IS gameplay pixels); after it,
intro_video is cutscene. publisher_logo vs intro_video: a logo is static (moving false) for its whole show;
a moving logo-classed frame is intro_video. pathfind's own rule 5 (an input visibly changes the scene) is
still the only gameplay CLAIM; this classifier only names candidates.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VENV = os.environ.get("PATHCLASS_VENV", os.path.expanduser("~/hakux-work/venvs/pathclass"))
MODELS = os.environ.get("PATHCLASS_MODELS", os.path.expanduser("~/hakux-work/models/pathclass"))
HEAD = os.environ.get("PATHCLASS_HEAD", os.path.join(HERE, "pathknow", "classifier", "head.npz"))
BACKBONE = ("ViT-B-16-SigLIP2-384", "webli")
UNAVAILABLE_EXIT = 3

STATES = ["intro_video", "publisher_logo", "title_screen", "main_menu", "submenu", "profile_creation",
          "name_entry", "save_load_prompt", "controller_prompt", "loading", "cutscene", "pause", "gameplay",
          "results", "game_over", "black", "unknown"]
MENU_STATES = {"title_screen", "main_menu", "submenu", "profile_creation", "name_entry", "save_load_prompt",
               "controller_prompt", "pause", "results", "game_over"}
# OCR runs on these image states: menus to steer, and the states an overlay's text can overturn
OCR_STATES = MENU_STATES | {"unknown", "gameplay", "intro_video", "cutscene", "loading"}

# classify.py's free-check constants (docs/testing/titles/classify.py), on a 640x480 frame
FPS_CORNER = (0, 0, 130, 50)
BLACK_LUMA = 8.0
FLAT_STD = 3.0
MOTION_SIZE = (160, 120)
MOTION_PIXEL = 16
MOVING_BAR = 0.05

CONFIDENCE_BAR = 0.6          # below this the answer says escalate: low_confidence

# Rule table: state -> (default action, why). pathfind owns the final decision; menus are refined by the OCR
# intent below and name_entry/save prompts carry the known traps (titleroutes NOTES).
RULES = {
    "black": ("wait", "black frame: a load or a fade"),
    "loading": ("wait", "loading screen"),
    "intro_video": ("START", "skip ladder: START, then A, then wait and reread"),
    "publisher_logo": ("START", "skip ladder: START, then A"),
    "title_screen": ("START", "title screen: START"),
    "controller_prompt": ("START", "press START/A prompt"),
    "main_menu": ("menu", "steer by menu text: select a play item"),
    "submenu": ("menu", "steer by menu text: accept the default (A) unless an avoid item is highlighted"),
    "profile_creation": ("A", "accept the default profile/slot"),
    "name_entry": ("START", "trap: A types a letter; START jumps to Accept/Done"),
    "save_load_prompt": ("escalate", "trap: prompts default to No; read the options"),
    "cutscene": ("START", "skip ladder: START, then A"),
    "pause": ("START", "resume"),
    "gameplay": ("verify", "candidate only: push an input and check the playfield changes (pathfind rule 5)"),
    "results": ("A", "continue past results"),
    "game_over": ("A", "retry/continue"),
    "unknown": ("escalate", "unknown screen"),
}

# Menu item text -> intent. Lowercased substring match, longest first; 'select' items lead to play fastest.
INTENTS = {
    "select": ["play now", "quick play", "quick race", "quick match", "quickplay", "exhibition", "arcade",
               "single player", "single race", "new game", "start game", "new campaign", "campaign", "story",
               "play game", "begin", "start", "play", "free play", "versus", "vs mode", "one player", "1 player",
               "career", "accept", "done", "ok", "continue without saving", "yes", "create", "next", "go"],
    "avoid": ["options", "settings", "credits", "xbox live", "live", "online", "system link", "extras",
              "bonus", "gallery", "high scores", "leaderboard", "load game", "delete", "quit", "exit",
              "controller", "audio", "video", "how to play", "tutorial", "help", "dashboard", "back", "cancel",
              "no"],
}


def intent_of(text):
    import re
    t = " ".join(text.lower().split())
    best, blen = None, 0
    for intent, words in INTENTS.items():
        for w in words:
            # whole words only: 'start' is not in 'Startled', 'no' is not in 'Nobody'
            hit = re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", t)
            if hit and len(w) > blen:
                best, blen = intent, len(w)
    return best


def decide(state, menu, context=None):
    """The rule table plus the menu intent: returns ({do, why}, escalate reason or None)."""
    do, why = RULES.get(state, ("escalate", "no rule"))
    if do == "menu":
        if not menu:
            return {"do": "A", "why": why + " (no text read: accept the default)"}, "menu_unread"
        hi = [m for m in menu if m.get("highlighted")]
        sel = [m for m in menu if m.get("intent") == "select"]
        if hi and hi[0].get("intent") == "select":
            return {"do": "A", "why": f"highlighted '{hi[0]['text']}' leads to play"}, None
        if sel and hi:
            h, s = hi[0]["box"], sel[0]["box"]
            dy, dx = (s[1] + s[3]) / 2 - (h[1] + h[3]) / 2, (s[0] + s[2]) / 2 - (h[0] + h[2]) / 2
            d = ("DOWN" if dy > 0 else "UP") if abs(dy) >= abs(dx) else ("RIGHT" if dx > 0 else "LEFT")
            return {"do": d, "why": f"move from '{hi[0]['text']}' toward '{sel[0]['text']}'"}, None
        if hi and hi[0].get("intent") == "avoid":
            return {"do": "DOWN", "why": f"highlighted '{hi[0]['text']}' is an avoid item"}, None
        if sel:
            return {"do": "A", "why": f"'{sel[0]['text']}' present, highlight unknown: accept the default"}, None
        return {"do": "A", "why": "no menu text matched the intent table"}, "menu_no_match"
    if do == "escalate":
        return {"do": "escalate", "why": why}, state
    return {"do": do, "why": why}, None


# ---------------------------------------------------------------- free checks (numpy + PIL only)

def _grey(path_or_im):
    from PIL import Image
    im = path_or_im if hasattr(path_or_im, "convert") else Image.open(path_or_im)
    im = im.convert("L")
    if im.size != (640, 480):
        im = im.resize((640, 480), Image.BILINEAR)
    im = im.copy()
    im.paste(0, FPS_CORNER)
    return im


def free_checks(frame, prev=None):
    import numpy as np
    from PIL import Image
    g = _grey(frame)
    a = np.asarray(g, dtype=np.float64)
    # the FPS corner is pasted black: measure luma and flatness outside it
    m = np.ones_like(a, dtype=bool)
    m[FPS_CORNER[1]:FPS_CORNER[3], FPS_CORNER[0]:FPS_CORNER[2]] = False
    lum, std = float(a[m].mean()), float(a[m].std())
    out = {"black": bool(lum < BLACK_LUMA or std < FLAT_STD), "luma": round(lum, 1), "moving": None, "diff": None}
    if prev:
        try:
            p = np.asarray(_grey(prev).resize(MOTION_SIZE, Image.BILINEAR), dtype=np.int16)
            c = np.asarray(g.resize(MOTION_SIZE, Image.BILINEAR), dtype=np.int16)
            ch = float((np.abs(c - p) > MOTION_PIXEL).mean())
            out.update(moving=bool(ch >= MOVING_BAR), diff=round(ch, 4))
        except Exception:
            pass
    return out


# ---------------------------------------------------------------- the GPU tiers (venv only)

class Unavailable(RuntimeError):
    pass


class Classifier:
    """In-process classifier. Needs the venv (torch, open_clip, easyocr) and a CUDA GPU."""

    def __init__(self, head=HEAD, ocr=True, device=None):
        os.environ.setdefault("HF_HOME", os.path.join(MODELS, "hf"))
        os.environ.setdefault("TORCH_HOME", os.path.join(MODELS, "torch"))
        try:
            import numpy as np
            import torch
            import open_clip
        except Exception as e:
            raise Unavailable(f"import failed ({e.__class__.__name__}: {e})")
        self.np, self.torch = np, torch
        dev = device or ("cuda" if torch.cuda.is_available() else None)
        if dev is None:
            raise Unavailable("no CUDA GPU visible to torch")
        self.dev = dev
        model, pretrained = BACKBONE
        self.head = None
        if head and os.path.exists(head):
            z = np.load(head, allow_pickle=True)
            model, pretrained = str(z["model"]), str(z["pretrained"])
            self.head = {k: z[k] for k in z.files}
        try:
            m, _, pre = open_clip.create_model_and_transforms(model, pretrained=pretrained, device=dev,
                                                             precision="fp16" if dev == "cuda" else "fp32")
        except Exception as e:
            raise Unavailable(f"backbone {model}/{pretrained} failed to load ({e})")
        m.eval()
        self.model = m
        self.size = m.visual.image_size if isinstance(m.visual.image_size, (tuple, list)) else \
            (m.visual.image_size, m.visual.image_size)
        norm = [t for t in pre.transforms if t.__class__.__name__ == "Normalize"][0]
        self.mean = torch.tensor(norm.mean, device=dev).view(1, 3, 1, 1)
        self.std = torch.tensor(norm.std, device=dev).view(1, 3, 1, 1)
        if self.head is None:
            self._zero_shot(open_clip.get_tokenizer(model))
        self.ocr_on = ocr
        self.reader = None
        self.gameplay_bar = float(self.head["gameplay_bar"]) if self.head is not None and "gameplay_bar" in self.head else 0.0
        self.feats = str(self.head["feats"]) if self.head is not None and "feats" in self.head else "pooled"
        if "text" in self.feats and not ocr:
            raise Unavailable(f"head {head} needs OCR (feats {self.feats}) and OCR is off")
        self.source = "head" if self.head is not None else "zero-shot"
        self.classify_image(None, [] if "text" in self.feats else None)  # warm

    def _zero_shot(self, tok):
        sys.path.insert(0, os.path.join(HERE, "pathknow", "classifier"))
        from prompts import PROMPTS
        torch = self.torch
        W = []
        with torch.no_grad():
            for s in STATES:
                f = torch.nn.functional.normalize(self.model.encode_text(tok(PROMPTS[s]).to(self.dev)).float(), dim=-1)
                W.append(torch.nn.functional.normalize(f.mean(0), dim=0))
        self.zs = torch.stack(W)

    def _tensor(self, path):
        """Decode on the CPU, resize and normalise on the GPU (PIL's bicubic resize cost ~40 ms here)."""
        from PIL import Image
        torch = self.torch
        if path is None:
            a = self.np.zeros((480, 640, 3), dtype=self.np.uint8)
        else:
            a = self.np.asarray(Image.open(path).convert("RGB"))
        x = torch.from_numpy(a).to(self.dev).permute(2, 0, 1).unsqueeze(0).float().div_(255)
        x = torch.nn.functional.interpolate(x, size=tuple(self.size), mode="bilinear", antialias=True,
                                            align_corners=False)
        x = (x - self.mean) / self.std
        return x.half() if self.dev == "cuda" else x

    def embed(self, path):
        torch = self.torch
        with torch.no_grad():
            f = self.model.encode_image(self._tensor(path))
            return torch.nn.functional.normalize(f.float(), dim=-1)[0]

    def embed_batch(self, paths, bs=16, grid=False):
        """The same preprocessing as embed(), batched (training uses this so its features match serving).
        grid=True also returns the patch tokens mean-pooled to a 4x4 grid, [n, 16, D]: where on the screen
        things are (a letterbox, a centred menu column, a corner HUD), which the attention-pooled vector
        mostly averages away."""
        torch = self.torch
        out, gout = [], []
        with torch.no_grad():
            for i in range(0, len(paths), bs):
                x = torch.cat([self._tensor(p) for p in paths[i:i + bs]])
                pooled, g = self._forward(x)
                out.append(pooled.cpu().numpy())
                if grid:
                    gout.append(g.cpu().numpy())
        if grid:
            return self.np.concatenate(out), self.np.concatenate(gout)
        return self.np.concatenate(out)

    def _forward(self, x):
        torch = self.torch
        trunk = getattr(self.model.visual, "trunk", None)
        if trunk is None or not hasattr(trunk, "forward_features"):
            f = self.model.encode_image(x)
            return torch.nn.functional.normalize(f.float(), dim=-1), None
        tok = trunk.forward_features(x)
        pooled = self.model.visual.head(trunk.forward_head(tok))
        n = int(round((tok.shape[1]) ** 0.5))
        g = tok[:, -n * n:].float().reshape(tok.shape[0], n, n, -1).permute(0, 3, 1, 2)
        g = torch.nn.functional.adaptive_avg_pool2d(g, 4).flatten(2).permute(0, 2, 1)
        return torch.nn.functional.normalize(pooled.float(), dim=-1), g

    def classify_image(self, path, menu=None):
        """State probabilities from the head (its feature spec) or, with no head, the zero-shot prompts."""
        torch, np = self.torch, self.np
        with torch.no_grad():
            pooled, grid = self._forward(self._tensor(path))
        if self.head is not None:
            h = self.head
            x = head_input(self.feats, pooled[0].cpu().numpy(), None if grid is None else grid[0].cpu().numpy(), menu)
            x = (x - h["mu"]) / h["sd"]
            logits = x @ h["W"].T + h["b"]
            states = [str(s) for s in h["states"]]
        else:
            logits = (pooled[0] @ self.zs.T).cpu().numpy() * 100.0
            states = STATES
        p = np.exp(logits - logits.max())
        p /= p.sum()
        return {s: float(v) for s, v in zip(states, p)}

    def read_menu(self, path):
        if self.reader is None:
            import easyocr
            self.reader = easyocr.Reader(["en"], gpu=self.dev == "cuda",
                                         model_storage_directory=os.path.join(MODELS, "easyocr"), verbose=False)
        from PIL import Image
        im = Image.open(path).convert("RGB")
        a = self.np.asarray(im)
        # batched recognition and a 640 canvas: 2-3x faster on dense text (legal screens: 3.1 s -> 0.7 s)
        res = self.reader.readtext(a, paragraph=False, batch_size=32, canvas_size=640)
        items = []
        for box, text, conf in res:
            if conf < 0.3 or len(text.strip()) < 2:
                continue
            xs, ys = [p[0] for p in box], [p[1] for p in box]
            b = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
            if b[2] <= FPS_CORNER[2] * im.size[0] / 640 and b[3] <= FPS_CORNER[3] * im.size[1] / 480:
                continue  # the FPS overlay
            items.append({"text": text.strip(), "box": b, "conf": round(float(conf), 2),
                          "intent": intent_of(text)})
        _mark_highlight(self.np, a, items)
        return items

    def _menu(self, frame):
        try:
            return self.read_menu(frame)
        except Exception as e:
            return [{"text": f"<ocr failed: {e}>", "box": None, "highlighted": None, "intent": None}]

    def classify(self, frame, prev=None, context=None, ocr=None):
        t0 = time.time()
        context = context or {}
        fc = free_checks(frame, prev)
        menu = None
        if "text" in self.feats and not fc["black"]:
            menu = self._menu(frame)
        probs = self.classify_image(frame, menu)
        ranked = sorted(probs.items(), key=lambda kv: -kv[1])
        state, conf = pick_state(probs, self.gameplay_bar)
        source = self.source
        if fc["black"]:
            state, conf, source = "black", max(conf, 0.99), "free:black"
        t_img = time.time()
        if menu is None:
            menu = []
            if (self.ocr_on if ocr is None else ocr) and state in OCR_STATES:
                menu = self._menu(frame)
        ts = text_state(state, menu)
        if ts and ts != state:
            state, source = ts, source + "+text"
            conf = max(conf, 0.8)
        state = temporal(state, fc, context)
        action, esc = decide(state, menu, context)
        if esc is None and conf < CONFIDENCE_BAR:
            esc = "low_confidence"
        return {"state": state, "confidence": round(conf, 3),
                "top3": [[s, round(p, 3)] for s, p in ranked[:3]],
                "moving": fc["moving"], "diff": fc["diff"], "black": fc["black"], "menu": menu,
                "action": action, "escalate": esc, "source": source,
                "ms": round((time.time() - t0) * 1000, 1), "ms_image": round((t_img - t0) * 1000, 1)}


# OCR text -> state, for the screens that ARE their text (an overlay on play looks like play to the image
# model: Sonic PAUSE, KOF WINNER, Burnout GAME OVER). Lowercased, OCR-noise-tolerant substrings; checked in
# this order; `few` = only when the screen has at most that many text items (a title card, not a menu
# that mentions the word).
TEXT_RULES = [
    ("name_entry", ["name entry", "enter a name", "enter your name", "caps lock", "backspace", "erase char",
                    "profile name", "campaign name"], None),
    ("pause", ["paused", "pause", "resume"], None),
    ("game_over", ["game over", "time is up", "mission failed", "you lose", "you died"], None),
    ("results", ["winner", "winni", "you win", "results", "final standings", "race over", "k.o."], None),
    ("loading", ["loading", "oading", "lodolng"], 6),
    ("save_load_prompt", ["continue without saving", "do you want to save", "no saved", "storage",
                          "overwrite", "no profiles", "save/load", "already exists"], None),
    ("title_screen", ["press start", "prass start", "press any button", "start button"], 4),
]
# HUD words that are text on gameplay, not a menu
_LEGEND = {"select", "back", "accept", "cancel", "options", "continue", "quit", "restart", "exit", "next"}


def text_state(state, menu):
    """A state forced by the screen's text, or None. Only overrides states the image model confuses with
    play (and play itself); a menu stays the menu the image said."""
    items = [m for m in menu if m.get("text") and not m["text"].startswith("<ocr failed")]
    if not items:
        return None
    # both joins: a phrase OCR split over boxes ('TIME | IS | UP') must still match
    blob = " | ".join(" ".join(m["text"].lower().split()) for m in items)
    blob += " || " + " ".join(" ".join(m["text"].lower().split()) for m in items)
    for st, words, few in TEXT_RULES:
        if few is not None and len(items) > few:
            continue
        if any(w in blob for w in words):
            if st == "title_screen" and state not in ("gameplay", "intro_video", "cutscene", "publisher_logo",
                                                      "title_screen", "controller_prompt", "main_menu"):
                continue
            return st
    if state == "gameplay":
        legend = sum(any(w == t or t.startswith(w + " ") for w in _LEGEND)
                     for t in (" ".join(m["text"].lower().split()) for m in items))
        if legend >= 2 or sum(1 for m in items if m.get("intent")) >= 3:
            return "submenu"
    return None


TEXT_FEATS = (["n_items", "n_chars", "area", "height", "x_spread", "bottom", "top", "single_chars", "digits",
               "legend", "select", "avoid", "press", "yes_no"] + [f"rule_{s}" for s, _, _ in TEXT_RULES])


def text_features(menu, size=(640, 480)):
    """A fixed-length vector from the OCR items, for the head: how much text, where, and which keyword groups.
    Feeds the same evidence as text_state() to the trained head instead of only hand rules."""
    import math
    import re
    W, H = size
    items = [m for m in menu if m.get("text") and m.get("box") and not m["text"].startswith("<ocr failed")]
    v = dict.fromkeys(TEXT_FEATS, 0.0)
    if items:
        txt = [" ".join(m["text"].lower().split()) for m in items]
        boxes = [m["box"] for m in items]
        v["n_items"] = math.log1p(len(items))
        v["n_chars"] = math.log1p(sum(len(t) for t in txt))
        v["area"] = min(1.0, sum((b[2] - b[0]) * (b[3] - b[1]) for b in boxes) / (W * H))
        v["height"] = sum(b[3] - b[1] for b in boxes) / len(boxes) / H
        xc = [(b[0] + b[2]) / 2 / W for b in boxes]
        v["x_spread"] = (sum((x - sum(xc) / len(xc)) ** 2 for x in xc) / len(xc)) ** 0.5
        v["bottom"] = sum(b[1] > 0.85 * H for b in boxes) / len(boxes)
        v["top"] = sum(b[3] < 0.15 * H for b in boxes) / len(boxes)
        v["single_chars"] = sum(len(re.findall(r"(?<!\S)\S(?!\S)", t)) for t in txt) / (1 + sum(len(t.split()) for t in txt))
        v["digits"] = sum(c.isdigit() for t in txt for c in t) / max(1, sum(len(t) for t in txt))
        v["legend"] = min(3, sum(any(w == t or t.startswith(w + " ") for w in _LEGEND) for t in txt)) / 3
        v["select"] = min(3, sum(m.get("intent") == "select" for m in items)) / 3
        v["avoid"] = min(3, sum(m.get("intent") == "avoid" for m in items)) / 3
        blob = " | ".join(txt) + " || " + " ".join(txt)
        v["press"] = float("press" in blob or "prass" in blob)
        v["yes_no"] = float(bool(re.search(r"(?<![a-z])yes(?![a-z])", blob)) and bool(re.search(r"(?<![a-z])no(?![a-z])", blob)))
        for s, words, few in TEXT_RULES:
            v[f"rule_{s}"] = float(any(w in blob for w in words))
    return [v[k] for k in TEXT_FEATS]


def head_input(feats, pooled, grid=None, menu=None, size=(640, 480)):
    """The head's input row for a feature spec like 'pooled+grid2+text' (the order is fixed)."""
    import numpy as np
    parts = []
    spec = feats.split("+")
    if "pooled" in spec:
        parts.append(np.asarray(pooled, dtype=np.float32).ravel())
    if "grid2" in spec or "grid4" in spec:
        g = np.asarray(grid, dtype=np.float32)            # [16, D], row-major 4x4
        if "grid2" in spec:
            g = g.reshape(2, 2, 2, 2, -1).mean((1, 3)).reshape(4, -1)
        parts.append(g.ravel())
    if "text" in spec:
        parts.append(np.asarray(text_features(menu or [], size), dtype=np.float32))
    return np.concatenate(parts)


def pick_state(probs, gameplay_bar=0.0):
    """(state, confidence) from the head's probabilities. A top-ranked gameplay below the head's gameplay bar
    gives way to the runner-up: a false gameplay is the costly error (the old pipeline's false passes)."""
    ranked = sorted(probs.items(), key=lambda kv: -kv[1])
    if ranked[0][0] == "gameplay" and ranked[0][1] < gameplay_bar and len(ranked) > 1:
        return ranked[1][0], float(ranked[1][1])
    return ranked[0][0], float(ranked[0][1])


def temporal(state, fc, context):
    """intro_video vs publisher_logo vs cutscene vs attract demo: needs time, not just pixels."""
    menu_seen = context.get("menu_seen")
    if menu_seen is False and state in ("cutscene", "gameplay"):
        return "intro_video"
    if menu_seen is True and state == "intro_video":
        return "cutscene"
    if state == "publisher_logo" and fc.get("moving"):
        return "intro_video"
    return state


def _mark_highlight(np, a, items):
    """Which item is highlighted: the one whose text box colour stands out from the others (a selection bar or
    a recoloured label). Only claimed when one item is a clear outlier; otherwise all False."""
    for it in items:
        it["highlighted"] = False
    rows = [it for it in items if it["box"]]
    if len(rows) < 2:
        return
    feats = []
    for it in rows:
        x0, y0, x1, y1 = it["box"]
        reg = a[max(0, y0):max(y0 + 1, y1), max(0, x0):max(x0 + 1, x1)].reshape(-1, 3).astype(np.float64)
        lum = reg.mean(1)
        bright = reg[lum >= np.percentile(lum, 75)].mean(0)   # the text strokes (or a light bar)
        dark = reg[lum <= np.percentile(lum, 25)].mean(0)     # the background behind them
        feats.append(np.concatenate([bright, dark]))
    f = np.array(feats)
    med = np.median(f, 0)
    d = np.sqrt(((f - med) ** 2).sum(1))
    order = np.argsort(-d)
    if d[order[0]] > 60 and (len(d) < 3 or d[order[0]] > 2.0 * max(d[order[1]], 15)):
        rows[order[0]]["highlighted"] = True


# ---------------------------------------------------------------- client for any python

class Client:
    """Talks to one `pathclass.py serve` child. Raises Unavailable when it cannot start or dies."""

    def __init__(self, timeout=120):
        import subprocess
        self.p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "serve"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        line = self.p.stdout.readline()
        if not line:
            err = self.p.stderr.read().strip().splitlines()
            raise Unavailable(err[-1] if err else "serve exited")
        hello = json.loads(line)
        if not hello.get("ready"):
            raise Unavailable(hello.get("error", "serve not ready"))
        self.info = hello

    def classify(self, frame, prev=None, context=None):
        if self.p.poll() is not None:
            raise Unavailable("serve process exited")
        self.p.stdin.write(json.dumps({"frame": frame, "prev": prev, "context": context or {}}) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        if not line:
            raise Unavailable("serve process exited")
        return json.loads(line)

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


# ---------------------------------------------------------------- CLI

def _unavailable(why):
    print(f"pathclass: unavailable: {why}", file=sys.stderr)
    sys.exit(UNAVAILABLE_EXIT)


def _in_venv():
    return os.path.realpath(sys.prefix) == os.path.realpath(VENV)


def _reexec():
    py = os.path.join(VENV, "bin", "python")
    if _in_venv():
        return
    if os.environ.get("PATHCLASS_NO_REEXEC"):
        return
    if not os.path.exists(py):
        _unavailable(f"no venv at {VENV} (see docs/lanes/pathclass/NOTES.md, Environment)")
    os.environ["PATHCLASS_NO_REEXEC"] = "1"
    os.execv(py, [py, os.path.abspath(__file__)] + sys.argv[1:])


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="local screen-state classifier for pathfind")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify")
    c.add_argument("frame")
    c.add_argument("--prev")
    c.add_argument("--context", default="{}")
    c.add_argument("--no-ocr", action="store_true")
    s = sub.add_parser("serve")
    s.add_argument("--no-ocr", action="store_true")
    sub.add_parser("check")
    a = ap.parse_args(argv)
    _reexec()
    try:
        clf = Classifier(ocr=not getattr(a, "no_ocr", False))
    except Unavailable as e:
        if a.cmd == "serve":
            print(json.dumps({"ready": False, "error": f"pathclass: unavailable: {e}"}), flush=True)
        _unavailable(str(e))
    if a.cmd == "check":
        print(f"pathclass: ok: {clf.source} on {clf.dev}, backbone {BACKBONE[0] if clf.head is None else clf.head['model']}")
        return 0
    if a.cmd == "classify":
        print(json.dumps(clf.classify(a.frame, a.prev, json.loads(a.context))))
        return 0
    print(json.dumps({"ready": True, "source": clf.source, "states": STATES}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            q = json.loads(line)
            r = clf.classify(q["frame"], q.get("prev"), q.get("context"), q.get("ocr"))
        except Exception as e:
            r = {"error": f"{e.__class__.__name__}: {e}", "state": "unknown", "escalate": "error"}
        print(json.dumps(r), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
