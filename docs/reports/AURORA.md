# The panel's look and the aurora on origen's page

Asked by marcos on 2026-11-16: give origen.pietri.dev the factory panel's look,
with the aurora night behind it.

## What changed

- `static/origen.css`: the page in the panel's look: one frosted-glass sheet on
  the aurora, the panel's palette, Bricolage Grotesque / Figtree / JetBrains
  Mono, tables as glass cards, the sky chart as a dark disc ringed in aurora
  green, the form with the panel's gradient button.
- The aurora layer (`<div class="aurora" aria-hidden="true">`, the `.aurora`
  rules and `aurora.jpg` / `aurora-tall.jpg`) is origen's **own copy** of the
  panel's. Sharing one file between the repos was proposed; marcos chose the
  own copy (2026-11-16), knowing the background's ~10 CSS lines look like the
  panel's.
- `static/fonts/`: the three fonts, self-hosted (spec §8: the browser calls no
  third party), latin subset, SIL OFL 1.1 (`fonts/OFL.txt`).
- The motto is still the page's first line; the aurora `div` sits at the end of
  `<body>` (it is fixed and hidden from screen readers).
- Tests: every `url()` in the CSS points to a local file; the photos are
  served; the page carries the layer.

Open point: the aurora photos came from the panel (mockup v1); their source and
licence are not recorded there either.

## Try it

    uv run origen fetch-data && uv run origen serve   # then open http://127.0.0.1:8800
    uv run pytest -q
