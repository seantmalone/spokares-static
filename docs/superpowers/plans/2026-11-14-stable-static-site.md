# Stable Static Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Hugo static version of spokares.org that looks the same as the WordPress build and carries only content that changes at most once a year, and publish it on GitHub Pages for review. The WordPress build and its deploy are left untouched.

**Architecture:** A Hugo project in `site/` renders five pages plus a 404 from Markdown prose, layout templates and one facts file (`data/facts.yaml`). Markup and CSS are ported from the WordPress-rendered pages. For review (Part 1), GitHub Actions builds with a pinned Hugo, runs a Python standard-library check over the output, and publishes to GitHub Pages. Moving to Enhance, with old Joomla URLs handled by a generated `.htaccess`, is Part 2 and happens only if this direction is chosen.

**Tech Stack:** Hugo 0.164.0 extended (pinned), Python 3 standard library (checks), Node standard library (redirect generator, run by hand, output committed), GitHub Actions, rsync over SSH, Enhance hosting (LiteSpeed family).

**Spec:** `docs/superpowers/specs/2026-11-14-stable-static-site-design.md`. Read it before any task.

## Global Constraints

- This plan is executed in the repository `/Users/sean/Projects/spokares-static`. All paths are relative to it unless they start with `../`.
- **Leave the WordPress project alone.** `../spokane_ares` is read-only source material: never edit, commit, tag, push or deploy there, and never touch the Enhance website, its secrets or DNS. Part 2 is the only place that changes, and it is not part of the review build.
- **Part 1 (Tasks 1 to 8, 9R, 12, 13) is the review build.** Part 2 (Tasks 9, 10, 11, 14, 15) is deferred until the owner chooses this direction; do not start it.
- **The preview is served under a path prefix** (`/spokares-static/`). Never write a bare root-relative address (`/about/`, `/css/site.css`) in a template: wrap it as `{{ partial "url.html" "/about/" }}`. Markdown links in content may be written root-relative (`[About](/about/)`); the link render hook adds the prefix. In CSS, refer to fonts and images with relative paths (`../fonts/…`).
- Steps that publish or change anything outside this folder are marked **OWNER GO-AHEAD**.
- The repo is public. Never commit `research/raw/`, `research/wayback/snapshots/`, rosters, personal phone numbers, home addresses or personal e-mail addresses. Never read or print anything from `/Users/sean/Projects/spokane_ares-secrets/` into the repo or a log.
- Hugo is pinned to exactly `0.164.0`. Building the site must need nothing but that binary. No npm packages in the build.
- The only hosted documents are the ARES application and the task books. Everything else is a link.
- No link may require signing in. The one exception is a single link to `https://spokaneares-acs.groups.io/g/main`, on `/members/` only (not in the footer).
- No links to net scripts. No `ag7qp.com` links except, if needed, Section-level documents on `/resources/`.
- Leadership keeps every call sign, read from `data/facts.yaml`. No "open position" rows.
- Contact is `info@spokares.org`, stated once on About (`/about/#contact`).
- Meetings are shown as rules only. No computed or printed dates anywhere.
- Removed wording must not appear in the built site: "Schedule as of", "Last reviewed", "Soon", "being recovered", "new website", "This week", "Next up", "Later this season", "Not posted yet", "Volunteer needed", "Open position", "Net Control Schedule".
- Owner wording rules: say each fact once; plain words a volunteer would say out loud; no jargon.
- Same look as the WordPress theme. Do not redesign. Class names from `site.css` are kept unless a step says otherwise.
- The preview stays `noindex` and has no sitemap.
- Commit after each task with the trailer `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.

## File Structure

```
site/
  hugo.toml                          Hugo config (no taxonomies, no RSS, pretty URLs)
  data/facts.yaml                    the yearly-edit file
  data/resources.yaml                Resources page links
  content/_index.md                  Home prose + shortcodes
  content/how-it-works.md
  content/about.md
  content/members.md
  content/resources.md
  layouts/_default/baseof.html       page shell
  layouts/_default/single.html       ordinary page
  layouts/index.html                 Home
  layouts/404.html
  layouts/partials/head.html         meta, font preload, css
  layouts/partials/header.html       masthead + menu
  layouts/partials/footer.html
  layouts/partials/brand.html        seal lockup (header and footer variants)
  layouts/partials/fact.html         facts lookup that fails the build when a value is missing
  layouts/partials/url.html          turns /path into an address that works under any base path
  layouts/_default/_markup/render-link.html   applies url.html to Markdown links
  layouts/shortcodes/*.html          one per designed component (listed in each task)
  static/css/site.css                ported from the theme
  static/js/menu.js                  mobile menu toggle
  static/js/copy.js                  "Copy" button for the repeater settings
  static/fonts/*.woff2               three fonts + two OFL licence files
  static/img/*                       seal PNGs, hero JPG
  static/files/*.pdf                 application + task books
  static/.htaccess                   (Part 2) GENERATED: old-URL rules (+ headers if supported)
  tools/check_site.py                build-output checks (the test suite)
  tools/check_links.py               external link report
  tools/redirects/gen-htaccess.mjs   (Part 2) redirect generator
  tools/redirects/repoint.csv        (Part 2) old-target → new-page map
  .reference/                        captured WordPress HTML + screenshots (gitignored)
MAINTAINING.md                       one-page guide for the yearly editor
README.md                            what this repository is
.github/workflows/pages.yml          build, check, publish the preview to GitHub Pages
.github/workflows/site.yml           (Part 2) build, check, deploy to Enhance
```

`site/tools/check_site.py` is the test suite. Each task first adds assertions to it, watches them fail, then makes them pass.

---

### Task 1: Capture the reference render

The WordPress build is the visual and markup source. Capture it before anything is removed.

**Files:**
- Create: `site/.reference/html/{home,how-it-works,about,members,exercises,documents,404}.html`
- Create: `site/.reference/shots/*.png`

**Interfaces:**
- Produces: `site/.reference/html/<page>.html`, the rendered WordPress HTML later tasks port from; `site/.reference/shots/<page>-<width>.png`, the baseline for Task 13.

- [ ] **Step 1: Ignore the reference folder and build output**

`.gitignore` in this repository already lists `site/.reference/`, `site/public/`, `site/resources/` and `site/.hugo_build.lock`. Confirm with `cat .gitignore`.

- [ ] **Step 2: Start the local WordPress site**

Run: `../spokane_ares/wordpress/dev/start.sh 9400`
Expected: it prints `http://127.0.0.1:9400` and admin URLs. Needs Node 22+ and network access. The blueprint pins "today" to 2026-09-26, so seeded schedule content renders filled in.

- [ ] **Step 3: Save the rendered pages**

```bash
mkdir -p site/.reference/html site/.reference/shots
B=http://127.0.0.1:9400
curl -fsS "$B/"                    -o site/.reference/html/home.html
curl -fsS "$B/how-it-works/"       -o site/.reference/html/how-it-works.html
curl -fsS "$B/about/"              -o site/.reference/html/about.html
curl -fsS "$B/members/"            -o site/.reference/html/members.html
curl -fsS "$B/members/exercises/"  -o site/.reference/html/exercises.html
curl -fsS "$B/members/documents/"  -o site/.reference/html/documents.html
curl -sS  "$B/no-such-page/"       -o site/.reference/html/404.html
wc -c site/.reference/html/*.html
```

Expected: seven files, each over 5 KB.

- [ ] **Step 4: Save baseline screenshots at phone and desktop widths**

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
for p in "home:/" "how-it-works:/how-it-works/" "about:/about/" "members:/members/"; do
  name=${p%%:*}; path=${p#*:}
  for w in 390 1280; do
    "$CHROME" --headless=new --hide-scrollbars --window-size=$w,12000 \
      --screenshot="site/.reference/shots/$name-$w.png" "http://127.0.0.1:9400$path"
  done
done
ls -l site/.reference/shots
```

Expected: eight PNG files.

- [ ] **Step 5: Save the core navigation CSS that the theme relies on**

The mobile menu uses WordPress's own navigation block. Record which stylesheets and scripts the page loads, so Task 2 knows what is being replaced:

```bash
grep -o '<link[^>]*stylesheet[^>]*>' site/.reference/html/home.html
grep -o '<script[^>]*src=[^>]*>' site/.reference/html/home.html
```

Save the output to `site/.reference/assets-loaded.txt`.

- [ ] **Step 6: Stop the local site and commit**

```bash
../spokane_ares/wordpress/dev/stop.sh 9400
git -C ../spokane_ares status --short   # expected: no output; the WordPress project is unchanged
```

Nothing is committed in this task; the capture is gitignored.

---

### Task 2: Hugo scaffold, page shell and the check harness

**Files:**
- Create: `site/hugo.toml`, `site/tools/check_site.py`
- Create: `site/layouts/_default/baseof.html`, `site/layouts/_default/single.html`, `site/layouts/index.html`, `site/layouts/404.html`
- Create: `site/layouts/partials/{head,header,footer,brand,url}.html`, `site/layouts/_default/_markup/render-link.html`
- Create: `site/static/css/site.css`, `site/static/js/menu.js`, `site/static/fonts/*`, `site/static/img/*`
- Create: `site/content/{_index,how-it-works,about,members,resources}.md` (title and description only for now)

**Interfaces:**
- Produces: `hugo --source site` builds to `site/public/`. `python3 site/tools/check_site.py site/public --base /spokares-static` exits 0 when all checks pass and prints one line per failure otherwise. Blocks in `baseof.html`: `main`. Partial `brand.html` takes a dict `(dict "variant" "header")` or `"footer"`.

- [ ] **Step 1: Write the check script**

Create `site/tools/check_site.py`:

```python
#!/usr/bin/env python3
"""Checks the built site. Usage: check_site.py <public-dir> [--stage N] [--base /prefix]

--base is the path prefix the site was built for (GitHub Pages preview:
/spokares-static). Every internal address must start with it.

Standard library only. Exits 1 and prints one line per problem.
Stages let early tasks run the checks that apply so far:
  1 shell   2 facts   3 home   4 how   5 about   6 members   7 resources (all)
"""
import csv
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

PAGES = {
    "index.html": 3,
    "how-it-works/index.html": 4,
    "about/index.html": 5,
    "members/index.html": 6,
    "resources/index.html": 7,
    "404.html": 1,
}
REMOVED_PATHS = ["members/exercises", "members/documents", "docs", "search"]
FORBIDDEN = [
    "Schedule as of", "Last reviewed", "being recovered", "new website",
    "This week", "Next up", "Later this season", "Not posted yet",
    "Volunteer needed", "Open position", "Net Control Schedule",
    "needs-verify", "data-verify", "wp-block-navigation", "wp-content",
    "wp-includes",
]
FORBIDDEN_WORDS = [r"\bSoon\b", r"\bNext: "]
GROUPS_IO = "https://spokaneares-acs.groups.io/g/main"
PHONE = re.compile(r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ALLOWED_EMAILS = {"info@spokares.org"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.loads, self.text = set(), [], [], []
        self.h1 = 0
        self.title = ""
        self.lang = None
        self._in_title = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self._in_title = True
        if tag in ("script", "style"):
            self._skip += 1
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag in ("script", "img", "source", "iframe") and a.get("src"):
            self.loads.append(a["src"])
        if tag == "link" and a.get("href") and a.get("rel") in (
            "stylesheet", "preload", "icon", "modulepreload"
        ):
            self.loads.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in ("script", "style"):
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.text.append(data)


def main():
    root = Path(sys.argv[1])
    stage = 7
    if "--stage" in sys.argv:
        stage = int(sys.argv[sys.argv.index("--stage") + 1])
    base = ""
    if "--base" in sys.argv:
        base = sys.argv[sys.argv.index("--base") + 1].rstrip("/")
    problems = []
    pages = {}

    def local(path, where, what):
        """Strip the base path from an internal address; complain if it is missing."""
        if not base or not path.startswith("/"):
            return path
        if path == base or path.startswith(base + "/"):
            return path[len(base):] or "/"
        problems.append(f"{where}: {what} is not under {base}/: {path}")
        return path

    for rel, need in PAGES.items():
        f = root / rel
        if not f.is_file():
            if stage >= need:
                problems.append(f"missing page: {rel}")
            continue
        p = Page()
        p.feed(f.read_text(encoding="utf-8"))
        pages[rel] = p

    for rel in REMOVED_PATHS:
        if (root / rel).exists():
            problems.append(f"removed path is present: {rel}")

    def target_ok(path, frag):
        path = unquote(path)
        f = root / path.lstrip("/")
        if f.is_dir():
            f = f / "index.html"
        if not f.is_file():
            return False
        if not frag:
            return True
        key = str(f.relative_to(root))
        if key not in pages:
            return f.suffix != ".html"
        if stage < PAGES.get(key, 0):
            return True  # that page's sections arrive in a later task
        return frag in pages[key].ids

    groups_links = 0
    for rel, p in pages.items():
        raw = (root / rel).read_text(encoding="utf-8")
        text = " ".join(p.text)
        if p.lang != "en-US":
            problems.append(f"{rel}: <html lang> is not en-US")
        if p.h1 != 1:
            problems.append(f"{rel}: expected one h1, found {p.h1}")
        if not p.title.strip():
            problems.append(f"{rel}: empty <title>")
        for phrase in FORBIDDEN:
            if phrase.lower() in raw.lower():
                problems.append(f"{rel}: forbidden text {phrase!r}")
        for pat in FORBIDDEN_WORDS:
            if re.search(pat, text):
                problems.append(f"{rel}: forbidden wording /{pat}/")
        if PHONE.search(text):
            problems.append(f"{rel}: something that looks like a phone number")
        for e in set(EMAIL.findall(raw)) - ALLOWED_EMAILS:
            problems.append(f"{rel}: e-mail address not allowed: {e}")
        for src in p.loads:
            u = urlparse(src)
            if u.scheme or u.netloc:
                problems.append(f"{rel}: third-party load {src}")
            elif not (root / local(u.path, rel, "asset").lstrip("/")).is_file():
                problems.append(f"{rel}: missing asset {src}")
        for href in p.links:
            u = urlparse(href)
            if u.scheme in ("mailto", "tel"):
                continue
            if u.scheme or u.netloc:
                if "groups.io" in u.netloc:
                    groups_links += 1
                    if rel != "members/index.html" or href != GROUPS_IO:
                        problems.append(f"{rel}: groups.io link not allowed here: {href}")
                if "ag7qp.com" in u.netloc and rel != "resources/index.html":
                    problems.append(f"{rel}: ag7qp.com link outside Resources: {href}")
                if "/files" in u.path and "groups.io" in u.netloc:
                    problems.append(f"{rel}: link needs sign-in: {href}")
                continue
            path = local(u.path, rel, "link") if u.path else "/" + rel.replace("index.html", "")
            if not target_ok(path, u.fragment):
                problems.append(f"{rel}: broken internal link {href}")
    if stage >= 6 and groups_links != 1:
        problems.append(f"expected exactly one groups.io link, found {groups_links}")

    repoint = Path(__file__).parent / "redirects" / "repoint.csv"
    if stage >= 7 and repoint.is_file():
        for row in csv.DictReader(repoint.open(encoding="utf-8")):
            u = urlparse(row["new_target"])
            if not target_ok(u.path, u.fragment):
                problems.append(f"repoint.csv: target does not exist: {row['new_target']}")

    for line in problems:
        print(line)
    print(f"{len(problems)} problem(s)" if problems else "all checks passed")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `mkdir -p site/public && python3 site/tools/check_site.py site/public --base /spokares-static --stage 1`
Expected: `missing page: 404.html`, exit status 1.

- [ ] **Step 3: Write the Hugo config**

Create `site/hugo.toml`:

```toml
baseURL = "https://spokares.org/"
languageCode = "en-US"
title = "Spokane County ARES-ACS"
disableKinds = ["taxonomy", "term", "RSS", "sitemap", "section"]
enableRobotsTXT = false
uglyURLs = false

[markup.goldmark.renderer]
  unsafe = false

[markup.goldmark.parser.attribute]
  title = true
  block = true

[markup.tableOfContents]
  startLevel = 2
  endLevel = 2
```

Sitemap is disabled on purpose for now; Task 11 turns it on at go-live together with indexing.

- [ ] **Step 4: Copy the static assets from the theme**

```bash
T=../spokane_ares/wordpress/theme/spokares/assets
mkdir -p site/static/{css,js,fonts,img,files}
cp $T/css/site.css site/static/css/site.css
cp $T/fonts/* site/static/fonts/
cp $T/img/* site/static/img/
```

- [ ] **Step 4b: Write the address helper and the Markdown link hook**

The preview is served from `/spokares-static/` and the real site from `/`. One helper makes every internal address right for both.

Create `site/layouts/partials/url.html`:

```html
{{- return (printf "%s%s" (strings.TrimSuffix "/" site.Home.RelPermalink) .) -}}
```

It takes a root-relative address (`"/about/#contact"`) and returns it with the site's base path in front.

Create `site/layouts/_default/_markup/render-link.html`:

```html
{{- $d := .Destination -}}
{{- if strings.HasPrefix $d "/" }}{{ $d = partial "url.html" $d }}{{ end -}}
<a href="{{ $d | safeURL }}"{{ with .Title }} title="{{ . }}"{{ end }}>{{ .Text }}</a>
{{- /* no trailing newline */ -}}
```

Rule for every later task: in any layout, partial or shortcode, an internal `href`, `src` or `srcset` is written `{{ partial "url.html" "/path" }}`. The check script fails the build if one is missed.

- [ ] **Step 5: Write the head partial**

Open `site/.reference/html/home.html` and find the `<head>`. Port only: charset, viewport, `<title>`, meta description, the font preloads, the `@font-face` rules and CSS custom properties that WordPress printed from `theme.json` (the inline `<style id="global-styles-inline-css">` and the font-face style block), and the theme stylesheet link. Drop every WordPress-generated tag (`wp-block-library`, emoji, `wp-json`, oEmbed, generator, speculation rules).

Create `site/layouts/partials/head.html`:

```html
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ if .IsHome }}{{ site.Title }}{{ else }}{{ .Title }} · {{ site.Title }}{{ end }}</title>
<meta name="description" content="{{ .Description }}">
<meta name="robots" content="noindex">
<link rel="preload" href="{{ partial "url.html" "/fonts/schibsted-grotesk-roman.woff2" }}" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{{ partial "url.html" "/fonts/crimson-pro-roman.woff2" }}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{{ partial "url.html" "/css/site.css" }}">
<link rel="icon" href="{{ partial "url.html" "/img/seal-ares-acs-92.png" }}">
<script src="{{ partial "url.html" "/js/menu.js" }}" defer></script>
```

Then move the captured `@font-face` rules and the `:root` custom properties (the `--wp--preset--*` variables that `site.css` references) to the top of `site/static/css/site.css`, with font URLs rewritten to the relative form `../fonts/<file>.woff2` (relative to `css/site.css`, so they work under any base path). Do the same for any `url(…)` image reference in the stylesheet. Find which variables are needed:

```bash
grep -o 'var(--wp--[a-z0-9-]*' site/static/css/site.css | sort -u
```

Every variable in that list must be defined in the `:root` block you add. The `noindex` meta stays until go-live (Task 11).

- [ ] **Step 6: Write the brand partial**

In the reference HTML, find the element the `spokares-theme/brand` block rendered in the header (inside `.masthead__bar`) and in the footer (inside `.footer__bar`). Create `site/layouts/partials/brand.html` containing that markup verbatim, switching on `.variant`:

```html
{{- if eq .variant "header" -}}
<!-- header lockup markup copied from the reference, image paths changed to /img/... -->
{{- else -}}
<!-- footer lockup markup copied from the reference, image paths changed to /img/... -->
{{- end -}}
```

Replace each comment with the copied markup. Image `src` and `srcset` values must be written with the helper, for example `{{ partial "url.html" "/img/seal-ares-acs-92.png" }}` (also `-138.png` and `-400.png`). The lockup's link to Home is `{{ partial "url.html" "/" }}`.

- [ ] **Step 7: Write the header partial with a plain menu**

The WordPress navigation block is replaced by plain markup. Create `site/layouts/partials/header.html`:

```html
<a class="skip-link" href="#main">Skip to content</a>
<header class="masthead">
  <div class="wrap masthead__bar">
    {{ partial "brand.html" (dict "variant" "header") }}
    <div class="masthead__actions">
      <a class="btn btn--red masthead__join" href="{{ partial "url.html" "/#join" }}">Join the team</a>
    </div>
    <nav class="nav" aria-label="Primary">
      <button class="nav__toggle" type="button" aria-expanded="false" aria-controls="nav-menu">Menu</button>
      <ul class="nav__list" id="nav-menu">
        {{- $here := .RelPermalink -}}
        {{- range (slice
              (dict "label" "Home" "url" "/")
              (dict "label" "How it works" "url" "/how-it-works/")
              (dict "label" "About ARES & ACS" "url" "/about/")
              (dict "label" "Resources" "url" "/resources/")
              (dict "label" "For Members" "url" "/members/")) }}
        {{- $u := partial "url.html" .url }}
        <li><a href="{{ $u }}"{{ if eq $u $here }} aria-current="page"{{ end }}>{{ .label }}</a></li>
        {{- end }}
        <li class="nav__join"><a class="btn btn--red" href="{{ partial "url.html" "/#join" }}">Join the team</a></li>
      </ul>
    </nav>
  </div>
