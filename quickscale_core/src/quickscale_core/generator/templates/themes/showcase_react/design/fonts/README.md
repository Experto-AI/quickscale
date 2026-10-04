# Project-owned fonts

Drop webfont files here and reference them from `../tokens.css` with
`@font-face { src: url("./fonts/<file>") }`. Vite resolves the relative URL and
emits or serves the font with the stylesheet.

This folder belongs to the project's design layer: no QuickScale command or
upgrade overwrites it. See `docs/technical/generated_file_ownership.md`.
