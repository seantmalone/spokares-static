#!/usr/bin/env python3
"""Reports on every outside link in the built site.

Usage: check_links.py <public-dir> [--strict]

Fetches each http(s) link found in an <a href> on any page (GET, following
redirects) and prints one line per link:

  ok           the page loaded
  ok (moved)   the page loaded at another address (shown after "->")
  CHECK        the site refused an automated request (401, 403 or 429);
               open it by hand in a private window
  SIGN-IN      the link ends on a sign-in page
  FAIL         the page did not load (error code, timeout, unknown host,
               or a redirect to a "page not found" page)

The members' group link on /members/ is expected to ask members to sign in.
Standard library only. Exits 0 unless --strict is given and a link is FAIL or
SIGN-IN (CHECK never fails the run: it needs a person to look).
"""
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# A generic browser identity. Some government sites refuse unknown clients.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
TIMEOUT = 25
ALLOWED_SIGN_IN = {"https://spokaneares-acs.groups.io/g/main"}
MANUAL = {401, 403, 429}
# A final address that looks like a sign-in page.
LOGIN_PATH = re.compile(
    r"(^|/)(log-?in|sign-?in|sign_in|signon|auth|sso|oauth2?|saml|account/login|"
    r"users/sign_in|cas/login)(/|$|\.)", re.I)
LOGIN_HOSTS = ("accounts.google.com", "login.microsoftonline.com", "login.live.com",
               "auth0.com", "okta.com", "login.gov")
# A redirect that lands on a "page not found" page (some sites answer 200).
ERROR_PAGE = re.compile(r"error-?404|/404(/|\.|$)|not-?found|/error(/|\.|$)", re.I)
LOGIN_QUERY = {"returnurl", "return_to", "redirect_uri", "next", "continue"}


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = (dict(attrs).get("href") or "").strip()
            if urlparse(href).scheme.lower() in ("http", "https"):
                self.found.append(href)


def is_sign_in(final):
    u = urlparse(final)
    host = (u.hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in LOGIN_HOSTS):
        return True
    if LOGIN_PATH.search(u.path):
        return True
    keys = {k.lower() for k in parse_qs(u.query)}
    return bool(keys & LOGIN_QUERY) and re.search(r"log|sign|auth", u.path, re.I) is not None


def fetch(url):
    """Returns (status, final address or error text). Status 0 = no answer."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
    })
    last = None
    for _ in range(2):  # one retry for a timeout or a dropped connection
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                r.read(65536)
                return r.status, r.geturl()
        except urllib.error.HTTPError as e:
            return e.code, e.geturl() or url
        except Exception as e:  # DNS, TLS, timeout, reset
            last = f"{type(e).__name__}: {e}"
    return 0, last


def verdict(url, status, final):
    if url in ALLOWED_SIGN_IN:
        return "ok (members' group)", False
    if status == 0:
        return "FAIL (no answer)", True
    if status in MANUAL:
        return f"CHECK {status}", False
    if status >= 400:
        return f"FAIL {status}", True
    if is_sign_in(final):
        return "SIGN-IN", True
    if ERROR_PAGE.search(urlparse(final).path) and not ERROR_PAGE.search(urlparse(url).path):
        return "FAIL (error page)", True
    if final.rstrip("/") != url.rstrip("/"):
        return "ok (moved)", False
    return "ok", False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    root = Path(args[0])
    strict = "--strict" in sys.argv
    found = {}
    for f in sorted(root.rglob("*.html")):
        p = Links()
        p.feed(f.read_text(encoding="utf-8"))
        for url in p.found:
            found.setdefault(url, f.relative_to(root).as_posix())
    urls = sorted(found)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(fetch, urls))
    problems = manual = 0
    for url, (status, final) in zip(urls, results):
        word, bad = verdict(url, status, final)
        problems += bad
        manual += word.startswith("CHECK")
        note = ""
        if status == 0:
            note = f" ({final})"
        elif final and final.rstrip("/") != url.rstrip("/"):
            note = f" -> {final}"
        if url.startswith("http://"):
            note += " (not https)"
        print(f"{word:20} {url}  [{found[url]}]{note}")
    print(f"{len(urls)} links, {problems} problem(s), {manual} to check by hand")
    sys.exit(1 if strict and problems else 0)


if __name__ == "__main__":
    main()
