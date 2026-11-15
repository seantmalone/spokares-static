#!/usr/bin/env python3
"""Checks the built site.

Usage: check_site.py <public-dir> [--base /prefix] [--preview | --live]
                     [--facts path/to/facts.yaml] [--stage N]

--base     the path prefix the site was built for (GitHub Pages preview:
           /spokares-static). Every internal address must start with it.
--preview  (the default) every page must carry <meta name="robots" content="noindex">.
--live     no page may carry it (the build for spokares.org itself).
--facts    the facts file the site was built from (default: site/data/facts.yaml
           beside this script). The checker reads the contact address, the
           hosted files and their versions from it.
--stage    only for building the site task by task: which of the named PAGES
           must exist yet (1 shell 2 facts 3 home 4 how 5 about 6 members
           7 resources, the default).

Every other check runs on every *.html file (and every *.css file, and every
hosted file under files/) under <public-dir>. Standard library only. Prints
one line per problem and exits 1 if there are any.

Self-test: python3 site/tools/test_check_site.py
"""
import csv
import datetime
import html
import re
import sys
import zipfile
import zlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_data  # noqa: E402  (same folder; standard library only)

USAGE = ("usage: check_site.py <public-dir> [--base /prefix] [--preview | --live] "
         "[--facts facts.yaml] [--stage 1-7]")
PAGES = {
    "index.html": 3,
    "how-it-works/index.html": 4,
    "about/index.html": 5,
    "members/index.html": 6,
    "resources/index.html": 7,
    "404.html": 1,
}
REMOVED_PATHS = ["members/exercises", "members/documents", "docs", "search"]
SITE_DOMAIN = check_data.SITE_DOMAIN
FILES_AUTHOR = "Spokane County ARES-ACS"

STALE = ("goes out of date: the site is edited about once a year, so it must not say "
         "when something will happen or when it was last checked; say what is true all year, or leave it out")
EMPTY_ROLE = "leave an empty position out of facts.yaml instead of announcing it"
SCHEDULE = "schedules are kept on the members' group, not on the site"
# Removed wording, matched as whole words, ignoring case, against the page's
# text with all whitespace folded to one space and tags removed.
FORBIDDEN = {
    "schedule as of": STALE, "last reviewed": STALE, "being recovered": STALE,
    "new website": STALE, "this week": STALE, "next up": STALE,
    "later this season": STALE, "not posted yet": STALE, "coming soon": STALE,
    "posted soon": STALE, "available soon": STALE, "ready soon": STALE,
    "volunteer needed": EMPTY_ROLE, "open position": EMPTY_ROLE, "position open": EMPTY_ROLE,
    "net control schedule": SCHEDULE,
}
FORBIDDEN_RE = [(re.compile(r"(?<![\w-])" + re.escape(k).replace(r"\ ", r"\s+") + r"(?![\w-])", re.I), k, why)
                for k, why in FORBIDDEN.items()]
# "Next:" as a label, and "Soon" as a label on its own ("Soon", "(soon)", "Soon:").
LABELS = [(re.compile(r"(?i)\bnext:\s"), "Next:", STALE),
          (re.compile(r"(?i)\(soon\)"), "Soon", STALE)]
# Class and path tokens, matched in the raw HTML.
FORBIDDEN_RAW = ["needs-verify", "data-verify", "wp-block-navigation", "wp-content", "wp-includes"]
# Words that mark an unfilled position, inside the leadership tables.
PLACEHOLDER = check_data.PLACEHOLDER
FACTCHECK = ["147.300", "100 Hz", "8:00 PM", "Second Saturday", "Third Thursday",
             "1121 W Gardner Ave", "W7TSC", "info@spokares.org"]
GROUPS_IO = "https://spokaneares-acs.groups.io/g/main"
# Elements and attributes the site never uses; any of them is a sign of
# pasted or injected HTML.
BANNED_TAGS = {"base", "form", "iframe", "object", "embed", "animate", "set", "frame", "frameset",
               "applet", "portal"}
