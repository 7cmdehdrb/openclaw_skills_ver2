#!/usr/bin/env python3
import argparse
import json
import os
import requests

NV = "2025-09-03"


def plain(rt):
    return "".join(x.get("plain_text", "") for x in (rt or []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-id", required=True)
    args = ap.parse_args()

    key = os.getenv("NOTION_API_KEY")
    if not key:
        raise SystemExit("NOTION_API_KEY is required")

    h = {"Authorization": f"Bearer {key}", "Notion-Version": NV}
    r = requests.get(f"https://api.notion.com/v1/blocks/{args.page_id}/children?page_size=100", headers=h, timeout=30)
    r.raise_for_status()

    bad = []
    has_image = False
    has_file = False
    bad_directives = []
    bad_fingerprint = []

    blocks = r.json().get("results", [])
    img_heading_idx = None
    pdf_heading_idx = None
    image_indices = []
    file_indices = []

    for i, b in enumerate(blocks):
        t = b.get("type")
        text = ""
        if t in b and isinstance(b[t], dict):
            text = plain(b[t].get("rich_text", []))

        if "(아래에" in text and "첨부" in text:
            bad_directives.append({"block": b.get("id"), "text": text[:200]})

        if "source_fingerprint:" in text and i < 10:
            bad_fingerprint.append({"block": b.get("id"), "reason": "fingerprint exposed too early", "text": text[:200]})

        if t == "image":
            has_image = True
            image_indices.append(i)
        if t == "file":
            has_file = True
            file_indices.append(i)
        if t in {"heading_1", "heading_2", "heading_3"}:
            txt = text
            if txt.strip() == "논문 이미지":
                img_heading_idx = i
            if txt.strip() == "원본 PDF":
                pdf_heading_idx = i
            if "\n" in txt:
                bad.append({"block": b.get("id"), "reason": "heading contains newline", "text": txt[:200]})
            if txt.strip().startswith(("#", "- ", "> ")):
                bad.append({"block": b.get("id"), "reason": "heading contains markdown marker", "text": txt[:200]})

    bad_placement = []
    if img_heading_idx is None:
        bad_placement.append("missing '논문 이미지' heading")
    if pdf_heading_idx is None:
        bad_placement.append("missing '원본 PDF' heading")

    if img_heading_idx is not None and pdf_heading_idx is not None:
        # images should be under '논문 이미지' section and before '원본 PDF'
        if not any(img_heading_idx < idx < pdf_heading_idx for idx in image_indices):
            bad_placement.append("images are not under '논문 이미지' section")
        # file should be after '원본 PDF' heading
        if not any(idx > pdf_heading_idx for idx in file_indices):
            bad_placement.append("file is not under '원본 PDF' section")

    ok = (len(bad) == 0) and has_image and has_file and (len(bad_directives) == 0) and (len(bad_placement) == 0) and (len(bad_fingerprint) == 0)
    print(json.dumps({
        "ok": ok,
        "badHeadings": bad,
        "hasImage": has_image,
        "hasFile": has_file,
        "badDirectives": bad_directives,
        "badPlacement": bad_placement,
        "badFingerprint": bad_fingerprint,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
