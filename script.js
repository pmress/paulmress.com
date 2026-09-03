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
    const revealObserver = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          revealCount += batchSize;
          apply();
        }
      },
      { rootMargin: "0px 0px 200px 0px" }
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
