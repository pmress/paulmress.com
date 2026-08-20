// Footer year
document.getElementById("year").textContent = new Date().getFullYear();

// ---------------------------------------------------------------
// Hero network canvas: a quiet nod to "this person builds with AI"
// rather than just claiming it in copy.
// ---------------------------------------------------------------
(function initHeroNetwork() {
  const canvas = document.getElementById("hero-canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const hero = canvas.closest(".hero");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let nodes = [];
  let pulses = [];
  let width = 0;
  let height = 0;
  let dpr = Math.min(window.devicePixelRatio || 1, 2);
  let rafId = null;

  const LINK_DIST = 140;
  const NODE_COLOR = "76, 58, 227";
  const LINE_COLOR = "76, 58, 227";
  const SPARK_COLOR = "76, 58, 227";
  const BRANCH_COLOR = "228, 87, 46";
  const MAX_PULSES = 3;
  const GROW_FRAC = 0.55; // fraction of a bolt's life spent striking outward

  function sizeCanvas() {
    const rect = hero.getBoundingClientRect();
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
    const count = Math.max(18, Math.min(56, Math.round(area / 16000)));
    nodes = Array.from({ length: count }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
    }));
  }

  function maybeSpawnPulse(edges, now) {
    if (pulses.length >= MAX_PULSES) return;
    if (Math.random() > 0.02) return;
    if (!edges.length) return;
    const [i, j, dist] = edges[Math.floor(Math.random() * edges.length)];
    // Slow, deliberate strike-hold-fade lifecycle rather than a fast pulse.
    const duration = 1700 + dist * 5.5;
    pulses.push({ i, j, duration, startedAt: now });
  }

  // Draws the whole bolt from node a up to the current growth point
  // (lengthFrac of the way to b) as one continuous jagged zigzag, like real
  // lightning striking across the connection, with occasional forked
  // branches off the main channel.
  function drawBolt(a, b, lengthFrac, alpha) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist === 0) return;
    const nx = -dy / dist;
    const ny = dx / dist;

    const segments = Math.max(5, Math.min(16, Math.round((dist * lengthFrac) / 16)));
    const points = [{ x: a.x, y: a.y }];
    for (let k = 1; k <= segments; k++) {
      const t = (lengthFrac * k) / segments;
      const px = a.x + dx * t;
      const py = a.y + dy * t;
      const edgeFade = Math.min(1, t * 9, (1 - t) * 9);
      const amp = 9 * edgeFade;
      const jitter = (Math.random() - 0.5) * 2 * amp;
      points.push({ x: px + nx * jitter, y: py + ny * jitter });
    }

    ctx.lineJoin = "miter";
    ctx.lineCap = "butt";

    // outer glow, thin and sharp
    ctx.strokeStyle = `rgba(${SPARK_COLOR}, ${0.22 * alpha})`;
    ctx.lineWidth = 3.2;
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let k = 1; k < points.length; k++) ctx.lineTo(points[k].x, points[k].y);
    ctx.stroke();

    // bright white-hot core
    ctx.strokeStyle = `rgba(255,255,255,${0.92 * alpha})`;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let k = 1; k < points.length; k++) ctx.lineTo(points[k].x, points[k].y);
    ctx.stroke();

    // one or two branch forks off random points along the bolt, like real
    // lightning splintering off the main channel
    const forkCount = points.length > 4 ? (Math.random() < 0.5 ? 1 : 2) : 1;
    for (let f = 0; f < forkCount; f++) {
      if (Math.random() > 0.6) continue;
      const originIdx = 1 + Math.floor(Math.random() * (points.length - 2));
      const origin = points[originIdx];
      const baseAngle = Math.atan2(dy, dx) + (Math.random() - 0.5) * 1.4;
      const len1 = 10 + Math.random() * 14;
      const bend = baseAngle + (Math.random() - 0.5) * 0.8;
      const len2 = 8 + Math.random() * 10;
      const mx = origin.x + Math.cos(baseAngle) * len1;
      const my = origin.y + Math.sin(baseAngle) * len1;
      const ex = mx + Math.cos(bend) * len2;
      const ey = my + Math.sin(bend) * len2;
      ctx.strokeStyle = `rgba(${BRANCH_COLOR}, ${0.5 * alpha})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(origin.x, origin.y);
      ctx.lineTo(mx, my);
      ctx.lineTo(ex, ey);
      ctx.stroke();
    }

    // small flash at the leading tip while still growing
    if (lengthFrac < 1) {
      const tip = points[points.length - 1];
      for (let r = 0; r < 3; r++) {
        const angle = Math.random() * Math.PI * 2;
        const len = 4 + Math.random() * 4;
        const ex = tip.x + Math.cos(angle) * len;
        const ey = tip.y + Math.sin(angle) * len;
        ctx.strokeStyle = `rgba(255,255,255,${0.7 * alpha})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(tip.x, tip.y);
        ctx.lineTo(ex, ey);
        ctx.stroke();
      }
    }
  }

  function step(now) {
    ctx.clearRect(0, 0, width, height);

    nodes.forEach((n) => {
      n.x += n.vx;
      n.y += n.vy;
      if (n.x < 0 || n.x > width) n.vx *= -1;
      if (n.y < 0 || n.y > height) n.vy *= -1;
    });

    const activeEdgeKeys = new Set(pulses.map((p) => `${p.i}-${p.j}`));
    const edges = [];

    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < LINK_DIST) {
          edges.push([i, j, dist]);
          const carrying = activeEdgeKeys.has(`${i}-${j}`);
          if (carrying) {
            const flicker = 0.22 + Math.random() * 0.12;
            ctx.strokeStyle = `rgba(${LINE_COLOR}, ${flicker})`;
            ctx.lineWidth = 1.2;
          } else {
            ctx.strokeStyle = `rgba(${LINE_COLOR}, ${0.16 * (1 - dist / LINK_DIST)})`;
            ctx.lineWidth = 1;
          }
          ctx.beginPath();
          ctx.moveTo(nodes[i].x, nodes[i].y);
          ctx.lineTo(nodes[j].x, nodes[j].y);
          ctx.stroke();
        }
      }
    }

    maybeSpawnPulse(edges, now);

    pulses = pulses.filter((p) => (now - p.startedAt) / p.duration < 1 && nodes[p.i] && nodes[p.j]);

    pulses.forEach((p) => {
      const a = nodes[p.i];
      const b = nodes[p.j];
      if (!a || !b) return;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist > LINK_DIST * 1.4) return;

      const progress = (now - p.startedAt) / p.duration;
      let lengthFrac, alpha;
      if (progress < GROW_FRAC) {
        lengthFrac = progress / GROW_FRAC;
        alpha = 1;
      } else {
        lengthFrac = 1;
        const fadeT = (progress - GROW_FRAC) / (1 - GROW_FRAC);
        alpha = 1 - fadeT;
      }
      drawBolt(a, b, lengthFrac, alpha);
    });

    nodes.forEach((n) => {
      ctx.fillStyle = `rgba(${NODE_COLOR}, 0.45)`;
      ctx.beginPath();
      ctx.arc(n.x, n.y, 1.8, 0, Math.PI * 2);
      ctx.fill();
    });

    if (!reduceMotion) rafId = requestAnimationFrame(step);
  }

  function start() {
    sizeCanvas();
    makeNodes();
    pulses = [];
    if (rafId) cancelAnimationFrame(rafId);
    step(performance.now());
  }

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(start, 150);
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (rafId) cancelAnimationFrame(rafId);
    } else if (!reduceMotion) {
      step(performance.now());
    }
  });

  start();
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
