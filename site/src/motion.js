/* Reveal-on-scroll.
   The contract (see base.css): nothing is hidden unless <html> carries the
   class "js", and only elements with .reveal are affected. So a visitor
   without JavaScript, or with a script that failed, sees everything.
   An element gets .is-in once 15% of it is inside the viewport (measured
   8% in from the bottom edge). A [data-stagger] container reveals its
   .reveal children one after the other. */
(function(){
  var root = document.documentElement;
  var reduce = false;
  try { reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch(e){}

  var all = document.querySelectorAll(".reveal");
  function show(el){ el.classList.add("is-in"); }
  function inView(el){
    var r = el.getBoundingClientRect(), h = window.innerHeight || root.clientHeight;
    return r.bottom > 0 && r.top < h * 0.92 + 1;
  }
  function stagger(box){
    var kids = box.querySelectorAll(".reveal"), i, d = 0, step = 90;
    for (i = 0; i < kids.length; i++) {
      if (kids[i].classList.contains("is-in")) continue;
      kids[i].style.transitionDelay = d + "ms"; d += step;
      show(kids[i]);
    }
  }

  if (reduce || !("IntersectionObserver" in window)) {
    for (var i = 0; i < all.length; i++) show(all[i]);
    root.classList.add("js");
    return;
  }

  /* Anything already on screen is marked before the class goes on, so the
     first paint never shows a blank fold. */
  var boxes = document.querySelectorAll("[data-stagger]"), j;
  for (j = 0; j < boxes.length; j++) if (inView(boxes[j])) stagger(boxes[j]);
  for (j = 0; j < all.length; j++) if (inView(all[j])) show(all[j]);
  root.classList.add("js");

  var io = new IntersectionObserver(function(entries){
    for (var k = 0; k < entries.length; k++) {
      var en = entries[k];
      if (!en.isIntersecting) continue;
      var el = en.target;
      if (el.hasAttribute("data-stagger")) stagger(el); else show(el);
      io.unobserve(el);
    }
  }, { threshold: 0.15, rootMargin: "0px 0px -8% 0px" });

  for (j = 0; j < boxes.length; j++) io.observe(boxes[j]);
  for (j = 0; j < all.length; j++) {
    if (!all[j].classList.contains("is-in") && !all[j].closest("[data-stagger]")) io.observe(all[j]);
  }
})();
