(function(){
  var r = document.documentElement, KEY = "atlas.lang";
  function set(l, save){
    r.setAttribute("data-lang", l);
    r.setAttribute("lang", l);
    var bs = document.querySelectorAll(".langsw button");
    for (var i = 0; i < bs.length; i++)
      bs[i].setAttribute("aria-pressed", bs[i].dataset.lang === l ? "true" : "false");
    if (save) { try { localStorage.setItem(KEY, l); } catch(e){} }
  }
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch(e){}
  set(saved === "en" ? "en" : "nl", false);
  document.addEventListener("click", function(e){
    var b = e.target.closest(".langsw button");
    if (b) set(b.dataset.lang, true);
  });
})();
