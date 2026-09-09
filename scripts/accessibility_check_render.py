#!/usr/bin/env python3
"""
Render-based pre-deploy checks — the other half of the pre-deploy gate.

accessibility_check.py covers everything knowable from static HTML/CSS
text. Contrast ratio and touch-target size are NOT knowable that way —
both depend on the CSS cascade actually resolving (inheritance,
specificity, root-relative stylesheet links like <link href="/styles.css">)
and on real layout. So this script actually renders the page instead of
guessing at it:

1. Starts a plain local static file server (Python stdlib `http.server`,
   not a third-party service) rooted at the directory containing the site
   files, so root-relative links resolve exactly like they do in
   production. A raw file:// open would NOT resolve "/styles.css"
   correctly — this is the actual reason a local server is used instead of
   just opening the HTML file directly.
2. Uses Playwright (already used throughout this project for screenshot
   verification — local browser automation, no external API, no cost) to
   render each page and read real computed styles and real layout.
3. Runs the same contrast_ratio() math as accessibility_check.py and the
   live browser tool, so a page that passes here and a page that passes
   the live prototype agree by construction.

Known limitation, found by running this against the real site: this
script does NOT do real alpha compositing. If a text color or a
background color anywhere in the walked-up chain is translucent
(rgba(...) with alpha < 1) or fully transparent (color:transparent, e.g.
a gradient/background-clip:text headline), it cannot know the true
rendered color, and reports that element as a WARN ("could not resolve
...") instead of guessing a ratio. This was deliberate after an early
version silently stripped alpha and produced a false 1.00:1 "identical
colors" failure for light, 80%-opacity text over a dark section purely
because an unrelated ancestor's own 4%-opacity background tint got
treated as fully opaque along the way. Elements not currently visible
(display:none on themselves or an ancestor — e.g. the opt-in path-tracker
widget before it's opened) are skipped entirely for the same reason: an
invisible element has no rendered color or size to check.

Usage:
    python3 accessibility_check_render.py <site_root_dir> <path1> [path2 ...]

    e.g. python3 accessibility_check_render.py . test_render_page.html

Exit code 1 if any FAIL-level issue found, 0 otherwise — same contract as
accessibility_check.py, meant to run alongside it as one gate.
"""

import sys
import http.server
import threading
import socket
import contextlib

from accessibility_check import contrast_ratio, Issue


