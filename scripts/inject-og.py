#!/usr/bin/env python3
"""Inject Open Graph + Twitter card meta tags into encrypted HTML files.

Reads per-file metadata from og-meta.json at repo root.
Idempotent: replaces an existing OG block (delimited by start/end markers)
or inserts after the <title> line.

Usage: scripts/inject-og.py [path-to-og-meta.json]
"""
import html
import json
import re
import sys
from pathlib import Path

START = "<!-- OG-INJECT:START -->"
END = "<!-- OG-INJECT:END -->"

REPO = Path(__file__).resolve().parent.parent

def build_block(meta: dict, defaults: dict) -> str:
    img = meta.get("og_image", defaults["_default_image"])
    w = meta.get("og_image_w", defaults["_default_image_w"])
    h = meta.get("og_image_h", defaults["_default_image_h"])
    site = meta.get("og_site_name", defaults["_default_site_name"])
    e = html.escape  # safe for attribute values
    return "\n".join([
        f"        {START}",
        f'        <meta property="og:type" content="website">',
        f'        <meta property="og:url" content="{e(meta["og_url"])}">',
        f'        <meta property="og:title" content="{e(meta["og_title"])}">',
        f'        <meta property="og:description" content="{e(meta["og_description"])}">',
        f'        <meta property="og:image" content="{e(img)}">',
        f'        <meta property="og:image:width" content="{w}">',
        f'        <meta property="og:image:height" content="{h}">',
        f'        <meta property="og:site_name" content="{e(site)}">',
        f'        <meta name="twitter:card" content="summary_large_image">',
        f'        <meta name="twitter:title" content="{e(meta["og_title"])}">',
        f'        <meta name="twitter:description" content="{e(meta["og_description"])}">',
        f'        <meta name="twitter:image" content="{e(img)}">',
        f"        {END}",
    ])


def update_file(path: Path, meta: dict, defaults: dict) -> str:
    src = path.read_text()
    block = build_block(meta, defaults)

    page_title = meta.get("page_title")
    if page_title:
        src = re.sub(r"<title>[^<]*</title>", f"<title>{html.escape(page_title)}</title>", src, count=1)

    if START in src and END in src:
        # Match the whole block including its leading indent so the replacement
        # doesn't double-indent on subsequent runs.
        pattern = r"[ \t]*" + re.escape(START) + r".*?" + re.escape(END)
        new = re.sub(pattern, block, src, count=1, flags=re.DOTALL)
        action = "replaced"
    else:
        new, n = re.subn(r"(<title>[^<]*</title>\s*\n)", r"\1" + block + "\n", src, count=1)
        if n == 0:
            return f"SKIP {path}: no <title> tag found"
        action = "inserted"

    path.write_text(new)
    return f"{action} OG tags in {path.relative_to(REPO)}"


def main():
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "og-meta.json"
    cfg = json.loads(cfg_path.read_text())
    defaults = {k: v for k, v in cfg.items() if k.startswith("_")}
    pages = {k: v for k, v in cfg.items() if not k.startswith("_")}

    for rel, meta in pages.items():
        p = REPO / rel
        if not p.exists():
            print(f"MISS {rel}: file not found")
            continue
        print(update_file(p, meta, defaults))


if __name__ == "__main__":
    main()
