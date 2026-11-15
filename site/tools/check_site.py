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
FACTCHECK = ["147.300", "100 Hz", "8:00 PM", "Second Saturday", "Third Thursday",
             "1121 W Gardner Ave", "W7TSC", "info@spokares.org"]
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
