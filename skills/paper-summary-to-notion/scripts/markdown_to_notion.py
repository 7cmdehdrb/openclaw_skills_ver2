#!/usr/bin/env python3
import os
import re
import sys
import json
from pathlib import Path
import requests

"""
Minimal markdown -> Notion page writer.
Usage:
  python scripts/markdown_to_notion.py <title> <markdown_file>
Env:
  NOTION_API_KEY           required
  NOTION_PARENT_PAGE_ID    required (target parent page id)
"""

NOTION_VERSION = "2025-09-03"


def rich(text: str):
    out = []
    i = 0
    while i < len(text):
        m = re.search(r"\*\*(.+?)\*\*", text[i:])
        if not m:
            if text[i:]:
                out.append({"type": "text", "text": {"content": text[i:]}})
            break
        s = i + m.start()
        e = i + m.end()
        if s > i:
            out.append({"type": "text", "text": {"content": text[i:s]}})
        out.append({
            "type": "text",
            "text": {"content": m.group(1)},
            "annotations": {"bold": True},
        })
        i = e
    return out or [{"type": "text", "text": {"content": ""}}]


def _single_line(text: str) -> str:
    # Notion heading blocks must be single-line to avoid "# 전체 본문" 깨짐 현상.
    return " ".join((text or "").replace("\r", "\n").splitlines()).strip()


def mk_block(kind, text):
    if kind in {"heading_1", "heading_2", "heading_3"}:
        text = _single_line(text)
    return {"object": "block", "type": kind, kind: {"rich_text": rich(text)}}


def list_item_block(text: str):
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich(text)},
    }


def parse_markdown(md: str):
    lines = md.splitlines()
    root_blocks = []
    list_stack = []  # stack of list-item blocks by depth
    i = 0

    def flush_list_stack():
        list_stack.clear()

    def append_block(block):
        if list_stack:
            parent = list_stack[-1]
            parent.setdefault("bulleted_list_item", {}).setdefault("children", []).append(block)
        else:
            root_blocks.append(block)

    while i < len(lines):
        raw = lines[i]
        line = raw.replace("\t", "    ")
        s = line.strip()

        if not s:
            flush_list_stack()
            i += 1
            continue
        if s == "---":
            flush_list_stack()
            root_blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue
        if line.startswith("# "):
            flush_list_stack()
            htxt = line[2:].strip()
            root_blocks.append(mk_block("heading_1", htxt))
            # Formatting guard: keep a visible one-line gap after sections 1)~3)
            if re.match(r"^[1-3]\)\s+", htxt):
                root_blocks.append(mk_block("paragraph", ""))
            i += 1
            continue
        if line.startswith("## "):
            flush_list_stack()
            root_blocks.append(mk_block("heading_2", line[3:].strip()))
            i += 1
            continue
        if line.startswith("### "):
            flush_list_stack()
            root_blocks.append(mk_block("heading_3", line[4:].strip()))
            i += 1
            continue

        # nested bullets by indentation (2 or 4 spaces / tab)
        m = re.match(r"^(\s*)-\s+(.*)$", line)
        if m:
            indent = len(m.group(1))
            depth = indent // 2
            text = m.group(2).strip()
            item = list_item_block(text)

            if depth <= 0:
                root_blocks.append(item)
                list_stack[:] = [item]
            else:
                while len(list_stack) > depth:
                    list_stack.pop()
                if not list_stack:
                    root_blocks.append(item)
                    list_stack[:] = [item]
                else:
                    parent = list_stack[-1]
                    parent.setdefault("bulleted_list_item", {}).setdefault("children", []).append(item)
                    list_stack.append(item)
            i += 1
            continue

        # block quote
        if s.startswith(">"):
            flush_list_stack()
            quote_text = re.sub(r"^>\s?", "", s)
            root_blocks.append(mk_block("quote", quote_text))
            i += 1
            continue

        # markdown table
        if "|" in line and i + 1 < len(lines) and re.match(r"^\|\s*-+", lines[i + 1].strip()):
            flush_list_stack()
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            width = max(len(header), max((len(r) for r in rows), default=0))

            def row_block(cells):
                cells = (cells + [""] * width)[:width]
                return {
                    "object": "block",
                    "type": "table_row",
                    "table_row": {
                        "cells": [rich(c) for c in cells]
                    },
                }

            table = {
                "object": "block",
                "type": "table",
                "table": {
                    "table_width": width,
                    "has_column_header": True,
                    "has_row_header": False,
                    "children": [row_block(header)] + [row_block(r) for r in rows],
                },
            }
            root_blocks.append(table)
            continue

        flush_list_stack()
        root_blocks.append(mk_block("paragraph", s))
        i += 1
    return root_blocks


def main():
    if len(sys.argv) < 3:
        print("Usage: markdown_to_notion.py <title> <markdown_file>")
        sys.exit(1)

    title = sys.argv[1]
    md_file = Path(sys.argv[2])
    key = os.getenv("NOTION_API_KEY")
    parent = os.getenv("NOTION_PARENT_PAGE_ID")
    if not key or not parent:
        print("NOTION_API_KEY and NOTION_PARENT_PAGE_ID are required", file=sys.stderr)
        sys.exit(2)

    md = md_file.read_text(encoding="utf-8")
    blocks = parse_markdown(md)

    headers = {
        "Authorization": f"Bearer {key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    create_payload = {
        "parent": {"page_id": parent},
        "properties": {
            "title": {"title": [{"type": "text", "text": {"content": title}}]}
        },
    }
    r = requests.post("https://api.notion.com/v1/pages", headers=headers, json=create_payload, timeout=30)
    r.raise_for_status()
    page = r.json()
    pid = page["id"]

    for i in range(0, len(blocks), 50):
        rr = requests.patch(
            f"https://api.notion.com/v1/blocks/{pid}/children",
            headers=headers,
            json={"children": blocks[i : i + 50]},
            timeout=30,
        )
        rr.raise_for_status()

    print(json.dumps({"ok": True, "id": pid, "url": page.get("url")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
