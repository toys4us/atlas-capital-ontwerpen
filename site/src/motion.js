/* motion.js -- the reveal contract and a few calm primitives.

   The contract (see base.css): nothing is hidden unless <html> carries the
   class "js", and only elements with .reveal are affected. So a visitor
   without JavaScript, or with a script that failed, sees everything.

   Reveal     .reveal gets .is-in once it is inside the viewport (measured
              8% in from the bottom edge). A [data-stagger] container
              reveals its .reveal children one after the other, STEP ms
              apart (or the attribute's own value); a child with
              [data-at="ms"] takes that slot instead of the next one (the
              spread's plate develops from the first beat while the words
              rise); on scroll the whole sequence is capped so nothing
              waits behind its siblings.
              Whatever is on screen at load comes in as one sequence
              starting on the first frame, after the web fonts (never later
              than FONTS ms). When a reveal has run, the .reveal class is
              dropped so the element returns to its own cascade.
   Auto       the roll's own blocks are tagged here, before the first frame,
              so the section partials carry no motion markup: group titles
              (.card: the rule draws, the title fades), credit pairs (a
              stagger of rows), plates and proofs (a stagger of figures),
              ledes, quotes, the end card and the footer.
   Mask       a .mask wrapper clips its .reveal child, which rises from below
              the fold line instead of fading (base.css does the styling; the
              observer is the same).
   Draw       .reveal.draw is a rule that draws itself (scaleX), same observer.
   Parallax   [data-parallax="0.12"] drifts at that fraction of the scroll
              distance from the viewport centre: positive lags like a
              background, negative leads. With [data-parallax-top] it drifts
              from where it sits at scroll 0 instead (for the fold). Do not
              put it on a .reveal element (both write transform); put it on
              a child or a wrapper.
   Header     .is-top while the page is at the top (the bar is transparent
              over the title card); .solid on the header's link whenever no
              other gold button is on screen, so there is one gold button
              per viewport and the link becomes it when the card's has gone.
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

  var STEP = 160;         /* ms between staggered siblings (default)      */
  var SCROLL_SPAN = 420;  /* on scroll a whole stagger fits in this        */
  var GAP = 110;          /* ms between groups in the load sequence        */
  var CAP = 900;          /* the load sequence never waits longer          */
  var FONTS = 350;        /* ms we are willing to wait for the web fonts   */
  var BEAT = 140;         /* ms of black before the page comes in          */
  var DUR = 2000;         /* >= the longest reveal transition in css       */

  /* ---- auto: tag the roll's blocks -------------------------------------
     Before anything is measured. Each entry: selector, what to add to the
     match, and (for a stagger) what to add to which children. */
  function tag(el, cls){ if (el && !el.classList.contains("reveal")) el.classList.add.apply(el.classList, cls.split(" ")); }
  function auto(sel, cls, kids, kidCls, step){
    var els = document.querySelectorAll(sel), i, k, c;
    for (i = 0; i < els.length; i++) {
      if (els[i].closest("[data-stagger]") || els[i].classList.contains("reveal")) continue;
      if (kids) {
        c = els[i].querySelectorAll(kids);
        if (!c.length) continue;
        els[i].setAttribute("data-stagger", step || "");
        for (k = 0; k < c.length; k++) tag(c[k], kidCls || "reveal");
      } else {
        tag(els[i], cls);
      }
    }
  }
  function wrapMask(el){
    if (!el || (el.parentNode && el.parentNode.classList.contains("mask"))) return;
    var m = document.createElement("div");
    m.className = "mask";
    el.parentNode.insertBefore(m, el);
    m.appendChild(el);
    tag(el, "reveal");
  }
  if (!reduce) {
    auto(".roll .grp", "reveal card");
    auto(".roll .lesson-lede", "reveal");
    auto(".roll dl.pairs", null, ":scope > dt, :scope > dd", "reveal", 70);
    auto(".roll .lessons", null, ":scope > figure, :scope > *", "reveal", 110);
    auto(".roll .proofs", null, ":scope > figure, :scope > *", "reveal", 90);
    auto(".roll .still", null, ".hair, blockquote, .who", "reveal", 180);
    auto(".roll .interstitial", null, ":scope > *", "reveal", 140);
    auto(".roll .proofs-hint, .roll .caveat", "reveal");
    wrapMask(document.querySelector("#closer .endword"));
    auto("#closer", null, ":scope > svg, .mask > .endword, :scope > .subtitle, :scope > .cta", "reveal", 140);
    auto("footer", "reveal");
    var em = document.querySelector("#closer svg");
    if (em && !em.hasAttribute("data-parallax")) { /* the reel emblem lags a little behind the card */
      var w = document.createElement("span"); w.setAttribute("data-parallax", "0.08"); w.style.display = "block";
      em.parentNode.insertBefore(w, em); w.appendChild(em);
    }
  }

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
  function stepOf(box, n, onScroll){
    var s = parseInt(box.getAttribute("data-stagger"), 10);
    if (isNaN(s) || s <= 0) s = STEP;
    if (onScroll && n > 1) s = Math.min(s, Math.floor(SCROLL_SPAN / (n - 1)));
    return s;
  }
  /* reveal a container's children in sequence; returns the delay after the
     last. A child with data-at takes that slot (ms after the sequence
     starts) and does not advance the sequence. */
  function stagger(box, base, onScroll){
    var kids = box.querySelectorAll(".reveal"), i, at, d = base || 0, s = stepOf(box, kids.length, onScroll);
    for (i = 0; i < kids.length; i++) {
      if (kids[i].classList.contains("is-in")) continue;
      at = kids[i].getAttribute("data-at");
      if (at !== null) {
        at = parseInt(at, 10) || 0;
        if (onScroll) at = Math.min(at, SCROLL_SPAN);
        show(kids[i], (base || 0) + at);
        continue;
      }
      show(kids[i], d); d += s;
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

  /* ---- the header: transparent at the top, one gold button per viewport --
     The link in the bar is quiet text while any other .cta.solid is on
     screen and is the gold button itself when none is. Works with or
     without reduced motion: it is state, not decoration. */
  var hdr = document.querySelector("#header");
  var hdrCta = hdr ? hdr.querySelector(".cta") : null;
  var golds = [], g, gv = [];
  (function header(){
    if (!hdr) return;
    var sol = document.querySelectorAll(".cta.solid");
    for (g = 0; g < sol.length; g++) if (!hdr.contains(sol[g])) { golds.push(sol[g]); gv.push(false); }
    function top(){ hdr.classList.toggle("is-top", (W.scrollY || W.pageYOffset || 0) < 8); }
    function swap(){
      var any = false, i;
      for (i = 0; i < gv.length; i++) if (gv[i]) any = true;
      if (hdrCta) hdrCta.classList.toggle("solid", !any && golds.length > 0);
    }
    top();
    W.addEventListener("scroll", top, { passive: true });
    if ("IntersectionObserver" in W && golds.length) {
      var gio = new IntersectionObserver(function(entries){
        for (var k = 0; k < entries.length; k++) {
          var i = golds.indexOf(entries[k].target);
          if (i >= 0) gv[i] = entries[k].isIntersecting;
        }
        swap();
      }, { threshold: 0, rootMargin: "-" + (hdr.offsetHeight || 52) + "px 0px 0px 0px" });
      for (g = 0; g < golds.length; g++) gio.observe(golds[g]);
    }
  })();

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
     next frame starts the intro. Groups above the fold follow each other
     (the bar first, then the spread); nothing waits past CAP. The intro
     itself waits one BEAT after the fonts, so the page is black for a
     breath and then arrives; the whole sequence is over inside two
     seconds, and the first thing in it is on screen within half of one. */
  if (!root.classList.contains("js")) {
    root.classList.add("no-tr");
    root.classList.add("js");
    void root.offsetHeight;
    root.classList.remove("no-tr");
  }
  var j, started = false;
  /* what is on screen right now belongs to the intro, not to the observer */
  var fold = [];
  for (j = 0; j < boxes.length; j++) if (inView(boxes[j])) fold.push(boxes[j]);
  for (j = 0; j < all.length; j++) if (!all[j].closest("[data-stagger]") && inView(all[j])) fold.push(all[j]);
  function intro(){
    if (started) return;
    started = true;
    setTimeout(function(){ W.requestAnimationFrame(run); }, BEAT);
  }
  function snap(el){ el.classList.add("no-tr"); el.classList.add("is-in"); setTimeout(function(){ el.classList.remove("no-tr"); done(el); }, 60); }
  function run(){
      var d = 0, moved = (W.scrollY || W.pageYOffset || 0) > 60, f;
      if (moved) {
        /* the visitor has already left the top: the fold is simply there,
           and the sequence starts from where they are */
        for (f = 0; f < fold.length; f++) {
          if (fold[f].hasAttribute("data-stagger")) {
            var ks = fold[f].querySelectorAll(".reveal"), q;
            for (q = 0; q < ks.length; q++) snap(ks[q]);
          } else snap(fold[f]);
        }
      }
      /* in document order: the bar, then the spread, then whatever else
         the first screen holds; a box is one beat, a lone element another */
      var seq = document.querySelectorAll("[data-stagger], .reveal");
      for (j = 0; j < seq.length; j++) {
        var el = seq[j];
        if (!inView(el)) continue;
        if (el.hasAttribute("data-stagger")) { d = Math.min(stagger(el, d, false) + GAP, CAP); continue; }
        if (el.classList.contains("is-in") || el.closest("[data-stagger]")) continue;
        show(el, d); d = Math.min(d + GAP, CAP);
      }
      fold = [];
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

  /* ---- scroll: the observers ------------------------------------------
     Watching from the first frame, so a visitor who scrolls at once never
     passes anything unseen -- except the fold, which the intro owns until
     it has run (an observer fires for whatever is already in view, and
     that would pre-empt the beat). Single elements come in once 15% of
     them is inside; a stagger box starts as soon as its first pixel is, so
     a long list never sits hidden while its top rows are in view. */
  function onSeen(entries, obs){
    for (var k = 0; k < entries.length; k++) {
      var en = entries[k];
      if (!en.isIntersecting) continue;
      var el = en.target;
      if (fold.indexOf(el) >= 0) continue;
      if (el.hasAttribute("data-stagger")) stagger(el, 0, true);
      else if (!el.classList.contains("is-in")) show(el, 0);
      obs.unobserve(el);
    }
  }
  var io = new IntersectionObserver(onSeen, { threshold: 0.15, rootMargin: "0px 0px -8% 0px" });
  var bio = new IntersectionObserver(onSeen, { threshold: 0, rootMargin: "0px 0px -8% 0px" });
  for (j = 0; j < boxes.length; j++) bio.observe(boxes[j]);
  for (j = 0; j < all.length; j++) {
    if (!all[j].closest("[data-stagger]")) io.observe(all[j]);
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

  var offs = [], fromTop = [], p;
  for (p = 0; p < px.length; p++) { offs.push(0); fromTop.push(px[p].hasAttribute("data-parallax-top")); }

  var ticking = false;
  function frame(){
    ticking = false;
    var h = W.innerHeight || root.clientHeight, mid = h / 2, r, y, c, f, i;
    var sy = W.scrollY || W.pageYOffset || 0;
    for (i = 0; i < px.length; i++) {
      f = parseFloat(px[i].getAttribute("data-parallax"));
      if (isNaN(f)) f = 0.1;
      if (fromTop[i]) {
        y = sy * f;                                 /* lags behind the page  */
        if (sy > h * 1.5) continue;                 /* long gone: leave it   */
      } else {
        r = px[i].getBoundingClientRect();
        c = r.top + r.height / 2 - offs[i];         /* centre before our own shift */
        if (c < -h || c > h * 2) continue;          /* far off screen: leave it    */
        y = (c - mid) * f;
      }
      if (Math.abs(y - offs[i]) < 0.05) continue;
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
    if (rail) rail.classList.toggle("is-scrolled", sy > 40);
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
