#!/usr/bin/env python3
"""Checks the built site. Usage: check_site.py <public-dir> [--stage N] [--base /prefix]

--base is the path prefix the site was built for (GitHub Pages preview:
/spokares-static). Every internal address must start with it.

Standard library only. Exits 1 and prints one line per problem.
Stages let early tasks run the checks that apply so far:
  1 shell   2 facts   3 home   4 how   5 about   6 members   7 resources (all)
The stage only decides which of the named PAGES must exist and whether their
anchors are checked yet. Every other check runs on every *.html file (and
every *.css file) under <public-dir>.

Self-test: python3 site/tools/test_check_site.py
"""
import csv
import html
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
# Removed wording, matched case-insensitively against the page's text with all
# whitespace (line breaks, no-break spaces) folded to one space and tags removed.
FORBIDDEN = [
    "Schedule as of", "Last reviewed", "being recovered", "new website",
    "This week", "Next up", "Later this season", "Not posted yet",
    "Volunteer needed", "Open position", "Net Control Schedule", "coming soon",
]
# Class and path tokens, matched in the raw HTML.
FORBIDDEN_RAW = ["needs-verify", "data-verify", "wp-block-navigation", "wp-content",
                 "wp-includes"]
# Patterns matched against the same normalised text. "Soon" as a label is
# capitalised; "as soon as" in a sentence is fine.
FORBIDDEN_WORDS = [r"\bSoon\b", r"(?i)\bnext:\s"]
FACTCHECK = ["147.300", "100 Hz", "8:00 PM", "Second Saturday", "Third Thursday",
             "1121 W Gardner Ave", "W7TSC", "info@spokares.org"]
GROUPS_IO = "https://spokaneares-acs.groups.io/g/main"

DASH = "\\-\u2010‑‒–—−"
SEP = f"[{DASH}.\\s]"
# (509) 555-1234, 509-555-1234, 509.555.1234, 509 555 1234, 509–555–1234,
# +1 509 555 1234, 5095551234, and 555-1234. Frequencies (147.300), offsets,
# times, years, ZIPs and form numbers do not have these shapes.
PHONE = re.compile(
    rf"(?<![\d.])(?:\+?1{SEP}?)?(?:\(\d{{3}}\)\s?|\d{{3}}{SEP})\d{{3}}{SEP}\d{{4}}(?![\d])"
    rf"|(?<![\d.])1?\d{{10}}(?!\d)"
    rf"|(?<![\d.{DASH}])\d{{3}}[{DASH}]\d{{4}}(?![\d{DASH}])"
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ALLOWED_EMAILS = {"info@spokares.org"}
NOT_EMAIL_TLDS = {"png", "jpg", "jpeg", "gif", "webp", "avif", "svg", "ico"}

MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?"
         r"|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
WEEKDAY = r"(?:Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun)(?:day)?"
# Printed dates: "Sat, Oct 10", "November 7", "27 June", 2026-11-14, 11/14/2026.
# Month + year ("August 2023") and bare years are history, not dates.
DATE = re.compile(
    rf"\b{WEEKDAY},?\s+{MONTH}\.?\s+\d"
    rf"|\b{MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?![\d:])"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{MONTH}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})\b"
)
# A date is allowed only as a hosted file's version: in the same block (list
# item, paragraph, table cell…) as a link to /files/….
DATE_BLOCKS = {"li", "p", "td", "th", "dd", "dt", "figcaption", "caption",
               "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "div", "section",
               "main", "body"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}
TEXT_ATTRS = ("alt", "title", "aria-label", "placeholder", "data-copy-text")
CSS_URL = re.compile(r"""url\(\s*(['"]?)(.*?)\1\s*\)|@import\s+(['"])(.*?)\3""", re.S)


