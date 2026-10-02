# lane.pathclass NOTES

A local screen-state classifier for pathfind's tiers 1-2: `docs/testing/titles/pathclass.py` (runtime),
`docs/testing/titles/pathclass_selftest.py`, and the training tools in `docs/testing/titles/pathknow/classifier/`.

## Scoreboard (pathknow eval: 120 frames, 64 titles; right = primary or an accepted label)

| version | all | seen titles | held-out titles | gameplay on non-gameplay | ms (warm) |
|---|---|---|---|---|---|
| zero-shot SigLIP2 B/16-384, prompts | 71/120 59% | | | 0/103 (never says gameplay; 14 FN) | 26 |
| + linear head (583 Haiku labels) | 87/120 72.5% | 51/62 | 36/58 | 8/103 7.8% | 26 |
| + OCR text rules | 95/120 79.2% | 56/62 | 39/58 | 6/103 5.8% | 26 + OCR 221 median |

Bar: >= 90% and <= 2% gameplay confusion. Not met yet.

## Environment

- venv `~/hakux-work/venvs/pathclass`: torch 2.14.1+cu126 (CUDA OK on the RTX 2070), open_clip_torch,
  transformers (SigLIP2 tokenizer), easyocr, scikit-learn. Weights/caches: `~/hakux-work/models/pathclass/`
  (`hf/`, `easyocr/`, `emb/` embedding caches). Recreate: `python3 -m venv <dir>`; `pip install torch
  torchvision --index-url https://download.pytorch.org/whl/cu126`; `pip install open_clip_torch easyocr
  transformers sentencepiece protobuf scikit-learn`.
- The host CPU sits at load 20-26 on 8 cores (other lanes). PIL's resize to 384 cost 43 ms/frame there, so
  the classifier resizes and normalises on the GPU (warm 105 ms -> 26 ms/frame). Training embeds through the
  same `Classifier.embed_batch`, so the head sees serve-time numbers.

## Data

- Pool (`pool.py`): 2786 distinct frames (16x12 grey thumbnail dedup per title, <= 80 per title) from 76 titles
  in `dispatch/results/*/{route-frames,frames}` and lanes' scratch frames. pathknow's eval runs (71) are
  excluded entirely; half the eval titles (fixed sha1 split, 31 in the pool) are held out of training.
- Labels: Haiku through `claude -p`, ten frames per call (`label.py`): **588 frames, 60 calls**, ~25 s/call.
  Class counts are skewed to gameplay (155) and cutscene (87); pause 7, results 7, game_over 1.
- Route step names (`menu-start`, `play`, `gameplay`) were NOT used as labels: they name the input sent, not
  the screen (a `menu-start` frame is as often a pause menu or a cutscene as a menu).

## What was tried

- Backbones (linear probe, same labels): SigLIP2 B/16-384 72.5-74.2%, L/16-384 74.2%. A bigger backbone does
  not move it; the labels and the overlay-text states do. Kept B/16 (26 ms).
- Zero-shot never says gameplay on menus but misses play itself (14 of 16 gameplay frames).
- OCR (easyocr, GPU): reads PAUSE/Resume/Loading/Press START/Name Entry well; fixed pause 2/8 -> 8/8.

## Temporal separation

intro_video vs cutscene vs attract demo cannot be told from one frame (Haiku misses them too: 4/8 intro_video).
pathclass takes `context.menu_seen` from pathfind: before the first menu, cutscene/gameplay pixels are
intro_video; after it, intro_video is cutscene. A logo-classed frame that is moving is intro_video.
