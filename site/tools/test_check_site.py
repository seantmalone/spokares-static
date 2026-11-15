#!/usr/bin/env python3
"""Self-test for check_site.py. Standard library only.

Run: python3 site/tools/test_check_site.py   (or python3 -m unittest from site/tools)

Each test builds a small site tree in a temporary directory and runs the
checker on it as a subprocess, the way CI does. The "Bad" tests prove that a
problem the checker must catch makes it fail; the "Good" tests prove that
content this site legitimately contains passes.
"""
import io
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

CHECKER = Path(__file__).with_name("check_site.py")

CSS = """@font-face{font-family:"X";src:url('../fonts/x.woff2') format('woff2');}
:root{--i:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3C/svg%3E");}
"""

FACTS = """# test facts
contact:
  email: "info@spokares.org"
files:
  - id: "ares-application"
    title: "ARES application"
    file: "ares-application.docx"
    kind: "Word document"
    version: "November 7, 2024"
  - id: "acs-task-book"
    title: "ACS task book"
    file: "acs-task-book.docx"
    kind: "Word document"
    version: "August 9, 2024"
  - id: "arrl-ares-task-book"
    title: "ARRL ARES Task Book"
    file: "arrl-ares-task-book.pdf"
    kind: "PDF"
    version: "July 2024"
"""


def docx(text="Phone: ________  Email: ________", creator="Spokane County ARES-ACS", modified="", rels="",
         body="", parts=None, company=""):
    """A small Word file: one paragraph of text, the two author fields, and any
    extra XML in the body or extra parts ({name: xml})."""
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for name, xml in (parts or {}).items():
            z.writestr(name, xml)
        z.writestr("docProps/app.xml", f"<Properties><Company>{company}</Company></Properties>")
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f"<w:document><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p>{body}</w:body></w:document>")
        z.writestr("word/_rels/document.xml.rels", f"<Relationships>{rels}</Relationships>")
        z.writestr("docProps/core.xml", f"<cp:coreProperties><dc:creator>{creator}</dc:creator>"
                                        f"<cp:lastModifiedBy>{modified}</cp:lastModifiedBy></cp:coreProperties>")
    return b.getvalue()


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


MEMBERS = """<ul class="lines">
<li><a href="/files/ares-application.docx">ARES application</a><span class="doc-note">Word document, November 7, 2024</span></li>
<li><a href="/files/acs-task-book.docx">ACS task book</a><span class="doc-note">Word document, August 9, 2024</span></li>
<li><a href="/files/arrl-ares-task-book.pdf">ARRL ARES Task Book</a><span class="doc-note">PDF, July 2024</span></li>
</ul>
<p><a href="https://spokaneares-acs.groups.io/g/main">Members' group on groups.io</a></p>
"""


