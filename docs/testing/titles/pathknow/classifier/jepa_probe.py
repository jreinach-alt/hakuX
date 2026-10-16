#!/usr/bin/env python3
"""Cache JEPA-encoder features in embed.py's format, so train.py probes them on the same labels. Venv python.

    python jepa_probe.py --hf facebook/ijepa_vith14_1k --tag ijepa-h14 --list <paths.txt>
    python jepa_probe.py --hf facebook/vjepa2-vitl-fpc64-256 --tag vjepa2-l --list <paths.txt>
    python train.py --model ijepa-h14 --pretrained hf --pool <dir>

Features: the last hidden state mean-pooled over tokens (JEPA has no pooled, language-aligned vector), L2-
normalised. V-JEPA 2 is a video encoder: each frame goes in as a still 2-frame clip (its tubelet is 2 frames).
"""
import argparse
import os
import sys
import time

import numpy as np
import torch
from PIL import Image

MODELS = os.path.expanduser("~/hakux-work/models/pathclass")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--list", required=True)
    a = ap.parse_args()
    from transformers import AutoModel, AutoProcessor, AutoImageProcessor, AutoVideoProcessor
    paths = [l.strip() for l in open(a.list) if l.strip()]
    paths = [p for p in dict.fromkeys(paths) if os.path.exists(p)]
    video = "vjepa" in a.hf
    m = AutoModel.from_pretrained(a.hf, torch_dtype=torch.float16).cuda().eval()
    proc = AutoVideoProcessor.from_pretrained(a.hf) if video else AutoImageProcessor.from_pretrained(a.hf)
    out = []
    t0 = time.time()
    with torch.no_grad():
        for i in range(0, len(paths), 8):
            ims = [Image.open(p).convert("RGB") for p in paths[i:i + 8]]
            if video:
                clips = [np.stack([np.asarray(im)] * 2) for im in ims]
                x = proc(clips, return_tensors="pt")
                x = {k: v.cuda().half() if v.dtype.is_floating_point else v.cuda() for k, v in x.items()}
                h = m(**x, skip_predictor=True).last_hidden_state
            else:
                x = proc(images=ims, return_tensors="pt")
                h = m(pixel_values=x["pixel_values"].cuda().half()).last_hidden_state
            out.append(torch.nn.functional.normalize(h.float().mean(1), dim=-1).cpu().numpy())
    e = np.concatenate(out).astype(np.float16)
    print(f"{a.tag}: {len(paths)} frames in {time.time() - t0:.0f}s, dim {e.shape[1]}", file=sys.stderr)
    # warm single-frame latency
    with torch.no_grad():
        im = Image.open(paths[0]).convert("RGB")
        for k in range(12):
            if k == 2:
                torch.cuda.synchronize()
                t1 = time.time()
            if video:
                x = proc([np.stack([np.asarray(im)] * 2)], return_tensors="pt")
                x = {kk: v.cuda().half() if v.dtype.is_floating_point else v.cuda() for kk, v in x.items()}
                m(**x, skip_predictor=True)
            else:
                m(pixel_values=proc(images=[im], return_tensors="pt")["pixel_values"].cuda().half())
        torch.cuda.synchronize()
    print(f"{a.tag}: warm {(time.time() - t1) / 10 * 1000:.0f} ms/frame", file=sys.stderr)
    cache = os.path.join(MODELS, "emb", f"{a.tag}-hf.npz")
    np.savez(cache, paths=np.array(paths, dtype=object), emb=e, grid=np.zeros((len(paths), 16, 1), np.float16))
    print(f"wrote {cache}", file=sys.stderr)


if __name__ == "__main__":
    main()
