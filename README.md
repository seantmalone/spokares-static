# spokares-static

A static version of spokares.org (Spokane County ARES-ACS): the same design
as the WordPress build, limited to content that changes about once a year.
It is a review preview; it has not been chosen as the direction.

- Preview: <https://seantmalone.github.io/spokares-static/>, published by
  GitHub Pages from `main`.
- To change content: [MAINTAINING.md](MAINTAINING.md).
- Design decisions: `docs/superpowers/specs/2026-11-14-stable-static-site-design.md`.

Built with Hugo 0.164.0 and Python 3 (standard library only). Build and
check everything with `site/tools/build.sh`; preview locally with
`hugo server --source site`.