DANGEROUS_SCHEME = re.compile(r"^(?:javascript|vbscript|data):", re.I)

DASH = "\\-\u2010‑‒–—−"
SEP = f"[{DASH}.\\s]"
# North American numbers: area code and exchange start 2-9. (509) 555-1234,
# 509-555-1234, 509.555.1234, 509 555 1234, 509–555–1234, +1 509 555 1234,
# 5095551234 and 555-1234. Frequencies, offsets, times, years, ZIPs, form
# numbers and FCC Registration Numbers (0012345678) do not have these shapes.
PHONE = re.compile(
    rf"(?<![\d.])(?:\+?1{SEP}?)?(?:\([2-9]\d\d\)\s?|[2-9]\d\d{SEP})[2-9]\d\d{SEP}\d{{4}}(?![\d])"
    rf"|(?<![\d.])1?[2-9]\d\d[2-9]\d{{6}}(?!\d)"
    rf"|(?<![\d.{DASH}])[2-9]\d\d[{DASH}]\d{{4}}(?![\d{DASH}])"
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
NOT_EMAIL_TLDS = {"png", "jpg", "jpeg", "gif", "webp", "avif", "svg", "ico"}
# For the best-effort scan of PDF bytes: only addresses with a real-looking ending.
PDF_EMAIL = re.compile(rb"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})*"
                       rb"\.(?:com|org|net|gov|edu|mil|us|io|info|biz|co)\b")

MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?"
         r"|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
WEEKDAY = (r"(?:Mon(?:day)?|Tue(?:s(?:day)?)?|Wed(?:nesday)?|Thu(?:r(?:s(?:day)?)?)?|Fri(?:day)?"
           r"|Sat(?:urday)?|Sun(?:day)?)")
ORD = r"\d{1,2}(?:st|nd|rd|th)"
# Printed dates: "Sat, Oct 10", "November 7", "27 June", "Thursday the 18th",
# "the 21st this December", 2026-11-14, 2026.11.14, 11/14/2026, 12/18.
# Month + past year ("August 2023") and bare years are history, not dates.
DATE = re.compile(
    rf"\b{WEEKDAY},?\s+{MONTH}\.?\s+\d"
    rf"|\b{MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?![\d:])"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{MONTH}\b"
    rf"|\b{WEEKDAY}\s+(?:the\s+)?{ORD}\b"
    rf"|\b{ORD}\b[^.;!?|]{{0,25}}?\b{MONTH}\b"
    rf"|\b{MONTH}\b[^.;!?|]{{0,25}}?\b{ORD}\b"
    r"|\b\d{4}-\d{1,2}-\d{1,2}\b"
    r"|\b\d{4}\.\d{1,2}\.\d{1,2}\b"
    r"|(?<![\d/.])(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])(?:/(?:\d{4}|\d{2}))?(?![\d/])"
)
MONTH_YEAR = re.compile(rf"\b{MONTH}\.?,?\s+((?:19|20)\d\d)\b")
# A date is allowed only as a hosted file's version, written exactly as in
# facts.yaml, in the same block (list item, paragraph, table cell…) as a link
# to that file under /files/.
DATE_BLOCKS = {"li", "p", "td", "th", "dd", "dt", "figcaption", "caption",
               "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "div", "section",
               "main", "body"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}
TEXT_ATTRS = ("alt", "title", "aria-label", "placeholder", "data-copy-text")
CSS_URL = re.compile(r"""url\(\s*(['"]?)(.*?)\1\s*\)|@import\s+(['"])(.*?)\3""", re.S)


def norm(s):
    return re.sub(r"\s+", " ", s)


def context(text, m, width=45):
    a, b = max(0, m.start() - width), min(len(text), m.end() + width)
    return ("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else "")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.dup_ids, self.links, self.loads, self.text = set(), [], [], [], []
        self.attr_text = []   # attribute values people read or copy
        self.attr_all = []    # every attribute value (for the e-mail check)
        self.attr_phone = []  # attributes that could carry a phone number (not SVG geometry)
        self.banned = []      # (what, detail)
        self.styles = 0
        self.h1 = 0
        self.title = ""
        self.lang = None
        self.description = None
        self.robots = []
        self._in_title = False
        self._skip = 0
        self._stack = []          # open elements: [tag, block_id, is_roles]
        self._block = 0
        self.block_links = {}     # block_id -> hrefs inside it
        self.block_text = {}      # block_id -> its own text, for the date check
        self.roles_text = []      # text inside the leadership tables (figure.roles)

    def _blocks(self):
        return [b for _, b, _ in self._stack if b is not None]

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if a.get("id"):
            if a["id"] in self.ids:
                self.dup_ids.append(a["id"])
            self.ids.add(a["id"])
        if "style" in a:
            self.styles += 1
        if tag in BANNED_TAGS:
            self.banned.append((f"<{tag}>", ""))
        if tag == "meta" and "http-equiv" in a:
            self.banned.append(("<meta http-equiv>", a["http-equiv"]))
        for k, v in a.items():
            self.attr_all.append(v)
            if k.startswith("on"):
                self.banned.append((f"the event handler {k}=", v[:40]))
            clean = re.sub(r"[\s\x00-\x1f]", "", v)
            if DANGEROUS_SCHEME.match(clean) and not (k == "content" and tag == "meta"):
                self.banned.append((f"a {clean.split(':')[0].lower()}: value in {k}=", v[:40]))
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
            for b in self._blocks():
                self.block_links.setdefault(b, []).append(a["href"])
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
        roles = "roles" in a.get("class", "").split() or any(r for _, _, r in self._stack)
        self._block += 1
        self._stack.append([tag, self._block if tag in DATE_BLOCKS else None, roles])

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
            if self._stack and self._stack[-1][2]:
                self.roles_text.append(data)


def parse_args(argv):
    opts = {"root": None, "stage": 7, "base": "", "mode": "preview", "facts": None}
    it = iter(argv)
    for a in it:
        if a in ("--stage", "--base", "--facts"):
            v = next(it, None)
            if v is None:
                sys.exit(f"check_site.py: {a} needs a value. {USAGE}")
            if a == "--stage":
                if not (v.isdigit() and 1 <= int(v) <= 7):
                    sys.exit(f"check_site.py: --stage must be a number from 1 to 7, not {v!r}. {USAGE}")
                opts["stage"] = int(v)
            elif a == "--base":
                if v and not v.startswith("/"):
                    sys.exit(f"check_site.py: --base must start with a slash, like /spokares-static. {USAGE}")
                opts["base"] = v.rstrip("/")
            else:
                opts["facts"] = Path(v)
        elif a in ("--preview", "--live"):
            opts["mode"] = a[2:]
        elif a.startswith("-"):
            sys.exit(f"check_site.py: unknown option {a}. {USAGE}")
        elif opts["root"] is None:
            opts["root"] = Path(a)
        else:
            sys.exit(f"check_site.py: give one folder to check. {USAGE}")
    if opts["root"] is None:
        sys.exit(USAGE)
    if not opts["root"].is_dir():
        sys.exit(f"check_site.py: {opts['root']} is not a folder; build the site first. {USAGE}")
    if opts["facts"] is None:
        opts["facts"] = Path(__file__).resolve().parent.parent / "data" / "facts.yaml"
    return opts


def read_facts(path):
    """Returns (allowed e-mail addresses, {file name: version}, problems)."""
    try:
        facts = check_data.strip(check_data.load(path))
    except check_data.DataError as e:
        return set(), None, [f"cannot read the facts file: {e}"]
    problems, emails, files = [], set(), {}
    email = (facts.get("contact") or {}).get("email") if isinstance(facts.get("contact"), dict) else None
    if not isinstance(email, str) or not re.fullmatch(rf"[a-z0-9._%+-]+@{re.escape(SITE_DOMAIN)}", email):
        problems.append(f"{path}: contact.email must be an address at {SITE_DOMAIN}, not {email!r}")
    else:
        emails.add(email)
    for item in facts.get("files") or []:
        if isinstance(item, dict) and isinstance(item.get("file"), str):
            files[item["file"]] = item.get("version") if isinstance(item.get("version"), str) else ""
    return emails, files, problems


def docx_text(path):
    """Text and metadata of a Word file: (text, {creator, lastModifiedBy}, error)."""
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        return "", {}, "is not a readable Word document"
    out, meta = [], {}
    for n in z.namelist():
        if not re.fullmatch(r"word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml"
                            r"|word/_rels/[^/]+\.rels|docProps/[^/]+\.xml", n):
            continue
        t = z.read(n).decode("utf-8", "replace")
        if n == "docProps/core.xml":
            for k in ("dc:creator", "cp:lastModifiedBy"):
                m = re.search(rf"<{k}>([^<]*)</{k}>", t)
                meta[k] = html.unescape(m.group(1)).strip() if m else ""
        if n.endswith(".rels"):
            out.append(" ".join(unquote(x) for x in re.findall(r'Target="([^"]*)"', t)))
            continue
        t = re.sub(r"</w:p>|<w:br/>|<w:tab/>", "\n", t)
        out.append(html.unescape(re.sub(r"<[^>]+>", "", t)))
    return "\n".join(out), meta, None


def pdf_emails(path):
    """Best effort: e-mail addresses in a PDF's bytes and its deflated streams."""
    b = path.read_bytes()
    parts = [b]
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", b, re.S):
        try:
            parts.append(zlib.decompress(m.group(1)))
        except zlib.error:
            pass
    found = set()
    for p in parts:
        found |= {e.decode("ascii", "replace").lower() for e in PDF_EMAIL.findall(p)}
    return found


def main():
    o = parse_args(sys.argv[1:])
    root, stage, base, mode = o["root"], o["stage"], o["base"], o["mode"]
    problems = []
    pages = {}
    allowed_emails, files_listed, fp = read_facts(o["facts"])
    problems += fp
    versions = sorted({v for v in (files_listed or {}).values() if v}, key=len, reverse=True)
    this_year = datetime.date.today().year

    def local(path, where, what):
        """Strip the base path from an internal address; complain if it is missing."""
        if not base or not path.startswith("/"):
            return path
        if path == base or path.startswith(base + "/"):
            return path[len(base):] or "/"
        problems.append(f"{where}: {what} is not under {base}/: {path}")
        return path

    def own_file_link(href):
        u = urlparse(href.strip())
        if u.scheme or u.netloc or not u.path.startswith("/"):
            return False
        p = u.path[len(base):] if base and u.path.startswith(base + "/") else u.path
        return p.startswith("/files/")

    for rel, need in PAGES.items():
        if not (root / rel).is_file() and stage >= need:
            problems.append(f"missing page: {rel}")

    for f in sorted(root.rglob("*.html")):
        rel = f.relative_to(root).as_posix()
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append(f"{rel}: is not UTF-8 text")
            continue
        p = Page()
        p.feed(text)
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

    def dates_in(chunk):
        m = DATE.search(chunk)
        if m:
            return m
        for m in MONTH_YEAR.finditer(chunk):
            if int(m.group(1)) >= this_year:
                return m
        return None

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
        noindex = any("noindex" in r for r in p.robots)
        if mode == "preview" and not noindex:
            problems.append(f'{rel}: missing <meta name="robots" content="noindex"> (this is a preview build)')
        if mode == "live" and noindex:
            problems.append(f"{rel}: has noindex, but this is the live build; build with HUGO_PARAMS_PREVIEW=false")
        if p.styles:
            problems.append(f"{rel}: inline style (style= or <style>) found {p.styles} time(s)")
        for d in sorted(set(p.dup_ids)):
            problems.append(f'{rel}: the id "{d}" is used more than once on the page; ids must be unique')
        for what, detail in p.banned:
            problems.append(f"{rel}: {what} is not allowed on this site" + (f" ({detail})" if detail else ""))
        for rx, phrase, why in FORBIDDEN_RE + LABELS:
            m = rx.search(text)
            if m:
                problems.append(f'{rel}: "{context(text, m)}": "{m.group(0).strip(" |")}" {why}')
        for token in FORBIDDEN_RAW:
            if token in raw.lower():
                problems.append(f"{rel}: forbidden class or path {token!r} in the HTML")
        roles = norm(" ".join(p.roles_text))
        m = PLACEHOLDER.search(roles)
        if m:
            problems.append(f'{rel}: the leadership table says "{m.group(0)}"; {EMPTY_ROLE}')
        tels = [unquote(h[4:]) for h in p.links if h.lower().startswith("tel:")]
        for s in [norm(" ".join(p.text))] + p.attr_phone + tels:
            m = PHONE.search(s)
            if m:
                problems.append(f"{rel}: something that looks like a phone number: {m.group(0)!r}")
                break
        found = emails(html.unescape(raw)) | emails(" ".join(p.attr_all))
        for h in p.links:
            found |= emails(unquote(h))
        for e in sorted(found - allowed_emails):
            problems.append(f"{rel}: e-mail address not allowed: {e}")
        for block, chunk in p.block_text.items():
            chunk = norm(chunk)
            if re.fullmatch(r"\W*soon\W*", chunk, re.I):
                problems.append(f'{rel}: "{chunk.strip()}" as a label {STALE}')
            if any(own_file_link(h) for h in p.block_links.get(block, [])):
                for v in versions:
                    chunk = chunk.replace(v, " ")
            m = dates_in(chunk)
            if m:
                problems.append(f"{rel}: printed date {m.group(0)!r} in \"{context(chunk, m)}\" "
                                "(meetings are rules only; a date may appear only as a hosted file's version)")
        m = dates_in(norm(" ".join(p.attr_text)))
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
        problems.append(f"expected exactly one groups.io link (on /members/), found {groups_links}")

    # Hosted files: exactly the ones listed in facts.yaml, and nothing personal in them.
    fdir = root / "files"
    shipped = {f.name for f in fdir.iterdir() if f.is_file()} if fdir.is_dir() else set()
    if files_listed is not None:
        for name in sorted(shipped - set(files_listed)):
            listed = ", ".join(sorted(files_listed)) or "none"
            problems.append(f"files/{name} is not listed under files in facts.yaml; a replacement must keep "
                            f"the listed name ({listed}), so delete this upload or rename it")
        for name in sorted(set(files_listed) - shipped):
            problems.append(f"files/{name} is listed in facts.yaml but missing from site/static/files/; "
                            "upload it with exactly that name")
    for name in sorted(shipped):
        f = fdir / name
        if name.lower().endswith(".docx"):
            text, meta, err = docx_text(f)
            if err:
                problems.append(f"files/{name}: {err}")
                continue
            for e in sorted(emails(text) - allowed_emails):
                problems.append(f"files/{name}: e-mail address not allowed: {e}")
            m = PHONE.search(norm(text))
            if m:
                problems.append(f"files/{name}: something that looks like a phone number: {m.group(0)!r}")
            for k, v in meta.items():
                if v not in ("", FILES_AUTHOR):
                    problems.append(f"files/{name}: the document's {k} is {v!r}; set it to {FILES_AUTHOR!r} "
                                    "or empty (in Word: File, Info, Properties)")
        elif name.lower().endswith(".pdf"):
            for e in sorted(pdf_emails(f) - allowed_emails):
                problems.append(f"files/{name}: e-mail address not allowed: {e}")

    for f in sorted(root.rglob("*.css")):
        rel = f.relative_to(root).as_posix()
        css = re.sub(r"/\*.*?\*/", "", f.read_text(encoding="utf-8", errors="replace"), flags=re.S)
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