</header>
```

- [ ] **Step 8: Port the navigation CSS**

`site.css` has 57 selectors that target `.wp-block-navigation*`. For each rule, rewrite the selector to the new markup and keep the declarations unchanged:

| WordPress selector part | New selector |
|---|---|
| `.wp-block-navigation` (the nav element) | `.nav` |
| `.wp-block-navigation__container` | `.nav__list` |
| `.wp-block-navigation-item` | `.nav__list > li` |
| `.wp-block-navigation-item__content` | `.nav__list a` |
| `.wp-block-navigation__responsive-container-open` | `.nav__toggle` |
| `.wp-block-navigation__responsive-container.is-menu-open` | `.nav.is-open .nav__list` |
| `.wp-block-navigation__responsive-container-close` | delete the rule (the one toggle button opens and closes) |
| `.current-menu-item` | `[aria-current="page"]` |

Below 1020px the list is hidden unless `.nav.is-open`; at 1020px and above the list is always shown and `.nav__toggle` is hidden. Also rewrite `.wp-block-button__link` to `.btn` and remove the `.wp-block-button`/`.wp-block-buttons` wrappers from selectors, matching the markup in Step 7. Finish with:

```bash
grep -c 'wp-block-navigation' site/static/css/site.css
```

Expected: `0`.

- [ ] **Step 9: Write the menu script**

Create `site/static/js/menu.js`:

```js
(function () {
  var nav = document.querySelector('.nav');
  if (!nav) return;
  var button = nav.querySelector('.nav__toggle');
  var wide = window.matchMedia('(min-width: 1020px)');

  function set(open) {
    nav.classList.toggle('is-open', open);
    button.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  button.addEventListener('click', function () {
    set(!nav.classList.contains('is-open'));
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && nav.classList.contains('is-open')) {
      set(false);
      button.focus();
    }
  });
  nav.addEventListener('click', function (e) {
    if (e.target.closest('a')) set(false);
  });
  wide.addEventListener('change', function () { set(false); });
})();
```

- [ ] **Step 10: Write the footer partial**

Create `site/layouts/partials/footer.html`. The groups.io link from the WordPress footer is deliberately gone:

```html
<footer class="site-footer">
  <div class="wrap">
    <div class="footer__bar">
      {{ partial "brand.html" (dict "variant" "footer") }}
      <nav class="footer__nav" aria-label="Footer">
        <ul class="footer__links">
          <li><a href="{{ partial "url.html" "/how-it-works/" }}">How it works</a></li>
          <li><a href="{{ partial "url.html" "/about/" }}">About ARES &amp; ACS</a></li>
          <li><a href="{{ partial "url.html" "/resources/" }}">Resources</a></li>
          <li><a href="{{ partial "url.html" "/members/" }}">For Members</a></li>
          <li><a href="{{ partial "url.html" "/about/#contact" }}">Contact</a></li>
        </ul>
      </nav>
    </div>
    <div class="footer__bottom">
      <p class="footer__emergency">Volunteers, not first responders. In an emergency, call 911.</p>
      <p class="footer__copy">© Spokane County ARES-ACS</p>
    </div>
  </div>
