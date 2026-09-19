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
- The reduced-motion check reads CSS from both inline <style> tags AND
  local stylesheets referenced via <link rel="stylesheet" href="...">.
  Root-relative hrefs ("/styles.css") resolve against the repo root
  (two directories up from this script); relative hrefs resolve against
  the HTML file's own directory. "?v=..." cache-busting query strings are
  stripped before resolving. External stylesheets (http(s):, protocol-
  relative "//...", data:) are skipped — there's nothing local to read.
- The reduced-motion check is selector-level, not just "does a guard exist
  somewhere". It collects every selector that declares a non-"none"
  `animation`/`animation-name`, and every selector inside an
  `@media (prefers-reduced-motion: reduce) { ... }` block that sets that
  property to `none`, then reports by name any animated selector with no
  matching (or parent-scoped) guard. This is regex-based selector-text
  matching, not a real CSS selector engine: it recognizes an exact selector
  match, a match after stripping pseudo-classes/elements (e.g.
  `.foo:nth-child(2)` vs. a guard on `.foo`), or a guard on the leading
  compound of a descendant selector (e.g. a guard on `.foo` covers
  `.foo .bar`). It does not evaluate `@import`, CSS custom properties used
  as animation names, or specificity/cascade order across files.
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

import os
import sys
import re
from html.parser import HTMLParser

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
        self.stylesheet_hrefs = []  # hrefs from <link rel="stylesheet">'s

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

        if tag == "link":
            rel = attrs.get("rel", "").lower().split()
            href = attrs.get("href")
            if "stylesheet" in rel and href:
                self.stylesheet_hrefs.append(href)

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


_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_MEDIA_REDUCE_RE = re.compile(
    r"@media\s*\([^)]*prefers-reduced-motion\s*:\s*reduce[^)]*\)\s*\{", re.I)
_ANIM_PROP_RE = re.compile(r"animation(?:-name)?\s*:\s*([^;{}]+)", re.I)
_PSEUDO_RE = re.compile(r":{1,2}[a-zA-Z-]+(?:\([^)]*\))?")


def _resolve_stylesheet_path(href, html_path):
    href = href.split("#", 1)[0].split("?", 1)[0]
    if not href:
        return None
    if re.match(r"^([a-z][a-z0-9+.-]*:)?//", href, re.I) or href.lower().startswith("data:"):
        return None  # external — nothing local to read
    if href.startswith("/"):
        path = os.path.join(REPO_ROOT, href.lstrip("/"))
    else:
        base_dir = os.path.dirname(html_path) if html_path else REPO_ROOT
        path = os.path.join(base_dir, href)
    return os.path.normpath(path)


def _collect_css_text(p, html_path):
    chunks = list(p.style_chunks)
    missing = []
    for href in p.stylesheet_hrefs:
        path = _resolve_stylesheet_path(href, html_path)
        if path is None:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                chunks.append(f.read())
        except OSError:
            missing.append(href)
    return "".join(chunks), missing


def _normalize_selector(sel):
    return re.sub(r"\s+", " ", sel).strip()


def _strip_pseudo(sel):
    return re.sub(r"\s+", " ", _PSEUDO_RE.sub("", sel)).strip()


def _extract_rules(css_chunk):
    """Flat (selector, declarations) pairs. Because the regex requires no
    nested braces, it naturally skips over `@media (...) {` / `@supports
    (...) {` wrapper lines (they never find a matching `}` immediately
    after their own content) and lands on the innermost real rules —
    good enough for this codebase without a full CSS parser."""
    rules = []
    for m in _RULE_RE.finditer(css_chunk):
        selector_text = m.group(1).strip()
        if not selector_text or selector_text.startswith("@"):
            continue
        rules.append((selector_text, m.group(2)))
    return rules


def _find_reduce_guard_blocks(css_no_comments):
    blocks = []
    for m in _MEDIA_REDUCE_RE.finditer(css_no_comments):
        depth = 1
        i = m.end()
        while i < len(css_no_comments) and depth > 0:
            if css_no_comments[i] == "{":
                depth += 1
            elif css_no_comments[i] == "}":
                depth -= 1
            i += 1
        blocks.append(css_no_comments[m.end():i - 1])
    return blocks


def _last_animation_value(decl_text):
    values = _ANIM_PROP_RE.findall(decl_text)
    return values[-1].strip() if values else None


def _is_selector_covered(selector, guarded_norms, guarded_bases):
    norm = _normalize_selector(selector)
    base = _strip_pseudo(norm)
    if norm in guarded_norms or base in guarded_bases:
        return True
    parts = base.split(" ")
    # parent-scoped equivalent: a guard on the leading compound of a
    # descendant selector (e.g. guard on ".foo" covers ".foo .bar")
    return len(parts) > 1 and parts[0] in guarded_bases


def check_reduced_motion(p, html_path=None):
    issues = []
    css_text, missing = _collect_css_text(p, html_path)
    for href in missing:
        issues.append(Issue("warn", "reduced-motion",
            f'Linked stylesheet "{href}" could not be read for reduced-motion analysis'))

    # strip comments first — a comment mentioning the phrase should never
    # count as an actual guard (this bit the regex-only version earlier)
    css_no_comments = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    guard_blocks = _find_reduce_guard_blocks(css_no_comments)

    if not guard_blocks:
        has_animation = re.search(r"@keyframes|animation(-name)?\s*:", css_no_comments, re.I)
        if has_animation:
            issues.append(Issue("fail", "reduced-motion",
                "CSS animation found with no @media (prefers-reduced-motion: reduce) "
                "block anywhere in <style> or linked stylesheets"))
        return issues

    guarded_norms = set()
    guarded_bases = set()
    for block in guard_blocks:
        for selector_text, decl_text in _extract_rules(block):
            value = _last_animation_value(decl_text)
            if value is None or value.split()[0].lower() != "none":
                continue
            for sel in selector_text.split(","):
                sel = sel.strip()
                if not sel:
                    continue
                guarded_norms.add(_normalize_selector(sel))
                guarded_bases.add(_strip_pseudo(_normalize_selector(sel)))

    # drop guard-block text so its own "animation: none" rules can't be
    # mistaken for animated selectors that still need covering
    css_outside_guards = css_no_comments
    for block in guard_blocks:
        css_outside_guards = css_outside_guards.replace(block, "", 1)

    reported = set()
    for selector_text, decl_text in _extract_rules(css_outside_guards):
        value = _last_animation_value(decl_text)
        if value is None or value.split()[0].lower() == "none":
            continue
        for sel in selector_text.split(","):
            sel = sel.strip()
            if not sel or _is_selector_covered(sel, guarded_norms, guarded_bases):
                continue
            norm = _normalize_selector(sel)
            if norm in reported:
                continue
            reported.add(norm)
            issues.append(Issue("fail", "reduced-motion",
                f'"{sel}" declares an animation with no prefers-reduced-motion: '
                f'reduce block overriding it'))
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


def run(html_text, html_path=None):
    p = parse(html_text)
    issues = []
    for check in ALL_CHECKS:
        if check is check_reduced_motion:
            issues.extend(check(p, html_path))
        else:
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
        issues = run(html_text, html_path=path)
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
