#!/usr/bin/env python3
"""Build tests: the templates refuse bad input, facts reach every page, and
build.sh behaves. Part of the publish gate (step 4 of build.sh).

Run: python3 site/tools/test_build.py     (needs hugo 0.164.0 on the PATH)

Every test copies site/ to a temporary folder WITHOUT its data files, page
files and hosted files, puts the frozen fixture copies from
site/tools/fixtures/ in their place, makes one change, and builds with the
hugo command CI uses. No test reads site/data/, site/content/ or
site/static/files/, so no edit to them can make a test fail; build.sh's step
4 (self_test.py) proves that on every run by running the tests in a copy
where those files are garbage.

The tests that edit the REAL data and run the real build.sh on it are a
developer's check, not part of the gate: site/tools/dev-check.sh.
"""
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
SITE = TOOLS.parent
FIXTURES = TOOLS / "fixtures"
BASE = "/spokares-static"
# The live data, pages and hosted files are never copied.
LIVE = ("data", "content", "static/files")
IGNORE = shutil.ignore_patterns("public", "resources", ".hugo_build.lock", ".reference", "__pycache__")

sys.path.insert(0, str(TOOLS))
import self_test  # noqa: E402  (same folder; standard library only)


def copy_site(dest, site=SITE):
    """Copies site/ to dest/site, with the fixture data files, page files and
    hosted files in place of the live ones (which are not read at all)."""
    copy = dest / "site"

    def ignore(folder, names):
        skip = set(IGNORE(folder, names))
        rel = Path(folder).resolve().relative_to(site.resolve()).as_posix()
        for part in LIVE:
            parent, _, leaf = part.rpartition("/")
            if rel == (parent or ".") and leaf in names:
                skip.add(leaf)
        return skip
    shutil.copytree(site, copy, ignore=ignore)
    for src, target in (("data", "data"), ("content", "content"), ("files", "static/files")):
        install_fixtures(FIXTURES / src, copy / target)
    return copy


def install_fixtures(src, dest):
    """Copies fixture files under their real names: facts.fixture.yaml
    becomes facts.yaml. (The ".fixture" keeps them from being mistaken for
    the real files in GitHub's file finder.)"""
    dest.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.iterdir()):
        shutil.copyfile(f, dest / f.name.replace(".fixture.", "."))


def page_text(path):
    """A built page as plain text: tags removed (inline ones without a space,
    so "<abbr>AEC</abbr>, Public" reads "AEC, Public"), entities decoded,
    every kind of space folded to one ordinary space and the true minus sign
    to "-"."""
    raw = path.read_text(encoding="utf-8")
    inline = r"</?(?:a|abbr|b|code|em|i|kbd|small|span|strong|sub|sup|time)\b[^>]*>"
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(inline, "", raw)))
    attrs = html.unescape(" ".join(re.findall(r'(?:data-copy-text|href)="([^"]*)"', raw)))
    text = (text + " " + attrs).replace("−", "-")
    return re.sub(r"[\s\u00a0\u202f\u2009]+", " ", text)


