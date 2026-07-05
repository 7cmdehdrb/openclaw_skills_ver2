#!/usr/bin/env python3
"""
Heuristic key-image selector for paper PDFs.
- Picks framework/architecture-like figure first (mandatory if found)
- Picks platform/hardware photo second (if found)

Usage:
  python3 scripts/select_key_images.py --pdf /path/paper.pdf --images-dir /path/extracted

Output JSON:
{
  "framework": "/abs/path/...jpg" | null,
  "platform": "/abs/path/...jpg" | null,
  "notes": [ ... ]
}
"""

import argparse
import json
import re
from pathlib import Path
from PIL import Image
import subprocess


FW_KEYWORDS = [
    "framework", "architecture", "pipeline", "system", "controller", "control diagram", "block diagram",
    "model predictive control", "mpc",
]

PLATFORM_KEYWORDS = [
    "robot", "platform", "test bed", "hardware", "king louie", "grub", "setup", "prototype",
]

PLOT_KEYWORDS = [
    "result", "tracking", "error", "response", "plot", "graph", "accuracy", "performance",
]


def extract_text_by_page(pdf_path: Path):
    cmd = ["pdftotext", str(pdf_path), "-"]
    txt = subprocess.check_output(cmd, text=True, errors="ignore")
    # pdftotext uses form-feed as page delimiter
    pages = txt.split("\f")
    return [p.lower() for p in pages]


def image_dims(path: Path):
    try:
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


def parse_page_num(name: str):
    m = re.search(r"page_(\d+)_img_\d+", name)
    return int(m.group(1)) if m else None


def score_for(page_text: str, mode: str):
    if mode == "framework":
        score = sum(2 for k in FW_KEYWORDS if k in page_text)
        score -= sum(1 for k in PLOT_KEYWORDS if k in page_text)
        return score
    if mode == "platform":
        score = sum(2 for k in PLATFORM_KEYWORDS if k in page_text)
        score -= sum(1 for k in PLOT_KEYWORDS if k in page_text)
        return score
    return 0


def choose(images, page_texts, mode):
    # rank pages first
    page_scores = {}
    for i, t in enumerate(page_texts, start=1):
        page_scores[i] = score_for(t, mode)

    candidates = []
    for p in images:
        pg = parse_page_num(p.name)
        if not pg:
            continue
        w, h = image_dims(p)
        area = w * h
        if area < 120000:
            continue
        aspect_bonus = 0
        # framework diagrams are often landscape-ish; platform photos less strict
        if mode == "framework" and w >= h:
            aspect_bonus = 0.5
        if mode == "platform" and h >= w:
            aspect_bonus = 0.2
        s = page_scores.get(pg, 0) + aspect_bonus + (area / 5_000_000)
        candidates.append((s, area, p))

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    if not candidates:
        return None

    # require positive semantic signal for framework; for platform allow weak selection
    if mode == "framework" and candidates[0][0] <= 0:
        return None
    return str(candidates[0][2].resolve())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--images-dir", required=True)
    args = ap.parse_args()

    pdf = Path(args.pdf)
    img_dir = Path(args.images_dir)
    images = sorted([p for p in img_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}])

    pages = extract_text_by_page(pdf)
    framework = choose(images, pages, "framework")
    platform = choose(images, pages, "platform")

    notes = []
    if not framework:
        notes.append("No framework/architecture candidate found by heuristic.")
    if not platform:
        notes.append("No platform/hardware candidate found by heuristic.")

    print(json.dumps({"framework": framework, "platform": platform, "notes": notes}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
