#!/usr/bin/env python3
"""
Pre-deploy accessibility checker — internal tool, not user-facing.

Experiment: "can AI build a pre-deploy accessibility checker that actually
runs, using nothing but the Python standard library." Meant to be run
against real page HTML before it's pushed live, as one more gate alongside
the existing tag-balance check and `scripts/audit-site.py`.

Design choices worth knowing before this gets wired into the real repo:

- Pure stdlib (`html.parser`, `re`) — zero pip installs, matching this
  project's "no third-party tools" constraint and the fact that pip installs
  are blocked in this sandbox anyway.
- Uses Python's real HTML parser instead of hand-rolled regex tag-matching.
  An earlier regex-based version of the aria-hidden/focusable scanner (in
  the live browser prototype) had a real bug: a CSS comment that happened
  to contain the phrase "prefers-reduced-motion" was misread as an actual
  guard. A proper parser with a stacked walk avoids that whole class of
  mistake, which is why this version is written this way instead of porting
  the regex approach.
- Two checks — contrast ratio against ACTUAL rendered colors, and
  touch-target size against ACTUAL rendered layout — are NOT included here.
  Neither is knowable from static HTML/CSS text alone; both need a real
  rendered page (computed styles, real box layout). Options for those:
  run them as a separate Playwright-based pass (local browser automation,
  no external service, already used throughout this project for
  screenshot verification), or keep them live-tool-only for now. Flagged
  rather than faked.

Usage:
    python3 accessibility_check.py path/to/page.html [more/pages.html ...]

Exit code is 1 if any FAIL-level issue is found in any file (so this can
gate a deploy), 0 otherwise. WARN-level issues never fail the run.
"""

import sys
import re
from html.parser import HTMLParser

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}
FOCUSABLE_TAGS = {"a", "button", "input", "select", "textarea"}
VAGUE_LINK_PHRASES = {"click here", "here", "read more", "more", "this link",
                       "link", "learn more"}


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    num = int(hex_color, 16)
    return (num >> 16) & 255, (num >> 8) & 255, num & 255


def _relative_luminance(rgb):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex1, hex2):
    """WCAG 2.x contrast ratio between two hex colors — same math as the
    live browser prototype and a11y_checks.py, so all three agree."""
    l1 = _relative_luminance(_hex_to_rgb(hex1))
    l2 = _relative_luminance(_hex_to_rgb(hex2))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class Issue:
    def __init__(self, level, check, message):
        self.level = level  # "fail" or "warn"
        self.check = check
        self.message = message

    def __repr__(self):
        return f"[{self.level.upper()}] {self.check}: {self.message}"