class Site:
    """A complete small built site: the six named pages, their assets, the two
    hosted files and a facts file. It passes the checker as it is."""

    def __init__(self, tmp):
        self.root = Path(tmp) / "public"
        self.facts = Path(tmp) / "facts.yaml"
        self.facts.write_text(FACTS, encoding="utf-8")
        self.write("404.html", page('<p>Not here. <a href="/">Home</a></p>', "Page not found"))
        self.write("index.html", page("<p>Welcome.</p>", "Home"))
        self.write("how-it-works/index.html", page("<p>How.</p>", "How it works"))
        self.write("about/index.html", page('<h2 id="contact">Contact</h2>', "About"))
        self.write("members/index.html", page(MEMBERS, "For members"))
        self.write("resources/index.html", page('<h2 id="forms">Forms</h2>', "Resources"))
        self.write("css/site.css", CSS)
        self.write("fonts/x.woff2", "")
        self.write("img/seal.png", "")
        self.write("img/seal@2x.png", "")
        self.write("js/menu.js", "")
        self.write_bytes("files/ares-application.docx", docx())
        self.write_bytes("files/acs-task-book.docx", docx("Level 1 New Member"))
        self.write_bytes("files/arrl-ares-task-book.pdf", b"%PDF-1.7\n% a form\n%%EOF\n")

    def write(self, rel, text):
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    def write_bytes(self, rel, data):
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)

    def run(self, *args, facts=True):
        extra = ["--facts", str(self.facts)] if facts else []
        r = subprocess.run(
            [sys.executable, str(CHECKER), str(self.root), *extra, *args],
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
        code, out = self.site.run(*args)
        self.assertEqual(code, 1, f"expected the checker to fail; output:\n{out}")
        self.assertNotIn("Traceback", out)
        if needle:
            self.assertIn(needle, out)
        return out

    def assertPasses(self, *args):
        code, out = self.site.run(*args)
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
        self.assertFails('"This\nweek" goes out of date'.replace("\n", " "))

    def test_split_by_nbsp_entity(self):
        self.body("<p>Open&nbsp;position</p>")
        self.assertFails('"Open position" leave an empty position out')

    def test_split_by_tag(self):
        self.body("<p><span>Open</span> position</p>")
        self.assertFails('"Open position" leave an empty position out')

    def test_next_colon_across_line_break(self):
        self.body("<p>Next:\nthe 12th</p>")
        self.assertFails('"Next:" goes out of date')

    def test_lowercase_coming_soon(self):
        self.body("<p>Photos coming soon</p>")
        self.assertFails('"coming soon" goes out of date')

    def test_in_meta_description(self):
        self.body("<p>Hi</p>", description="Volunteer needed for the net")
        self.assertFails('"Volunteer needed" leave an empty position out')

    def test_class_token_in_raw_html(self):
        self.body('<p class="needs-verify">Hi</p>')
        self.assertFails("forbidden class or path 'needs-verify'")


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
        self.assertFails("third-party load ")

    def test_srcset_missing_local(self):
        self.body('<img alt="" src="/img/seal.png" srcset="/img/seal.png 1x, /img/nope.png 3x">')
        self.assertFails("missing asset")

    def test_rel_token_list(self):
        self.body("<p>x</p>", head_extra='<link rel="stylesheet preload" href="https://fonts.googleapis.com/css">\n')
        self.assertFails("third-party load ")

    def test_link_manifest(self):
        self.body("<p>x</p>", head_extra='<link rel="manifest" href="https://evil.example/m.json">\n')
        self.assertFails("third-party load ")

    def test_link_apple_touch_icon(self):
        self.body("<p>x</p>", head_extra='<link rel="apple-touch-icon" href="https://evil.example/i.png">\n')
        self.assertFails("third-party load ")

    def test_video_poster(self):
        self.body('<video poster="https://evil.example/p.jpg"></video>')
        self.assertFails("third-party load ")

    def test_object_data(self):
        self.body('<object data="https://evil.example/x.svg"></object>')
        self.assertFails("third-party load ")

    def test_embed_src(self):
        self.body('<embed src="https://evil.example/x.swf">')
        self.assertFails("third-party load ")

    def test_protocol_relative_load(self):
        self.body('<img alt="" src="//evil.example/x.png">')
        self.assertFails("third-party load ")

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
        self.assertFails("looks like a phone number")

    def test_en_dashes(self):
        self.body("<p>Call 509–555–1234</p>")
        self.assertFails("looks like a phone number")

    def test_no_separators(self):
        self.body("<p>Call 5095551234</p>")
        self.assertFails("looks like a phone number")

    def test_parentheses_and_nbsp(self):
        self.body("<p>Call (509)&nbsp;555-1234</p>")
        self.assertFails("looks like a phone number")

    def test_phone_in_attribute(self):
        self.body('<p><button data-copy-text="509-555-1234">Copy</button></p>')
        self.assertFails("looks like a phone number")

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
        self.assertFails("relative ")

    def test_relative_href_dot(self):
        self.body('<p><a href="./">Here</a></p>', rel="about/index.html")
        self.assertFails("relative ")

    def test_relative_src(self):
        self.body('<img alt="" src="img/seal.png">')
        self.assertFails("relative ")

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
        self.assertFails("inline style")

    def test_style_element(self):
        self.body("<p>x</p>", head_extra="<style>p{color:red}</style>\n")
        self.assertFails("inline style")

    def test_highlight_inline_style(self):
        self.body('<pre tabindex="0" style="color:#f8f8f2;background-color:#272822;"><code>x</code></pre>')
        self.assertFails("inline style")

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
        self.assertFails("printed date")

    def test_date_month_day_year(self):
        self.body("<p>The workshop is on November 7, 2026.</p>")
        self.assertFails("printed date")

    def test_date_month_day(self):
        self.body("<p>Field Day is June 27 this year.</p>")
        self.assertFails("printed date")

    def test_date_day_month(self):
        self.body("<p>Field Day is 27 June this year.</p>")
        self.assertFails("printed date")

    def test_date_iso(self):
        self.body("<p>Updated 2026-11-14</p>")
        self.assertFails("printed date")

    def test_date_numeric(self):
        self.body("<p>Updated 11/14/2026</p>")
        self.assertFails("printed date")

    def test_date_beside_unrelated_link(self):
        self.body('<p><a href="/">Home</a> was updated November 7, 2024.</p>')
        self.assertFails("printed date")

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

# ------------------------------------------------------------- final audit
class HostedFiles(Case):
    """M4: files/ holds exactly the files listed in facts.yaml."""

    def test_stray_upload(self):
        self.site.write_bytes("files/old-roster.docx", docx())
        self.assertFails("files/old-roster.docx is not listed under files in facts.yaml")

    def test_replacement_under_a_new_name(self):
        (self.site.root / "files/ares-application.docx").unlink()
        self.site.write_bytes("files/ARES Application 2026.docx", docx())
        out = self.assertFails("files/ARES Application 2026.docx is not listed")
        self.assertIn("files/ares-application.docx is listed in facts.yaml but missing", out)

    def test_listed_file_missing(self):
        (self.site.root / "files/arrl-ares-task-book.pdf").unlink()
        self.assertFails("files/arrl-ares-task-book.pdf is listed in facts.yaml but missing")


class FileContents(Case):
    """F1: nothing personal inside the hosted files."""

    def test_docx_personal_email(self):
        self.site.write_bytes("files/ares-application.docx", docx("Send it to bob.smith@gmail.com"))
        self.assertFails("files/ares-application.docx: e-mail address not allowed: bob.smith@gmail.com")

    def test_docx_mailto_in_rels(self):
        self.site.write_bytes("files/ares-application.docx",
                              docx(rels='<Relationship Target="mailto:bob%40gmail.com" TargetMode="External"/>'))
        self.assertFails("e-mail address not allowed: bob@gmail.com")

    def test_docx_phone(self):
        self.site.write_bytes("files/ares-application.docx", docx("Call Bob at (509) 555-1234"))
        self.assertFails("files/ares-application.docx: something that looks like a phone number")

    def test_docx_blank_phone_line_is_fine(self):
        self.site.write_bytes("files/ares-application.docx", docx("Phone: (____) ____-______  Email: info@spokares.org"))
        self.assertPasses()

    def test_docx_author(self):
        self.site.write_bytes("files/ares-application.docx", docx(creator="Jane Member"))
        self.assertFails("the document's dc:creator is 'Jane Member'")

    def test_docx_last_modified_by(self):
        self.site.write_bytes("files/ares-application.docx", docx(modified="jsmith"))
        self.assertFails("cp:lastModifiedBy is 'jsmith'")

    def test_pdf_email_in_a_compressed_stream(self):
        import zlib
        stream = zlib.compress(b"BT (Questions: bob.smith@gmail.com) Tj ET")
        self.site.write_bytes("files/arrl-ares-task-book.pdf",
                              b"%PDF-1.7\n1 0 obj<</Filter/FlateDecode>>stream\n" + stream + b"\nendstream\n%%EOF\n")
        self.assertFails("files/arrl-ares-task-book.pdf: e-mail address not allowed: bob.smith@gmail.com")

    def test_not_a_word_file(self):
        self.site.write_bytes("files/ares-application.docx", b"not a zip")
        self.assertFails("is not a readable Word document")


class DocumentsAnywhere(Case):
    """R1: a document anywhere in the build must be one of the listed files."""

    def test_document_in_a_subfolder_of_files(self):
        self.site.write_bytes("files/old/roster.docx", docx())
        self.assertFails("files/old/roster.docx is a document that is not one of the files listed in facts.yaml")

    def test_document_elsewhere(self):
        self.site.write_bytes("img/scan.pdf", b"%PDF-1.7\n%%EOF\n")
        self.assertFails("img/scan.pdf is a document that is not one of the files listed")

    def test_spreadsheet(self):
        self.site.write_bytes("roster.xlsx", b"PK")
        self.assertFails("roster.xlsx is a document")

    def test_zip(self):
        self.site.write_bytes("files/all.zip", b"PK")
        self.assertFails("files/all.zip is")

    def test_document_in_subfolder_is_scanned_too(self):
        self.site.write_bytes("files/old/x.docx", docx("bob@gmail.com"))
        self.assertFails("files/old/x.docx: e-mail address not allowed: bob@gmail.com")


class DocumentPeople(Case):
    """R2: names and sign-in addresses carried inside Word and PDF files."""

    def test_tracked_change(self):
        self.site.write_bytes("files/ares-application.docx",
                              docx(body='<w:ins w:id="1" w:author="Jane Member" w:date="2026-01-01T00:00:00Z"><w:r><w:t>x</w:t></w:r></w:ins>'))
        out = self.assertFails("files/ares-application.docx: has tracked changes")
        self.assertIn("accept all changes and delete comments", out)
        self.assertIn("Jane Member", out)

    def test_deletion_by_group_still_refused(self):
        self.site.write_bytes("files/ares-application.docx",
                              docx(body='<w:del w:id="1" w:author="Spokane County ARES-ACS"><w:r><w:delText>x</w:delText></w:r></w:del>'))
        self.assertFails("has tracked changes")

    def test_comments(self):
        self.site.write_bytes("files/ares-application.docx", docx(parts={
            "word/comments.xml": '<w:comments><w:comment w:id="0" w:author="Jane Member" w:initials="JM"><w:p><w:r><w:t>check</w:t></w:r></w:p></w:comment></w:comments>'}))
        self.assertFails("files/ares-application.docx: has comments")

    def test_people_part(self):
        self.site.write_bytes("files/ares-application.docx", docx(parts={
            "word/people.xml": '<w15:people><w15:person w15:author="Jane Member"><w15:presenceInfo w15:providerId="AD" w15:userId="jane@example.com"/></w15:person></w15:people>'}))
        out = self.assertFails("files/ares-application.docx: names a person")
        self.assertIn("Inspect Document", out)

    def test_company(self):
        self.site.write_bytes("files/ares-application.docx", docx(company="Acme Plumbing"))
        self.assertFails("the document's Company is 'Acme Plumbing'")

    def test_group_name_is_fine(self):
        self.site.write_bytes("files/ares-application.docx", docx(parts={
            "word/people.xml": '<w15:people><w15:person w15:author="Spokane County ARES-ACS"/></w15:people>'}))
        self.assertPasses()

    def test_pdf_author(self):
        self.site.write_bytes("files/arrl-ares-task-book.pdf",
                              b"%PDF-1.7\n1 0 obj<</Author(Jane Member)/Producer(x)>>endobj\n%%EOF\n")
        self.assertFails("files/arrl-ares-task-book.pdf: the PDF's author is 'Jane Member'")

    def test_pdf_xmp_creator(self):
        self.site.write_bytes("files/arrl-ares-task-book.pdf",
                              b"%PDF-1.7\n<x:xmpmeta><dc:creator><rdf:Seq><rdf:li>Jane Member</rdf:li></rdf:Seq></dc:creator></x:xmpmeta>\n%%EOF\n")
        self.assertFails("the PDF's author is 'Jane Member'")

    def test_pdf_hex_author(self):
        self.site.write_bytes("files/arrl-ares-task-book.pdf",
                              b"%PDF-1.7\n1 0 obj<</Author<FEFF004A0061006E0065>>>endobj\n%%EOF\n")
        self.assertFails("the PDF's author is 'Jane'")

    def test_pdf_creator_tool_is_fine(self):
        self.site.write_bytes("files/arrl-ares-task-book.pdf",
                              b"%PDF-1.7\n<xmp:CreatorTool>Adobe InDesign</xmp:CreatorTool>\n%%EOF\n")
        self.assertPasses()


class Dates(Case):
    """M5: the date check no longer leaks."""

    def test_message_says_how_to_write_it(self):
        self.body("<p>Training meeting: November 19, 6:00 PM</p>")
        out = self.assertFails("printed date 'November 19'")
        self.assertIn("write the rule, not the date: 'Third Thursday of each month'", out)

    def test_ordinal_with_month_later(self):
        self.body("<p>Moved to the 21st this December.</p>")
        self.assertFails("printed date '21st this December'")

    def test_weekday_ordinal(self):
        self.body("<p>Thursday the 18th is cancelled.</p>")
        self.assertFails("printed date 'Thursday the 18th'")

    def test_full_weekday_names(self):
        for text, hit in [("Exam on Saturday the 14th.", "Saturday the 14th"),
                          ("Wednesday, March 4 at the EOC.", "Wednesday, March 4")]:
            self.body(f"<p>{text}</p>")
            self.assertFails(f"printed date '{hit}'")

    def test_dotted_iso(self):
        self.body("<p>2026.12.18 cancelled</p>")
        self.assertFails("printed date '2026.12.18'")

    def test_month_and_future_year(self):
        self.body("<p>Starting January 2099 the net moves.</p>")
        self.assertFails("printed date 'January 2099'")

    def test_external_files_link_does_not_exempt(self):
        self.body('<p><a href="https://example.org/files/x.pdf">Class</a> on Saturday, March 14.</p>')
        self.assertFails("printed date")

    def test_file_link_exempts_only_the_version(self):
        self.body('<p>The next orientation is December 12. <a href="/files/acs-task-book.docx">ACS task book</a> (Word document, August 9, 2024)</p>')
        self.assertFails("printed date 'December 12'")

    def test_unlisted_date_beside_file_link(self):
        self.body('<p><a href="/files/acs-task-book.docx">ACS task book</a> (Word document, March 1, 2026)</p>')
        self.assertFails("printed date 'March 1'")

    def test_version_away_from_file_link(self):
        self.body("<p>Updated August 9, 2024.</p>")
        self.assertFails("printed date 'August 9'")

    def test_version_beside_file_link_under_base(self):
        base = "/spokares-static"
        self.body(f'<p><a href="{base}/files/acs-task-book.docx">ACS task book</a> (Word document, August 9, 2024)</p>',
                  rel="about/index.html")
        out = self.site.run("--base", base)[1]
        self.assertNotIn("printed date", out)

    def test_more_numeric_and_spelled_dates(self):
        for text in ["Moved to 12-18-2026.", "Moved to 18/12/2026.", "Moved to 2026/12/18.", "Moved to 12.18.26.",
                     "Moved to December eighteenth.", "Moved to the eighteenth of December.",
                     "Moved to the 2nd of December."]:
            self.body(f"<p>{text}</p>")
            self.assertFails("printed date")

    def test_fractions_ratios_and_sizes_are_fine(self):
        # T4: a bare d/d or d-d without a year is not a date.
        for text in ["1/2 hour", "2 1/2 hours", "12/24 V", "1/4 in.", "80/40/20 m", "3/8-24 thread", "5/9",
                     "2/3 majority", "7/24", "Channel 1/2", "next one 12/18", "a 5/8-wave antenna",
                     "drills since 9/11", "a 1/2 inch mast", "IS-100.c and v1.2.10"]:
            with self.subTest(text=text):
                self.body(f"<p>Bring {text}.</p>")
                self.assertPasses()

    def test_month_and_day_in_any_capitals_and_with_a_hyphen(self):
        for text, hit in [("Meet november 7.", "november 7"), ("Meet NOV 7.", "NOV 7"), ("Meet Dec-18.", "Dec-18"),
                          ("Meet 18-Dec.", "18-Dec"), ("Meet December the eighteenth.", "December the eighteenth"),
                          ("Meet 18-Dec-2026.", "18-Dec"), ("Meet 12/18/26.", "12/18/26"),
                          ("Meet 2026/12/18.", "2026/12/18"), ("Meet 12.18.2026.", "12.18.2026")]:
            with self.subTest(text=text):
                self.body(f"<p>{text}</p>")
                self.assertFails(f"printed date '{hit}'")

    def test_external_files_link_with_a_version_does_not_exempt(self):
        self.body('<p><a href="https://example.org/files/acs-task-book.docx">Task book</a> (Word document, August 9, 2024)</p>')
        self.assertFails("printed date 'August 9'")

    def test_history_is_fine(self):
        self.body("<p>In August 2023, and in 1999, 2004, 2017 and 2019; 2nd and 4th Tuesdays; "
                  "Rev. 2019/2020; 24/7; IS-100; 147.300 MHz; 4 of 5 members.</p>")
        self.assertPasses()


class Leadership(Case):
    """M6: placeholder words in the leadership tables."""

    def table(self, call):
        return (f'<figure class="wp-block-table table roles"><table><tbody><tr><td>AEC, Hospital</td>'
                f"<td>{call}</td></tr></tbody></table></figure>")

    def test_vacant(self):
        self.body(self.table("vacant"), rel="about/index.html")
        self.assertFails('the leadership table says "vacant"')

    def test_tbd(self):
        self.body(self.table("TBD"), rel="about/index.html")
        self.assertFails('the leadership table says "TBD"')

    def test_open(self):
        self.body(self.table("(open)"), rel="about/index.html")
        self.assertFails('the leadership table says "(open)"')

    def test_open_house_is_fine(self):
        self.body(self.table("AA7RT").replace("AEC, Hospital", "AEC, Public Events and Open House")
                  + '<h2 id="contact">Contact</h2>', rel="about/index.html")
        self.assertPasses()

    def test_call_signs_pass(self):
        self.body(self.table("AA7RT, W7UWC") + '<h2 id="contact">Contact</h2>', rel="about/index.html")
        self.assertPasses()


class InjectedHtml(Case):
    """M7: elements and attributes the site never uses."""

    def test_base(self):
        self.body('<div><base href="https://evil.example/"></div>')
        self.assertFails("<base> is not allowed")

    def test_meta_refresh(self):
        self.body('<div><meta http-equiv="refresh" content="0;url=https://evil.example/"></div>')
        self.assertFails("<meta http-equiv> is not allowed")

    def test_form(self):
        self.body('<form action="https://evil.example/"><input name="p" type="password"></form>')
        self.assertFails("<form> is not allowed")

    def test_iframe(self):
        self.body('<iframe title="x"></iframe>')
        self.assertFails("<iframe> is not allowed")

    def test_object(self):
        self.body('<object title="x"></object>')
        self.assertFails("<object> is not allowed")

    def test_embed(self):
        self.body('<embed title="x">')
        self.assertFails("<embed> is not allowed")

    def test_svg_animate(self):
        self.body('<svg><a><animate attributeName="href" values="javascript:alert(1)"/><text>x</text></a></svg>')
        self.assertFails("<animate> is not allowed")

    def test_svg_set(self):
        self.body('<svg><set attributeName="href" to="https://evil.example/"/></svg>')
        self.assertFails("<set> is not allowed")

    def test_event_handler(self):
        self.body('<img alt="" src="/img/seal.png" onerror="alert(1)">')
        self.assertFails("the event handler onerror= is not allowed")

    def test_javascript_in_any_attribute(self):
        self.body('<svg><a xlink:href=" java\tscript:alert(1)"><text>x</text></a></svg>')
        self.assertFails("a javascript: value in xlink:href= is not allowed")

    def test_inline_script(self):
        self.body("<script>alert(1)</script><p>x</p>")
        self.assertFails("an inline <script> (without src) is not allowed")

    def test_svg_image_external(self):
        self.body('<svg><image href="https://evil.example/x.png"/></svg>')
        self.assertFails("an outside address on an SVG <image> is not allowed")

    def test_svg_use_external(self):
        self.body('<svg><use xlink:href="//evil.example/s.svg#a"/></svg>')
        self.assertFails("an outside address on an SVG <use> is not allowed")

    def test_svg_use_local_is_fine(self):
        self.body('<svg><defs><path id="p" d="M0 0"/></defs><use href="#p"/></svg>')
        self.assertPasses()

    def test_ping(self):
        self.body('<p><a href="https://www.arrl.org/" ping="https://evil.example/t">ARRL</a></p>')
        self.assertFails("the ping= attribute is not allowed")

    def test_raw_html_omitted(self):
        self.body("<p><!-- raw HTML omitted -->Hello</p>")
        self.assertFails("raw HTML was dropped")

    def test_vbscript_href(self):
        self.body('<p><a href="vbscript:msgbox">x</a></p>')
        self.assertFails("vbscript")


class Wording(Case):
    """m1: whole words, case-insensitive status phrases, plain messages."""

    def test_next_upgrade_is_fine(self):
        self.body("<p>Your next upgrade is General class.</p>")
        self.assertPasses()

    def test_this_weekly_net_is_fine(self):
        self.body("<p>This weekly net is open to all; Field Day runs this weekend.</p>")
        self.assertPasses()

    def test_soon_after_is_fine(self):
        self.body("<p>Soon after you join, you get a badge.</p>")
        self.assertPasses()

    def test_frn_is_not_a_phone(self):
        self.body("<p>An FRN looks like 0012345678.</p>")
        self.assertPasses()

    def test_posted_soon(self):
        self.body("<p>The new schedule will be posted soon.</p>")
        out = self.assertFails('"posted soon" goes out of date')
        self.assertIn("will be posted soon", out)

    def test_available_soon(self):
        self.body("<p>Photos available soon.</p>")
        self.assertFails('"available soon"')

    def test_soon_label(self):
        self.body('<p class="tag">Soon</p>')
        self.assertFails('"Soon" as a label')


class DuplicateIds(Case):
    def test_duplicate_id(self):
        self.body('<h2 id="contact">Contact</h2><div id="contact"></div>', rel="about/index.html")
        self.assertFails('the id "contact" is used more than once')


class Email(Case):
    """m8: the allowed address comes from facts.yaml and must be at spokares.org."""

    def test_address_from_facts(self):
        self.site.facts.write_text(FACTS.replace("info@spokares.org", "contact@spokares.org"), encoding="utf-8")
        self.body('<p><a href="mailto:contact@spokares.org">Write</a> or info@spokares.org</p>')
        out = self.assertFails("e-mail address not allowed: info@spokares.org")
        self.assertNotIn("contact@spokares.org", out)

    def test_changed_address_still_in_the_form(self):
        self.site.write_bytes("files/ares-application.docx", docx("Send it to info@spokares.org"))
        self.site.facts.write_text(FACTS.replace("info@spokares.org", "contact@spokares.org"), encoding="utf-8")
        out = self.assertFails("files/ares-application.docx: the file gives info@spokares.org, facts.yaml (contact.email) "
                               "gives contact@spokares.org; make them match")
        self.assertNotIn("still", out)
        self.assertNotIn("now says", out)

    def test_facts_address_off_domain(self):
        self.site.facts.write_text(FACTS.replace("info@spokares.org", "bob@gmail.com"), encoding="utf-8")
        self.assertFails("contact.email must be an address at spokares.org")


class Stages(Case):
    """m12: the full checks (default stage 7) run in the tests."""

    def test_missing_page_at_full_stage(self):
        (self.site.root / "resources/index.html").unlink()
        self.assertFails("missing page: resources/index.html")

    def test_no_groups_io_link(self):
        self.body("<p>No group link.</p>" + MEMBERS.split("<p>")[0], rel="members/index.html", title="For members")
        self.assertFails("expected exactly one groups.io link")

    def test_two_groups_io_links(self):
        self.body(MEMBERS + '<p><a href="https://spokaneares-acs.groups.io/g/main">again</a></p>',
                  rel="members/index.html")
        self.assertFails("expected exactly one groups.io link (on /members/), found 2")

    def test_groups_io_on_another_page(self):
        self.body('<p><a href="https://spokaneares-acs.groups.io/g/main">group</a></p>')
        self.assertFails("index.html: groups.io link not allowed here")


class Modes(Case):
    """M8: --preview requires noindex, --live forbids it."""

    def test_live_with_noindex(self):
        self.assertFails("has noindex, but this is the live build", "--live")

    def test_live_without_noindex(self):
        for f in self.site.root.rglob("*.html"):
            f.write_text(f.read_text(encoding="utf-8").replace('<meta name="robots" content="noindex">', ""),
                         encoding="utf-8")
        self.assertPasses("--live")
        self.assertFails("missing <meta name=\"robots\"", "--preview")


class Arguments(Case):
    """m12: bad arguments and bad input give one line, never a traceback."""

    def one_line(self, *args, facts=True):
        code, out = self.site.run(*args, facts=facts)
        self.assertNotEqual(code, 0)
        self.assertNotIn("Traceback", out)
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        return out

    def test_no_arguments(self):
        r = subprocess.run([sys.executable, str(CHECKER)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("usage", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_bad_stage(self):
        self.assertIn("--stage must be a number", self.one_line("--stage", "x"))

    def test_stage_without_value(self):
        self.assertIn("--stage needs a value", self.one_line("--stage"))

    def test_unknown_option(self):
        self.assertIn("unknown option --nope", self.one_line("--nope"))

    def test_base_without_slash(self):
        self.assertIn("--base must start with a slash", self.one_line("--base", "spokares-static"))

    def test_missing_folder(self):
        r = subprocess.run([sys.executable, str(CHECKER), str(self.site.root / "nope")], capture_output=True, text=True)
        self.assertIn("is not a folder", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_not_utf8_page(self):
        (self.site.root / "index.html").write_bytes(b"<html>caf\xe9</html>")
        out = self.assertFails("index.html: is not UTF-8 text")
        self.assertNotIn("Traceback", out)

    def test_bad_facts_file(self):
        self.site.facts.write_text('contact:\n  email: "info@spokares.org\n', encoding="utf-8")
        self.assertFails("cannot read the facts file")


if __name__ == "__main__":
    unittest.main(verbosity=2)
