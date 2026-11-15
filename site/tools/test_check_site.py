#!/usr/bin/env python3
"""Self-test for check_site.py. Standard library only.

Run: python3 site/tools/test_check_site.py   (or python3 -m unittest from site/tools)

Each test builds a small site tree in a temporary directory and runs the
checker on it as a subprocess, the way CI does. The "Bad" tests prove that a
problem the checker must catch makes it fail; the "Good" tests prove that
content this site legitimately contains passes.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).with_name("check_site.py")

CSS = """@font-face{font-family:"X";src:url('../fonts/x.woff2') format('woff2');}
:root{--i:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3C/svg%3E");}
"""


def page(body, title="Page", description="A page.", head_extra="", robots=True):
    robots_tag = '<meta name="robots" content="noindex">' if robots else ""
    return (
        '<!doctype html>\n<html lang="en-US">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        f'<meta name="description" content="{description}">\n{robots_tag}\n'
        '<link rel="stylesheet" href="/css/site.css">\n'
        '<link rel="icon" href="/img/seal.png" type="image/png">\n'
        '<script src="/js/menu.js" defer></script>\n'
        f"{head_extra}</head>\n<body>\n<h1>{title}</h1>\n{body}\n</body>\n</html>\n"
    )


class Site:
    """A minimal built site: 404.html, index.html and the assets they load."""

    def __init__(self, tmp):
        self.root = Path(tmp)
        self.write("404.html", page('<p>Not here. <a href="/">Home</a></p>', "Page not found"))
        self.write("index.html", page("<p>Welcome.</p>", "Home"))
        self.write("css/site.css", CSS)
        self.write("fonts/x.woff2", "")
        self.write("img/seal.png", "")
        self.write("img/seal@2x.png", "")
        self.write("js/menu.js", "")

    def write(self, rel, text):
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    def run(self, *args):
        r = subprocess.run(
            [sys.executable, str(CHECKER), str(self.root), *args],
            capture_output=True, text=True,
        )
        return r.returncode, r.stdout + r.stderr


class Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.site = Site(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def assertFails(self, needle=None, *args):
        code, out = self.site.run("--stage", "1", *args)
        self.assertEqual(code, 1, f"expected the checker to fail; output:\n{out}")
        if needle:
            self.assertIn(needle, out)
        return out

    def assertPasses(self, *args):
        code, out = self.site.run("--stage", "1", *args)
        self.assertEqual(code, 0, f"expected the checker to pass; output:\n{out}")

    def body(self, html, rel="index.html", **kw):
        self.site.write(rel, page(html, **kw))


class Baseline(Case):
    def test_minimal_site_passes(self):
        self.assertPasses()


# ---------------------------------------------------------------- Important 1
class Bad1ForbiddenWording(Case):
    """Removed wording is found across line breaks, entities, tags and case."""

    def test_split_by_line_break(self):
        self.body("<p>This\nweek on the net</p>")
        self.assertFails("forbidden")

    def test_split_by_nbsp_entity(self):
        self.body("<p>Open&nbsp;position</p>")
        self.assertFails("forbidden")

    def test_split_by_tag(self):
        self.body("<p><span>Open</span> position</p>")
        self.assertFails("forbidden")

    def test_next_colon_across_line_break(self):
        self.body("<p>Next:\nthe 12th</p>")
        self.assertFails("forbidden")

    def test_lowercase_coming_soon(self):
        self.body("<p>Photos coming soon</p>")
        self.assertFails("forbidden")

    def test_in_meta_description(self):
        self.body("<p>Hi</p>", description="Volunteer needed for the net")
        self.assertFails("forbidden")

    def test_class_token_in_raw_html(self):
        self.body('<p class="needs-verify">Hi</p>')
        self.assertFails("forbidden")


# ---------------------------------------------------------------- Important 2
class Bad2EveryPage(Case):
    """Every *.html file is checked, not only the six named pages."""

    def test_extra_page_with_forbidden_wording(self):
        self.body("<p>Open position</p>", rel="extra/index.html")
        self.assertFails("extra/index.html")

    def test_extra_page_with_personal_email(self):
        self.body("<p>Write to joe@gmail.com</p>", rel="extra/index.html")
        self.assertFails("joe@gmail.com")

    def test_extra_page_with_broken_link(self):
        self.body('<p><a href="/nowhere/">x</a></p>', rel="extra/index.html")
        self.assertFails("broken internal link")


# ---------------------------------------------------------------- Important 3
class Bad3ThirdPartyLoads(Case):
    def test_srcset_external(self):
        self.body('<img alt="" src="/img/seal.png" srcset="https://evil.example/x.png 2x, /img/seal.png 3x">')
        self.assertFails("third-party load")

    def test_srcset_missing_local(self):
        self.body('<img alt="" src="/img/seal.png" srcset="/img/seal.png 1x, /img/nope.png 3x">')
        self.assertFails("missing asset")

    def test_rel_token_list(self):
        self.body("<p>x</p>", head_extra='<link rel="stylesheet preload" href="https://fonts.googleapis.com/css">\n')
        self.assertFails("third-party load")

    def test_link_manifest(self):
        self.body("<p>x</p>", head_extra='<link rel="manifest" href="https://evil.example/m.json">\n')
        self.assertFails("third-party load")

    def test_link_apple_touch_icon(self):
        self.body("<p>x</p>", head_extra='<link rel="apple-touch-icon" href="https://evil.example/i.png">\n')
        self.assertFails("third-party load")

    def test_video_poster(self):
        self.body('<video poster="https://evil.example/p.jpg"></video>')
        self.assertFails("third-party load")

    def test_object_data(self):
        self.body('<object data="https://evil.example/x.svg"></object>')
        self.assertFails("third-party load")

    def test_embed_src(self):
        self.body('<embed src="https://evil.example/x.swf">')
        self.assertFails("third-party load")

    def test_protocol_relative_load(self):
        self.body('<img alt="" src="//evil.example/x.png">')
        self.assertFails("third-party load")

    def test_css_import(self):
        self.site.write("css/site.css", CSS + '@import url("https://fonts.googleapis.com/css2");\n')
        self.assertFails("css/site.css")

    def test_css_url_external(self):
        self.site.write("css/site.css", CSS + ".x{background:url(https://evil.example/b.png)}\n")
        self.assertFails("css/site.css")

    def test_css_url_root_relative(self):
        self.site.write("css/site.css", CSS + ".x{background:url('/img/seal.png')}\n")
        self.assertFails("css/site.css")

    def test_css_url_missing_file(self):
        self.site.write("css/site.css", CSS + ".x{background:url(../img/nope.png)}\n")
        self.assertFails("css/site.css")


class Bad3PhonesAndEmails(Case):
    def test_tel_link(self):
        self.body('<p><a href="tel:+15095551234">Call</a></p>')
        self.assertFails("phone")

    def test_en_dashes(self):
        self.body("<p>Call 509–555–1234</p>")
        self.assertFails("phone")

    def test_no_separators(self):
        self.body("<p>Call 5095551234</p>")
        self.assertFails("phone")

    def test_parentheses_and_nbsp(self):
        self.body("<p>Call (509)&nbsp;555-1234</p>")
        self.assertFails("phone")

    def test_phone_in_attribute(self):
        self.body('<p><button data-copy-text="509-555-1234">Copy</button></p>')
        self.assertFails("phone")

    def test_entity_encoded_email(self):
        self.body("<p>joe&#64;gmail.com</p>")
        self.assertFails("joe@gmail.com")

    def test_percent_encoded_mailto(self):
        self.body('<p><a href="mailto:joe%40gmail.com">Write</a></p>')
        self.assertFails("joe@gmail.com")


# ---------------------------------------------------------------- Important 4
class Bad4RelativeLinks(Case):
    def test_relative_href(self):
        self.site.write("members/index.html", page("<p>m</p>", "Members"))
        self.body('<p><a href="members/">Members</a></p>', rel="about/index.html")
        self.assertFails("relative")

    def test_relative_href_dot(self):
        self.body('<p><a href="./">Here</a></p>', rel="about/index.html")
        self.assertFails("relative")

    def test_relative_src(self):
        self.body('<img alt="" src="img/seal.png">')
        self.assertFails("relative")

    def test_relative_under_base(self):
        base = "/spokares-static"
        html = page(f'<p><a href="{base}/">Home</a> <a href="about/">About</a></p>').replace(
            'href="/', f'href="{base}/').replace('src="/', f'src="{base}/')
        self.site.write("index.html", html)
        self.site.write("404.html", page(f'<p><a href="{base}/">Home</a></p>').replace(
            'href="/', f'href="{base}/').replace('src="/', f'src="{base}/'))
        self.site.write("about/index.html", page("<p>a</p>").replace(
            'href="/', f'href="{base}/').replace('src="/', f'src="{base}/'))
        self.assertFails("relative", "--base", base)


# ---------------------------------------------------------------- Minor items
class BadMinor(Case):
    def test_style_attribute(self):
        self.body('<p style="color:red">x</p>')
        self.assertFails("style")

    def test_style_element(self):
        self.body("<p>x</p>", head_extra="<style>p{color:red}</style>\n")
        self.assertFails("style")

    def test_highlight_inline_style(self):
        self.body('<pre tabindex="0" style="color:#f8f8f2;background-color:#272822;"><code>x</code></pre>')
        self.assertFails("style")

    def test_groups_io_mixed_case_host(self):
        self.body('<p><a href="https://SpokaneARES-ACS.Groups.IO/g/main">group</a></p>')
        self.assertFails("groups.io")

    def test_ag7qp_mixed_case_host(self):
        self.body('<p><a href="https://AG7QP.com/x">x</a></p>')
        self.assertFails("ag7qp.com")

    def test_javascript_href(self):
        self.body('<p><a href="javascript:alert(1)">x</a></p>')
        self.assertFails("javascript")

    def test_missing_noindex(self):
        self.body("<p>x</p>", robots=False)
        self.assertFails("noindex")

    def test_sitemap_present(self):
        self.site.write("sitemap.xml", "<urlset/>")
        self.assertFails("sitemap")

    def test_empty_meta_description(self):
        self.body("<p>x</p>", description="")
        self.assertFails("description")

    def test_date_weekday_month_day(self):
        self.body("<p>Next meeting Sat, Oct 10</p>")
        self.assertFails("date")

    def test_date_month_day_year(self):
        self.body("<p>The workshop is on November 7, 2026.</p>")
        self.assertFails("date")

    def test_date_month_day(self):
        self.body("<p>Field Day is June 27 this year.</p>")
        self.assertFails("date")

    def test_date_day_month(self):
        self.body("<p>Field Day is 27 June this year.</p>")
        self.assertFails("date")

    def test_date_iso(self):
        self.body("<p>Updated 2026-11-14</p>")
        self.assertFails("date")

    def test_date_numeric(self):
        self.body("<p>Updated 11/14/2026</p>")
        self.assertFails("date")

    def test_date_beside_unrelated_link(self):
        self.body('<p><a href="/">Home</a> was updated November 7, 2024.</p>')
        self.assertFails("date")

    def test_email_inside_word_still_checked(self):
        self.body("<p>Write to bob@example.org.</p>")
        self.assertFails("bob@example.org")


# ---------------------------------------------------------------- legitimate content
GOOD_HOME = """
<div class="netbox" id="weekly-net">
<p>Tuesday at 8:00 PM on W7GBU, 147.300 MHz, &#43;600 kHz offset, tone 100 Hz.</p>
<button class="btn" data-copy-text="147.300 MHz +600 kHz 100 Hz">Copy</button>
<p>Alternate 146.880 MHz, -600 kHz, tone 123 Hz. Weather radio WXL86, 162.400 MHz.</p>
</div>
<ul class="meetings">
<li><span><strong>Second Saturday Workshop:</strong> Second Saturday of each month, 9:00 AM to noon; then a Winlink workshop, 12:30 to 3:30 PM.</span></li>
<li><span><strong>Third Thursday training meeting:</strong> Third Thursday of each month, 6:00 PM.</span></li>
</ul>
<p><strong>In person</strong> at Spokane County Emergency Management, 1121 W Gardner Ave, Spokane, WA 99260.</p>
<p>Take FEMA IS-100.c and IS-700.b; send traffic on an ICS 213. As soon as you are licensed, come to the net.
A monsoon of messages; the soonest check-in is welcome.</p>
<p>Questions? Write to <a href="mailto:info@spokares.org">info@spokares.org</a>. Or write to info@spokares.org.</p>
<img alt="" src="/img/seal.png" srcset="/img/seal.png 1x, /img/seal@2x.png 2x">
<p><a href="#weekly-net">Net settings</a> <a href="https://www.arrl.org/">ARRL</a></p>
"""

GOOD_ABOUT = """
<h2 id="history">History</h2>
<ul class="timeline">
<li>1999: the county radio room opens.</li>
<li>2004: W7GBU is licensed.</li>
<li>August 2023: the unit joins ACS.</li>
<li>Spring 2024 and July 2024: new task books.</li>
</ul>
<h2 id="ares-path">Joining</h2>
<p>Fill in the <a href="/files/ares-application.docx">ARES application</a> (November 7, 2024 version) and send it in.</p>
<p><a href="/files/acs-task-book.docx">ACS task book</a> <span class="meta">Word, August 9, 2024</span></p>
<h2 id="contact">Contact</h2>
<p>Write to info@spokares.org.</p>
"""

GOOD_MEMBERS = """
<ul class="doc-list">
<li><a href="/files/ares-application.docx">ARES application</a> <span class="meta">Word, November 7, 2024</span></li>
<li><a href="/files/acs-task-book.docx">ACS task book</a> <span class="meta">Word, August 9, 2024</span></li>
<li><a href="/files/arrl-ares-task-book.pdf">ARRL ARES Task Book</a> <span class="meta">PDF, July 2024</span></li>
</ul>
<p><a href="https://spokaneares-acs.groups.io/g/main">Spokane ARES-ACS on groups.io</a></p>
"""


class GoodContent(Case):
    def setUp(self):
        super().setUp()
        self.site.write("index.html", page(GOOD_HOME, "Home"))
        self.site.write("about/index.html", page(GOOD_ABOUT, "About"))
        self.site.write("members/index.html", page(GOOD_MEMBERS, "For members"))
        for f in ("ares-application.docx", "acs-task-book.docx", "arrl-ares-task-book.pdf"):
            self.site.write(f"files/{f}", "")

    def test_legitimate_content_passes(self):
        self.assertPasses()

    def test_legitimate_content_passes_under_base(self):
        base = "/spokares-static"
        for f in self.site.root.rglob("*.html"):
            t = f.read_text(encoding="utf-8")
            t = t.replace('href="/', f'href="{base}/').replace('src="/', f'src="{base}/')
            t = t.replace('srcset="/img/seal.png 1x, /img/', f'srcset="{base}/img/seal.png 1x, {base}/img/')
            f.write_text(t, encoding="utf-8")
        self.assertPasses("--base", base)

    def test_unprefixed_build_fails_under_base(self):
        self.assertFails("not under /spokares-static/", "--base", "/spokares-static")


if __name__ == "__main__":
    unittest.main(verbosity=2)
