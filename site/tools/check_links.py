#!/usr/bin/env python3
"""Reports on every outside link in the built site.

Usage: check_links.py <public-dir> [--strict] [--max-seconds N]

Fetches each http(s) link found in an <a href> on any page (GET, following
redirects) and prints one line per link:

  ok           the page loaded
  ok (moved)   the page loaded at another address (shown after "->")
  CHECK        the site refused an automated request (401, 403 or 429, or a
               Cloudflare "Just a moment..." check), or there was no time left
               to try it; open it by hand in a private window
  SIGN-IN      the link ends on a sign-in page
  FAIL         the page did not load (error code, timeout, unknown host,
               or a redirect to a "page not found" page)

The members' group link on /members/ is expected to ask members to sign in.
In GitHub Actions each FAIL and SIGN-IN is also printed as a ::warning:: so
it shows on the run's summary page. The whole report stops after
--max-seconds (default 150); links not tried by then are reported CHECK.

Standard library only. Exits 0 unless --strict is given and a link is FAIL or
SIGN-IN (CHECK never fails the run: it needs a person to look).
"""
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote, urlsplit, urlunsplit

# A generic browser identity. Some government sites refuse unknown clients.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
TIMEOUT = 20
MAX_SECONDS = 150
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
# Cloudflare's browser check: the page a script gets instead of the real one.
CHALLENGE = re.compile(rb"<title>\s*Just a moment\.\.\.\s*</title>|cf-browser-verification|"
                       rb"challenges\.cloudflare\.com/cdn-cgi/challenge-platform|_cf_chl_opt", re.I)


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = (dict(attrs).get("href") or "").strip()
            if urlparse(href).scheme.lower() in ("http", "https"):
                self.found.append(href)


def ascii_url(url):
    """Percent-encodes anything outside ASCII (and spaces) so urllib can send it."""
    s = urlsplit(url)
    try:
        host = s.hostname.encode("idna").decode("ascii") if s.hostname else ""
    except UnicodeError:
        host = s.hostname or ""
    netloc = host + (f":{s.port}" if s.port else "")
    safe = "/%:@!$&'()*+,;=-._~"
    return urlunsplit((s.scheme, netloc, quote(s.path, safe=safe), quote(s.query, safe=safe + "?"),
                       quote(s.fragment, safe=safe)))


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
    """Returns (status, final address or error text, challenged). Status 0 = no answer."""
    try:
        req = urllib.request.Request(ascii_url(url), headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
        })
    except ValueError as e:
        return 0, f"bad address: {e}", False
    last = None
    for _ in range(2):  # one retry for a timeout or a dropped connection
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = r.read(65536)
                challenged = bool(r.headers.get("cf-mitigated")) or bool(CHALLENGE.search(body))
                return r.status, r.geturl(), challenged
        except urllib.error.HTTPError as e:
            try:
                body = e.read(65536)
            except Exception:
                body = b""
            challenged = bool(e.headers.get("cf-mitigated")) or bool(CHALLENGE.search(body))
            return e.code, e.geturl() or url, challenged
        except Exception as e:  # DNS, TLS, timeout, reset
            last = f"{type(e).__name__}: {e}"
    return 0, last, False


def verdict(url, status, final, challenged=False):
    if url in ALLOWED_SIGN_IN:
        return "ok (members' group)", False
    if status is None:
        return "CHECK (time limit)", False
    if status == 0:
        return "FAIL (no answer)", True
    if challenged:
        return "CHECK (Cloudflare)", False
    if status in MANUAL:
        return f"CHECK {status}", False
    if status >= 400:
        return f"FAIL {status}", True
    if is_sign_in(final):
        return "SIGN-IN", True
    if ERROR_PAGE.search(urlparse(final).path) and not ERROR_PAGE.search(urlparse(url).path):
        return "FAIL (error page)", True
    if final.rstrip("/") != url.rstrip("/") and final.rstrip("/") != ascii_url(url).rstrip("/"):
        return "ok (moved)", False
    return "ok", False


def main():
    argv = sys.argv[1:]
    max_seconds = MAX_SECONDS
    if "--max-seconds" in argv:
        i = argv.index("--max-seconds")
        try:
            max_seconds = float(argv[i + 1])
        except (IndexError, ValueError):
            sys.exit("check_links.py: --max-seconds needs a number. " + __doc__.splitlines()[2])
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    unknown = [a for a in argv if a.startswith("--") and a != "--strict"]
    if len(args) != 1 or unknown or not Path(args[0]).is_dir():
        sys.exit(__doc__.splitlines()[2].strip())
    root = Path(args[0])
    strict = "--strict" in argv
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    found = {}
    for f in sorted(root.rglob("*.html")):
        p = Links()
        p.feed(f.read_text(encoding="utf-8", errors="replace"))
        for url in p.found:
            found.setdefault(url, f.relative_to(root).as_posix())
    urls = sorted(found)
    start = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=6)
    futures = [pool.submit(fetch, u) for u in urls]
    wait(futures, timeout=max_seconds)
    results = [f.result() if f.done() else (None, "", False) for f in futures]
    pool.shutdown(wait=False, cancel_futures=True)
    problems = manual = 0
    for url, (status, final, challenged) in zip(urls, results):
        word, bad = verdict(url, status, final, challenged)
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
        if bad and in_actions:
            print(f"::warning title=Outside link {word}::{url} on {found[url]}: {word}{note}. "
                  "Fix or remove it in site/data/resources.yaml or the page that has it.")
    took = time.monotonic() - start
    print(f"{len(urls)} links, {problems} problem(s), {manual} to check by hand ({took:.0f} s)")
    sys.stdout.flush()
    # Threads still waiting on a slow site must not hold the run open.
    os._exit(1 if strict and problems else 0)


if __name__ == "__main__":
    main()