class Build(unittest.TestCase):
    """Template tests: a copy of the site with the fixture data and pages."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.site = copy_site(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def edit(self, rel, old, new, count=1):
        f = self.site / rel
        text = f.read_text(encoding="utf-8")
        if old not in text:
            self.fail(f"test setup: {old!r} is not in the fixture {rel}")
        f.write_text(text.replace(old, new, count), encoding="utf-8")

    def build(self, *extra, env=None, base=f"http://localhost{BASE}/"):
        out = self.root / "public"
        r = subprocess.run(["hugo", "--source", str(self.site), "--destination", str(out), "--cleanDestinationDir",
                            "--panicOnWarning", "--baseURL", base, *extra],
                           capture_output=True, text=True, env={**os.environ, **(env or {})})
        return r.returncode, r.stdout + r.stderr, out

    def refused(self, *needles):
        code, out, _ = self.build()
        self.assertNotEqual(code, 0, f"expected the build to stop; output:\n{out[-2000:]}")
        errors = [l for l in out.splitlines() if "ERROR" in l]
        self.assertTrue(errors, out)
        for n in needles:
            self.assertIn(n, out)
        self.assertNotIn("%!", out, "a Go formatting placeholder leaked into the message")
        return out

    def built(self):
        code, out, pub = self.build()
        self.assertEqual(code, 0, out[-3000:])
        return pub

    def page(self, pub, rel):
        return (pub / rel).read_text(encoding="utf-8")


class Baseline(Build):
    def test_fixture_site_builds_and_passes_the_checker(self):
        pub = self.built()
        r = subprocess.run([sys.executable, str(TOOLS / "check_site.py"), str(pub), "--base", BASE,
                            "--facts", str(self.site / "data" / "facts.yaml")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class FactsReachEveryPage(Build):
    """M2: a changed net day, time or repeater call sign reaches every page."""

    # Text that stays on purpose when the net or repeater changes: the history
    # of the club call sign W7GBU (About, "History and W7GBU") and the trustee
    # of that club licence, which is its own line in facts.yaml.
    HISTORY = [
        r"History and W7GBU",
        r"The W7GBU story",
        r"Bula, W7GBU",
        r"<strong>2017</strong> W7GBU becomes",
        r"<strong>2004</strong> The earliest website records show the Tuesday net",
        r"W7GBU license trustee",
    ]

    def test_changed_net_and_repeater(self):
        f = "data/facts.yaml"
        self.edit(f, 'day: "Tuesday"', 'day: "Wednesday"')
        self.edit(f, 'time: "8:00 PM"', 'time: "7:30 PM"')
        self.edit(f, 'call: "W7GBU"', 'call: "K7ABC"')
        pub = self.built()
        left = []
        for p in sorted(pub.rglob("*.html")):
            text = html.unescape(p.read_text(encoding="utf-8")).replace(" ", " ")
            for h in self.HISTORY:
                text = re.sub(h, "", text)
            for needle in ("Tuesday", "8:00 PM", "W7GBU"):
                for m in re.finditer(needle, text):
                    left.append(f"{p.relative_to(pub)}: …{text[max(0, m.start() - 60):m.end() + 30]}…")
        self.assertEqual(left, [], "\n".join(left))
        how = html.unescape(self.page(pub, "how-it-works/index.html"))
        self.assertIn("Every Wednesday, 7:30", how)
        self.assertIn("K7ABC repeater", how)
        self.assertIn("second and fourth Wednesdays", how)


# ------------------------------------------------------------------ every fact changed

# Leaves that are not page text: names the templates and pages refer to.
STRUCTURAL = {"id", "file", "kind"}
# Text that stays on purpose when every fact changes, matched in the built
# pages' text (tags removed). Each is history, or a name that is not the fact.
STAYS = [
    # History: the club call sign's story and the 2004 net (About, "History and W7GBU").
    r"History and W7GBU", r"The W7GBU story", r"Bula, W7GBU", r"W7GBU becomes",
    r"records show the Tuesday net",
    # The agency that hosts the meetings is named as the agency we serve, and
    # "Spokane" is part of the group's and agencies' names, not the meeting city.
    r"Spokane County Emergency Management", r"\bSpokane\b",
    # The office, named in sentences about what it does (the leadership table
    # reads its holder and title from facts.yaml).
    r"(?i)Emergency Coordinators?\b",
]


def new_values():
    """A new value for every kind of leaf, unlike any value the site has."""
    n = iter(range(1, 1000))
    calls = (f"K7Z{a}{b}" for a in "QRSTUVWXY" for b in "ABCDEFGHJKLMNPQRSTUVWXYZ")
    made = {
        "weekday": lambda old: "Friday" if old != "Friday" else "Monday",
        "time": lambda old: "6:45 PM" if old != "6:45 PM" else "5:15 PM",
        "freq": lambda old: f"44{next(n) % 10}.{next(n) % 10}75 MHz",
        "offset": lambda old: "+5 MHz" if not old.startswith("+") else "-5 MHz",
        "tone": lambda old: f"DCS {700 + next(n):03d}",
        "call": lambda old: next(calls),
        "weather_call": lambda old: "WNG604" if old != "WNG604" else "KEC88",
        "nights": lambda old: "first and third" if old != "first and third" else "second and fourth",
        "text": lambda old: f"Zed words {next(n)}",
        "role": lambda old: f"Zed role {next(n)}",
        "callsigns": lambda old: next(calls),
        "email": lambda old: "zed-secretary@" + old.split("@", 1)[1],
        "groupsio": lambda old: "https://zed-group.groups.io/g/zed",
        "version": lambda old: f"March {next(n)}, 2031",
    }
    return made


def leaves(schema, node, path=()):
    """(kind, value, line, path) for every leaf of a data file, as check_data reads it."""
    if isinstance(schema, dict):
        for k, sub in schema.items():
            k = k.rstrip("?")
            if isinstance(node, dict) and k in node:
                v, n = node[k]
                if isinstance(sub, str):
                    yield sub, v, n, path + (k,)
                else:
                    yield from leaves(sub, v, path + (k,))
    elif isinstance(schema, list):
        for i, item in enumerate(node):
            yield from leaves(schema[0], item, path + (i,))


def change_every_fact(site, docx_with):
    """Changes every leaf of site/data/facts.yaml that is page text to a new
    value, and puts in place of each hosted Word file that gives the contact
    address a clean one, made by docx_with(paragraphs), with the new address.
    Returns [(path, old value, new value)]."""
    import check_data
    import check_site
    f = site / "data" / "facts.yaml"
    tree = check_data.load(f)
    lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
    made, changed = new_values(), []
    for kind, old, line, path in leaves(check_data.SCHEMA_FACTS, tree):
        if path[-1] in STRUCTURAL:
            continue
        new = made[kind](old)
        lines[line - 1] = re.sub(r'"(?:\\.|[^"\\])*"', lambda m: f'"{new}"', lines[line - 1], count=1)
        changed.append((".".join(map(str, path)), old, new))
    f.write_text("".join(lines), encoding="utf-8")
    old_email = check_data.strip(tree)["contact"]["email"]
    new_email = next(new for p, _, new in changed if p == "contact.email")
    for doc in sorted((site / "static" / "files").glob("*.docx")):
        text, _, err = check_site.docx_text(doc)
        if old_email in text:
            doc.write_bytes(docx_with([l.replace(old_email, new_email) for l in text.splitlines() if l.strip()]))
    return changed


def stale_values(pub, changed):
    """Old values still on the built pages, outside the text that STAYS."""
    left = []
    for p in sorted(pub.rglob("*.html")):
        text = page_text(p)
        stays = [m.span() for s in STAYS for m in re.finditer(s, text)]
        for path, old, _ in changed:
            # A name of several words may also start a sentence or sit inside one.
            forms = {old, old.lower(), old[:1].lower() + old[1:]} if " " in old else {old}
            for m in (m for f in forms for m in re.finditer(re.escape(f), text)):
                if any(a <= m.start() and m.end() <= b for a, b in stays):
                    continue
                left.append(f"{p.relative_to(pub)}: {path} {old!r}: …{text[max(0, m.start() - 60):m.end() + 30]}…")
    return left


def small_docx(paragraphs):
    """A small, clean Word file with these paragraphs."""
    import io
    import zipfile
    from xml.sax.saxutils import escape
    body = "".join(f"<w:p><w:r><w:t>{escape(p)}</w:t></w:r></w:p>" for p in paragraphs)
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f"<w:document><w:body>{body}</w:body></w:document>")
        z.writestr("docProps/core.xml", "<cp:coreProperties><dc:creator>Spokane County ARES-ACS</dc:creator>"
                                        "<cp:lastModifiedBy></cp:lastModifiedBy></cp:coreProperties>")
    return b.getvalue()


class EveryFactChanged(Build):
    """F1: when every fact in facts.yaml changes, no old value stays on the
    site except the text listed in STAYS. (A sentence that restated a fact
    would go stale the day the fact changed.)"""

    def test_no_old_value_is_left(self):
        changed = change_every_fact(self.site, small_docx)
        self.assertGreater(len(changed), 30)
        code, out, pub = self.build()
        self.assertEqual(code, 0, out[-3000:])
        r = subprocess.run([sys.executable, str(TOOLS / "check_site.py"), str(pub), "--base", BASE,
                            "--facts", str(self.site / "data" / "facts.yaml")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:])
        left = stale_values(pub, changed)
        self.assertEqual(left, [], "\n".join(left))
        about = page_text(pub / "about" / "index.html")
        for path, _, new in changed:
            if path.startswith(("leadership", "contact")):
                self.assertIn(new, about, path)


class TemplateGuards(Build):
    """M1, m3, m4, m7: a bad value that got past check_data.py stops the build clearly."""

    def test_unquoted_number(self):
        self.edit("data/facts.yaml", 'freq: "147.300 MHz"', "freq: 147.300")
        self.refused('"repeater.primary.freq"', "double quotes")

    def test_unquoted_integer_tone(self):
        self.edit("data/facts.yaml", 'tone: "100 Hz"', "tone: 100")
        self.refused('"repeater.primary.tone"', "double quotes")

    def test_unquoted_in_meeting_list(self):
        self.edit("data/facts.yaml", 'name: "Workshop"', "name: 12")
        self.refused("meetings", "name", "double quotes")

    def test_unquoted_in_leadership(self):
        self.edit("data/facts.yaml", 'callsign: "K7MHG"', "callsign: 7")
        self.refused("leadership", "callsign", "double quotes")

    def test_unquoted_file_version(self):
        self.edit("data/facts.yaml", 'version: "July 2024"', "version: 2024")
        self.refused("files", "version", "double quotes")

    def test_unquoted_resource_note(self):
        self.edit("data/resources.yaml", 'note: "Forecasts and warnings for the Inland Northwest."', "note: 12")
        self.refused("resources.yaml", "note", "double quotes")

    def test_tone_values_read_naturally(self):
        self.edit("data/facts.yaml", 'tone: "123 Hz"', 'tone: "no tone"')
        self.edit("data/facts.yaml", 'tone: "100 Hz"', 'tone: "DCS 023"')
        how = html.unescape(self.page(self.built(), "how-it-works/index.html")).replace(" ", " ")
        self.assertIn("146.880 MHz, −600 kHz, no tone<", how)
        self.assertIn("147.300 MHz, +600 kHz, DCS 023<", how)
        self.assertIn('data-copy-text="Alternate repeater 146.880 MHz, -600 kHz offset, no tone"', how)
        self.assertNotIn("tone tone", how)

    def test_no_tone_in_capitals_reads_in_lower_case(self):
        self.edit("data/facts.yaml", 'tone: "123 Hz"', 'tone: "No Tone"')
        how = html.unescape(self.page(self.built(), "how-it-works/index.html")).replace("\u00a0", " ")
        self.assertIn("146.880 MHz, −600 kHz, no tone<", how)

    def test_file_title_is_text_not_markdown(self):
        self.edit("data/facts.yaml", 'title: "ACS Position Task Book"', 'title: "ACS Position Task Book *new* & more"')
        about = self.page(self.built(), "about/index.html")
        self.assertIn("ACS Position Task Book *new* &amp; more", about)
        self.assertNotIn("<em>new</em>", about)

    def test_percent_in_resource_url(self):
        self.edit("data/resources.yaml", 'url: "https://hamstudy.org/"', 'url: "https://example.org/50%off"')
        out = self.refused("resources.yaml", "50%off")
        self.assertLess(len([l for l in out.splitlines() if "ERROR" in l][0]), 400)

    def test_resource_without_title(self):
        self.edit("data/resources.yaml", '      - title: "HamStudy"\n', "      - \n", 1)
        self.refused("resources.yaml", "title")

    def test_how_row_level_4(self):
        self.edit("content/how-it-works.md", 'title="When no one has called yet" level="3"',
                  'title="When no one has called yet" level="4"')
        self.refused("how-row", "level", "2 or 3")

    def test_button_javascript(self):
        self.edit("content/about.md", 'text="Get the ARES application"',
                  'text="Get the ARES application" href="javascript:alert(1)"')
        self.edit("content/about.md", 'button file="ares-application"', "button")
        out = self.refused("button")
        self.assertNotIn("ZgotmplZ", out)

    def test_empty_leadership_group(self):
        text = (self.site / "data/facts.yaml").read_text(encoding="utf-8")
        start, end = text.index("  section:\n"), text.index("\ncontact:")
        (self.site / "data/facts.yaml").write_text(text[:start] + "  section: []\n" + text[end:], encoding="utf-8")
        self.refused("leadership.section has no positions")


class RawHtmlInBlocks(Build):
    """M7: raw HTML typed inside a designed block stops the build."""

    SPOT = "Sign-ups go out through the members’ group.\n"

    def typed(self, snippet):
        self.edit("content/members.md", self.SPOT, f"{snippet}\n\n{self.SPOT}")
        return self.refused("HTML tags are not allowed in page text")

    def test_plain_external_link_div(self):
        self.typed('<div><a href="https://evil.example/">x</a></div>')

    def test_svg_animate(self):
        self.typed('<svg><a><animate attributeName="href" values="javascript:alert(1)"/><text y="20">x</text></a></svg>')

    def test_base(self):
        self.typed('<div><base href="https://evil.example/"></div>')

    def test_meta_refresh(self):
        self.typed('<div><meta http-equiv="refresh" content="0;url=https://evil.example/"></div>')

    def test_password_form(self):
        self.typed('<div><form action="https://evil.example/"><input name=p type=password></form></div>')

    def test_closing_tag_alone(self):
        self.typed("</div>")

    def test_inline_html(self):
        self.edit("content/members.md", "Sign-ups go out", "Sign-ups <b>go</b> out")
        code, out, _ = self.build()
        self.assertNotEqual(code, 0, out)

    def test_marker_cannot_be_typed(self):
        # The marker that lets a shortcode's HTML through changes every build.
        pub = self.built()
        m = re.search(r"SPK[0-9a-f]{8,}", "".join(p.read_text(encoding="utf-8") for p in pub.rglob("*.html")))
        self.assertIsNone(m, "the per-build marker leaked into the built pages")

    def test_shortcodes_still_nest(self):
        members = self.page(self.built(), "members/index.html")
        self.assertIn('id="weekly-net"', members)
        self.assertIn("ares-application.docx", members)

    def test_attribute_like_text_is_fine(self):
        # m5: text that merely looks like an attribute is not refused.
        self.edit("data/facts.yaml", 'title: "ACS Position Task Book"', 'title: "ACS Position Task Book (style=2024 onboard=yes)"')
        self.assertIn("style=2024 onboard=yes", self.page(self.built(), "members/index.html"))

    def test_code_block_keeps_its_lines(self):
        # m14: a fenced block inside chapter keeps its line breaks.
        self.edit("content/about.md", "## Contact {#contact}\n", "## Contact {#contact}\n\n```\nline one\nline two\n```\n")
        about = self.page(self.built(), "about/index.html")
        self.assertRegex(about, r"line one\nline two")


class InlineHtml(Build):
    """R5: HTML tags typed in page text stop the build with one line naming the file and line."""

    SPOT = "**After any exercise:**"

    def one_line(self, out):
        errors = [l for l in out.splitlines() if "ERROR" in l and "error building site" not in l]
        self.assertTrue(errors, out)
        self.assertLess(len(errors[0]), 400, errors[0])
        self.assertNotIn("ignoreLogs", out)
        return errors[0]

    def line_of(self, rel, text):
        for n, l in enumerate((self.site / rel).read_text(encoding="utf-8").splitlines(), 1):
            if text in l:
                return n

    def test_inline_tag_inside_a_column(self):
        self.edit("content/members.md", self.SPOT, "Press <kbd>Enter</kbd> to send.\n\n" + self.SPOT)
        n = self.line_of("content/members.md", "<kbd>")
        e = self.one_line(self.refused())
        self.assertIn(f"members.md:{n}: HTML tags are not allowed in page text; remove <kbd>", e)

    def test_inline_tag_at_top_level(self):
        self.edit("content/members.md", '{{< section class="members-row members-row--cards"',
                  'Hello <span class="x">there</span>.\n\n{{< section class="members-row members-row--cards"')
        n = self.line_of("content/members.md", "<span")
        e = self.one_line(self.refused())
        self.assertIn(f"members.md:{n}: HTML tags are not allowed in page text; remove <span", e)

    def test_br_inside_how_row(self):
        self.edit("content/how-it-works.md", "2. Officials check in.", "2. Officials<br>check in.")
        self.assertIn("remove <br>", self.one_line(self.refused()))

    def test_comment(self):
        self.edit("content/members.md", self.SPOT, "<!-- note to self -->\n\n" + self.SPOT)
        self.assertIn("remove <!--", self.one_line(self.refused()))

    def test_plain_text_with_angle_brackets_is_fine(self):
        self.edit("content/members.md", self.SPOT, "Check-ins take < 5 minutes. We <3 Field Day. "
                  "Type `<kbd>` in a code span.\n\n```\n<b>in a code block</b>\n```\n\n" + self.SPOT)
        page = self.page(self.built(), "members/index.html")
        self.assertIn("&lt; 5 minutes", page)
        self.assertIn("&lt;kbd&gt;", page)

    def test_html_in_about_is_one_error(self):
        # G1: the contents list does not add errors of its own when the page text was refused.
        self.edit("content/about.md", "## Contact {#contact}", "Our <strong>club</strong>.\n\n## Contact {#contact}")
        errors = [l for l in self.refused().splitlines() if l.startswith("ERROR") and "error building site" not in l]
        self.assertEqual(len(errors), 1, errors)

    def test_removed_heading_id_named_in_toc_labels(self):
        # G1 (M53): the message says which id went missing and how to put it back.
        self.edit("content/about.md", "## History and W7GBU {#history}", "## History and W7GBU")
        e = self.one_line(self.refused())
        self.assertIn("site/content/about.md: a chapter heading lost its id {#history}", e)
        self.assertIn("put {#history} back at the end of that heading line", e)

    def test_attribute_line_after_an_empty_line(self):
        # G2: {.lede} below an empty line would silently lose its look.
        self.edit("content/resources.md", "keeps it current.\n{.lede}", "keeps it current.\n\n{.lede}")
        n = self.line_of("content/resources.md", "{.lede}")
        e = self.one_line(self.refused())
        self.assertIn(f"resources.md:{n}: remove the empty line above {{.lede}}", e)

    def test_attribute_lines_in_place_are_fine(self):
        self.built()

    def test_ignore_logs_in_config(self):
        (self.site / "hugo.toml").write_text((self.site / "hugo.toml").read_text(encoding="utf-8")
                                              + '\nignoreLogs = ["warning-goldmark-raw-html"]\n', encoding="utf-8")
        self.assertIn("ignoreLogs", [l for l in self.refused().splitlines() if "ERROR" in l][0])


class Regressions(Build):
    """R15, R17: behaviour the first fix wave added, kept by tests."""

    def test_copy_js_only_where_there_is_a_copy_button(self):
        pub = self.built()
        for p in sorted(pub.rglob("*.html")):
            page = p.read_text(encoding="utf-8")
            self.assertEqual("copy.js" in page, "netbox__copy" in page, p.relative_to(pub))
        self.assertIn("copy.js", self.page(pub, "how-it-works/index.html"))
        self.assertNotIn("copy.js", self.page(pub, "about/index.html"))

    def test_menu_js_keeps_its_fallbacks(self):
        js = (SITE / "static/js/menu.js").read_text(encoding="utf-8")
        self.assertIn("addListener(", js)
        self.assertIn("preventScroll: true", js)
        self.assertIn("window.scrollTo(x, y)", js)

    def test_print_hides_decoration_and_closed_controls(self):
        # T9: rings and the closed "On this page" control do not print.
        css = (SITE / "static/css/site.css").read_text(encoding="utf-8")
        hidden = " ".join(m.group(1) for m in re.finditer(r"@media print\s*{((?:[^{}]|{[^{}]*})*)}", css)
                          if "display: none" in m.group(1))
        for sel in ("hr.wp-block-separator::before", "hr.wp-block-separator::after", ".chains__team::before",
                    ".toc-mobile:not([open])"):
            self.assertIn(sel, hidden, f"{sel} is not hidden in print")

    def test_file_version_date_does_not_wrap(self):
        # T11: at 320px the note may wrap between kind and date, never inside the date.
        about = self.page(self.built(), "about/index.html")
        for note in ('<span class="file-meta">(Word document, <span class="nobr">November 7, 2024)</span></span>',
                     '<span class="nowrap">(Word document, <span class="nobr">August 9, 2024)</span></span>',
                     '<span class="nowrap">(PDF, <span class="nobr">July 2024)</span></span>'):
            if note not in about:
                self.fail(f"About lacks {note}")

    def test_about_training_agrees_with_the_task_book(self):
        # G5: the ACS book marks the General license as kept ("R-Maintain"), not done once;
        # what the task books list is said once; AEC is spelled out where it is first used.
        pub = self.built()
        about = self.page(pub, "about/index.html")
        row = re.search(r"Level 3: </span>.*?</tr>", about).group(0)
        once, regularly = re.findall(r'<td data-label="[^"]+">(.*?)</td>', row)
        self.assertNotIn("General license", once)
        self.assertIn("General license", regularly)
        text = page_text(pub / "about" / "index.html")
        self.assertNotIn("who signs off", text)
        body = text[text.index("ARES and ACS ARES Amateur Radio"):]
        first = re.search(r"\bAECs?\b", body)
        self.assertTrue(body[:first.end()].endswith("Assistant Emergency Coordinators (AECs"), body[first.start() - 80:first.end()])

    def test_form_numbers_do_not_break(self):
        pub = self.built()
        self.assertIn('<span class="nobr">(ICS-213RR)</span>', self.page(pub, "resources/index.html"))
        self.assertIn('<span class="nobr">ICS-213RR</span>', self.page(pub, "members/index.html"))
        self.assertNotIn('nobr"><span class="nobr', self.page(pub, "members/index.html"))


class BuildScript(unittest.TestCase):
    """R11: build.sh refuses arguments it does not understand, in one line."""

    # Always a copy with the self-test step skipped: if a refusal ever stops
    # working, the test builds that copy and fails, instead of starting a
    # full build (and its self-tests) in the real repository.
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.site = copy_site(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def run_sh(self, *args):
        r = subprocess.run(["sh", str(self.site / "tools" / "build.sh"), *args], capture_output=True, text=True,
                           timeout=300, env={**os.environ, "BUILD_SKIP_SELF_TESTS": "1"})
        return r.returncode, r.stdout + r.stderr

    def test_live_without_an_address(self):
        code, out = self.run_sh("--live")
        self.assertEqual(code, 2)
        self.assertIn("must be the site's address, starting with http", out)
        self.assertEqual(len(out.strip().splitlines()), 1, out)

    def test_unknown_second_argument(self):
        code, out = self.run_sh("https://spokares.org/", "--lve")
        self.assertEqual(code, 2)
        self.assertIn("unknown argument --lve", out)

    def test_too_many_arguments(self):
        code, out = self.run_sh("https://spokares.org/", "--live", "extra")
        self.assertEqual(code, 2)
        self.assertIn("too many arguments", out)

    def refused(self, *args, says):
        code, out = self.run_sh(*args)
        self.assertEqual(code, 2, out)
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        self.assertIn(says, out)
        self.assertIn("usage: site/tools/build.sh", out)

    def test_missing_scheme(self):
        self.refused("spokares.org", says="must be the site's address, starting with http")

    def test_flag_first(self):
        self.refused("--live", "https://spokares.org/", says="must be the site's address, starting with http")

    def test_live_with_an_empty_address(self):
        # T7
        self.refused("", "--live", says="--live needs the real site's address")

    def test_live_with_the_scheme_alone(self):
        self.refused("https://", "--live", says="--live needs the real site's address")

    def test_live_with_a_github_io_address(self):
        self.refused("https://example.github.io/spokares-static/", "--live", says="github.io")

    def test_live_refuses_addresses_that_are_not_the_real_site(self):
        # G3
        for addr in ("http://spokares.org/", "https://localhost/", "https://127.0.0.1/", "https://spokares.org/?x=1",
                     "https://spokares.org/#top", "https://user@spokares.org/", "http://localhost:1313/"):
            with self.subTest(addr=addr):
                self.refused(addr, "--live", says="--live needs the real site's address")

    def test_hugo_error_prints_our_line_first(self):
        # F6: the one-line message from the templates comes first, then a note, then Hugo's own lines.
        about = self.site / "content" / "about.md"
        text = about.read_text(encoding="utf-8")
        about.write_text(text.replace("## Contact {#contact}", "Our <strong>club</strong>.\n\n## Contact {#contact}"),
                         encoding="utf-8")
        try:
            code, out = self.run_sh()
        finally:
            about.write_text(text, encoding="utf-8")
        self.assertEqual(code, 1, out[-2000:])
        after = out[out.index("== 2."):].splitlines()[1:3]
        self.assertRegex(after[0], r"^ERROR site/content/about\.md:\d+: HTML tags are not allowed in page text; remove <strong>")
        self.assertEqual(after[1], "Later lines are consequences of the first.")

    def test_preview_for_any_address_and_no_arguments(self):
        # No arguments is the local preview; a preview may be built for any address.
        for args, base in (((), "http://localhost/spokares-static/"), (("https://spokares.org/",), "https://spokares.org/")):
            code, out = self.run_sh(*args)
            self.assertEqual(code, 0, out[-2000:])
            self.assertIn(f"Building with Hugo for {base}", out)


class PreviewSwitch(Build):
    """M8: params.preview decides noindex; the live build has none."""

    def test_preview_build_has_noindex(self):
        self.assertIn('name="robots" content="noindex"', self.page(self.built(), "index.html"))

    def test_live_build_has_no_noindex_and_passes_live_check(self):
        code, out, pub = self.build(env={"HUGO_PARAMS_PREVIEW": "false"}, base="https://spokares.org/")
        self.assertEqual(code, 0, out)
        for p in pub.rglob("*.html"):
            self.assertNotIn("noindex", p.read_text(encoding="utf-8"), p)
        r = subprocess.run([sys.executable, str(TOOLS / "check_site.py"), str(pub), "--live",
                            "--facts", str(self.site / "data" / "facts.yaml")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = subprocess.run([sys.executable, str(TOOLS / "check_site.py"), str(pub), "--preview",
                            "--facts", str(self.site / "data" / "facts.yaml")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("noindex", r.stdout)


class FixtureNames(unittest.TestCase):
    """G4: a fixture cannot be mistaken for the real file it copies."""

    def test_every_fixture_is_marked(self):
        for f in sorted(FIXTURES.rglob("*")):
            if not f.is_file():
                continue
            self.assertIn(".fixture.", f.name, f"{f.relative_to(TOOLS)} is not named *.fixture.*")
            if f.suffix in (".yaml", ".md"):
                self.assertIn("# TEST DATA: do not edit; the real file is site/",
                              "\n".join(f.read_text(encoding="utf-8").splitlines()[:2]), f.name)


class SelfTestStep(unittest.TestCase):
    """S1, S2, S3: step 4 runs the self-tests where the live data is garbage,
    so they cannot depend on it, and a failure there says it is not the
    editor's fault."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def tiny_site(self, test_body):
        """A site folder with one data file, one page, one hosted file and one test."""
        site = self.root / "src" / "site"
        for rel, text in (("data/facts.yaml", 'net:\n  day: "Tuesday"\n'), ("content/about.md", "---\n---\nHi.\n"),
                          ("static/files/form.docx", "a form"), ("layouts/index.html", "x")):
            (site / rel).parent.mkdir(parents=True, exist_ok=True)
            (site / rel).write_text(text, encoding="utf-8")
        (site / "tools").mkdir()
        (site / "tools" / "test_x.py").write_text(
            "import unittest\nfrom pathlib import Path\nSITE = Path(__file__).resolve().parent.parent\n"
            "class T(unittest.TestCase):\n    def test(self):\n        " + test_body + "\n"
            "unittest.main()\n", encoding="utf-8")
        return site

    def test_every_live_file_is_garbage_in_the_copy(self):
        site = self.tiny_site("pass")
        copy = self_test.prepare(self.root / "out", site)
        for rel in ("data/facts.yaml", "content/about.md", "static/files/form.docx"):
            self.assertEqual((copy / rel).read_text(encoding="utf-8"), self_test.GARBAGE, rel)
        self.assertEqual((copy / "layouts/index.html").read_text(encoding="utf-8"), "x")

    def test_a_test_that_reads_live_data_fails_the_step(self):
        site = self.tiny_site("self.assertIn('Tuesday', (SITE / 'data' / 'facts.yaml').read_text())")
        ok, lines = self_test.run(("test_x.py",), site)
        self.assertFalse(ok)
        self.assertEqual(lines[0], self_test.NOT_YOUR_EDIT)

    def test_a_test_that_uses_only_its_own_files_passes(self):
        ok, lines = self_test.run(("test_x.py",), self.tiny_site("self.assertTrue((SITE / 'layouts').is_dir())"))
        self.assertTrue(ok, lines)

    def test_the_gate_runs_the_self_tests_through_this_step(self):
        sh = (TOOLS / "build.sh").read_text(encoding="utf-8")
        steps = sh[sh.index('echo "== 4.'):]
        self.assertIn("python3 site/tools/self_test.py", steps)
        self.assertNotRegex(steps, r"python3 site/tools/test_\w+\.py")
        self.assertEqual(set(self_test.TESTS), {p.name for p in TOOLS.glob("test_*.py")})

    def test_build_sh_says_a_failed_self_test_is_not_the_editors_fault(self):
        site = copy_site(self.root)
        for name in self_test.TESTS:
            body = "self.fail('boom')" if name == "test_check_links.py" else "pass"
            (site / "tools" / name).write_text("import unittest\nclass T(unittest.TestCase):\n    def test(self):\n"
                                               f"        {body}\nunittest.main()\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "BUILD_SKIP_SELF_TESTS"}
        r = subprocess.run(["sh", str(site / "tools" / "build.sh")], capture_output=True, text=True, env=env,
                           timeout=300)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        after = r.stdout[r.stdout.index("== 4."):].splitlines()
        self.assertEqual(after[1], self_test.NOT_YOUR_EDIT, r.stdout[-1500:])
        self.assertIn("boom", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
