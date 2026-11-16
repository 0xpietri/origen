# The panel's look and the aurora on origen's page

Asked by marcos on 2026-11-16: give origen.pietri.dev the factory panel's look,
with the aurora night behind it.

## What changed

- `static/aurora.css` + `aurora.jpg` + `aurora-tall.jpg`: the aurora layer
  (`<div class="aurora" aria-hidden="true">`). It now **lives here** and the
  factory panel and the vault link it from
  `https://origen.pietri.dev/static/aurora.css` instead of keeping their own
  copy (no duplicated code between repositories). Its class and the two photos
  are a contract like `/v1`: added to, never renamed or removed. A site may
  restyle `.aurora::after` (the veil) in its own CSS.
- `static/origen.css`: the page in the panel's look: one frosted-glass sheet on
  the aurora, the panel's palette, Bricolage Grotesque / Figtree / JetBrains
  Mono, tables as glass cards, the sky chart as a dark disc ringed in aurora
  green, the form with the panel's gradient button.
- `static/fonts/`: the three fonts, self-hosted (spec §8: the browser calls no
  third party), latin subset, SIL OFL 1.1 (`fonts/OFL.txt`).
- The motto is still the page's first line; the aurora `div` sits at the end of
  `<body>` (it is fixed and hidden from screen readers).
- Tests: every `url()` in the CSS points to a local file; `aurora.css` and its
  photos are served; the page carries the layer.

The companion change in factory-panel removes the panel's own copy and links
this file (its CSP gains `https://origen.pietri.dev` for styles and images).
Deploy origen first, then the panel.

Open point: the aurora photos came from the panel (mockup v1); their source and
licence are not recorded there either.

## Try it

    uv run origen fetch-data && uv run origen serve   # then open http://127.0.0.1:8800
    uv run pytest -q