def norm(s):
    return re.sub(r"\s+", " ", s)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.loads, self.text = set(), [], [], []
        self.attr_text = []   # attribute values people read or copy
        self.attr_all = []    # every attribute value (for the e-mail check)
        self.attr_phone = []  # attributes that could carry a phone number (not SVG geometry)
        self.styles = 0
        self.h1 = 0
        self.title = ""
        self.lang = None
        self.description = None
        self.robots = []
        self._in_title = False
        self._skip = 0
        self._stack = []          # open elements: [tag, block_id]
        self._block = 0           # id of the innermost open date block
        self.blocks_with_files = set()
        self.block_text = {}      # block_id -> its own text, for the date check

    def _blocks(self):
        return [b for _, b in self._stack if b is not None]

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if a.get("id"):
            self.ids.add(a["id"])
        if "style" in a:
            self.styles += 1
        for k, v in a.items():
            self.attr_all.append(v)
            if k in TEXT_ATTRS:
                self.attr_text.append(v)
            if k in TEXT_ATTRS + ("href", "content", "value"):
                self.attr_phone.append(v)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            name = a.get("name", "").lower()
            if name == "description":
                self.description = a.get("content", "")
                self.attr_text.append(self.description)
            if name == "robots":
                self.robots.append(a.get("content", "").lower())
        if tag == "style":
            self.styles += 1
        if tag in ("script", "style"):
            self._skip += 1
        if tag in ("a", "area") and "href" in a:
            self.links.append(a["href"])
            if "/files/" in a["href"]:
                self.blocks_with_files.update(self._blocks())
        if a.get("src") and tag in ("script", "img", "source", "iframe", "video",
                                    "audio", "track", "embed", "input"):
            self.loads.append(a["src"])
        if a.get("poster") and tag == "video":
            self.loads.append(a["poster"])
        if a.get("data") and tag == "object":
            self.loads.append(a["data"])
        if "srcset" in a or "imagesrcset" in a:
            for part in (a.get("srcset", "") + "," + a.get("imagesrcset", "")).split(","):
                url = part.strip().split(" ")[0] if part.strip() else ""
                if url:
                    self.loads.append(url)
        if tag == "link" and a.get("href"):
            self.loads.append(a["href"])
        if tag in VOID:
            return
        self._block += 1
        self._stack.append([tag, self._block if tag in DATE_BLOCKS else None])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self._stack:
            self._stack.pop()

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in ("script", "style"):
            self._skip -= 1
        if tag in VOID:
            return
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.text.append(data)
            blocks = self._blocks()
            b = blocks[-1] if blocks else 0
            self.block_text[b] = self.block_text.get(b, "") + data


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
        if not (root / rel).is_file() and stage >= need:
            problems.append(f"missing page: {rel}")

    for f in sorted(root.rglob("*.html")):
        rel = f.relative_to(root).as_posix()
        p = Page()
        p.feed(f.read_text(encoding="utf-8"))
        p.close()
        pages[rel] = p

    for rel in REMOVED_PATHS:
        if (root / rel).exists():
            problems.append(f"removed path is present: {rel}")
    for f in root.glob("sitemap*.xml"):
        problems.append(f"sitemap must not ship: {f.name}")

    def target_ok(path, frag):
        path = unquote(path)
        f = root / path.lstrip("/")
        if f.is_dir():
            f = f / "index.html"
        if not f.is_file():
            return False
        if not frag:
            return True
        key = f.relative_to(root).as_posix()
        if key not in pages:
            return f.suffix != ".html"
        if stage < PAGES.get(key, 0):
            return True  # that page's sections arrive in a later task
        return frag in pages[key].ids

    def emails(s):
        out = set()
        for e in EMAIL.findall(s):
            e = e.rstrip(".")
            if e.rsplit(".", 1)[-1].lower() in NOT_EMAIL_TLDS:
                continue
            out.add(e.lower())
        return out

    def relative(addr):
        """An internal address that a browser resolves against the page's own URL."""
        u = urlparse(addr)
        return not (u.scheme or u.netloc or addr.startswith("/") or addr.startswith("#")
                    or addr == "")

    groups_links = 0
    for rel, p in pages.items():
        raw = (root / rel).read_text(encoding="utf-8")
        text = norm(" ".join(p.text) + " | " + " | ".join(p.attr_text))
        if p.lang != "en-US":
            problems.append(f"{rel}: <html lang> is not en-US")
        if p.h1 != 1:
            problems.append(f"{rel}: expected one h1, found {p.h1}")
        if not p.title.strip():
            problems.append(f"{rel}: empty <title>")
        if not (p.description or "").strip():
            problems.append(f"{rel}: empty or missing meta description")
        if not any("noindex" in r for r in p.robots):
            problems.append(f'{rel}: missing <meta name="robots" content="noindex">')
        if p.styles:
            problems.append(f"{rel}: inline style (style= or <style>) found {p.styles} time(s)")
        for phrase in FORBIDDEN:
            if phrase.lower() in text.lower():
                problems.append(f"{rel}: forbidden text {phrase!r}")
        for token in FORBIDDEN_RAW:
            if token in raw.lower():
                problems.append(f"{rel}: forbidden text {token!r}")
        for pat in FORBIDDEN_WORDS:
            if re.search(pat, text):
                problems.append(f"{rel}: forbidden wording /{pat}/")
        tels = [unquote(h[4:]) for h in p.links if h.lower().startswith("tel:")]
        for s in [norm(" ".join(p.text))] + p.attr_phone + tels:
            m = PHONE.search(s)
            if m:
                problems.append(f"{rel}: something that looks like a phone number: {m.group(0)!r}")
                break
        found = emails(html.unescape(raw)) | emails(" ".join(p.attr_all))
        for h in p.links:
            found |= emails(unquote(h))
        for e in sorted(found - ALLOWED_EMAILS):
            problems.append(f"{rel}: e-mail address not allowed: {e}")
        for block, chunk in p.block_text.items():
            m = DATE.search(norm(chunk))
            if m and block not in p.blocks_with_files:
                problems.append(f"{rel}: printed date {m.group(0)!r} (meetings are rules only)")
        m = DATE.search(norm(" ".join(p.attr_text)))
        if m:
            problems.append(f"{rel}: printed date {m.group(0)!r} in an attribute")
        for src in p.loads:
            u = urlparse(src)
            if u.scheme or u.netloc:
                if u.scheme != "data":
                    problems.append(f"{rel}: third-party load {src}")
            elif relative(src):
                problems.append(f"{rel}: relative address {src} (write it root-relative)")
            elif not (root / unquote(local(u.path, rel, "asset")).lstrip("/")).is_file():
                problems.append(f"{rel}: missing asset {src}")
        for href in p.links:
            u = urlparse(href.strip())
            scheme = u.scheme.lower()
            if scheme in ("mailto", "tel"):
                continue
            if scheme not in ("", "http", "https"):
                problems.append(f"{rel}: {scheme}: link not allowed: {href}")
                continue
            if scheme or u.netloc:
                host = (u.hostname or "").lower()
                if host == "groups.io" or host.endswith(".groups.io"):
                    groups_links += 1
                    same = (scheme == "https" and host == urlparse(GROUPS_IO).hostname
                            and u.path.rstrip("/") == urlparse(GROUPS_IO).path
                            and not u.query and not u.fragment)
                    if rel != "members/index.html" or not same:
                        problems.append(f"{rel}: groups.io link not allowed here: {href}")
                    if "/files" in u.path:
                        problems.append(f"{rel}: link needs sign-in: {href}")
                if (host == "ag7qp.com" or host.endswith(".ag7qp.com")) and rel != "resources/index.html":
                    problems.append(f"{rel}: ag7qp.com link outside Resources: {href}")
                continue
            if relative(href):
                problems.append(f"{rel}: relative link {href} (write it root-relative, e.g. /about/)")
                continue
            path = local(u.path, rel, "link") if u.path else "/" + rel.replace("index.html", "")
            if not target_ok(path, u.fragment):
                problems.append(f"{rel}: broken internal link {href}")
    if stage >= 6 and groups_links != 1:
        problems.append(f"expected exactly one groups.io link, found {groups_links}")

    for f in sorted(root.rglob("*.css")):
        rel = f.relative_to(root).as_posix()
        css = re.sub(r"/\*.*?\*/", "", f.read_text(encoding="utf-8"), flags=re.S)
        for m in CSS_URL.finditer(css):
            addr = (m.group(2) if m.group(2) is not None else m.group(4)).strip()
            u = urlparse(addr)
            if u.scheme == "data" or addr.startswith("#") or not addr:
                continue
            if u.scheme or u.netloc:
                problems.append(f"{rel}: third-party load {addr}")
            elif addr.startswith("/"):
                problems.append(f"{rel}: root-relative address {addr} breaks under a base path; use ../")
            elif not (f.parent / unquote(u.path)).resolve().is_file():
                problems.append(f"{rel}: missing asset {addr}")

    repoint = Path(__file__).parent / "redirects" / "repoint.csv"
    if stage >= 7 and repoint.is_file():
        for row in csv.DictReader(repoint.open(encoding="utf-8")):
            u = urlparse(row["new_target"])
            if not target_ok(u.path, u.fragment):
                problems.append(f"repoint.csv: target does not exist: {row['new_target']}")

    fc = root / "factcheck" / "index.html"
    if stage == 2:
        body = fc.read_text(encoding="utf-8") if fc.is_file() else ""
        for needle in FACTCHECK:
            if needle not in body:
                problems.append(f"factcheck: {needle!r} not rendered")
    elif fc.exists():
        problems.append("factcheck page must not ship")

    for line in problems:
        print(line)
    print(f"{len(problems)} problem(s)" if problems else "all checks passed")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