</footer>
```

Compare the outer element and class with the reference footer and match it (the wrapper element the template part rendered), so existing footer CSS applies.

- [ ] **Step 11: Write the page shell and templates**

Create `site/layouts/_default/baseof.html`:

```html
<!doctype html>
<html lang="en-US">
<head>
{{ partial "head.html" . }}
</head>
<body class="{{ block "bodyclass" . }}page{{ end }}">
{{ partial "header.html" . }}
<main id="main">
{{ block "main" . }}{{ end }}
</main>
{{ partial "footer.html" . }}
</body>
</html>
```

Copy the `<body>` classes that `site.css` actually uses from the reference (check with `grep -o 'body\.[a-z-]*' site/static/css/site.css | sort -u`) into the `bodyclass` block defaults.

Create `site/layouts/_default/single.html`:

```html
{{ define "main" }}
{{ .Content }}
{{ end }}
```

Create `site/layouts/index.html`:

```html
{{ define "bodyclass" }}home{{ end }}
{{ define "main" }}
{{ .Content }}
{{ end }}
```

Create `site/layouts/404.html`:

```html
{{ define "main" }}
<div class="wrap">
  <h1>Page not found</h1>
  <p>That page is not here. Try <a href="{{ partial "url.html" "/" }}">Home</a>, <a href="{{ partial "url.html" "/how-it-works/" }}">How it works</a>, <a href="{{ partial "url.html" "/about/" }}">About</a>, <a href="{{ partial "url.html" "/resources/" }}">Resources</a> or <a href="{{ partial "url.html" "/members/" }}">For members</a>.</p>
</div>
{{ end }}
```

- [ ] **Step 12: Create the content stubs**

Each file gets front matter only for now. Take the description from the matching reference page's `<meta name="description">`.

`site/content/_index.md`:

```markdown
---
title: "Spokane County ARES-ACS"
description: "Volunteer radio operators who carry messages for Spokane County when normal lines go down. Visitors welcome on the Tuesday 8:00 PM net."
---
```

Create `how-it-works.md` (`title: "How it works"`), `about.md` (`title: "About ARES & ACS"`), `members.md` (`title: "For members"`, `description: "Net settings, forms and task books for Spokane County ARES-ACS members."`) and `resources.md` (`title: "Resources"`, `description: "Public sources for emergency communications training, forms, weather and licensing."`) the same way. Until its task adds real content, each stub body is a single heading line, for example `# How it works`.

- [ ] **Step 13: Build and run the checks**

```bash
hugo --source site --cleanDestinationDir --panicOnWarning --baseURL http://localhost/spokares-static/
python3 site/tools/check_site.py site/public --base /spokares-static --stage 1
```

Expected: Hugo reports 6 pages with no warnings; the check prints `all checks passed`.

- [ ] **Step 14: Look at it**

Run: `hugo server --source site --port 9401` and open `http://127.0.0.1:9401/` at phone and desktop widths. The masthead, menu (open, close, Escape, resize) and footer must match `site/.reference/shots/home-390.png` and `home-1280.png`. Stop the server.

- [ ] **Step 15: Commit**

```bash
git add site
git commit -m "Static site: Hugo scaffold, page shell, menu and build checks"
```

---

### Task 3: The facts file and the fact components

**Files:**
- Create: `site/data/facts.yaml`, `site/layouts/partials/fact.html`
- Create: `site/layouts/shortcodes/{net-settings,net-from-home,other-nets,meetings,leadership,contact}.html`
- Create: `site/static/js/copy.js`
- Create: `site/content/factcheck.md` (temporary, removed in Step 9)
- Modify: `site/tools/check_site.py`

**Interfaces:**
- Consumes: `baseof.html` from Task 2.
- Produces: `{{ partial "fact.html" "net.time" }}` returns the value at a dotted path in `facts.yaml` and stops the build with `facts.yaml: missing "net.time"` when it is absent or empty. Shortcodes, all without arguments: `{{< net-settings >}}`, `{{< net-from-home >}}`, `{{< other-nets >}}`, `{{< meetings >}}`, `{{< leadership >}}`, `{{< contact >}}`.

- [ ] **Step 1: Add the failing check**

In `check_site.py`, after the `FORBIDDEN_WORDS` line add:

```python
FACTCHECK = ["147.300", "100 Hz", "8:00 PM", "Second Saturday", "Third Thursday",
             "1121 W Gardner Ave", "W7TSC", "info@spokares.org"]
```

and at the end of `main()`, before the `for line in problems` loop:

```python
    fc = root / "factcheck" / "index.html"
    if stage == 2:
        body = fc.read_text(encoding="utf-8") if fc.is_file() else ""
        for needle in FACTCHECK:
            if needle not in body:
                problems.append(f"factcheck: {needle!r} not rendered")
    elif fc.exists():
        problems.append("factcheck page must not ship")
```

Run: `python3 site/tools/check_site.py site/public --base /spokares-static --stage 2`
Expected: eight `factcheck: ... not rendered` lines.

- [ ] **Step 2: Write the facts file**

Create `site/data/facts.yaml`. Values come from `../spokane_ares/wordpress/dev/seed/data.json` (`radio`, `nets`, `meetings`, `org`, `roles`, `sectionRoles`):

```yaml
# The facts on spokares.org that can change.
# To change one, edit the value after the colon and commit.
# Keep the quotes. Do not rename the labels on the left.

net:
  day: "Tuesday"
  time: "8:00 PM"

repeater:
  primary:
    call: "W7GBU"
    freq: "147.300 MHz"
    offset: "+600 kHz"
    tone: "100 Hz"
  alternate:
    freq: "146.880 MHz"
    offset: "-600 kHz"
    tone: "123 Hz"
  weather:
    call: "WXL86"
    freq: "162.400 MHz"

# Winlink nights: which Tuesdays of the month.
winlink_nights: "second and fourth Tuesdays"

# Meetings. "when" is the rule exactly as it should read on the site.
# Never put a date here.
meetings:
  - name: "Second Saturday Workshop"
    when: "Second Saturday of each month, 9:00 AM to noon"
    extra: "then a Winlink workshop, 12:30 to 3:30 PM"
  - name: "Third Thursday training meeting"
    when: "Third Thursday of each month, 6:00 PM"

place:
  name: "Spokane County Emergency Management"
  street: "1121 W Gardner Ave"
  city: "Spokane, WA 99260"

# Leadership. One line per position. Remove a line when a position is empty;
# do not write "open" or "vacant".
leadership:
  unit:
    - role: "Emergency Coordinator"
      callsign: "W7TSC"
    - role: "Assistant Emergency Coordinator, Public Events; Winlink coordinator"
      callsign: "NV2Z"
    - role: "Assistant Emergency Coordinator, Hospital Coordinator"
      callsign: "K7MHG"
    - role: "Assistant Emergency Coordinator, Logistics and Communications; W7GBU license trustee"
      callsign: "K7DSR"
    - role: "Assistant Emergency Coordinator, Net Manager"
      callsign: "AG7QP"
    - role: "SKYWARN representatives"
      callsign: "AA7RT, W7UWC"
  section:
    - role: "ARRL Section Manager"
      callsign: "KA7LJQ"
    - role: "Section Emergency Coordinator"
      callsign: "AG7QP"
    - role: "ARES District 9 Emergency Coordinator"
      callsign: "WA7EC"

contact:
  email: "info@spokares.org"

groupsio: "https://spokaneares-acs.groups.io/g/main"
```

Compare the role wording with the leadership table in `site/.reference/html/about.html` and use the wording shown there if it differs. The staff meeting, the simplex net, the GMRS net and the Public Information Officer row are left out on purpose (spec, content rules 1, 3, 4).

- [ ] **Step 3: Write the fact lookup**

Create `site/layouts/partials/fact.html`:

```html
{{- $v := site.Data.facts -}}
{{- range split . "." -}}
  {{- if not (reflect.IsMap $v) -}}{{- errorf "facts.yaml: missing %q" $ -}}{{- end -}}
  {{- $v = index $v . -}}
{{- end -}}
{{- if not $v -}}{{- errorf "facts.yaml: missing %q" $ -}}{{- end -}}
{{- return $v -}}
```

- [ ] **Step 4: Write the net components**

For each of these, find the matching element in the reference HTML and copy its markup, replacing each literal value with a fact lookup. The source element for each:

| Shortcode | Reference file | Element to copy |
|---|---|---|
| `net-settings.html` | `how-it-works.html` | the settings box in the `#weekly-net` section (output of the `spokares/net` block, view `settings`), including the Copy button |
| `net-from-home.html` | `home.html` | the "From home" card in `#visit` (view `from-home`) |
| `other-nets.html` | `how-it-works.html` | the "Other nets" list (view `other-nets`), keeping only the Winlink nights item and removing the link to `#winlink-assignments` |

Lookups to use, for example in `net-settings.html`:

```html
{{- $p := partial "fact.html" "repeater.primary" -}}
{{- $a := partial "fact.html" "repeater.alternate" -}}
{{- $copy := printf "%s %s, %s offset, %s tone" $p.call $p.freq $p.offset $p.tone -}}
<!-- copied settings-box markup; literal values replaced like this: -->
<!-- Every {{ partial "fact.html" "net.day" }}, {{ partial "fact.html" "net.time" }} -->
<!-- {{ $p.call }} {{ $p.freq }} {{ $p.offset }} {{ $p.tone }} -->
<!-- Alternate: {{ $a.freq }} {{ $a.offset }} {{ $a.tone }} -->
<!-- <button type="button" class="..." data-copy="{{ $copy }}">Copy</button> -->
```

Replace the comments with the real copied markup. Keep every class name. Remove any `needs-verify` class and any "Edit this list in…" admin link.

- [ ] **Step 5: Write the copy script**

Open `../spokane_ares/wordpress/plugins/spokares-core/assets/js/copy.js` and copy it to `site/static/js/copy.js`, changing it from an ES module to a plain deferred script if it uses `export`/`import`, and keeping the same `data-` attribute the settings box uses. Add to `head.html` after the menu script:

```html
<script src="{{ partial "url.html" "/js/copy.js" }}" defer></script>
```

- [ ] **Step 6: Write the meetings, leadership and contact components**

`site/layouts/shortcodes/meetings.html` (copy the wrapper markup and classes from the "In person" card in `#visit` of `home.html`; there is no "Next:" line):

```html
{{- $place := partial "fact.html" "place" -}}
<!-- wrapper element and heading copied from the reference -->
<p>{{ $place.name }}, {{ $place.street }}</p>
<ul>
  {{- range partial "fact.html" "meetings" }}
  <li><strong>{{ .name }}:</strong> {{ .when }}{{ with .extra }}; {{ . }}{{ end }}.</li>
  {{- end }}
</ul>
<p>Changes are announced on the Tuesday net.</p>
```

`site/layouts/shortcodes/leadership.html` (copy table markup and classes, including the `data-label` attributes on cells, from the two tables in `#leadership` of `about.html`):

```html
{{- $l := partial "fact.html" "leadership" -}}
<table class="copied-classes">
  <thead><tr><th scope="col">Position</th><th scope="col">Call sign</th></tr></thead>
  <tbody>
    {{- range $l.unit }}
    <tr><td data-label="Position">{{ .role }}</td><td data-label="Call sign"><b>{{ .callsign }}</b></td></tr>
    {{- end }}
  </tbody>
</table>
<table class="copied-classes">
  <thead><tr><th scope="col">Position</th><th scope="col">Call sign</th></tr></thead>
  <tbody>
    {{- range $l.section }}
    <tr><td data-label="Position">{{ .role }}</td><td data-label="Call sign"><b>{{ .callsign }}</b></td></tr>
    {{- end }}
  </tbody>
</table>
```

Use the column headings and captions the reference tables use.

`site/layouts/shortcodes/contact.html`:

```html
{{- $e := partial "fact.html" "contact.email" -}}
<p>Write to <a href="mailto:{{ $e }}">{{ $e }}</a>.</p>
```

- [ ] **Step 7: Render them on a temporary page and run the checks**

Create `site/content/factcheck.md`:

```markdown
---
title: "Fact check"
description: "Temporary."
---
# Fact check

{{< net-settings >}}
{{< net-from-home >}}
{{< other-nets >}}
{{< meetings >}}
{{< leadership >}}
{{< contact >}}
```

```bash
hugo --source site --cleanDestinationDir --panicOnWarning --baseURL http://localhost/spokares-static/
python3 site/tools/check_site.py site/public --base /spokares-static --stage 2
```

Expected: `all checks passed`.

- [ ] **Step 8: Prove a missing fact stops the build**

Temporarily delete the `time:` line under `net:` in `facts.yaml`, then run `hugo --source site`.
Expected: the build fails with `facts.yaml: missing "net.time"`. Restore the line and rebuild to confirm it passes.

- [ ] **Step 9: Remove the temporary page and commit**

```bash
rm site/content/factcheck.md
hugo --source site --cleanDestinationDir --panicOnWarning --baseURL http://localhost/spokares-static/
python3 site/tools/check_site.py site/public --base /spokares-static --stage 1
git add site
git commit -m "Static site: facts file and the components that read it"
```

Expected: `all checks passed`.

---

### How to port a page (applies to Tasks 4 to 7)

The reference HTML is WordPress block output. Convert it with these rules, in this order:

