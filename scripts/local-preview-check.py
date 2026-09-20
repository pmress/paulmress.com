#!/usr/bin/env python3
"""
Local responsive-preview checker for paulmress.com.

Loads a page from the local static server (python3 -m http.server) via
local Playwright Chromium, at a fixed set of widths, and reports:
  - horizontal scroll (scrollWidth > clientWidth)
  - console pageerror events
  - anchor-link-lands-under-sticky-header check (for each in-page #hash link)

Usage:
  python3 scripts/local-preview-check.py <path-or-url> [path-or-url ...]

Examples:
  python3 scripts/local-preview-check.py /index.html
  python3 scripts/local-preview-check.py /lab/ /thinking/
"""
import os
import sys
import json
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8899"
WIDTHS = [1440, 1024, 768, 390]
HEIGHT = 900

# Prefer a pinned Chromium if one exists at this well-known path (true in
# some sandboxed dev environments); otherwise fall back to Playwright's own
# default browser resolution so this runs unmodified on any machine that's
# just done a normal `playwright install chromium`.
_PINNED_CHROMIUM = "/opt/pw-browsers/chromium"
CHROMIUM_PATH = _PINNED_CHROMIUM if os.path.exists(_PINNED_CHROMIUM) else None


def check_page(page, url, width):
    page.set_viewport_size({"width": width, "height": HEIGHT})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(url, wait_until="networkidle")

    # bypass scroll-reveal animations so screenshots/measurements are stable
    page.evaluate("""
        document.querySelectorAll('[data-reveal]').forEach(el => el.classList.add('is-visible'));
        document.querySelectorAll('.is-scroll-hidden').forEach(el => el.classList.remove('is-scroll-hidden'));
    """)

    metrics = page.evaluate("""
        () => ({
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
            bodyScrollWidth: document.body.scrollWidth,
        })
    """)
    h_scroll = metrics["scrollWidth"] > metrics["clientWidth"] + 1

    # sticky header height, if any
    header_height = page.evaluate("""
        () => {
            const hdr = document.querySelector('header, .site-header, nav[class*="nav"]');
            if (!hdr) return 0;
            const cs = getComputedStyle(hdr);
            if (cs.position !== 'sticky' && cs.position !== 'fixed') return 0;
            return hdr.getBoundingClientRect().height;
        }
    """)

    # anchor-link landing check: for each in-page hash link, scroll to it and
    # see if the target's top is obscured by the sticky header
    # skip-links and "back to top" links are meant to land at/near the very
    # top of the page (above or level with the header) -- that's correct
    # behavior, not a sticky-header overlap bug, so exclude them
    KNOWN_TOP_TARGETS = {"top", "main"}

    anchor_issues = []
    hrefs = page.eval_on_selector_all(
        'a[href^="#"]:not([href="#"])',
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in set(hrefs):
        target_id = href[1:]
        if target_id in KNOWN_TOP_TARGETS:
            continue
        exists = page.evaluate(f"() => !!document.getElementById({json.dumps(target_id)})")
        if not exists:
            continue
        page.evaluate(f"""
            () => {{
                const el = document.getElementById({json.dumps(target_id)});
                el.scrollIntoView({{block: 'start', behavior: 'instant'}});
            }}
        """)
        # wait for layout/scroll position to settle (handles smooth-scroll
        # CSS and any late layout shift from deferred/lazy content) rather
        # than a fixed sleep, which produced false positives on pages with
        # animated scrolling
        top = page.evaluate(f"""
            () => new Promise(resolve => {{
                const el = document.getElementById({json.dumps(target_id)});
                let last = null, stableCount = 0;
                function poll() {{
                    const t = el.getBoundingClientRect().top;
                    if (last !== null && Math.abs(t - last) < 0.5) {{
                        stableCount++;
                    }} else {{
                        stableCount = 0;
                    }}
                    last = t;
                    if (stableCount >= 3) {{
                        resolve(t);
                        return;
                    }}
                    requestAnimationFrame(poll);
                }}
                requestAnimationFrame(poll);
                setTimeout(() => resolve(el.getBoundingClientRect().top), 2000);
            }})
        """)
        if header_height and top < header_height:
            anchor_issues.append({"href": href, "top": top, "header_height": header_height})

    return {
        "url": url,
        "width": width,
        "h_scroll": h_scroll,
        "scrollWidth": metrics["scrollWidth"],
        "clientWidth": metrics["clientWidth"],
        "console_errors": errors,
        "anchor_issues": anchor_issues,
    }


def main():
    paths = sys.argv[1:] or ["/index.html"]
    results = []
    with sync_playwright() as p:
        launch_kwargs = {"executable_path": CHROMIUM_PATH} if CHROMIUM_PATH else {}
        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page()
        for path in paths:
            url = path if path.startswith("http") else BASE + path
            for width in WIDTHS:
                r = check_page(page, url, width)
                results.append(r)
                flag = []
                if r["h_scroll"]:
                    flag.append("HORIZONTAL SCROLL")
                if r["console_errors"]:
                    flag.append(f"{len(r['console_errors'])} CONSOLE ERROR(S)")
                if r["anchor_issues"]:
                    flag.append(f"{len(r['anchor_issues'])} ANCHOR-UNDER-HEADER")
                status = "FAIL: " + ", ".join(flag) if flag else "OK"
                print(f"[{width:>4}px] {url}  ->  {status}")
                if r["anchor_issues"]:
                    for ai in r["anchor_issues"]:
                        print(f"    anchor {ai['href']} lands at top={ai['top']:.0f} under header height={ai['header_height']:.0f}")
                if r["console_errors"]:
                    for e in r["console_errors"]:
                        print(f"    console error: {e}")
        browser.close()

    any_fail = any(r["h_scroll"] or r["console_errors"] or r["anchor_issues"] for r in results)
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
