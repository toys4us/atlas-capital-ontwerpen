/* motion.js -- the reveal contract and three calm primitives.

   The contract (see base.css): nothing is hidden unless <html> carries the
   class "js", and only elements with .reveal are affected. So a visitor
   without JavaScript, or with a script that failed, sees everything.

   Reveal     .reveal gets .is-in once 15% of it is inside the viewport
              (measured 8% in from the bottom edge). A [data-stagger]
              container reveals its .reveal children one after the other,
              80ms apart. Whatever is on screen at load comes in as one short
              sequence starting on the first frame. When a reveal has run,
              the .reveal class is dropped so the element returns to its own
              cascade (a button keeps its hover transition).
   Mask       a .mask wrapper clips its .reveal child, which rises from below
              the fold line instead of fading (base.css does the styling; the
              observer is the same).
   Parallax   [data-parallax="0.12"] drifts at that fraction of the scroll
              distance from the viewport centre: positive lags like a
              background, negative leads. Do not put it on a .reveal element
              (both write transform); put it on a child or a wrapper.
   Spine      writes --spine-y on .roll so the bright lead on the centre
              spine sits level with the middle of the viewport.

   Everything scroll-linked is one passive listener and one rAF. Reduced
   motion: everything is simply shown, nothing drifts. */
(function(){
  var root = document.documentElement, W = window;
  try {
  var reduce = false;
  try { reduce = W.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch(e){}

  var STEP = 80;          /* ms between staggered siblings            */
  var GAP = 120;          /* ms between groups in the load sequence    */
  var CAP = 700;          /* the load sequence never waits longer      */
  var DUR = 1200;         /* >= the longest reveal transition in css   */

  var all = document.querySelectorAll(".reveal");
  var boxes = document.querySelectorAll("[data-stagger]");

  function done(el){
    el.style.transitionDelay = "";
    el.classList.remove("reveal");
  }
  function show(el, delay){
    delay = delay || 0;
    el.style.transitionDelay = delay + "ms";
    el.classList.add("is-in");
    setTimeout(function(){ done(el); }, delay + DUR + 60);
  }
  function inView(el){
    var r = el.getBoundingClientRect(), h = W.innerHeight || root.clientHeight;
    return r.bottom > 0 && r.top < h * 0.92 + 1;
  }
  /* reveal a container's children in sequence; returns the delay after the last */
  function stagger(box, base){
    var kids = box.querySelectorAll(".reveal"), i, d = base || 0;
    for (i = 0; i < kids.length; i++) {
      if (kids[i].classList.contains("is-in")) continue;
      show(kids[i], d); d += STEP;
    }
    return d;
  }

  if (reduce || !("IntersectionObserver" in W)) {
    for (var i = 0; i < all.length; i++) all[i].classList.add("is-in");
    root.classList.add("js");
    return;
  }

  /* ---- load: the fold as a sequence ------------------------------------
     html.js is normally set by the one-line script in <head>, before the
     body exists, so the fold is painted hidden from the first frame. If that
     line is missing, set it here behind .no-tr: the hide is then a cut, not
     a transition that the next frame would only reverse. Either way the
     next frame starts the intro. Groups above the fold follow each other;
     nothing waits past CAP. */
  if (!root.classList.contains("js")) {
    root.classList.add("no-tr");
    root.classList.add("js");
    void root.offsetHeight;
    root.classList.remove("no-tr");
  }
  var j, started = false;
  function intro(){
    if (started) return;
    started = true;
    W.requestAnimationFrame(function(){
      var d = 0;
      for (j = 0; j < boxes.length; j++) {
        if (!inView(boxes[j])) continue;
        d = Math.min(stagger(boxes[j], d) + GAP, CAP);
      }
      for (j = 0; j < all.length; j++) {
        var el = all[j];
        if (el.classList.contains("is-in") || el.closest("[data-stagger]") || !inView(el)) continue;
        show(el, d); d = Math.min(d + GAP, CAP);
      }
    });
  }
  /* the fold is hidden anyway, so give the web fonts a moment (never more
     than FONTS ms) and let the serif arrive as itself, not as a swap */
  var FONTS = 400;
  try {
    var fs = document.fonts;
    if (fs && fs.load) {
      Promise.all([fs.load('1em "Instrument Serif"'), fs.load('italic 1em "Instrument Serif"'),
                   fs.load('1em Geist'), fs.load('1em "Geist Mono"')]).then(intro, intro);
    }
  } catch(e){}
  setTimeout(intro, FONTS);

  /* ---- scroll: the observer ------------------------------------------- */
  var io = new IntersectionObserver(function(entries){
    for (var k = 0; k < entries.length; k++) {
      var en = entries[k];
      if (!en.isIntersecting) continue;
      var el = en.target;
      if (el.hasAttribute("data-stagger")) stagger(el, 0); else show(el, 0);
      io.unobserve(el);
    }
  }, { threshold: 0.15, rootMargin: "0px 0px -8% 0px" });

  for (j = 0; j < boxes.length; j++) io.observe(boxes[j]);
  for (j = 0; j < all.length; j++) {
    if (!all[j].classList.contains("is-in") && !all[j].closest("[data-stagger]")) io.observe(all[j]);
  }

  /* ---- scroll-linked: parallax + spine lead ---------------------------- */
  var px = document.querySelectorAll("[data-parallax]");
  var roll = document.querySelector(".roll");
  if (!px.length && !roll) return;

  var offs = [], p;
  for (p = 0; p < px.length; p++) offs.push(0);

  var ticking = false;
  function frame(){
    ticking = false;
    var h = W.innerHeight || root.clientHeight, mid = h / 2, r, y, c, f, i;
    for (i = 0; i < px.length; i++) {
      r = px[i].getBoundingClientRect();
      c = r.top + r.height / 2 - offs[i];          /* centre before our own shift */
      if (c < -h || c > h * 2) continue;            /* far off screen: leave it     */
      f = parseFloat(px[i].getAttribute("data-parallax"));
      if (isNaN(f)) f = 0.1;
      y = (c - mid) * f;
      offs[i] = y;
      px[i].style.transform = "translate3d(0," + y.toFixed(1) + "px,0)";
    }
    if (roll) {
      r = roll.getBoundingClientRect();
      y = Math.max(0, Math.min(r.height, mid - r.top));
      roll.style.setProperty("--spine-y", y.toFixed(0) + "px");
    }
  }
  function ask(){ if (!ticking) { ticking = true; W.requestAnimationFrame(frame); } }
  W.addEventListener("scroll", ask, { passive: true });
  W.addEventListener("resize", ask);
  frame();
  } catch (err) {
    /* a broken script must never leave the page hidden */
    root.classList.remove("js");
    throw err;
  }
})();