1. **Work section by section.** Each top-level `<section>` or group inside `<main>` in the reference becomes either Markdown in the content file or one shortcode.
2. **Plain prose becomes Markdown:** a section whose content is only headings, paragraphs, simple lists and links, inside a standard wrapper. Headings keep their ids with `## Title {#id}`.
3. **Designed sections become shortcodes** named `<page>-<section>.html` (for example `home-hero.html`): anything with cards, grids, steps, tables with `data-label`, figures or SVG. Copy the markup verbatim into the shortcode.
4. **A section that is prose inside a designed wrapper** becomes a paired shortcode: `{{< section id="nets" class="copied classes" >}} …Markdown… {{< /section >}}`. Create `site/layouts/shortcodes/section.html` once:

   ```html
   <section{{ with .Get "id" }} id="{{ . }}"{{ end }} class="{{ .Get "class" }}"><div class="wrap">{{ .Inner | .Page.RenderString (dict "display" "block") }}</div></section>
   ```

   Match the inner wrapper to the reference.
5. **Strip WordPress leftovers** from copied markup: `<!-- wp:… -->` comments, the classes `wp-block-group`, `wp-block-heading`, `wp-block-list`, `wp-block-columns`, `wp-block-column`, `wp-block-table`, `has-*-color`, `has-*-font-size`, `is-layout-*`, `wp-container-*`, `wp-elements-*`, and any `needs-verify` class. Before deleting a class, check it is not used by `site.css`: `grep -c '\.CLASSNAME' site/static/css/site.css`. If it is used, keep it.
6. **Keep** every other class, every `id`, every `aria-*` attribute, `data-label`, and the external-link labels the theme's render filters added.
7. **Replace facts with components.** Wherever the reference shows the net time, repeater settings, meeting lines, place, leadership or contact, use the Task 3 shortcode instead of text.
8. **Image paths** become `{{ partial "url.html" "/img/<file>" }}`. The hero uses `/img/1920x1200sunset.jpg`, written the same way. Every internal `href` copied from the reference is wrapped with the helper too.
9. **Internal links** that pointed at removed pages are re-pointed as each task says.
10. After each page: build, run the stage check, then compare with the reference screenshots at 390 and 1280 wide.

---

### Task 4: Home

**Files:**
- Modify: `site/content/_index.md`
- Create: `site/layouts/shortcodes/{section,home-hero,home-what-we-do,home-visit,home-join}.html`

**Interfaces:**
- Consumes: `net-from-home`, `meetings` shortcodes; the porting rules above.
- Produces: anchors `#what-we-do`, `#visit`, `#join` on `/` (other pages and the redirect map link to them).

- [ ] **Step 1: Run the failing check**

