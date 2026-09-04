// Footer year
document.getElementById("year").textContent = new Date().getFullYear();

// ---------------------------------------------------------------
// Nav toggle: hamburger opens a slide-in panel
// ---------------------------------------------------------------
(function initNavToggle() {
  const toggle = document.getElementById("nav-toggle");
  const panel = document.getElementById("nav-panel");
  const scrim = document.getElementById("nav-scrim");
  if (!toggle || !panel || !scrim) return;

  const panelCanvas = document.getElementById("nav-panel-canvas");
  const panelNet = panelCanvas
    ? createNodeNetwork(panelCanvas, panel, {
        linkDist: 110,
        density: 9000,
        minCount: 10,
        maxCount: 26,
        speed: 0.18,
      })
    : null;

  function openNav() {
    toggle.setAttribute("aria-expanded", "true");
    panel.classList.add("is-open");
    scrim.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    if (panelNet) panelNet.start();
  }

  function closeNav() {
    toggle.setAttribute("aria-expanded", "false");
    panel.classList.remove("is-open");
    scrim.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    if (panelNet) panelNet.stop();
  }

  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    if (isOpen) closeNav();
    else openNav();
  });

  scrim.addEventListener("click", closeNav);

  panel.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", closeNav);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeNav();
  });
})();

// ---------------------------------------------------------------
// Node network canvas: a quiet nod to "this person builds with AI"
// rather than just claiming it in copy. Shared by the hero background
// and the nav panel, so the same "techy" motif shows up in both places.
// ---------------------------------------------------------------
function createNodeNetwork(canvas, boundsEl, opts) {
  const ctx = canvas.getContext("2d");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const LINK_DIST = opts.linkDist || 140;
  const NODE_COLOR = opts.color || "76, 58, 227";
  const LINE_COLOR = opts.color || "76, 58, 227";
  const SPEED = opts.speed || 0.25;
  const DENSITY = opts.density || 16000;
  const MIN_COUNT = opts.minCount || 18;
  const MAX_COUNT = opts.maxCount || 56;

  let nodes = [];
  let width = 0;
  let height = 0;
  let dpr = Math.min(window.devicePixelRatio || 1, 2);
  let rafId = null;
  let running = false;

  function sizeCanvas() {
    const rect = boundsEl.getBoundingClientRect();
    width = rect.width;
    height = rect.height;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function makeNodes() {
    const area = width * height;
    const count = Math.max(MIN_COUNT, Math.min(MAX_COUNT, Math.round(area / DENSITY)));
    nodes = Array.from({ length: count }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * SPEED,
      vy: (Math.random() - 0.5) * SPEED,
    }));
  }

  function step() {
    ctx.clearRect(0, 0, width, height);

    nodes.forEach((n) => {
      n.x += n.vx;
      n.y += n.vy;
      if (n.x < 0 || n.x > width) n.vx *= -1;
      if (n.y < 0 || n.y > height) n.vy *= -1;
    });

    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < LINK_DIST) {
          ctx.strokeStyle = `rgba(${LINE_COLOR}, ${0.16 * (1 - dist / LINK_DIST)})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(nodes[i].x, nodes[i].y);
          ctx.lineTo(nodes[j].x, nodes[j].y);
          ctx.stroke();
        }
      }
    }

    nodes.forEach((n) => {
      ctx.fillStyle = `rgba(${NODE_COLOR}, 0.45)`;
      ctx.beginPath();
      ctx.arc(n.x, n.y, 1.8, 0, Math.PI * 2);
      ctx.fill();
    });

    if (running && !reduceMotion) rafId = requestAnimationFrame(step);
  }

  function start() {
    running = true;
    sizeCanvas();
    makeNodes();
    if (rafId) cancelAnimationFrame(rafId);
    step();
  }

  function stop() {
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
  }

  return { start, stop };
}

(function initNetworkCanvases() {
  // Generalized so any section can opt into the same background motif by
  // giving its canvas the .hero-canvas class — not just the homepage hero.
  const canvases = document.querySelectorAll(".hero-canvas");
  if (!canvases.length) return;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  canvases.forEach((canvas) => {
    const bounds = canvas.parentElement;
    if (!bounds) return;

    const net = createNodeNetwork(canvas, bounds, {
      linkDist: 140,
      density: 16000,
      minCount: 18,
      maxCount: 56,
      speed: 0.25,
    });

    let resizeTimer;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(net.start, 150);
    });

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) net.stop();
      else if (!reduceMotion) net.start();
    });

    net.start();
  });
})();

// ---------------------------------------------------------------
// Scroll progress bar
// ---------------------------------------------------------------
const progressBar = document.getElementById("scroll-progress");

function updateProgress() {
  const scrollTop = window.scrollY;
  const docHeight = document.documentElement.scrollHeight - window.innerHeight;
  const pct = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
  progressBar.style.width = pct + "%";
}

let ticking = false;
window.addEventListener("scroll", () => {
  if (!ticking) {
    requestAnimationFrame(() => {
      updateProgress();
      ticking = false;
    });
    ticking = true;
  }
});
updateProgress();

// ---------------------------------------------------------------
// Reveal-on-scroll
// ---------------------------------------------------------------
const revealEls = document.querySelectorAll("[data-reveal]");

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
  );
  revealEls.forEach((el) => observer.observe(el));
} else {
  revealEls.forEach((el) => el.classList.add("is-visible"));
}

// Stagger timeline items slightly for a nicer cascade
document.querySelectorAll(".timeline-item").forEach((el, i) => {
  el.style.transitionDelay = Math.min(i * 60, 240) + "ms";
});

// ---------------------------------------------------------------
// Contact form -> Web3Forms
// ---------------------------------------------------------------
const WEB3FORMS_ACCESS_KEY = "de639a7b-3f57-4f6f-b113-dfadd5346e5d";

const form = document.getElementById("contact-form");
const status = document.getElementById("form-status");

// Only present on the homepage's Connect section; guard so pages without
// it (Story, About) don't throw and halt the rest of this script.
if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!WEB3FORMS_ACCESS_KEY) {
      status.textContent = "Form isn't wired up to send email yet, so for now please reach out on LinkedIn.";
      status.className = "form-status is-error";
      return;
    }

    const submitBtn = form.querySelector("button[type='submit']");
    submitBtn.disabled = true;
    status.textContent = "Sending...";
    status.className = "form-status";

    const formData = new FormData(form);
    formData.append("access_key", WEB3FORMS_ACCESS_KEY);
    formData.append("subject", "New message from paulmress.com");

    try {
      const response = await fetch("https://api.web3forms.com/submit", {
        method: "POST",
        headers: { Accept: "application/json" },
        body: formData,
      });
      const result = await response.json();

      if (result.success) {
        status.textContent = "Thanks! Your message is on its way.";
        status.className = "form-status is-success";
        form.reset();
      } else {
        throw new Error(result.message || "Submission failed");
      }
    } catch (err) {
      status.textContent = "Something went wrong sending that. Try LinkedIn instead?";
      status.className = "form-status is-error";
    } finally {
      submitBtn.disabled = false;
    }
  });
}

// ---------------------------------------------------------------
// Content toolbar: shared filter / sort / search organism.
// Used on /lab/ (facet: status) and /thinking/ (facet: topic) — same
// markup, same logic; only the data-status vocabulary differs per page.
// Guarded so pages without a .content-toolbar do nothing.
// ---------------------------------------------------------------
document.querySelectorAll(".content-toolbar").forEach((toolbar) => {
  const list = toolbar.nextElementSibling;
  if (!list) return;

  // Filter to items that opt in via data-status, so decorative siblings
  // (e.g. .thought-nodes-pulse) never get treated as filterable/sortable.
  const items = Array.from(list.children).filter((el) => el.hasAttribute("data-status"));
  const searchInput = toolbar.querySelector(".js-search");
  const searchField = toolbar.querySelector(".search-field");
  const clearSearchBtn = toolbar.querySelector(".search-field-clear");
  const sortSelect = toolbar.querySelector(".js-sort");
  const filterGroup = toolbar.querySelector(".js-filters");
  const countEl = toolbar.querySelector(".js-count");
  const clearAllBtn = toolbar.querySelector(".js-clear");
  if (!searchInput || !sortSelect || !filterGroup || !countEl) return;

  const noun = (countEl.textContent.split(" of ")[1] || "items").replace(/^\d+\s*/, "");
  let activeFilter = "all";

  // Progressive reveal (Experiment 5): every item already sits in the
  // page's static HTML -- nothing is fetched on scroll -- so a crawler
  // that never executes JavaScript (most AI crawlers, as of the research
  // behind this experiment) sees the full list regardless of how far a
  // person has scrolled. This only staggers what's *visually* shown,
  // batch by batch, as a real visitor nears the bottom of the list.
  const batchSize = parseInt(list.getAttribute("data-scroll-batch"), 10) || 2;
  let revealCount = batchSize;
  let sentinel = list.nextElementSibling;
  if (!sentinel || !sentinel.classList.contains("scroll-sentinel")) {
    sentinel = document.createElement("div");
    sentinel.className = "scroll-sentinel";
    sentinel.setAttribute("aria-hidden", "true");
    list.insertAdjacentElement("afterend", sentinel);
  }
  if ("IntersectionObserver" in window) {
    // No bottom rootMargin: on a short page a look-ahead margin fires the
    // reveal (and hides the sentinel as exhausted) before it's ever actually
    // scrolled into view, so "Scroll for more" never gets seen. Only trigger
    // once the sentinel is genuinely on screen. A short deliberate pause
    // before revealing the next batch (there's no real fetch to wait on)
    // gives "Scroll for more" a moment to actually be readable, instead of
    // being replaced within the same frame it appears.
    let isRevealing = false;
    const revealObserver = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !isRevealing) {
          isRevealing = true;
          setTimeout(() => {
            revealCount += batchSize;
            apply();
            isRevealing = false;
          }, 350);
        }
      },
      { rootMargin: "0px" }
    );
    revealObserver.observe(sentinel);
  } else {
    revealCount = items.length; // no IntersectionObserver: just show everything
  }

  function apply() {
    const q = searchInput.value.trim().toLowerCase();
    if (searchField) searchField.classList.toggle("has-value", q.length > 0);

    let visible = 0;
    items.forEach((el) => {
      const matchesFilter = activeFilter === "all" || el.getAttribute("data-status") === activeFilter;
      const matchesSearch = q === "" || (el.getAttribute("data-search") || "").indexOf(q) !== -1;
      const show = matchesFilter && matchesSearch;
      el.classList.toggle("is-toolbar-hidden", !show);
      if (show) visible++;
    });

    const sortMode = sortSelect.value;
    const statusOrder = { supported: 0, ongoing: 1, inconclusive: 2, rejected: 3 };
    const sorted = items.slice().sort((a, b) => {
      const oa = parseInt(a.getAttribute("data-order"), 10) || 0;
      const ob = parseInt(b.getAttribute("data-order"), 10) || 0;
      if (sortMode === "oldest") return oa - ob;
      if (sortMode === "status") {
        const sa = statusOrder[a.getAttribute("data-status")] ?? 9;
        const sb = statusOrder[b.getAttribute("data-status")] ?? 9;
        if (sa !== sb) return sa - sb;
        return ob - oa;
      }
      return ob - oa; // newest first (default)
    });
    sorted.forEach((el) => list.appendChild(el));

    // Layer progressive reveal on top of the filter result, in the same
    // sorted order, so "first N shown" always means the first N a person
    // would actually see -- filtered-out items are left alone here.
    let shownSoFar = 0;
    sorted.forEach((el) => {
      if (el.classList.contains("is-toolbar-hidden")) {
        el.classList.remove("is-scroll-hidden");
        return;
      }
      shownSoFar++;
      el.classList.toggle("is-scroll-hidden", shownSoFar > revealCount);
    });
    sentinel.classList.toggle("is-scroll-exhausted", visible <= revealCount);

    countEl.textContent = `${visible} of ${items.length} ${noun}`;
  }

  // Any filter/search/sort change starts the reveal over at one batch --
  // otherwise switching filters could leave a stale reveal count that no
  // longer matches what's actually been scrolled into view.
  function resetAndApply() {
    revealCount = batchSize;
    apply();
  }

  searchInput.addEventListener("input", resetAndApply);
  if (clearSearchBtn) {
    clearSearchBtn.addEventListener("click", () => {
      searchInput.value = "";
      resetAndApply();
    });
  }
  sortSelect.addEventListener("change", resetAndApply);
  filterGroup.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      filterGroup.querySelectorAll(".filter-chip").forEach((c) => c.classList.remove("is-active"));
      chip.classList.add("is-active");
      activeFilter = chip.getAttribute("data-filter");
      resetAndApply();
    });
  });
  if (clearAllBtn) {
    clearAllBtn.addEventListener("click", () => {
      searchInput.value = "";
      activeFilter = "all";
      filterGroup.querySelectorAll(".filter-chip").forEach((c) => c.classList.remove("is-active"));
      const allChip = filterGroup.querySelector('[data-filter="all"]');
      if (allChip) allChip.classList.add("is-active");
      sortSelect.value = sortSelect.querySelector("option")?.value || "newest";
      resetAndApply();
    });
  }

  apply();
});

// ---------------------------------------------------------------
// Path tracker: opt-in, first-party, self-destructing 15-minute
// cookie feature (Lab Experiment 6). Tracks which pages were visited
// during one session -- nothing more. No renewal, no re-prompt: once
// the 15 minutes are up, it's gone. Dismissing the widget kills it
// immediately. Never transmitted anywhere -- see /privacy-policy/ for
// the full disclosure. The widget itself is injected here rather than
// living in per-page markup, so no page's HTML has to change to carry
// it, and no new page needs to remember to include it.
// ---------------------------------------------------------------
// Shared cookie helpers -- used by both the corner widget below and the
// full-page trail view on /breadcrumbs/, so the two stay in lockstep without
// duplicating the read/write/clear logic.
const PM_PATH_TRACKER_COOKIE = "pmPathTracker";
const PM_PATH_TRACKER_DURATION_MS = 15 * 60 * 1000; // fixed 15 minutes -- no renewal

function pmReadPathTrackerCookie() {
  const match = document.cookie.match(new RegExp("(?:^|; )" + PM_PATH_TRACKER_COOKIE + "=([^;]*)"));
  if (!match) return null;
  try {
    const data = JSON.parse(decodeURIComponent(match[1]));
    if (!data || !Array.isArray(data.trail) || typeof data.expires !== "number") return null;
    return data;
  } catch (e) {
    return null;
  }
}

function pmWritePathTrackerCookie(data) {
  const maxAge = Math.max(0, Math.round((data.expires - Date.now()) / 1000));
  document.cookie =
    PM_PATH_TRACKER_COOKIE + "=" + encodeURIComponent(JSON.stringify(data)) +
    "; path=/; max-age=" + maxAge + "; SameSite=Lax";
}

function pmClearPathTrackerCookie() {
  document.cookie = PM_PATH_TRACKER_COOKIE + "=; path=/; max-age=0";
}

(function initPathTracker() {
  const readCookie = pmReadPathTrackerCookie;
  const writeCookie = pmWritePathTrackerCookie;
  const clearCookie = pmClearPathTrackerCookie;
  const DURATION_MS = PM_PATH_TRACKER_DURATION_MS;

  const root = document.createElement("div");
  root.className = "path-tracker";
  root.innerHTML =
    '<button type="button" class="path-tracker-toggle">' +
      '<span class="path-tracker-dot" aria-hidden="true"></span>Track my path' +
    "</button>" +
    '<div class="path-tracker-panel" role="status">' +
      '<span class="path-tracker-dot path-tracker-dot--live" aria-hidden="true"></span>' +
      '<span class="path-tracker-countdown">15:00</span>' +
      '<span class="path-tracker-trail"></span>' +
      '<a href="/breadcrumbs/" class="path-tracker-view">View path</a>' +
      '<button type="button" class="path-tracker-dismiss" aria-label="Stop tracking now">&times;</button>' +
    "</div>";
  document.body.appendChild(root);

  const toggleBtn = root.querySelector(".path-tracker-toggle");
  const panel = root.querySelector(".path-tracker-panel");
  const countdownEl = root.querySelector(".path-tracker-countdown");
  const trailEl = root.querySelector(".path-tracker-trail");
  const dismissBtn = root.querySelector(".path-tracker-dismiss");

  let timerId = null;

  function formatCountdown(ms) {
    const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return m + ":" + String(s).padStart(2, "0");
  }

  function render(data) {
    const remaining = data.expires - Date.now();
    if (remaining <= 0) {
      selfDestruct();
      return;
    }
    countdownEl.textContent = formatCountdown(remaining);
    trailEl.textContent = data.trail.length + (data.trail.length === 1 ? " page" : " pages");
    root.classList.add("is-active");
    panel.classList.toggle("is-critical", remaining < 60000);
  }

  function selfDestruct() {
    clearCookie();
    if (timerId) clearInterval(timerId);
    timerId = null;
    root.classList.remove("is-active");
    panel.classList.remove("is-critical");
  }

  function startTicking() {
    if (timerId) clearInterval(timerId);
    timerId = setInterval(() => {
      const data = readCookie();
      if (!data) {
        selfDestruct();
        return;
      }
      render(data);
    }, 1000);
  }

  function beginTracking(existing) {
    const path = window.location.pathname;
    let data = existing;
    if (!data) {
      data = { trail: [path], expires: Date.now() + DURATION_MS };
    } else if (data.trail[data.trail.length - 1] !== path) {
      data.trail.push(path);
    }
    writeCookie(data);
    render(data);
    startTicking();
  }

  toggleBtn.addEventListener("click", () => beginTracking(null));
  dismissBtn.addEventListener("click", selfDestruct);

  // Resume an already-active session on load (logging this page into
  // the trail) rather than starting fresh -- opting in once should
  // follow a visitor around the site until it expires or is dismissed,
  // not reset every time they open a new page.
  const existing = readCookie();
  if (existing && existing.expires > Date.now()) {
    beginTracking(existing);
  }
})();

// ---------------------------------------------------------------
// Path map: the full-page live view of the path-tracker trail, at
// /breadcrumbs/. Reads the same cookie as the corner widget above and
// renders every visited page as a connected, growing trail of nodes.
// Guarded so pages without a .path-map container do nothing. Start/Stop
// delegate to the corner widget's own toggle/dismiss buttons instead of
// duplicating the opt-in/clear logic, so the two views can never drift
// out of sync with each other or with what the cookie actually holds.
// ---------------------------------------------------------------
(function initPathMap() {
  const mapEl = document.querySelector(".path-map");
  if (!mapEl) return;

  const PATH_LABELS = {
    "/": "Home",
    "/story/": "Story",
    "/thinking/": "Thinking",
    "/lab/": "Lab",
    "/lab/1/": "Lab · Experiment 1",
    "/lab/2/": "Lab · Experiment 2",
    "/lab/3/": "Lab · Experiment 3",
    "/lab/4/": "Lab · Experiment 4",
    "/lab/5/": "Lab · Experiment 5",
    "/lab/6/": "Lab · Experiment 6",
    "/about/": "About",
    "/design-system/": "Design System",
    "/privacy-policy/": "Privacy Policy",
    "/terms-and-conditions/": "Terms & Conditions",
    "/breadcrumbs/": "Breadcrumbs"
  };

  function labelFor(path) {
    if (PATH_LABELS[path]) return PATH_LABELS[path];
    const seg = path.replace(/\/+$/, "").split("/").pop();
    if (!seg) return "Home";
    return seg.replace(/-/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function formatCountdown(ms) {
    const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return m + ":" + String(s).padStart(2, "0");
  }

  function emptyStateHtml() {
    return (
      '<div class="path-map-empty">' +
        '<p class="path-map-empty-text">You haven&rsquo;t turned on path tracking yet &mdash; there&rsquo;s nothing to show. ' +
        'Opt in below (or via the widget in the corner) and this page fills in live, right up until it self-destructs.</p>' +
        '<button type="button" class="btn btn-primary path-map-start">Start tracking my path</button>' +
      "</div>"
    );
  }

  function activeStateHtml(data) {
    const remaining = data.expires - Date.now();
    const nodes = data.trail
      .map(function (path, i) {
        const isCurrent = i === data.trail.length - 1;
        return (
          '<li class="path-map-node' + (isCurrent ? " path-map-node--current" : "") + '">' +
            '<span class="path-map-node-dot" aria-hidden="true"></span>' +
            '<span class="path-map-node-body">' +
              '<span class="path-map-node-title">' + escapeHtml(labelFor(path)) + "</span>" +
              '<span class="path-map-node-path">' + escapeHtml(path) + "</span>" +
            "</span>" +
          "</li>"
        );
      })
      .join("");
    return (
      '<div class="path-map-status">' +
        '<span class="path-tracker-dot path-tracker-dot--live" aria-hidden="true"></span>' +
        '<span class="path-map-countdown">' + formatCountdown(remaining) + "</span>" +
        '<span class="path-map-count">' + data.trail.length + (data.trail.length === 1 ? " page" : " pages") + " visited</span>" +
        '<button type="button" class="path-map-stop">Stop tracking now</button>' +
      "</div>" +
      '<ol class="path-map-track">' + nodes + "</ol>"
    );
  }

  function wireStart() {
    const btn = mapEl.querySelector(".path-map-start");
    if (!btn) return;
    btn.addEventListener("click", function () {
      const toggle = document.querySelector(".path-tracker-toggle");
      if (toggle) toggle.click();
      render();
    });
  }

  function wireStop() {
    const btn = mapEl.querySelector(".path-map-stop");
    if (!btn) return;
    btn.addEventListener("click", function () {
      const dismiss = document.querySelector(".path-tracker-dismiss");
      if (dismiss) dismiss.click();
      render();
    });
  }

  function render() {
    const data = pmReadPathTrackerCookie();
    if (!data || data.expires <= Date.now()) {
      mapEl.innerHTML = emptyStateHtml();
      wireStart();
      return;
    }
    mapEl.innerHTML = activeStateHtml(data);
    wireStop();
  }

  render();
  setInterval(render, 1000);
})();