def _free_port():
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@contextlib.contextmanager
def local_static_server(root_dir):
    port = _free_port()
    handler = lambda *a, **kw: _QuietHandler(*a, directory=root_dir, **kw)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def _rgb_string_to_hex(rgb_str):
    """Converts 'rgb(32, 28, 23)' or 'rgba(32, 28, 23, 1)' to '#201c17'."""
    nums = rgb_str.strip("rgba() ").split(",")
    r, g, b = (int(float(n)) for n in nums[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def check_rendered_page(playwright_page, url):
    issues = []

    # ---- Contrast: walk real text-bearing elements, read computed styles ----
    text_pairs = playwright_page.evaluate("""
        () => {
            const results = [];
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
            let node = walker.currentNode;
            while (node) {
                const hasDirectText = Array.from(node.childNodes).some(
                    n => n.nodeType === 3 && n.textContent.trim().length > 0
                );
                // skip anything not actually presented to the user right
                // now (display:none on itself or an ancestor, e.g. the
                // opt-in path-tracker widget before it's opened) — a
                // hidden element has no rendered contrast to fail
                if (hasDirectText && node.offsetParent !== null) {
                    const style = getComputedStyle(node);
                    const alphaOf = (rgbaStr) => {
                        const m = rgbaStr.match(/[\\d.]+\\)$/);
                        return m ? parseFloat(m[0]) : 1;
                    };
                    // gradient/background-clip:text headlines set
                    // color:transparent and paint via background-image —
                    // getComputedStyle(node).color can't see that fill, so
                    // don't compute a bogus ratio against a color that was
                    // never actually rendered; flag as unverifiable instead.
                    // Same for any partial text-color alpha (e.g. a light
                    // color at 80% opacity over a dark section): naively
                    // stripping the alpha and treating it as opaque can
                    // make text collide with an unrelated ancestor's own
                    // (also alpha'd) background and read as near-identical
                    // when the real, composited render is not — this
                    // checker doesn't do real alpha compositing, so it
                    // flags rather than guesses.
                    const textAlpha = alphaOf(style.color);
                    if (textAlpha < 1) {
                        results.push({ id: node.id || node.tagName, unverifiable: true });
                        node = walker.nextNode();
                        continue;
                    }
                    let bg = style.backgroundColor;
                    let el = node;
                    // walk up until a fully-opaque background is found — a
                    // simple, not-fully-general resolution of the cascade.
                    // A background with any alpha < 1 (not just exactly 0)
                    // is translucent and lets whatever is behind it show
                    // through, so it isn't the real rendered color either —
                    // keep walking past those the same as fully-transparent
                    // ones instead of treating a near-transparent tint as
                    // if it were solid.
                    while (el && alphaOf(bg) < 1) {
                        el = el.parentElement;
                        if (!el) break;
                        bg = getComputedStyle(el).backgroundColor;
                    }
                    if (alphaOf(bg) < 1) {
                        // walked all the way to <html> and never found a
                        // fully opaque background — can't resolve a real
                        // rendered color, so don't guess
                        results.push({ id: node.id || node.tagName, unverifiable: true });
                        node = walker.nextNode();
                        continue;
                    }
                    results.push({
                        id: node.id || node.tagName,
                        color: style.color,
                        background: bg || 'rgb(255, 255, 255)',
                        fontSize: parseFloat(style.fontSize),
                        fontWeight: style.fontWeight,
                    });
                }
                node = walker.nextNode();
            }
            return results;
        }
    """)

    for item in text_pairs:
        if item.get("unverifiable"):
            issues.append(Issue("warn", "contrast-rendered",
                f'#{item["id"]}: could not resolve an opaque rendered color '
                f'(transparent/gradient text fill, or a translucent text or '
                f'background color this checker does not alpha-composite) '
                f'— verify contrast visually'))
            continue
        fg_hex = _rgb_string_to_hex(item["color"])
        bg_hex = _rgb_string_to_hex(item["background"])
        ratio = contrast_ratio(fg_hex, bg_hex)
        is_large = item["fontSize"] >= 24 or (item["fontSize"] >= 18.66 and int(item["fontWeight"]) >= 700)
        threshold = 3.0 if is_large else 4.5
        if ratio < threshold:
            issues.append(Issue("fail", "contrast-rendered",
                f'#{item["id"]}: {ratio:.2f}:1 ({fg_hex} on {bg_hex}), '
                f'needs {threshold}:1 for {"large" if is_large else "normal"} text'))

    # ---- Touch targets: real getBoundingClientRect() on real elements ----
    targets = playwright_page.evaluate("""
        () => Array.from(document.querySelectorAll('button, a[href], input, select, textarea'))
            .filter(el => el.offsetParent !== null)
            .map(el => {
                const r = el.getBoundingClientRect();
                return { id: el.id || el.tagName, w: Math.round(r.width), h: Math.round(r.height) };
            })
    """)
    for t in targets:
        min_dim = min(t["w"], t["h"])
        if min_dim < 24:
            issues.append(Issue("fail", "touch-target-rendered",
                f'#{t["id"]}: {t["w"]}×{t["h"]}px, fails WCAG 2.5.8 AA minimum (24×24px)'))
        elif min_dim < 44:
            issues.append(Issue("warn", "touch-target-rendered",
                f'#{t["id"]}: {t["w"]}×{t["h"]}px, passes AA but below the 44×44 AAA/comfort target'))

    return issues


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    site_root, paths = argv[0], argv[1:]

    from playwright.sync_api import sync_playwright

    any_fail = False
    with local_static_server(site_root) as base_url:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            for rel_path in paths:
                url = f"{base_url}/{rel_path}"
                page.goto(url)
                issues = check_rendered_page(page, url)
                fails = [i for i in issues if i.level == "fail"]
                warns = [i for i in issues if i.level == "warn"]
                print(f"\n{rel_path}: {len(fails)} failure(s), {len(warns)} warning(s)")
                for issue in issues:
                    print(f"  {issue}")
                if fails:
                    any_fail = True
            browser.close()
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