Run: `python3 site/tools/check_site.py site/public --base /spokares-static --stage 3`
Expected: FAIL with `broken internal link /#join` on every page (the header's "Join the team" button).

- [ ] **Step 2: Port the four sections**

From `site/.reference/html/home.html`, following the porting rules:

| Section | Becomes | Changes from the reference |
|---|---|---|
| Hero (`home-hero.php`) | `home-hero.html` | none |
| What we do (`#what-we-do`) | `home-what-we-do.html` | none |
| Visit (`#visit`) | `home-visit.html`, a paired shortcode holding the section wrapper; `{{< net-from-home >}}` and `{{< meetings >}}` go between its tags in `_index.md` | no "Next:" dates; no staff meeting line |
| Join (`#join`) | `home-join.html` | the step that says to join groups.io links to `/members/` (the single groups.io link lives there); wording becomes "then ask to join the members' group, linked from For members" |

For the paired `home-visit.html`:

```html
<section id="visit" class="copied classes"><div class="wrap">
  <!-- heading and intro copied from the reference -->
  <div class="copied grid classes">{{ .Inner }}</div>
</div></section>
```

- [ ] **Step 3: Write the content file**

`site/content/_index.md`:

```markdown
---
title: "Spokane County ARES-ACS"
description: "Volunteer radio operators who carry messages for Spokane County when normal lines go down. Visitors welcome on the Tuesday 8:00 PM net."
---
{{< home-hero >}}
{{< home-what-we-do >}}
{{< home-visit >}}
{{< net-from-home >}}
{{< meetings >}}
{{< /home-visit >}}
{{< home-join >}}
```

The `h1` is inside `home-hero.html`, as in the reference.

- [ ] **Step 4: Build and check**

```bash
hugo --source site --cleanDestinationDir --panicOnWarning --baseURL http://localhost/spokares-static/
python3 site/tools/check_site.py site/public --base /spokares-static --stage 3
```

Expected: `all checks passed`.

- [ ] **Step 5: Compare with the reference**

Run `hugo server --source site --port 9401`, open `/` at 390 and 1280 wide beside `site/.reference/shots/home-390.png` and `home-1280.png`. The only differences allowed: no "Next:" dates, no staff meeting line, the join step's wording, and "Resources" in the menu.

- [ ] **Step 6: Commit**

```bash
git add site
git commit -m "Static site: Home"
```

---

### Task 5: How it works

**Files:**
- Modify: `site/content/how-it-works.md`
- Create: `site/layouts/partials/message-path.html`, `site/layouts/shortcodes/{how-opener,how-activation-steps,how-readiness,how-messages,how-exercises,how-roles}.html`

**Interfaces:**
- Consumes: `net-settings`, `other-nets`, `section` shortcodes.
- Produces: anchors `#nets`, `#weekly-net`, `#alert-levels` on `/how-it-works/`, plus every section id in the reference.

- [ ] **Step 1: Run the failing check**

Run: `python3 site/tools/check_site.py site/public --base /spokares-static --stage 4`
Expected: FAIL if Home already links to a section of this page (`broken internal link /how-it-works/#…`). If Home has no such link the check passes at this point; the anchors are then proved by Task 10 Step 1, and Step 5 below is this task's test.

- [ ] **Step 2: Port the sections**

From `site/.reference/html/how-it-works.html`:

| Section | Becomes | Changes from the reference |
|---|---|---|
| Opener with the message-path drawing | `how-opener.html`; the inline SVG goes in `partials/message-path.html` | none |
| Weekly net (`#nets`, `#weekly-net`) | Markdown in a `section`, with `{{< net-settings >}}` and `{{< other-nets >}}` | Other nets shows Winlink nights only |
| Activation (7 steps), "It has happened for real" | `how-activation-steps.html` + Markdown | remove the link to the Section standing order unless a public non-ag7qp source exists; if kept, it moves to Resources |
| Readiness levels (`#alert-levels`) | `how-readiness.html`, weather radio values from `repeater.weather` | none |
| How a message moves | `how-messages.html` | links to `/members/documents/#…` become links to `/resources/#forms` |
| Training and exercises | `how-exercises.html` | "Dates: Exercises & events" becomes "Members get dates through the members' group; see [For members](/members/)." |
| Roles table | `how-roles.html` | the public-event row links to `/members/#public-service` |

- [ ] **Step 3: Write the content file**

`site/content/how-it-works.md` is the front matter, `{{< how-opener >}}` (which contains the `h1`), then the sections in reference order using the shortcodes above and Markdown inside `{{< section >}}` pairs. Keep the reference's heading text and ids exactly.

- [ ] **Step 4: Build and check**

```bash
hugo --source site --cleanDestinationDir --panicOnWarning --baseURL http://localhost/spokares-static/
python3 site/tools/check_site.py site/public --base /spokares-static --stage 4
```

Expected: `all checks passed`. (Links into `/members/` and `/resources/` sections are checked once those pages are built.)

- [ ] **Step 5: Compare with the reference**

Compare `/how-it-works/` with `how-it-works-390.png` and `how-it-works-1280.png`. Allowed differences: the changes listed in Step 2.

- [ ] **Step 6: Commit**

```bash
git add site
git commit -m "Static site: How it works"
```

---

### Task 6: About

**Files:**
- Modify: `site/content/about.md`
- Create: `site/layouts/about.html`, `site/layouts/shortcodes/{about-chains,about-legal-basis,about-agreements,about-ares-path,about-acs-path,about-training,about-timeline}.html`

**Interfaces:**
- Consumes: `leadership`, `contact`, `section` shortcodes.
- Produces: anchors `#leadership`, `#history`, `#w7gbu`, `#who-we-serve`, `#agreements`, `#membership`, `#ares-path`, `#licensing`, `#contact` on `/about/`.

- [ ] **Step 1: Run the failing check**

Run: `python3 site/tools/check_site.py site/public --base /spokares-static --stage 5`
Expected: FAIL with `broken internal link /about/#contact` (from the footer).

- [ ] **Step 2: Write the About layout with a built table of contents**

Chapter headings are Markdown `## Title {#id}` lines in `about.md`, so Hugo can list them. Create `site/layouts/about.html` (and set `layout: about` in the page's front matter):

```html
{{ define "main" }}
<div class="copied about wrapper classes">
  <header class="copied about-head classes"><div class="wrap"><h1>{{ .Title }}</h1></div></header>
  <nav class="toc" aria-label="On this page">
    <ol>
      {{- range .Fragments.Headings }}{{ range .Headings }}
      <li><a href="#{{ .ID }}">{{ .Title }}</a></li>
      {{- end }}{{ end }}
    </ol>
  </nav>
  <div class="copied about-body classes">
    {{ .Content }}
  </div>
</div>
{{ end }}
```

Copy the wrapper elements and the `toc` markup from the reference so the existing CSS applies. If the heading list comes out empty, the Markdown starts at `##` with no `#`; in that case range `.Fragments.Headings` directly. There is no "Last reviewed" line.

- [ ] **Step 3: Port the chapters**

From `site/.reference/html/about.html`. Prose chapters are Markdown; tables and diagrams are shortcodes.

| Chapter | Changes from the reference |
|---|---|
| ARES / ACS / RACES definitions | none |
| Legal basis table (`about-legal-basis.html`) | none |
| Who we serve; Agreements (`about-agreements.html`) | none |
| Leadership: two-chains diagram (`about-chains.html`), then `{{< leadership >}}` | the hand-written tables are replaced by the component; no Public Information Officer row |
| Joining; ARES path (`about-ares-path.html`) | the application is linked as `/files/…` (Task 7 adds the file); the version date appears once, beside the link |
| ACS path (`about-acs-path.html`) | orientation line reads "Orientation is held regularly; ask at a meeting or on the net for the next date." |
| Training and task books (`about-training.html`) | task book links point at `/files/…`; no version date in headings |
| Getting licensed | the exam sessions table and fees are removed; one sentence: "Exam sessions and study help are listed on [Resources](/resources/#licensing)." |
| History and W7GBU; timeline (`about-timeline.html`) | the 2026 line reads "2026: This website is rebuilt." |
| Contact (`#contact`) | existing text about coming to a meeting or the net, then `{{< contact >}}`; the groups.io sentence is removed; agencies are still pointed to Spokane County Emergency Management |

Links to `ag7qp.com` are removed from this page. Links to `/members/documents/#…` become `/files/…` (application, task books) or `/resources/#…`.

- [ ] **Step 4: Build and check**

```bash
hugo --source site --cleanDestinationDir --panicOnWarning --baseURL http://localhost/spokares-static/
python3 site/tools/check_site.py site/public --base /spokares-static --stage 5
```

Expected: the only lines left are `broken internal link /files/…` for the three PDFs, which Task 7 adds.

- [ ] **Step 5: Compare with the reference and commit**

Compare `/about/` with `about-390.png` and `about-1280.png`; allowed differences are the Step 3 changes. Check the table of contents links jump to each chapter.

```bash
git add site
git commit -m "Static site: About"
```

---

### Task 7: For members and the hosted files

**Files:**
- Modify: `site/content/members.md`
- Create: `site/static/files/ares-application.pdf`, `site/static/files/acs-task-book.pdf`, `site/static/files/arrl-ares-task-book.pdf`
- Create: `site/layouts/shortcodes/{hosted-files,members-link}.html`
- Modify: `site/data/facts.yaml`

**Interfaces:**
- Consumes: `net-settings`, `section` shortcodes.
- Produces: anchors `#forms`, `#bring`, `#public-service` on `/members/`. `facts.yaml` key `files`: list of `{title, file, version, note}`.

- [ ] **Step 1: Run the failing check**

Run: `python3 site/tools/check_site.py site/public --base /spokares-static --stage 6`
Expected: FAIL, including `expected exactly one groups.io link, found 0`.

- [ ] **Step 2: Get the three files**

Find the sources in the seed data:

```bash
python3 -I -c "
import json
d=json.load(open('../spokane_ares/wordpress/dev/seed/data.json'))
for x in d['documents']:
    t=(x.get('title') or '').lower()
    if 'application' in t or 'task book' in t or 'taskbook' in t: print(x.get('title'),'|',x.get('href'),'|',x.get('version') or x.get('date'))
"
```

Download each PDF into `site/static/files/` under the names above, in its own step, into a clean folder. Then check each one before committing:

```bash
for f in site/static/files/*.pdf; do
  echo "== $f"; file "$f"
  pdftotext "$f" - | grep -n -E '\(?[0-9]{3}\)?[-. ][0-9]{3}[-. ][0-9]{4}|@' | head -20
done
```

Expected: `PDF document` for each. Any phone number or e-mail address the grep finds must be an office or role contact printed on a public form. If a file contains a private person's contact details, stop and ask the owner. If the application's current version is unclear (two versions exist: 2024-09-15 and 2024-11-07), use 2024-11-07 and list it as an open item in the final report.

- [ ] **Step 3: Add the files to the facts file**

Append to `site/data/facts.yaml`:

```yaml
# Files kept on the site. To replace one, upload the new file with the
# same name to site/static/files/ and change the version here.
files:
  - title: "Spokane County ARES membership application"
    file: "ares-application.pdf"
    version: "November 7, 2024"
  - title: "ACS Position Task Book"
    file: "acs-task-book.pdf"
    version: "August 9, 2024"
  - title: "ARRL ARES Task Book"
    file: "arrl-ares-task-book.pdf"
    version: "July 2024"
```

- [ ] **Step 4: Write the components**

`site/layouts/shortcodes/hosted-files.html`:

```html
<ul class="copied doc-list classes">
  {{- range partial "fact.html" "files" }}
  <li><a href="{{ partial "url.html" (printf "/files/%s" .file) }}">{{ .title }}</a> <span class="copied meta class">PDF, {{ .version }}</span></li>
  {{- end }}
</ul>
```

Take the list and meta classes from a document row in `site/.reference/html/documents.html`.

`site/layouts/shortcodes/members-link.html`:

```html
<p><a href="{{ partial "fact.html" "groupsio" }}">Spokane ARES-ACS on groups.io</a> is where members get the schedule, exercise dates and sign-ups. You need to ask to join.</p>
```

- [ ] **Step 5: Write the page**

`site/content/members.md`:

```markdown
---
title: "For members"
description: "Net settings, forms and task books for Spokane County ARES-ACS members."
---
{{< section class="copied page-head classes" >}}
# For members
{{< /section >}}

{{< section id="net" class="copied classes" >}}
## The Tuesday net {#net-heading}

{{< net-settings >}}

Members take turns as net control.
{{< /section >}}

{{< section id="schedule" class="copied classes" >}}
## Schedule and dates {#schedule-heading}

{{< members-link >}}
{{< /section >}}

{{< section id="forms" class="copied classes" >}}
## Application and task books {#forms-heading}

{{< hosted-files >}}

Other forms, such as the ICS message forms, are on [Resources](/resources/#forms).
{{< /section >}}

{{< section id="bring" class="copied classes" >}}
## At an exercise {#bring-heading}

(the "Bring to every exercise" and "After any exercise" lines, copied word for word from site/.reference/html/exercises.html)
{{< /section >}}

{{< section id="public-service" class="copied classes" >}}
## Public-service events {#public-service-heading}

We staff the same community events most years:

- Bloomsday
- The Lilac Festival Torchlight Parade
- Climb for the Cure
- Fun runs and bike races, as organisers ask

Sign-ups go out through the members' group.
{{< /section >}}
```

Replace the parenthesised line with the two lines of text from the reference. Take section and page-head classes from `site/.reference/html/members.html`. The repeater settings were already said on How it works; they are repeated here on purpose because the reference members page did so for operators on the air. If the owner's "say each fact once" rule is to win, replace `{{< net-settings >}}` with a link to `/how-it-works/#weekly-net`; note the choice in the final report.

- [ ] **Step 6: Build and check**

```bash
hugo --source site --cleanDestinationDir --panicOnWarning --baseURL http://localhost/spokares-static/
python3 site/tools/check_site.py site/public --base /spokares-static --stage 6
```

Expected: `all checks passed`.

- [ ] **Step 7: Commit**

```bash
git add site
git commit -m "Static site: For members page with the application and task books"
```

---

### Task 8: Resources and the link checker

**Files:**
- Create: `site/data/resources.yaml`, `site/layouts/shortcodes/resources-list.html`, `site/tools/check_links.py`
- Modify: `site/content/resources.md`

**Interfaces:**
- Produces: anchors `#training`, `#forms`, `#weather`, `#county`, `#licensing`, `#section` on `/resources/`. `python3 site/tools/check_links.py site/public` prints one line per external link with its result and exits 0 unless `--strict` is given.

- [ ] **Step 1: Run the failing check**

Run: `python3 site/tools/check_site.py site/public --base /spokares-static`
Expected: FAIL with `broken internal link /resources/#forms` and similar.

- [ ] **Step 2: Write the link checker**

Create `site/tools/check_links.py`:

```python
#!/usr/bin/env python3
"""Reports on every external link in the built site.

Usage: check_links.py <public-dir> [--strict]
Flags links that fail, and links that lead to a sign-in page.
Standard library only. Exits 0 unless --strict and a problem was found.
"""
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HREF = re.compile(r'href="(https?://[^"#]+)')
LOGIN = re.compile(r"/(login|signin|sign-in|auth|sso)\b|accounts\.google\.com", re.I)
ALLOWED_SIGN_IN = {"https://spokaneares-acs.groups.io/g/main"}
UA = "Mozilla/5.0 (link check)"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, url
    except Exception as e:  # DNS, TLS, timeout
        return 0, f"{type(e).__name__}: {e}"


def main():
    root = Path(sys.argv[1])
    strict = "--strict" in sys.argv
    found = {}
    for f in root.rglob("*.html"):
        for url in HREF.findall(f.read_text(encoding="utf-8")):
            found.setdefault(url, str(f.relative_to(root)))
    bad = 0
    for url, page in sorted(found.items()):
        status, final = fetch(url)
        if url in ALLOWED_SIGN_IN:
            verdict = "ok (members' group)"
        elif status == 0 or status >= 400:
            verdict, bad = f"FAIL {status}", bad + 1
        elif LOGIN.search(final):
            verdict, bad = "SIGN-IN", bad + 1
        elif url.startswith("http://"):
            verdict = "ok (not https)"
        else:
            verdict = "ok"
        print(f"{verdict:22} {url}  [{page}]" + (f" -> {final}" if final != url else ""))
    print(f"{len(found)} links, {bad} problem(s)")
    sys.exit(1 if strict and bad else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write the resources data**

Create `site/data/resources.yaml`. Start from the non-hosted, public entries in `../spokane_ares/wordpress/dev/seed/data.json` (`documents` and `links`) and the exam links in `about-licensing.php`. Every address must be the organisation's own page. Leave out anything on groups.io, anything on ag7qp.com that is Spokane's own content, every net script, and every "Soon" entry.

```yaml
# Links on the Resources page. Each needs a title, an address and one line
# saying what it is. Only link to pages anyone can open without signing in.
groups:
  - id: "training"
    title: "Training"
    links:
      - title: "ARRL Amateur Radio Emergency Service"
        url: "https://www.arrl.org/ares"
        note: "What ARES is and how it is organised nationally."
      - title: "FEMA Independent Study courses"
        url: "https://training.fema.gov/is/"
        note: "Free online courses, including IS-100, IS-200, IS-700 and IS-800."
      - title: "ARRL Simulated Emergency Test"
        url: "https://www.arrl.org/simulated-emergency-test"
        note: "The national exercise held each fall."
  - id: "forms"
    title: "Forms"
    links:
      - title: "FEMA ICS forms"
        url: "https://training.fema.gov/icsresource/icsforms.aspx"
        note: "The message form (ICS 213), activity log (ICS 214) and communications log (ICS 309)."
  - id: "weather"
    title: "Weather"
    links:
      - title: "National Weather Service Spokane"
        url: "https://www.weather.gov/otx/"
        note: "Forecasts, warnings and SKYWARN spotter training."
  - id: "county"
    title: "Spokane County"
    links:
      - title: "Alert Spokane"
        url: "https://www.spokanecounty.gov/3007/Alert-Spokane"
        note: "Sign up for the county's emergency alerts."
      - title: "Volunteer Emergency Worker application"
        url: "https://www.spokanecounty.gov/FormCenter/Emergency-Management-31/Volunteer-Emergency-Worker-Application-276"
        note: "The county form for ACS volunteers."
  - id: "licensing"
    title: "Getting licensed"
    links:
      - title: "HamStudy"
        url: "https://hamstudy.org/"
        note: "Free study tools, and a finder for exam sessions near you."
      - title: "ARRL exam session search"
        url: "https://www.arrl.org/find-an-amateur-radio-license-exam-session"
        note: "In-person and online exam sessions."
  - id: "section"
    title: "ARRL Eastern Washington Section"
    links:
      - title: "Eastern Washington Section"
        url: "https://www.arrl.org/sections/view/eastern-washington"
        note: "Section officials and news."
```

Add the remaining public entries from the seed data under the fitting group. Use the exact addresses in the seed data in preference to the ones above where they differ.

- [ ] **Step 4: Write the component and the page**

`site/layouts/shortcodes/resources-list.html`:

```html
{{- range site.Data.resources.groups }}
<section id="{{ .id }}" class="copied section classes"><div class="wrap">
  <h2>{{ .title }}</h2>
  <ul class="copied doc-list classes">
    {{- range .links }}
    <li><a href="{{ .url }}">{{ .title }}</a> <span class="copied meta class">{{ .note }}</span></li>
    {{- end }}
  </ul>
</div></section>
{{- end }}
```

Use the same list and meta classes as `hosted-files.html`.

`site/content/resources.md`:

```markdown
---
title: "Resources"
description: "Public sources for emergency communications training, forms, weather and licensing."
---
{{< section class="copied page-head classes" >}}
# Resources

Each link goes to the organisation that keeps it current.
{{< /section >}}

{{< resources-list >}}
```

- [ ] **Step 5: Build, check and test every link**

```bash
hugo --source site --cleanDestinationDir --panicOnWarning --baseURL http://localhost/spokares-static/
python3 site/tools/check_site.py site/public --base /spokares-static
python3 site/tools/check_links.py site/public --strict
```

Expected: `all checks passed`; the link report shows no `FAIL` and no `SIGN-IN`. Fix or remove any link that fails. Some government sites refuse automated requests with 403; open those by hand in a private browser window, and if the page loads without signing in, keep the link and note it in the final report.

- [ ] **Step 6: Commit**

```bash
git add site
git commit -m "Static site: Resources page and the external link report"
```

---

### Task 9R: Publish the preview on GitHub Pages

**OWNER GO-AHEAD required for Steps 3 and 4** (creates a public repository and a public preview address).

**Files:**
- Create: `.github/workflows/pages.yml`, `README.md`

**Interfaces:**
- Consumes: the built site and `check_site.py` from Tasks 2 to 8.
- Produces: the preview at `https://<account>.github.io/spokares-static/`, rebuilt on every push to `main`.

- [ ] **Step 1: Get the Hugo checksum**

```bash
curl -fsSL https://github.com/gohugoio/hugo/releases/download/v0.164.0/hugo_0.164.0_checksums.txt | grep 'hugo_extended_0.164.0_linux-amd64.tar.gz'
```

Copy the 64-character hash for `HUGO_SHA256` below.

- [ ] **Step 2: Write the workflow and the README**

Create `.github/workflows/pages.yml`, replacing `PASTE_HASH_HERE`:

```yaml
# Build the site with a pinned Hugo, check it, and publish the review
# preview to GitHub Pages. Runs on every commit to main.
name: Preview

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

env:
  HUGO_VERSION: 0.164.0
  HUGO_SHA256: PASTE_HASH_HERE

jobs:
  build:
    name: Build and check
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - id: pages
        uses: actions/configure-pages@v5
      - name: Install Hugo (pinned, checksum verified)
        run: |
          f=hugo_extended_${HUGO_VERSION}_linux-amd64.tar.gz
          curl -fsSL -o "$RUNNER_TEMP/$f" "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/$f"
          echo "$HUGO_SHA256  $RUNNER_TEMP/$f" | sha256sum --check
          mkdir -p "$RUNNER_TEMP/hugo" && tar -xzf "$RUNNER_TEMP/$f" -C "$RUNNER_TEMP/hugo" hugo
          echo "$RUNNER_TEMP/hugo" >> "$GITHUB_PATH"
      - name: Build
        env:
          BASE_URL: ${{ steps.pages.outputs.base_url }}
        run: hugo --source site --cleanDestinationDir --panicOnWarning --baseURL "$BASE_URL/"
      - name: Check the built site
        env:
          BASE_PATH: ${{ steps.pages.outputs.base_path }}
        run: python3 site/tools/check_site.py site/public --base "$BASE_PATH"
      - name: Report on outside links (does not block)
        continue-on-error: true
        run: python3 site/tools/check_links.py site/public
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site/public

  deploy:
    name: Publish the preview
    needs: build
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

Pin each `uses:` to a commit hash (look one up with `gh api repos/actions/checkout/git/ref/tags/v4 --jq .object.sha`, and likewise for `configure-pages`, `upload-pages-artifact` and `deploy-pages`).

Create `README.md`:

```markdown
# spokares-static

A review preview of a static version of spokares.org (Spokane County
ARES-ACS): the same design as the WordPress build, limited to content that
changes about once a year. It has not been chosen as the direction yet.

- Preview: published by GitHub Pages from `main` (see the repository's
  "Deployments").
- To change content: [MAINTAINING.md](MAINTAINING.md).
- Design decisions: `docs/superpowers/specs/2026-11-14-stable-static-site-design.md`.

Built with Hugo 0.164.0. Preview locally with `hugo server --source site`.
```

- [ ] **Step 3: Create the repository and turn on Pages**

Confirm with the owner whether the repository is public (GitHub Pages on a free account needs a public repository; the preview address is public either way). Then:

```bash
gh repo create spokares-static --public --source . --remote origin \
  --description "Review preview: static version of spokares.org"
gh api -X POST "repos/{owner}/spokares-static/pages" -f build_type=workflow
```

- [ ] **Step 4: Publish and check**

```bash
git add .github/workflows/pages.yml README.md
git commit -m "Publish the review preview with GitHub Pages"
git push -u origin main
gh run watch
```

Expected: both jobs succeed. Then:

```bash
P=$(gh api "repos/{owner}/spokares-static/pages" --jq .html_url)
for p in "" how-it-works/ about/ members/ resources/ files/ares-application.pdf css/site.css; do
  printf '%s %s\n' "$(curl -s -o /dev/null -w '%{http_code}' "$P$p")" "$p"
done
curl -s "$P" | grep -c 'name="robots" content="noindex"'
```

Expected: `200` on every line, then `1`. Open the preview in a browser at phone and desktop widths and click through the menu on every page.

---

## Part 2: only if this direction is chosen

**Do not start any task below during the review.** These tasks move the site to Enhance and retire the WordPress build. They were written before the work moved to its own repository, so before starting them: decide where the code finally lives, re-read each task against that, and get the owner's go-ahead. In particular Task 14 changes the `spokane_ares` repository, and paths such as `research/redirects.csv` refer to that repository.

---

### Task 9: Find out what the web server supports

**OWNER GO-AHEAD required for Steps 1 and 2** (creates a website on the hosting account and uploads test files).

**Files:**
- Create: `site/tools/probe/.htaccess`, `site/tools/probe/a.html`, `site/tools/probe/404.html`
- Create: `docs/superpowers/specs/2026-11-14-server-probe-result.md`

**Interfaces:**
- Produces: a recorded answer to four questions that Task 10 depends on: do `RewriteRule` redirects work (`REWRITE`), does the `QSD` flag work (`QSD`), does `Header set` work (`HEADERS`), does `ErrorDocument` work (`ERRORDOC`). Also the new site's preview address, SSH user and web root path (kept in the secrets folder, not the repo).

- [ ] **Step 1: Create a plain website on Enhance**

Use the `ss:enhance-api` skill. Create a new website under the owner's organisation with no application installed, on a preview or staging domain (not `spokares.org`). Record its preview address, SSH user and web root in `/Users/sean/Projects/spokane_ares-secrets/` and nowhere else. Add the existing deploy public key to its SSH access.

- [ ] **Step 2: Upload the probe**

`site/tools/probe/.htaccess`:

```apache
RewriteEngine On
RewriteRule ^probe-moved$ /a.html [R=301,L]
RewriteCond %{QUERY_STRING} (^|&)x=1(&|$)
RewriteRule ^probe-query$ /a.html [R=301,L,QSD]
RewriteRule ^probe-gone$ - [G]
<IfModule mod_headers.c>
Header set X-Probe "1"
</IfModule>
Header always set X-Probe-Plain "1"
ErrorDocument 404 /404.html
```

`a.html` contains `<!doctype html><title>a</title><p>probe a</p>`; `404.html` contains `<!doctype html><title>nf</title><p>probe-custom-404</p>`. Upload the three files to the new site's web root with `rsync` or `scp`.

- [ ] **Step 3: Run the probe**

```bash
P=https://PREVIEW-ADDRESS   # from the secrets folder; do not write it into the repo
curl -sI "$P/a.html" | tr -d '\r' | grep -i -E '^(HTTP|server|x-probe)'
curl -sI "$P/probe-moved" | tr -d '\r' | grep -i -E '^(HTTP|location)'
curl -sI "$P/probe-query?x=1" | tr -d '\r' | grep -i -E '^(HTTP|location)'
curl -sI "$P/probe-gone" | tr -d '\r' | grep -i '^HTTP'
curl -s  "$P/no-such-page" | grep -c probe-custom-404
```

Read the results:

| Result | Meaning |
|---|---|
| `probe-moved` returns 301 with `location: …/a.html` | `REWRITE` = yes |
| `probe-query?x=1` returns 301 and the location has no `?x=1` | `QSD` = yes |
| `probe-gone` returns 410 | the `G` flag works |
| `a.html` response has `x-probe` or `x-probe-plain` | `HEADERS` = yes |
| the last command prints `1` | `ERRORDOC` = yes |

If `probe-moved` does not redirect, wait two minutes and retry once (OpenLiteSpeed can need a reload after `.htaccess` changes).

- [ ] **Step 4: Record the result and clean up**

Write the four answers and the `server:` header value into `docs/superpowers/specs/2026-11-14-server-probe-result.md` (no addresses, users or paths). Delete the three probe files from the host. Commit:

```bash
git add site/tools/probe docs/superpowers/specs/2026-11-14-server-probe-result.md
git commit -m "Record what the host's web server supports"
```

---

### Task 10: Old-URL redirects and headers

**Files:**
- Create: `site/tools/redirects/gen-htaccess.mjs`, `site/tools/redirects/repoint.csv`
- Create: `site/static/.htaccess` (generated)
- Modify: `site/layouts/partials/head.html` (only if `HEADERS` = no)

**Interfaces:**
- Consumes: Task 9's `REWRITE`, `QSD`, `HEADERS`, `ERRORDOC` answers; `research/redirects.csv`.
- Produces: `node site/tools/redirects/gen-htaccess.mjs [--check] [--no-headers] [--no-qsd]` writes `site/static/.htaccess`. `repoint.csv` columns: `d15_target,new_target,note` (the check script reads `new_target`).

- [ ] **Step 1: Write the new re-point table**

Create `site/tools/redirects/repoint.csv`:

```csv
d15_target,new_target,note
/,/,Home
/nets/,/how-it-works/#nets,The weekly net
/nets/net-control/,/members/,Members page
/nets/repeaters/,/how-it-works/#weekly-net,Repeater settings box
/nets/#where-we-meet,/#visit,Where we meet
/privacy/,/,No privacy page
/join/,/#join,Join in four steps
/join/#apply,/about/#ares-path,How to apply
/join/#get-connected,/#join,Join in four steps
/join/requirements/,/about/#membership,Joining
/join/get-licensed/,/about/#licensing,Getting licensed
/about/,/about/,About
/about/leadership/,/about/#leadership,Leadership
/about/history/,/about/#history,History
/about/history/#plan,/about/#history,History
/about/history/#amateur-code,/about/#history,History
/about/w7gbu/,/about/#w7gbu,W7GBU
/about/what-we-do/,/#what-we-do,What we do
/about/what-we-do/#alert-levels,/how-it-works/#alert-levels,Readiness levels
/about/what-we-do/#skywarn,/about/#who-we-serve,Who we serve
/about/partners/#agreements,/about/#agreements,Agreements
/contact/,/about/#contact,Contact
/members/,/members/,For members
/library/,/resources/,Resources
/library/#forms,/resources/#forms,Forms
/library/#digital,/resources/,Resources
/library/#general,/resources/,Resources
/library/#membership,/members/#forms,Application and task books
/library/#net-scripts,/members/,Members page
/library/#presentations,/resources/,Resources
/library/go-kits/,/resources/,Resources
/library/resources/,/resources/,Resources
/library/resources/#digital,/resources/,Resources
/library/resources/#rfi,/resources/,Resources
```

Run: `python3 site/tools/check_site.py site/public --base /spokares-static`
Expected: `all checks passed` (every `new_target` exists in the built site). If a target is reported missing, fix the anchor id in the page or the row here.

- [ ] **Step 2: Write the generator**

Create `site/tools/redirects/gen-htaccess.mjs`. Copy the `parseCsv` and `keyOf` functions unchanged from `wordpress/tools/redirects/gen-redirect-map.mjs` (lines 32 to 92), then:

```js
#!/usr/bin/env node
/**
 * gen-htaccess.mjs: build site/static/.htaccess from research/redirects.csv
 * and site/tools/redirects/repoint.csv. Node standard library only.
 *   node site/tools/redirects/gen-htaccess.mjs [--check] [--no-headers] [--no-qsd]
 * The output is committed. Re-run after editing either CSV.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname( fileURLToPath( import.meta.url ) );
const repo = path.resolve( here, '../../..' );
const csvPath = path.join( repo, 'research/redirects.csv' );
const repointPath = path.join( here, 'repoint.csv' );
const outPath = path.join( repo, 'site/static/.htaccess' );
const check = process.argv.includes( '--check' );
const headers = ! process.argv.includes( '--no-headers' );
const qsd = ! process.argv.includes( '--no-qsd' );

// parseCsv( text ) and keyOf( oldPath ) pasted here, unchanged.

/** Escape a literal for use inside a rewrite pattern. */
function rx( s ) {
	return s.replace( /[.*+?^${}()|[\]\\]/g, '\\$&' ).replace( / /g, '\\ ' );
}

/** One rule: optional query conditions, then the RewriteRule. */
function rule( key, status, target ) {
	const q = key.indexOf( '?' );
	const p = ( q === -1 ? key : key.slice( 0, q ) ).replace( /^\//, '' );
	const pairs = q === -1 ? [] : key.slice( q + 1 ).split( '&' );
	const out = [];
	for ( const pair of pairs ) {
		// The server compares the raw query string, so match the encoded form too.
		const enc = encodeURIComponent( pair ).replace( /%3D/, '=' ).replace( /%20/g, '(%20|\\+)' );
		const forms = enc === pair ? rx( pair ) : `(${ rx( pair ) }|${ enc })`;
		out.push( `RewriteCond %{QUERY_STRING} (^|&)${ forms }(&|$)` );
	}
	if ( q === -1 ) {
		out.push( 'RewriteCond %{QUERY_STRING} ^$' );
	}
	const pattern = `^${ rx( p ) }$`;
	if ( status === 410 ) {
		out.push( `RewriteRule ${ pattern } - [G]` );
	} else if ( qsd ) {
		out.push( `RewriteRule ${ pattern } ${ target } [R=301,L,NE,QSD]` );
	} else {
		const [ base, frag ] = target.split( '#' );
		out.push( `RewriteRule ${ pattern } ${ base }?${ frag ? '#' + frag : '' } [R=301,L,NE]` );
	}
	return out.join( '\n' );
}

const rows = parseCsv( fs.readFileSync( csvPath, 'utf8' ) );
const repoint = new Map( parseCsv( fs.readFileSync( repointPath, 'utf8' ) ).map( ( r ) => [ r.d15_target, r.new_target ] ) );
const map = new Map();
const problems = [];
for ( const r of rows ) {
	const old = r.old_path;
	if ( ! old || old.startsWith( 'host:' ) || ! old.startsWith( '/' ) ) {
		continue;
	}
	if ( r.status === '410' ) {
		map.set( keyOf( old ), [ 410, '' ] );
	} else if ( r.status === '301' ) {
		const target = repoint.get( r.target );
		if ( ! target ) {
			problems.push( `no re-point for "${ r.target }" (from ${ old })` );
		} else if ( keyOf( old ) !== target.split( '#' )[ 0 ] ) {
			map.set( keyOf( old ), [ 301, target ] );
		}
	}
}

const keys = [ ...map.keys() ].sort();
const n301 = keys.filter( ( k ) => map.get( k )[ 0 ] === 301 ).length;
const lines = [
	'# GENERATED by site/tools/redirects/gen-htaccess.mjs. Do not edit by hand;',
	'# edit research/redirects.csv or site/tools/redirects/repoint.csv and re-run.',
	`# ${ n301 } redirects (301), ${ keys.length - n301 } gone (410).`,
	'',
	'Options -Indexes',
	'ErrorDocument 404 /404.html',
	'',
	'RewriteEngine On',
	'',
	'# Old addresses of the previous site.',
	...keys.map( ( k ) => rule( k, ...map.get( k ) ) ),
	'',
	'# Anything else from the previous site is gone.',
	'RewriteRule ^index\\.php(/|$) - [G]',
	'RewriteCond %{QUERY_STRING} (^|&)option=com_',
	'RewriteRule ^ - [G]',
	'',
];
if ( headers ) {
	lines.push(
		'<IfModule mod_headers.c>',
		'Header always set X-Content-Type-Options "nosniff"',
		'Header always set Referrer-Policy "strict-origin-when-cross-origin"',
		'Header always set X-Frame-Options "DENY"',
		'Header always set Strict-Transport-Security "max-age=86400"',
		"Header always set Content-Security-Policy \"default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'self'; form-action 'none'; frame-ancestors 'none'\"",
		'<FilesMatch "\\.(woff2|png|jpg|css|js)$">',
		'Header set Cache-Control "public, max-age=604800"',
		'</FilesMatch>',
		'</IfModule>',
		''
	);
}
const out = lines.join( '\n' );
if ( problems.length ) {
	console.error( problems.join( '\n' ) );
}
if ( check ) {
	const current = fs.existsSync( outPath ) ? fs.readFileSync( outPath, 'utf8' ) : '';
	if ( current !== out ) {
		console.error( '.htaccess is out of date: run node site/tools/redirects/gen-htaccess.mjs' );
		process.exit( 1 );
	}
	console.log( '.htaccess is up to date.' );
	process.exit( problems.length ? 1 : 0 );
}
fs.writeFileSync( outPath, out );
console.log( `Wrote site/static/.htaccess: ${ n301 } × 301, ${ keys.length - n301 } × 410.` );
process.exit( problems.length ? 1 : 0 );
```

The content security policy allows only same-origin scripts and styles. If any page has an inline `<style>` or `style=""` attribute, move it into `site.css` (check: `grep -rn 'style=' site/public --include=*.html | head`).

- [ ] **Step 3: Generate with the flags Task 9 found**

Run `node site/tools/redirects/gen-htaccess.mjs`, adding `--no-headers` if `HEADERS` = no and `--no-qsd` if `QSD` = no.
Expected: `Wrote site/static/.htaccess: 3xx × 301, 4xx × 410.` with no "no re-point" lines.

If `REWRITE` = no, stop: the spec's fallback (one `index.php` reusing the existing redirect map) applies, and that is a change of approach to raise with the owner before building it.

- [ ] **Step 4: If headers are not supported, carry the policy in the page**

Only when `HEADERS` = no: add to `site/layouts/partials/head.html`, directly after the charset line:

```html
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'self'; form-action 'none'">
```

and note in `MAINTAINING.md` (Task 12) that HTTPS is forced in the hosting panel.

- [ ] **Step 5: Test the whole map on the preview**

**OWNER GO-AHEAD** (uploads the built site to the preview website from Task 9).

```bash
hugo --source site --cleanDestinationDir --panicOnWarning --baseURL http://localhost/spokares-static/
rsync -az --delete --exclude .well-known site/public/ PREVIEW-SSH:WEB-ROOT/
```

Then test every row. Save as `site/tools/redirects/test-live.sh`:

```bash
#!/usr/bin/env bash
# Usage: test-live.sh https://preview-address
# Checks every old address in research/redirects.csv against the live answer.
set -u
BASE=$1
fail=0; n=0
while IFS=$'\t' read -r old status target; do
  n=$((n+1))
  got=$(curl -s -o /dev/null -w '%{http_code}\t%{redirect_url}' --path-as-is "$BASE$old")
  code=${got%%$'\t'*}; loc=${got#*$'\t'}
  if [[ $code != "$status" ]]; then
    echo "WRONG STATUS $code (want $status): $old"; fail=$((fail+1))
  elif [[ $status == 301 && ${loc#"$BASE"} != "$target" && ${loc#"$BASE"} != "${target%%#*}" ]]; then
    echo "WRONG TARGET $loc (want $target): $old"; fail=$((fail+1))
  fi
  sleep 0.05
done < <(node "$(dirname "$0")/gen-htaccess.mjs" --list)
echo "$n tested, $fail wrong"
exit $(( fail > 0 ))
```

Add a `--list` mode to the generator: when `process.argv.includes( '--list' )`, before writing anything, print one line per key as `old-path<TAB>status<TAB>target` (re-encode the key with `encodeURI`) and exit 0. Place this block right after `keys` is computed:

```js
if ( process.argv.includes( '--list' ) ) {
	for ( const k of keys ) {
		const [ status, target ] = map.get( k );
		console.log( `${ encodeURI( k ) }\t${ status }\t${ target }` );
	}
	process.exit( 0 );
}
```

Run: `bash site/tools/redirects/test-live.sh https://PREVIEW-ADDRESS`
Expected: `781 tested, 0 wrong` (the count may differ slightly from 781; it must equal the number of generated rules). Also confirm `curl -sI https://PREVIEW-ADDRESS/` returns 200 and, if `HEADERS` = yes, shows the security headers. Fix the generator for any failing pattern and re-run until zero are wrong.

- [ ] **Step 6: Commit**

```bash
git add site
git commit -m "Static site: old-address redirects and response headers"
```

---

### Task 11: Deploy workflow

**OWNER GO-AHEAD required for Step 3** (GitHub environment and secrets) **and Step 5** (first run).

**Files:**
- Create: `.github/workflows/site.yml`

**Interfaces:**
- Consumes: GitHub environment `static-site` with secrets `SITE_SSH_KEY`, `SITE_KNOWN_HOSTS`, `SITE_HOST`, `SITE_USER`, `SITE_PORT`, `SITE_PATH`.
- Produces: every push to `main` that touches `site/` builds, checks and deploys.

- [ ] **Step 1: Get the Hugo checksum**

```bash
curl -fsSL https://github.com/gohugoio/hugo/releases/download/v0.164.0/hugo_0.164.0_checksums.txt | grep 'hugo_extended_0.164.0_linux-amd64.tar.gz'
```

Copy the 64-character hash it prints for use as `HUGO_SHA256` below.

- [ ] **Step 2: Write the workflow**

Create `.github/workflows/site.yml`, replacing `PASTE_HASH_HERE` with the hash from Step 1:

```yaml
# Build the static site with a pinned Hugo, check it, and copy it to the host.
# Runs on every commit to main that touches site/. No approval step: the
# checks are the gate, so any editor with write access can publish.
name: Site

on:
  push:
    branches: [main]
    paths: ['site/**', '.github/workflows/site.yml']
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: site-deploy
  cancel-in-progress: false

env:
  HUGO_VERSION: 0.164.0
  HUGO_SHA256: PASTE_HASH_HERE

jobs:
  build:
    name: Build and check
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - name: Install Hugo (pinned, checksum verified)
        run: |
          f=hugo_extended_${HUGO_VERSION}_linux-amd64.tar.gz
          curl -fsSL -o "$RUNNER_TEMP/$f" "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/$f"
          echo "$HUGO_SHA256  $RUNNER_TEMP/$f" | sha256sum --check
          mkdir -p "$RUNNER_TEMP/hugo" && tar -xzf "$RUNNER_TEMP/$f" -C "$RUNNER_TEMP/hugo" hugo
          echo "$RUNNER_TEMP/hugo" >> "$GITHUB_PATH"
      - name: Build
        run: hugo --source site --cleanDestinationDir --panicOnWarning --minify=false
      - name: Check the built site
        run: python3 site/tools/check_site.py site/public
      - name: Report on outside links (does not block)
        continue-on-error: true
        run: python3 site/tools/check_links.py site/public
      - uses: actions/upload-artifact@v4
        with:
          name: site
          path: site/public
          include-hidden-files: true
          retention-days: 14

  deploy:
    name: Copy to the host
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    environment: static-site
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: site
          path: public
      - name: Set up SSH
        env:
          SITE_SSH_KEY: ${{ secrets.SITE_SSH_KEY }}
          SITE_KNOWN_HOSTS: ${{ secrets.SITE_KNOWN_HOSTS }}
          SITE_HOST: ${{ secrets.SITE_HOST }}
          SITE_USER: ${{ secrets.SITE_USER }}
          SITE_PORT: ${{ secrets.SITE_PORT }}
          SITE_PATH: ${{ secrets.SITE_PATH }}
        run: |
          for v in SITE_SSH_KEY SITE_KNOWN_HOSTS SITE_HOST SITE_USER SITE_PORT SITE_PATH; do
            [[ -n ${!v} ]] || { echo "::error::secret $v is not set"; exit 1; }
          done
          [[ $SITE_PORT =~ ^[0-9]+$ && $SITE_HOST =~ ^[A-Za-z0-9.:-]+$ && $SITE_USER =~ ^[A-Za-z0-9._-]+$ ]] || { echo "::error::unexpected characters in a host setting"; exit 1; }
          [[ $SITE_PATH =~ ^[A-Za-z0-9._/-]+/public_html$ ]] || { echo "::error::SITE_PATH must end in /public_html"; exit 1; }
          umask 077; mkdir -p ~/.ssh
          printf '%s\n' "$SITE_SSH_KEY" > ~/.ssh/site_deploy
          printf '%s\n' "$SITE_KNOWN_HOSTS" > ~/.ssh/site_known_hosts
          cat > ~/.ssh/config <<EOF
          Host site-live
            HostName $SITE_HOST
            User $SITE_USER
            Port $SITE_PORT
            IdentityFile ~/.ssh/site_deploy
            IdentitiesOnly yes
            UserKnownHostsFile ~/.ssh/site_known_hosts
            StrictHostKeyChecking yes
            BatchMode yes
            ControlMaster auto
            ControlPath ~/.ssh/cm-%C
            ControlPersist 300
            ConnectTimeout 25
          EOF
          echo "SITE_PATH=$SITE_PATH" >> "$GITHUB_ENV"
      - name: Copy the site
        run: |
          [[ -f public/index.html && -f public/404.html ]] || { echo "::error::build output is incomplete"; exit 1; }
          rsync -az --delete --exclude '.well-known' public/ "site-live:$SITE_PATH/"
      - name: Close SSH and remove the key
        if: always()
        run: |
          ssh -O exit site-live 2>/dev/null || true
          rm -f ~/.ssh/site_deploy ~/.ssh/config
```

Pin `actions/upload-artifact` and `actions/download-artifact` to commit hashes the same way `checkout` is pinned; look up the current v4 commit for each with `gh api repos/actions/upload-artifact/git/ref/tags/v4 --jq .object.sha` and the same for `download-artifact`.

- [ ] **Step 3: Create the environment and secrets**

In the GitHub repository settings, create the environment `static-site`: deployment branches limited to `main`, no required reviewers. Add the six secrets with the new website's values from the secrets folder. Use `gh secret set NAME --env static-site < file` so no value appears on a command line or in a log.

- [ ] **Step 4: Validate the workflow file locally**

```bash
python3 - <<'EOF'
import sys, yaml
yaml.safe_load(open('.github/workflows/site.yml'))
print('workflow parses')
EOF
```

Expected: `workflow parses`. (If PyYAML is missing, run `ruby -ryaml -e 'YAML.load_file(".github/workflows/site.yml"); puts "workflow parses"'`.)

- [ ] **Step 5: Commit, then first run after merge**

```bash
git add .github/workflows/site.yml
git commit -m "Workflow: build, check and deploy the static site on a commit to main"
```

The workflow only deploys from `main`. Its first real run happens when the branch is merged (Task 14). Until then, verify the `build` job by running it from the branch: `gh workflow run site.yml --ref stable-static-site` and confirm `build` passes and `deploy` is skipped.

---

### Task 12: The maintenance guide

**Files:**
- Create: `MAINTAINING.md`
- Modify: `README.md`

**Interfaces:**
- Produces: the one document a yearly editor needs.

- [ ] **Step 1: Write the guide**

Create `MAINTAINING.md`:

```markdown
# Keeping spokares.org current

The site is built to be left alone. It only holds facts that change about
once a year. This page covers every change you are likely to need.

You need a GitHub account with write access to this repository. You do not
need to install anything.

## Change a fact (officers, meeting times, repeater settings, contact)

1. Open `site/data/facts.yaml` on GitHub and choose the pencil (Edit).
2. Change the words between the quotes. Leave the labels on the left alone.
3. Choose "Commit changes".

The site rebuilds and publishes itself in about two minutes.

- Someone new in a position: change the call sign on that line.
- A position is empty: delete its two lines. Never write "open" or "vacant".
- Never put a date in this file. Meetings are written as rules, such as
  "Third Thursday of each month, 6:00 PM".

## Replace the application or a task book

1. Name the new file exactly as the old one (for example
   `ares-application.pdf`).
2. In `site/static/files/` on GitHub choose "Add file", then "Upload files",
   and commit.
3. Change that file's `version` in `site/data/facts.yaml`.

These three files are the only documents the site holds. Everything else is
a link to whoever keeps it current.

## Add, change or remove a link on Resources

Edit `site/data/resources.yaml`. Each link has a title, an address and one
line saying what it is. Only link to pages anyone can open without signing in.

## Change wording on a page

Page text is in `site/content/`. Lines that look like `{{< net-settings >}}`
place a designed piece of the page; leave those lines as they are.

## If a change does not appear

Open the "Actions" tab on GitHub. A red mark means the checks refused the
change, and the message says why. The live site is untouched until a change
passes. The usual causes are a deleted quote mark in `facts.yaml` or a
broken link.

## Once a year

- [ ] Leadership in `facts.yaml` matches who holds each position.
- [ ] Meeting days, times and place are still right.
- [ ] The application and task books are the current versions.
- [ ] Open the latest run under "Actions" and read "Report on outside links".
      Fix or remove any link marked FAIL or SIGN-IN.
- [ ] `info@spokares.org` still forwards to someone who reads it.
- [ ] The domain `spokares.org` is paid up and set to renew by itself.
- [ ] The hosting account is paid up.
- [ ] At least two people have write access to this repository.

## For whoever looks after the machinery

- The site is built by Hugo, pinned to version 0.164.0 in
  `.github/workflows/site.yml`. Preview locally with
  `hugo server --source site`.
- `python3 site/tools/check_site.py site/public --base /spokares-static` is the test suite.
- Old addresses from the previous site are handled by
  `site/static/.htaccess`, which is generated: edit
  `site/tools/redirects/repoint.csv`, then run
  `node site/tools/redirects/gen-htaccess.mjs`.
- Do not edit files on the host. The next publish replaces them.
- The earlier WordPress build is in git history at tag `v0.3.2`.
```

- [ ] **Step 2 (Part 2 only; skip during the review): Update the WordPress repository's README**

In `README.md`, replace the section that describes the WordPress build and how to preview it (the part beginning around line 7 that covers the Enhance preview and `/etc/hosts` pinning) with:

```markdown
## The site

`site/` is a Hugo static site. It holds only content that changes about once
a year. To change it, see [MAINTAINING.md](MAINTAINING.md). The design
decisions are in `docs/superpowers/specs/2026-11-14-stable-static-site-design.md`.

An earlier WordPress build, never launched, is in git history at tag `v0.3.2`.
```

Keep the README's research and privacy sections as they are.

- [ ] **Step 3: Check the guide against the repository**

During the review, leave the two redirect lines and the `site.yml` reference out of the guide's last section (they describe Part 2), say the preview is published by `.github/workflows/pages.yml`, and drop those three paths from the list below. Every path the guide names must exist:

```bash
for p in site/data/facts.yaml site/data/resources.yaml site/static/files site/content site/tools/check_site.py site/tools/redirects/repoint.csv site/tools/redirects/gen-htaccess.mjs .github/workflows/site.yml; do
  [[ -e $p ]] && echo "ok  $p" || echo "MISSING  $p"
done
```

Expected: every line starts with `ok`.

- [ ] **Step 4: Commit**

```bash
git add MAINTAINING.md README.md
git commit -m "Guide for the yearly editor; README points at the static site"
```

---

### Task 13: Pre-launch verification

Run against the local build and the GitHub Pages preview. These are one-time checks; the tools here are not part of the build. During the review, skip the `gen-htaccess.mjs --check` line in Step 1 and the redirect test in Step 6 (both belong to Part 2), and in Step 6 use the Pages preview address.

**Files:**
- Create: `docs/superpowers/specs/2026-11-14-verification-results.md`

- [ ] **Step 1: Build output**

```bash
hugo --source site --cleanDestinationDir --panicOnWarning --baseURL http://localhost/spokares-static/
python3 site/tools/check_site.py site/public --base /spokares-static
python3 site/tools/check_links.py site/public --strict
node site/tools/redirects/gen-htaccess.mjs --check   # add the same --no-* flags used in Task 10
```

Expected: `all checks passed`; no `FAIL` or `SIGN-IN`; `.htaccess is up to date.`

- [ ] **Step 2: HTML validation**

```bash
npx --yes html-validate@9 "site/public/**/*.html"
```

Expected: no errors. Fix real errors (unclosed elements, duplicate ids, missing alt text) in the templates. A rule that only disputes style may be recorded as accepted in the results file.

- [ ] **Step 3: Accessibility**

```bash
hugo server --source site --port 9401 &
for p in / /how-it-works/ /about/ /members/ /resources/; do
  npx --yes @axe-core/cli@4 "http://127.0.0.1:9401$p" --exit
done
kill %1
```

Expected: `0 violations found` for each page. Then, by keyboard only, at a 390-wide window: Tab to "Menu", open it with Enter, Tab through the links, close with Escape and confirm focus returns to the button.

- [ ] **Step 4: Screenshot comparison**

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
mkdir -p site/.reference/new
hugo server --source site --port 9401 &
for p in "home:/" "how-it-works:/how-it-works/" "about:/about/" "members:/members/" "resources:/resources/"; do
  name=${p%%:*}; path=${p#*:}
  for w in 390 1280; do
    "$CHROME" --headless=new --hide-scrollbars --window-size=$w,12000 \
      --screenshot="site/.reference/new/$name-$w.png" "http://127.0.0.1:9401$path"
  done
done
kill %1
```

Open each pair (`site/.reference/shots/X.png` beside `site/.reference/new/X.png`) for Home, How it works and About. Every difference must be one of the content changes named in Tasks 4 to 6. Type, colour, spacing and layout must match. List each difference found in the results file. Members and Resources have no baseline; check they use the same type, spacing and components as the other pages.

- [ ] **Step 5: No third-party requests**

```bash
grep -rhoE '(src|href)="https?://[^"]+"' site/public --include=*.html | grep -vE 'href=' | sort -u
grep -rhoE 'url\(["'"'"']?https?://[^)]+' site/public/css | sort -u
```

Expected: both print nothing (outside links in `href` are fine; nothing loads from another site).

- [ ] **Step 6: The live preview**

```bash
P=https://PREVIEW-ADDRESS
for p in / /how-it-works/ /about/ /members/ /resources/ /files/ares-application.pdf; do
  printf '%s %s\n' "$(curl -s -o /dev/null -w '%{http_code}' "$P$p")" "$p"
done
curl -s -o /dev/null -w '%{http_code}\n' "$P/no-such-page"
bash site/tools/redirects/test-live.sh "$P"
```

Expected: `200` for the six paths; `404` for the missing page; the redirect test reports `0 wrong`.

- [ ] **Step 7: Record and commit**

Write the outcome of each step, the list of accepted screenshot differences, and any link that needed a manual check into `docs/superpowers/specs/2026-11-14-verification-results.md`. Do not include the preview address.

```bash
git add docs/superpowers/specs/2026-11-14-verification-results.md
git commit -m "Record pre-launch verification of the static site"
```

---

### Task 14: Remove the WordPress build from the branch and merge

**OWNER GO-AHEAD required for Step 4** (merge to `main`, which triggers the first deploy to the preview website).

**Files:**
- Delete: `wordpress/`, `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`
- Modify: `research/README.md` (one pointer line)

- [ ] **Step 1: Confirm nothing outside `wordpress/` depends on it**

```bash
git grep -n -I "wordpress/" -- . ':!wordpress' ':!docs/superpowers' ':!site/tools/redirects/gen-htaccess.mjs' | head -40
```

Expected: only prose references in `README.md`, `research/` and `design/` notes. Any script or workflow outside `wordpress/` that reads a file from it must be fixed first. The redirect generator's `parseCsv` and `keyOf` were copied in Task 10, so it has no dependency.

- [ ] **Step 2: Confirm the tag that preserves it**

Run: `git tag --list 'v0.3.2' && git merge-base --is-ancestor v0.3.2 HEAD && echo preserved`
Expected: `v0.3.2` then `preserved`.

- [ ] **Step 3: Remove it**

```bash
git rm -r -q wordpress .github/workflows/ci.yml .github/workflows/deploy.yml
```

In `research/README.md`, where it points readers at `wordpress/PLAN.md` or the WordPress decision, add one line: "The WordPress build was set aside on 2026-11-14 for a static site with stable content only; see `docs/superpowers/specs/2026-11-14-stable-static-site-design.md`. The WordPress code is at tag `v0.3.2`."

```bash
hugo --source site --cleanDestinationDir --panicOnWarning && python3 site/tools/check_site.py site/public --base /spokares-static
git add -A
git commit -m "Remove the WordPress build from main; it remains at tag v0.3.2"
```

Expected: `all checks passed`.

- [ ] **Step 4: Merge**

Open a pull request from `stable-static-site` to `main`. After the owner approves and merges, watch the `Site` workflow: `gh run watch`. Expected: `build` and `deploy` both succeed, and the preview address serves the site.

---

### Task 15: Go-live checklist

Every step here needs the owner. None is run without an explicit go-ahead; several are irreversible or outward-facing.

**Files:**
- Modify: `site/layouts/partials/head.html`, `site/hugo.toml` (Step 4)

- [ ] **Step 1: Confirm the open facts with the Emergency Coordinator and Net Manager**

Third Thursday time; whether December has a meeting; the alternate repeater's settings; whether the Winlink gateway line stays; "no dues"; current versions of the application and ACS task book. Update `site/data/facts.yaml` and page text accordingly. A fact that cannot be confirmed is removed, not guessed.

- [ ] **Step 2: Set up `info@spokares.org`**

Decide who receives it. Create the forwarder on Enhance. This needs the domain's mail to move off the old host, which is a DNS change.

- [ ] **Step 3: Domain and DNS**

Confirm who holds the registrar account and that auto-renew is on (the domain expires 2027-03-10). Add `spokares.org` and `www.spokares.org` to the new website on Enhance. Move the nameservers to Enhance, or point the records at it, following the existing rule that nothing is re-pointed without the owner's go-ahead. Confirm the certificate is issued for both names.

- [ ] **Step 4: Turn on indexing**

Remove the `<meta name="robots" content="noindex">` line from `site/layouts/partials/head.html`. In `site/hugo.toml`, remove `"sitemap"` from `disableKinds` and set `enableRobotsTXT = true`. Build, run the checks, commit, merge.

- [ ] **Step 5: Check the live site**

```bash
bash site/tools/redirects/test-live.sh https://spokares.org
curl -sI https://spokares.org/ | tr -d '\r' | grep -i -E '^(HTTP|strict-transport|content-security)'
curl -sI http://spokares.org/ | tr -d '\r' | grep -i -E '^(HTTP|location)'
curl -sI https://www.spokares.org/ | tr -d '\r' | grep -i -E '^(HTTP|location)'
```

Expected: `0 wrong`; HTTPS returns 200; plain HTTP redirects to HTTPS; `www` and the bare domain agree on one canonical host.

- [ ] **Step 6: Set up the monitor**

Create an external uptime and certificate-expiry monitor for `https://spokares.org/`, with the keyword "Spokane County ARES-ACS", alerting `info@spokares.org`. The account belongs to the role address, not a person.

- [ ] **Step 7: Retire what is no longer needed**

Only after the live site has been checked: delete the WordPress preview website and its database on Enhance; delete the `production` GitHub environment and its secrets; revoke the Enhance API token; remove WordPress-only items from the secrets folder. Add a second person with write access to the repository.

---

## Self-review notes

- **Spec coverage:** pages (Tasks 4 to 8); content rules (Tasks 3 to 8, enforced by `check_site.py`); structure (Tasks 2, 3); hosting, redirects and headers (Tasks 9 to 11); the WordPress build (Task 14, Task 15 Step 7); keeping it alive (Tasks 8, 12, Task 15 Step 6); verification items 1 to 8 (Task 13 and `check_site.py`); items that need people (Task 15).
- **Known judgement calls an implementer must report, not decide silently:** whether the members page repeats the repeater settings (Task 7 Step 5); which application version is current (Task 7 Step 2); any link that only passes a manual check (Task 8 Step 5); any accepted HTML-validator rule (Task 13 Step 2).
- **Porting steps** give the source element, the destination file and the exact content changes instead of reproducing about 1,600 lines of markup; the reference capture from Task 1 is the source of truth for that markup.
