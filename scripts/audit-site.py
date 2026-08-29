#!/usr/bin/env python3
"""
paulmress.com self-check — run this before every deploy.

The site has no templating system (every page is standalone HTML), so nothing
stops a class from being used without being styled, or a component from
shipping without a design-system entry. This script catches drift instead of
relying on someone noticing by eye. It replaces the ad-hoc shell one-liners
used during the Aug 2026 footer/design-system audit with a single repeatable
tool.

Usage: python3 scripts/audit-site.py   (run from the repo root)
Exit code is non-zero if anything is flagged, so it's CI/hook-friendly later
if this repo ever grows one.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Real, indexable pages only — redirect stubs have no content of their own
# and are excluded on purpose.
PAGES = [
    "index.html",
    "about/index.html",
    "story/index.html",
    "thinking/index.html",
    "lab/index.html",
    "lab/1/index.html",
    "lab/2/index.html",
    "design-system/index.html",
    "ask-paul/index.html",
    "design-system/template-experiment/index.html",
]

CSS_FILES = [
    "styles.css",
    "design-system/design-system.css",
]

CLASS_RE = re.compile(r'class="([^"]*)"')
CSS_CLASS_RE = re.compile(r'\.[a-zA-Z][a-zA-Z0-9_-]*')
CSS_COMMENT_RE = re.compile(r'/\*.*?\*/', re.S)


def html_classes():
    used = set()
    per_file = {}
    for p in PAGES:
        path = ROOT / p
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        classes = set()
        for m in CLASS_RE.finditer(text):
            classes.update(m.group(1).split())
        used |= classes
        per_file[p] = classes
    return used, per_file


def css_classes():
    defined = set()
    for c in CSS_FILES:
        path = ROOT / c
        if not path.exists():
            continue
        text = CSS_COMMENT_RE.sub("", path.read_text(encoding="utf-8"))
        for m in CSS_CLASS_RE.finditer(text):
            defined.add(m.group(0)[1:])
    return defined


def footer_blocks():
    blocks = {}
    for p in PAGES:
        path = ROOT / p
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        m = re.search(r'<footer class="site-footer">.*?</footer>', text, re.S)
        if m:
            # Normalize the one expected per-page variation (aria-current)
            # before comparing, so real drift doesn't get lost in noise.
            normalized = re.sub(r'\s*aria-current="page"', '', m.group(0))
            blocks[p] = normalized
    return blocks


def main():
    problems = 0

    used, per_file = html_classes()
    defined = css_classes()

    unstyled = sorted(used - defined)
    # Known-fine structural/semantic wrappers with no CSS rule of their own —
    # confirmed during the Aug 2026 audit, not bugs. Re-check before adding
    # to this list; it should stay short.
    known_unstyled_ok = {"chat-section", "footer-links--primary", "hero-copy", "values"}
    real_unstyled = [c for c in unstyled if c not in known_unstyled_ok]
    if real_unstyled:
        problems += 1
        print("CLASSES USED IN HTML WITH NO CSS RULE (possible typo or missing style):")
        for c in real_unstyled:
            pages = sorted(p for p, cs in per_file.items() if c in cs)
            print(f"  .{c}  (in {', '.join(pages)})")
        print()

    dead = sorted(defined - used)
    if dead:
        print("CSS CLASSES DEFINED BUT NOT USED ON ANY CURRENT PAGE (candidates for removal):")
        for c in dead:
            print(f"  .{c}")
        print()

    blocks = footer_blocks()
    unique_blocks = set(blocks.values())
    if len(unique_blocks) > 1:
        problems += 1
        print("FOOTER DRIFT — <footer class=\"site-footer\"> is not identical across all pages:")
        # group pages by which variant they have
        variants = {}
        for p, b in blocks.items():
            variants.setdefault(b, []).append(p)
        for i, (_, pages) in enumerate(variants.items(), 1):
            print(f"  variant {i}: {', '.join(pages)}")
        print()
    else:
        print(f"Footer check OK — identical across all {len(blocks)} pages checked.")

    if problems:
        print(f"\n{problems} issue(s) need attention before deploying.")
        sys.exit(1)
    else:
        print("\nNo drift found.")


if __name__ == "__main__":
    main()
