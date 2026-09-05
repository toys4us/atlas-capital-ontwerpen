/* motion.js -- the reveal contract and a few calm primitives.

   The contract (see base.css): nothing is hidden unless <html> carries the
   class "js", and only elements with .reveal are affected. So a visitor
   without JavaScript, or with a script that failed, sees everything.

   Reveal     .reveal gets .is-in once 15% of it is inside the viewport
              (measured 8% in from the bottom edge). A [data-stagger]
              container reveals its .reveal children one after the other,
              STEP ms apart. Whatever is on screen at load comes in as one
              short sequence starting on the first frame, after the web fonts
              (never later than FONTS ms). When a reveal has run, the .reveal
              class is dropped so the element returns to its own cascade.
   Mask       a .mask wrapper clips its .reveal child, which rises from below
              the fold line instead of fading (base.css does the styling; the
              observer is the same).
   Draw       .reveal.draw is a rule that draws itself (scaleX), same observer.
   Parallax   [data-parallax="0.12"] drifts at that fraction of the scroll
              distance from the viewport centre: positive lags like a
              background, negative leads. Do not put it on a .reveal element
              (both write transform); put it on a child or a wrapper.
   Lead       writes --spine-y on .roll so the bright lead on the strip's
              left edge sits level with the middle of the viewport.
   Rail       desktop only, markup in the template: two market clocks in
              [data-clock="<IANA zone>"], the number and title of the group
              in view in .rail__label (copied from that .grp's h2, so it is
              bilingual for free), and a scroll hint that leaves after the
              first 40px.

   Everything scroll-linked is one passive listener and one rAF. Reduced
   motion: everything is simply shown, nothing drifts; the clocks still tick
   because a clock is information, not decoration. */
(function(){
  var root = document.documentElement, W = window;
  try {
  var reduce = false;
  try { reduce = W.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch(e){}

  var STEP = 220;         /* ms between staggered siblings                */
  var GAP = 200;          /* ms between groups in the load sequence        */
  var CAP = 700;          /* the load sequence never waits longer          */
  var FONTS = 400;        /* ms we are willing to wait for the web fonts   */
  var BEAT = 220;         /* ms of stillness before the fold comes in      */
  var DUR = 1800;         /* >= the longest reveal transition in css       */

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

  /* ---- the clocks: independent of everything else ---------------------- */
  (function clocks(){
    var els = document.querySelectorAll("[data-clock]");
    if (!els.length || !W.Intl || !Intl.DateTimeFormat) return;
    var fmts = [], i;
    for (i = 0; i < els.length; i++) {
      try {
        fmts.push(new Intl.DateTimeFormat("nl-NL", { timeZone: els[i].getAttribute("data-clock"),
                  hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }));
      } catch(e) { fmts.push(null); }
    }
    function tick(){
      var now = new Date(), k;
      for (k = 0; k < els.length; k++) {
        if (!fmts[k]) continue;
        var s = fmts[k].format(now).replace(/\./g, ":");
        if (els[k].textContent !== s) els[k].textContent = s;
      }
      setTimeout(tick, 1000 - (Date.now() % 1000));
    }
    tick();
  })();

  function pad(n){ return n < 10 ? "0" + n : "" + n; }
  /* reduced motion: the rail still names the group in view, without sliding */
  function railStatic(){
    var rl = document.querySelector(".rail"), lb = rl ? rl.querySelector(".rail__label") : null;
    var rr = document.querySelector(".roll"), gs = rr ? rr.querySelectorAll(".grp") : [];
    if (!rl || !lb) return;
    function upd(){
      var h = W.innerHeight || root.clientHeight, mid = h / 2, at = -1, i;
      var r = rr ? rr.getBoundingClientRect() : null;
      if (r && r.top < mid && r.bottom > mid) {
        for (i = 0; i < gs.length; i++) { if (gs[i].getBoundingClientRect().top < mid) at = i; else break; }
      }
      var h2 = at >= 0 ? gs[at].querySelector("h2") : null;
      var html = h2 ? "<b>" + pad(at + 1) + "</b>" + h2.innerHTML : "";
      if (lb.innerHTML !== html) lb.innerHTML = html;
      rl.classList.toggle("is-scrolled", (W.scrollY || W.pageYOffset || 0) > 40);
    }
    W.addEventListener("scroll", upd, { passive: true });
    upd();
  }
  if (reduce || !("IntersectionObserver" in W)) {
    for (var i = 0; i < all.length; i++) all[i].classList.add("is-in");
    root.classList.add("js");
    railStatic();
    return;
  }

  /* ---- load: the fold as a sequence ------------------------------------
     html.js is normally set by the one-line script in <head>, before the
     body exists, so the fold is painted hidden from the first frame. If that
     line is missing, set it here behind .no-tr: the hide is then a cut, not
     a transition that the next frame would only reverse. Either way the
     next frame starts the intro. Groups above the fold follow each other;
     nothing waits past CAP. The intro itself waits one BEAT after the
     fonts, so the first thing the visitor sees is stillness, then the
     fold arriving; the whole sequence is over well inside two seconds. */
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
    setTimeout(function(){ W.requestAnimationFrame(run); }, BEAT);
  }
  function run(){
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
  }
  /* the fold is hidden anyway, so give the web fonts a moment (never more
     than FONTS ms) and let the serif arrive as itself, not as a swap */
  try {
    var fs = document.fonts;
    if (fs && fs.load) {
      Promise.all([fs.load('1em Newsreader'), fs.load('italic 1em Newsreader'),
                   fs.load('1em "Fragment Mono"')]).then(intro, intro);
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

  /* ---- scroll-linked: parallax, the lead, the rail ---------------------- */
  var px = document.querySelectorAll("[data-parallax]");
  var roll = document.querySelector(".roll");
  var rail = document.querySelector(".rail");
  var label = rail ? rail.querySelector(".rail__label") : null;
  var grps = roll ? roll.querySelectorAll(".grp") : [];
  var cur = -2, swapT = null;

  function setLabel(i){
    if (i === cur || !label) return;
    cur = i;
    var h2 = i >= 0 ? grps[i].querySelector("h2") : null;
    var html = h2 ? "<b>" + pad(i + 1) + "</b>" + h2.innerHTML : "";
    label.classList.add("is-out");
    clearTimeout(swapT);
    swapT = setTimeout(function(){
      label.innerHTML = html;
      label.classList.remove("is-out");
      label.classList.add("is-new");
      void label.offsetHeight;
      label.classList.remove("is-new");
    }, 320);
  }

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
      if (rail) {
        var at = -1;
        if (r.top < mid && r.bottom > mid) {
          for (i = 0; i < grps.length; i++) {
            if (grps[i].getBoundingClientRect().top < mid) at = i; else break;
          }
        }
        setLabel(at);
      }
    }
    if (rail) rail.classList.toggle("is-scrolled", (W.scrollY || W.pageYOffset || 0) > 40);
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
