#!/usr/bin/env python3
"""
paulmress.com content-diff checker (CMS-replacement recommendation #3).

check-content-sync.py (recommendation #1) tells you a Drive doc was edited
since the site last synced to it — but not what actually changed. This
script goes one level deeper: it diffs the Drive doc's *text* against the
live page's *text* directly, so you can see whether the page's actual copy
has drifted from its brief, not just whether the doc's timestamp moved.

It does NOT call the Google Drive API itself, for the same reason
check-content-sync.py doesn't: a Claude session reads Drive through the
mcp__Google_Drive__* connector, not a service account this script could
authenticate as. Workflow:

  1. A Claude session calls mcp__Google_Drive__read_file_content for each
     drive_doc_id in content-manifest.json's "pages" list, and writes the
     returned fileContent to a snapshot JSON:

       { "18Vk87dXJEIOyk7HDsxZ2ij90KDkQco2SkaDHn-BdWVo": "PAULMRESS.COM ..." }

     (doc_id -> full plain-text content. A partial snapshot, covering only
     the pages you care about right now, is fine.)

  2. Run: python3 scripts/check-content-diff.py path/to/snapshot.json

  3. For each page in the snapshot, this prints a similarity score plus
     the specific lines that appear in one side but not the other —
     "IN BRIEF, NOT ON PAGE" (drive content the live page doesn't reflect)
     and "ON PAGE, NOT IN BRIEF" (live copy that isn't in the brief —
     either written directly into the HTML, or the brief just hasn't
     caught up).

This is inherently fuzzy — a Drive brief and rendered HTML are different
shapes even when perfectly in sync (headings, labels, structural notes in
the brief; markup in the page). The comparison only looks at each live
page's <main>...</main> content (site chrome — nav/footer/provenance — is
already covered by audit-site.py's footer check, and would just be noise
here), normalizes whitespace/case, and flags line-level differences over a
length threshold so short structural fragments don't drown out real
content drift. Treat the output as "worth a look," not a precise diff —
a human (or a session) still has to judge whether a flagged line is a
real gap or just a phrasing difference.

Usage:
  python3 scripts/check-content-diff.py <snapshot.json> [--threshold N]

--threshold sets the minimum line length (in characters) to report,
default 20 — shorter lines are almost always structural noise (labels,
kickers, single words) rather than real content.
"""
import difflib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "scripts" / "content-manifest.json"

MAIN_RE = re.compile(r'<main\b[^>]*>(.*)</main>', re.S | re.I)
TAG_RE = re.compile(r'<[^>]+>')
WS_RE = re.compile(r'[ \t]+')
BLOCK_TAGS_RE = re.compile(
    r'</?(p|div|section|article|h[1-6]|li|ul|ol|br|details|summary|blockquote|figure|figcaption)\b[^>]*>',
    re.I,
)


def extract_main_text(html_path: Path) -> list[str]:
    raw = html_path.read_text(encoding="utf-8")
    m = MAIN_RE.search(raw)
    body = m.group(1) if m else raw
    # Turn block-level boundaries into newlines before stripping tags, so
    # what was visually separate content doesn't get glued into one line.
    body = BLOCK_TAGS_RE.sub("\n", body)
    body = TAG_RE.sub("", body)
    body = html.unescape(body)
    lines = []
    for line in body.split("\n"):
        line = WS_RE.sub(" ", line).strip()
        if line:
            lines.append(line)
    return lines


def normalize_doc_text(text: str) -> list[str]:
    lines = []
    for line in text.split("\n"):
        line = WS_RE.sub(" ", line).strip()
        # Drop pure markdown structural markers ("# 01 · Problem" etc.) —
        # kept as noise otherwise since they rarely appear verbatim in HTML.
        if not line or line.startswith("#") or line == "  ":
            continue
        lines.append(line)
    return lines


def norm(line: str) -> str:
    return re.sub(r'\s+', ' ', line).strip().lower()


def diff_page(doc_lines: list[str], page_lines: list[str], threshold: int):
    doc_norm = {norm(l) for l in doc_lines}
    page_norm = {norm(l) for l in page_lines}

    matcher = difflib.SequenceMatcher(a=[norm(l) for l in doc_lines], b=[norm(l) for l in page_lines])
    ratio = matcher.ratio()

    in_brief_not_page = [l for l in doc_lines if len(l) >= threshold and norm(l) not in page_norm]
    on_page_not_brief = [l for l in page_lines if len(l) >= threshold and norm(l) not in doc_norm]

    return ratio, in_brief_not_page, on_page_not_brief


def main():
    args = sys.argv[1:]
    threshold = 20
    if "--threshold" in args:
        i = args.index("--threshold")
        threshold = int(args[i + 1])
        del args[i:i + 2]

    if len(args) != 1:
        print(__doc__)
        sys.exit(2)

    snapshot_path = Path(args[0])
    if not snapshot_path.exists():
        print(f"Snapshot file not found: {snapshot_path}")
        sys.exit(2)

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    checked = 0
    flagged = 0

    for page in manifest.get("pages", []):
        doc_id = page["drive_doc_id"]
        if doc_id not in snapshot:
            continue
        checked += 1

        page_path = ROOT / page["file"]
        if not page_path.exists():
            print(f"SKIP {page['path']} — file not found at {page['file']}")
            continue

        doc_lines = normalize_doc_text(snapshot[doc_id])
        page_lines = extract_main_text(page_path)
        ratio, in_brief_not_page, on_page_not_brief = diff_page(doc_lines, page_lines, threshold)

        print(f"\n=== {page['path']}  ({page['drive_doc_title']}) ===")
        print(f"similarity: {ratio:.0%}")

        if in_brief_not_page:
            flagged += 1
            print(f"  IN BRIEF, NOT ON PAGE ({len(in_brief_not_page)} line(s)):")
            for l in in_brief_not_page:
                print(f"    - {l}")
        if on_page_not_brief:
            print(f"  ON PAGE, NOT IN BRIEF ({len(on_page_not_brief)} line(s)):")
            for l in on_page_not_brief:
                print(f"    + {l}")
        if not in_brief_not_page and not on_page_not_brief:
            print("  No lines flagged.")

    if checked == 0:
        print("No manifest pages matched the snapshot — nothing to check.")
        sys.exit(2)

    print(f"\nChecked {checked} page(s); {flagged} had brief content not reflected on the page.")


if __name__ == "__main__":
    main()
