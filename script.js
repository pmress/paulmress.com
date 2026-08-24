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