class A11yParser(HTMLParser):
    """Single-pass parser that collects everything the checks below need,
    including which elements sit inside an aria-hidden="true" subtree."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []  # list of (tag, attrs_dict, aria_hidden_depth_at_entry)
        self.aria_hidden_depth = 0
        self.inert_depth = 0

        self.images = []          # list of attrs dict
        self.headings = []        # list of (level, text)
        self._heading_stack_text = []
        self.form_fields = []     # list of dict(tag, attrs, in_label, aria_hidden)
        self.label_fors = set()   # ids referenced by <label for="...">
        self.links = []           # list of (attrs, text, aria_hidden)
        self._link_text_stack = []
        self.style_chunks = []
        self._in_style = False
        self.aria_hidden_focusable = []  # list of (tag, attrs)

        self._in_label_depth = 0

    def handle_starttag(self, tag, attrs_list):
        attrs = dict(attrs_list)
        is_void = tag in VOID_TAGS
        entering_aria_hidden = attrs.get("aria-hidden", "").strip().lower() == "true"
        if entering_aria_hidden:
            self.aria_hidden_depth += 1
        # `inert` (self or ancestor) removes an element from the a11y tree
        # and makes it unfocusable regardless of aria-hidden — the real
        # #nav-panel markup pairs aria-hidden="true" with inert for exactly
        # this reason, so a focusable element under an inert ancestor is
        # not a real aria-hidden-focusable bug.
        entering_inert = "inert" in attrs
        if entering_inert:
            self.inert_depth += 1

        if tag == "label":
            self._in_label_depth += 1
            if "for" in attrs:
                self.label_fors.add(attrs["for"])

        if tag == "img":
            self.images.append(attrs)

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append([int(tag[1]), ""])

        if tag in ("input", "select", "textarea"):
            ftype = attrs.get("type", "").lower()
            if not (tag == "input" and ftype in ("hidden", "submit", "button", "image")):
                self.form_fields.append({
                    "tag": tag, "attrs": attrs,
                    "in_label": self._in_label_depth > 0,
                })

        if tag == "a":
            self._link_text_stack.append("")
            self.links.append({"attrs": attrs, "text": "", "aria_hidden": self.aria_hidden_depth > 0})

        if tag == "style":
            self._in_style = True

        if tag in FOCUSABLE_TAGS and self.aria_hidden_depth > 0:
            tabindex = attrs.get("tabindex", "0")
            disabled = "disabled" in attrs
            is_real_link = tag != "a" or "href" in attrs
            excluded = (disabled or tabindex.strip() == "-1" or not is_real_link
                        or self.inert_depth > 0 or entering_inert)
            if not excluded:
                self.aria_hidden_focusable.append((tag, attrs))

        if not is_void:
            self.stack.append([tag, attrs, entering_aria_hidden, entering_inert])

    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False
        if tag == "label" and self._in_label_depth > 0:
            self._in_label_depth -= 1
        if tag == "a" and self._link_text_stack:
            text = self._link_text_stack.pop()
            if self.links:
                self.links[-1]["text"] = text.strip()
        # pop matching stack frame (handles mismatched/unclosed tags gracefully)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                # popping any unclosed descendants (best-effort) must also
                # unwind whatever depth counters *they* opened, or a stray
                # unclosed inert/aria-hidden tag would leak its depth count
                for frame in self.stack[i:]:
                    if frame[2]:
                        self.aria_hidden_depth = max(0, self.aria_hidden_depth - 1)
                    if frame[3]:
                        self.inert_depth = max(0, self.inert_depth - 1)
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self._in_style:
            self.style_chunks.append(data)
        if self.headings and self.stack and self.stack[-1][0] in (
                "h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings[-1][1] += data
        if self._link_text_stack:
            self._link_text_stack[-1] += data


def parse(html_text):
    p = A11yParser()
    p.feed(html_text)
    return p


# ---------------------------------------------------------------------------
# Checks — each takes a parsed A11yParser and returns a list of Issue
# ---------------------------------------------------------------------------

def check_alt_text(p):
    issues = []
    missing = [img for img in p.images if "alt" not in img]
    for img in missing:
        issues.append(Issue("fail", "alt-text",
            f'<img src="{img.get("src", "?")}"> has no alt attribute'))
    return issues


def check_heading_hierarchy(p):
    issues = []
    levels = [lvl for lvl, _ in p.headings]
    h1_count = levels.count(1)
    if h1_count == 0 and levels:
        issues.append(Issue("warn", "heading-hierarchy", "No <h1> found on page"))
    if h1_count > 1:
        issues.append(Issue("warn", "heading-hierarchy", f"{h1_count} <h1> elements found, expected 1"))
    for i in range(1, len(levels)):
        if levels[i] - levels[i - 1] > 1:
            issues.append(Issue("fail", "heading-hierarchy",
                f"Heading level skipped: h{levels[i-1]} → h{levels[i]}"))
    return issues


def check_form_labels(p):
    issues = []
    for field in p.form_fields:
        attrs = field["attrs"]
        has_id_match = attrs.get("id") in p.label_fors if attrs.get("id") else False
        has_aria = "aria-label" in attrs or "aria-labelledby" in attrs
        if not (field["in_label"] or has_id_match or has_aria):
            issues.append(Issue("fail", "form-labels",
                f'<{field["tag"]}> (name="{attrs.get("name", "?")}") has no associated label'))
    return issues


def check_link_text(p):
    issues = []
    for link in p.links:
        text = link["text"].strip().lower()
        if text in VAGUE_LINK_PHRASES and "aria-label" not in link["attrs"]:
            issues.append(Issue("warn", "link-text",
                f'Link text "{link["text"].strip()}" is not meaningful out of context'))
    return issues


def check_reduced_motion(p):
    issues = []
    style_text = "".join(p.style_chunks)
    # strip comments first — a comment mentioning the phrase should never
    # count as an actual guard (this bit the regex-only version earlier)
    style_text_no_comments = re.sub(r"/\*.*?\*/", "", style_text, flags=re.DOTALL)
    has_animation = re.search(r"@keyframes|animation(-name)?\s*:", style_text_no_comments, re.I)
    has_guard = re.search(r"prefers-reduced-motion", style_text_no_comments, re.I)
    if has_animation and not has_guard:
        issues.append(Issue("fail", "reduced-motion",
            "CSS animation found with no @media (prefers-reduced-motion) guard anywhere in <style>"))
    return issues


def check_aria_hidden_focusable(p):
    issues = []
    for tag, attrs in p.aria_hidden_focusable:
        issues.append(Issue("fail", "aria-hidden-focusable",
            f'<{tag}> inside aria-hidden="true" is still focusable (id="{attrs.get("id", "?")}")'))
    return issues


ALL_CHECKS = [
    check_alt_text,
    check_heading_hierarchy,
    check_form_labels,
    check_link_text,
    check_reduced_motion,
    check_aria_hidden_focusable,
]


def run(html_text):
    p = parse(html_text)
    issues = []
    for check in ALL_CHECKS:
        issues.extend(check(p))
    return issues


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    any_fail = False
    for path in argv:
        with open(path, encoding="utf-8") as f:
            html_text = f.read()
        issues = run(html_text)
        fails = [i for i in issues if i.level == "fail"]
        warns = [i for i in issues if i.level == "warn"]
        print(f"\n{path}: {len(fails)} failure(s), {len(warns)} warning(s)")
        for issue in issues:
            print(f"  {issue}")
        if fails:
            any_fail = True
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
