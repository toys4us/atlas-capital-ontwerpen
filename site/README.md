# Atlas Capital — site source

Split of `designs/d028.html` into one partial per piece so builders can work
in parallel without touching each other's files. `python build.py` writes
`index.html`; it is byte-for-byte the same render as d028 until a builder
changes a piece.

```
src/index.tpl.html        head + body wrapper + grain; slots <!-- css --> <!-- sections --> <!-- js -->
src/base.css              tokens, resets, shared components, lang rules, the .reveal contract
src/lang.js               NL/EN switch (localStorage 'atlas.lang')
src/motion.js             adds html.js, reveals .reveal on scroll ([data-stagger] children in sequence)
src/sections/NN-<id>.html one partial per piece, page order
src/sections/<id>.css     that piece's CSS, every selector under #<id>
assets/                   logo, charts, proof certificates -- referenced as assets/<file>
tools/gate.py             truth gate; exit 0 only if all pass; --json, --static, --file
tools/shot.py             python tools/shot.py --section <id> --out <dir> [--full] [--lang en]
tools/progress.py         renders ../progress.html from ../_progress/*.json
```

Pieces, in page order: header, hero, production, founder, education,
channels, markets (markets + live + their interstitial), material,
trackrecord (incl. the lightbox `<dialog>` and its script), access,
closer (`section#closer` + `<footer>`).

The sections production … access are wrapped by the build in
`<div class="roll">` (the centre spine). A piece owns exactly two files:
its partial and its CSS. Shared components live in base.css; do not fork them.

Reveal-on-scroll: give an element class `reveal` (and a container
`data-stagger` for a sequence). Nothing else may be invisible — the gate
rejects opacity:0 / visibility:hidden anywhere except `.js … .reveal`.
