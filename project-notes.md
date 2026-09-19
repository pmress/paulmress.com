# Project notes

## 2026-09-19 — Reduced-motion guard fix for `.scroll-cue` + related selectors

- Bug: `.scroll-cue span`'s `scroll-cue` animation had no
  `prefers-reduced-motion: reduce` coverage, so OS-level "reduce motion"
  users still saw it loop. Only the site's manual "Reduce motion" toggle
  (`html.a11y-motion-reduce`) stopped it.
- Root cause (found via Playwright render check, not visible from static
  CSS text): the site's `@media (prefers-reduced-motion: reduce)` block
  sits earlier in `styles.css` than the component rules it's meant to
  override. With matching selector specificity, plain CSS cascade order
  let the later, unguarded rule win even while the media query matched —
  so the guard block was silently non-functional for every selector in
  it (`.hero h1`, `.timeline-pulse`, `.steps-pulse`, `.frontier-node-glow`,
  `.frontier-node-core`, `.thinking-pulse-glow`), not just `.scroll-cue`.
- Fix: added `!important` to every declaration in that guard block
  (existing selectors + newly added `.scroll-cue span`,
  `.thought-nodes-pulse`, `.path-tracker-dot--live`,
  `.path-map-node--current .path-map-node-dot`). Verified via headless
  Chromium (Playwright) with `prefers-reduced-motion: reduce` emulated:
  all 10 selectors now compute `animation-name: none`.
- `scripts/accessibility_check.py` updated to read linked stylesheets
  (not just inline `<style>`) and check reduced-motion coverage
  per-selector instead of "does any guard exist anywhere."
- Cache-busting: bumped `styles.css?v=20260911` → `?v=20260919` on all
  30 pages that load it.
- `accessibility_check.py`: 0 reduced-motion failures across all 33 HTML
  files (was: 1 failure per page loading `styles.css`, before the fix).
  15 pre-existing, unrelated failures remain (`form-labels`,
  `heading-hierarchy` — not touched by this change). 1 warning
  (`templates/lab-experiment.template.html`'s `../../styles.css` href
  only resolves once the template is rendered into `lab/<slug>/`).
- `scripts/audit-site.py`: no drift, footer check OK across all 22 pages.
- Flagged, not edited: `/design-system/` (line ~1559) claims motion
  respects `prefers-reduced-motion` "everywhere," and `.scroll-cue` isn't
  documented there. Given the cascade-order bug above affected multiple
  selectors beyond `.scroll-cue`, that claim was inaccurate site-wide
  until this fix; may be worth a doc update.
