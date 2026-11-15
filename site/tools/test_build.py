#!/usr/bin/env python3
"""Build tests: the templates refuse bad input, facts reach every page, and a
routine yearly edit to the real site passes the whole gate.

Run: python3 site/tools/test_build.py     (needs hugo 0.164.0 on the PATH)

Two kinds of test:

- Template tests copy site/ to a temporary folder, put the frozen fixture copies
  from site/tools/fixtures/ in place of the data files, the page files and the
  hosted files, make one change, and build with the hugo command CI uses. They
  never read the live data, so a yearly edit to it cannot make them fail.
- RoutineEdits copies the REAL site with its REAL data, makes one routine edit
  a volunteer makes (worked out from whatever the data says today, never from
  fixed values), and runs the real site/tools/build.sh on the copy. Each edit
  must pass and its new value must be on the built page; each clear mistake
  must be refused with one plain line. Those runs skip build.sh's own
  self-test step (BUILD_SKIP_SELF_TESTS=1) to keep the gate quick; one test,
  FullGate, runs the whole build.sh, self-tests included, on edited real data.

A failing test never prints a data file: messages name the file and the value.
"""
import html
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
SITE = TOOLS.parent
FIXTURES = TOOLS / "fixtures"
BASE = "/spokares-static"
IGNORE = shutil.ignore_patterns("public", "resources", ".hugo_build.lock", ".reference", "__pycache__")
# Set by FullGate for the build.sh it runs, so that run's own self-tests do not
# start another full build.sh (which would never end).
NESTED = "BUILD_SH_NESTED"

sys.path.insert(0, str(TOOLS))
import check_data  # noqa: E402  (same folder; standard library only)


def copy_site(dest, fixtures):
    """Copies site/ to dest/site. With fixtures, the data files, the page files
    and the hosted files are the frozen copies in site/tools/fixtures/."""
    site = dest / "site"
    shutil.copytree(SITE, site, ignore=IGNORE)
    if fixtures:
        for src, target in (("data", "data"), ("content", "content"), ("files", "static/files")):
            shutil.rmtree(site / target)
            shutil.copytree(FIXTURES / src, site / target)
    return site


def page_text(path):
    """A built page as plain text: tags removed, entities decoded, every kind
    of space folded to one ordinary space and the true minus sign to "-"."""
    raw = path.read_text(encoding="utf-8")
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    attrs = html.unescape(" ".join(re.findall(r'(?:data-copy-text|href)="([^"]*)"', raw)))
    text = (text + " " + attrs).replace("−", "-")
    return re.sub(r"[\s   ]+", " ", text)


class Build(unittest.TestCase):
    """Template tests: a copy of the site with the fixture data and pages."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.site = copy_site(self.root, fixtures=True)

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
        cls.site = copy_site(Path(cls._tmp.name), fixtures=True)

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


# ------------------------------------------------------------------ routine edits to the real site

class DataFile:
    """Edits one of the real data files by position (as check_data.py reads
    it), the way a volunteer edits it: one value, one entry, one line at a
    time. Paths are label names and entry numbers, e.g.
    ("leadership", "unit", 0, "callsign")."""

    def __init__(self, path):
        self.path = path

    def lines(self):
        return self.path.read_text(encoding="utf-8").splitlines(keepends=True)

    def write(self, lines):
        self.path.write_text("".join(lines), encoding="utf-8")

    def node(self, *keys):
        """Returns (value, line) for a label, or (list, line) / (entry, first line)."""
        cur, line = check_data.load(self.path), 1
        for k in keys:
            if isinstance(k, int):
                cur = cur[k]
                line = min(n for _, n in cur.values())
            else:
                cur, line = cur[k]
        return cur, line

    def get(self, *keys):
        return check_data.strip(self.node(*keys)[0])

    def set(self, *keys, value):
        _, n = self.node(*keys)
        lines = self.lines()
        new, count = re.subn(r'^(\s*(?:- )?[A-Za-z0-9_-]+:\s+)"(?:\\.|[^"\\])*"', lambda m: f'{m.group(1)}"{value}"',
                             lines[n - 1], count=1)
        assert count == 1, f"could not set {'.'.join(map(str, keys))} on line {n}"
        lines[n - 1] = new
        self.write(lines)

    def entry_lines(self, *keys):
        entry, _ = self.node(*keys)
        ns = []

        def collect(e):
            for v, n in e.values():
                ns.append(n)
                if isinstance(v, list):
                    for item in v:
                        collect(item)
                elif isinstance(v, dict):
                    collect(v)
        collect(entry)
        return min(ns), max(ns)

    def remove_entry(self, *keys):
        first, last = self.entry_lines(*keys)
        lines = self.lines()
        del lines[first - 1:last]
        self.write(lines)

    def remove_line(self, *keys):
        _, n = self.node(*keys)
        lines = self.lines()
        del lines[n - 1]
        self.write(lines)

    def add_entry(self, *keys, fields):
        """Adds an entry at the end of a list, lined up with the entries above.
        fields: [(label, value)] or, for a nested list, [(label, [entries])]."""
        items, _ = self.node(*keys)
        first, _ = self.entry_lines(*keys, 0)
        _, last = self.entry_lines(*keys, len(items) - 1)
        lines = self.lines()
        dash = lines[first - 1].index("-")
        lines[last:last] = self.render(dash, fields)
        self.write(lines)

    def render(self, dash, fields):
        out = []
        for i, (k, v) in enumerate(fields):
            lead = " " * dash + ("- " if i == 0 else "  ")
            if isinstance(v, list):
                out.append(f"{lead}{k}:\n")
                for sub in v:
                    out += self.render(dash + 4, sub)
            else:
                out.append(f'{lead}{k}: "{v}"\n')
        return out

    def add_label(self, *keys, label, value):
        """Adds label: "value" as the last line of an entry."""
        first, last = self.entry_lines(*keys)
        lines = self.lines()
        col = lines[first - 1].index("-") + 2
        lines[last:last] = [" " * col + f'{label}: "{value}"\n']
        self.write(lines)


def docx_rewrite(path, change):
    """Rewrites every XML part of a Word file through change(name, text)."""
    src = zipfile.ZipFile(io.BytesIO(path.read_bytes()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for info in src.infolist():
            data = src.read(info)
            if info.filename.endswith((".xml", ".rels")):
                data = change(info.filename, data.decode("utf-8")).encode("utf-8")
            z.writestr(info, data)
    path.write_bytes(out.getvalue())


def docx_text_of(path):
    z = zipfile.ZipFile(path)
    return " ".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith((".xml", ".rels")))


def minimal_pdf(text=""):
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    return (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n"
            b"4 0 obj<</Length " + str(len(stream)).encode() + b">>stream\n" + stream + b"\nendstream endobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF\n")


def minimal_docx(text):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f"<w:document><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>")
        z.writestr("docProps/core.xml", "<cp:coreProperties><dc:creator>Spokane County ARES-ACS</dc:creator>"
                                        "<cp:lastModifiedBy></cp:lastModifiedBy></cp:coreProperties>")
    return b.getvalue()


class RealSite(unittest.TestCase):
    """A copy of the real site with its real data, built with the real build.sh."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.site = copy_site(self.root, fixtures=False)
        self.facts = DataFile(self.site / "data" / "facts.yaml")
        self.resources = DataFile(self.site / "data" / "resources.yaml")
        self.files = self.site / "static" / "files"

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self, self_tests=False):
        env = {**os.environ}
        if self_tests:
            env[NESTED] = "1"
        else:
            env["BUILD_SKIP_SELF_TESTS"] = "1"
        r = subprocess.run(["sh", str(self.site / "tools" / "build.sh")], capture_output=True, text=True, env=env,
                           timeout=900)
        return r.returncode, r.stdout + r.stderr

    def no_data_file_in(self, out):
        for name in ("facts.yaml", "resources.yaml"):
            lines = [l for l in DataFile(self.site / "data" / name).lines() if l.strip()][:4]
            for form in ("".join(lines), "\\n".join(l.rstrip("\n") for l in lines)):
                if form in out:
                    self.fail(f"the output printed {name}")

    def passes(self, *pages, values=(), self_tests=False):
        """Runs the gate; it must pass and every value must be on one of the pages."""
        code, out = self.gate(self_tests)
        self.no_data_file_in(out)
        tail = "\n".join(out.splitlines()[-25:])
        self.assertEqual(code, 0, f"the gate refused a routine edit:\n{tail}")
        texts = {p: page_text(self.site / "public" / p) for p in pages}
        for v in values:
            norm_v = re.sub(r"\s+", " ", v).replace("−", "-")
            self.assertTrue(any(norm_v in t for t in texts.values()),
                            f"{v!r} is not on {', '.join(pages)} after the edit")
        return texts

    def refused(self, needle):
        code, out = self.gate()
        self.no_data_file_in(out)
        tail = "\n".join(out.splitlines()[-25:])
        self.assertNotEqual(code, 0, f"the gate let a mistake through:\n{tail}")
        hits = [l for l in out.splitlines() if needle in l]
        self.assertEqual(len(hits), 1, f"expected one line saying {needle!r}:\n{tail}")
        self.assertLess(len(hits[0]), 400, hits[0])
        return hits[0]

    # helpers that read today's data, whatever it says
    def other(self, current, *choices):
        return next(c for c in choices if c != current)

    def unit(self):
        return self.facts.get("leadership", "unit")


class RoutineEdits(RealSite):
    """T1: each routine yearly edit to the real data passes the real gate and
    publishes the new value. The edits are worked out from today's data."""

    # -- leadership
    def test_change_one_call_sign(self):
        self.facts.set("leadership", "unit", 0, "callsign", value="K7ZQX")
        self.passes("about/index.html", values=["K7ZQX"])

    def test_change_every_call_sign(self):
        new = []
        for group in ("unit", "section"):
            for i in range(len(self.facts.get("leadership", group))):
                call = f"K7Z{chr(65 + len(new) // 26)}{chr(65 + len(new) % 26)}"
                self.facts.set("leadership", group, i, "callsign", value=call)
                new.append(call)
        self.passes("about/index.html", values=new)

    def test_two_call_signs_in_one_position(self):
        self.facts.set("leadership", "unit", 0, "callsign", value="K7ZQA, K7ZQB")
        self.passes("about/index.html", values=["K7ZQA, K7ZQB"])

    def test_slash_suffix_call_sign(self):
        self.facts.set("leadership", "unit", 0, "callsign", value="K7ZQA/AE")
        self.passes("about/index.html", values=["K7ZQA/AE"])

    def test_prefix_style_portable_call_sign(self):
        self.facts.set("leadership", "unit", 0, "callsign", value="KL7/K7ZQA")
        self.passes("about/index.html", values=["KL7/K7ZQA"])

    def test_remove_a_unit_position(self):
        unit = self.unit()
        gone = unit[-1]["role"]
        self.facts.remove_entry("leadership", "unit", len(unit) - 1)
        texts = self.passes("about/index.html", values=[unit[0]["role"]])
        if sum(u["role"] == gone for u in unit) == 1 and all(gone not in u["role"] for u in unit[:-1]):
            self.assertNotIn(f" {gone} ", texts["about/index.html"])

    def test_add_a_unit_position(self):
        self.facts.add_entry("leadership", "unit", fields=[("role", "AEC, Training"), ("callsign", "K7ZQY")])
        self.passes("about/index.html", values=["Training", "K7ZQY"])

    def test_change_a_role_name(self):
        self.facts.set("leadership", "section", 0, "role", value="Assistant Section Manager")
        self.passes("about/index.html", values=["Assistant Section Manager"])

    # -- the net and the repeaters
    def test_change_net_day_and_time(self):
        day = self.other(self.facts.get("net", "day"), "Wednesday", "Monday")
        time = self.other(self.facts.get("net", "time"), "7:15 PM", "6:45 PM")
        self.facts.set("net", "day", value=day)
        self.facts.set("net", "time", value=time)
        self.passes("how-it-works/index.html", "index.html", "about/index.html", values=[f"Every {day}, {time}"])

    def primary(self, tone):
        freq = self.other(self.facts.get("repeater", "primary", "freq"), "146.940 MHz", "147.020 MHz")
        offset = self.other(self.facts.get("repeater", "primary", "offset"), "-600 kHz", "+600 kHz")
        self.facts.set("repeater", "primary", "freq", value=freq)
        self.facts.set("repeater", "primary", "offset", value=offset)
        self.facts.set("repeater", "primary", "tone", value=tone)
        self.passes("how-it-works/index.html", "members/index.html", values=[f"{freq}, {offset}, {tone}"])

    def test_change_primary_frequency_offset_and_tone_hz(self):
        self.primary(self.other(self.facts.get("repeater", "primary", "tone"), "131.8 Hz", "127.3 Hz"))

    def test_change_primary_tone_to_dcs(self):
        self.primary("DCS 023")

    def test_change_primary_tone_to_no_tone(self):
        self.primary("no tone")

    def test_change_the_alternate_repeater(self):
        freq = self.other(self.facts.get("repeater", "alternate", "freq"), "145.490 MHz", "145.110 MHz")
        self.facts.set("repeater", "alternate", "freq", value=freq)
        self.facts.set("repeater", "alternate", "offset", value="-600 kHz")
        self.facts.set("repeater", "alternate", "tone", value="no tone")
        self.passes("how-it-works/index.html", values=[f"{freq}, -600 kHz, no tone"])

    def test_change_the_club_call_sign(self):
        call = self.other(self.facts.get("repeater", "primary", "call"), "K7ZQC", "K7ZQD")
        self.facts.set("repeater", "primary", "call", value=call)
        self.passes("how-it-works/index.html", "index.html", values=[call])

    def test_change_winlink_nights(self):
        nights = self.other(self.facts.get("winlink_nights"), "first and third", "second and fourth")
        self.facts.set("winlink_nights", value=nights)
        self.passes("how-it-works/index.html", values=[f"{nights} {self.facts.get('net', 'day')}s"])

    # -- meetings and place
    def test_change_a_meeting_time(self):
        when = self.other(self.facts.get("meetings", 0, "when"), "First Monday of each month, 7:00 PM",
                          "Second Monday of each month, 7:00 PM")
        self.facts.set("meetings", 0, "when", value=when)
        self.passes("index.html", values=[when])

    def test_add_a_meeting(self):
        self.facts.add_entry("meetings", fields=[("name", "Field Day planning"),
                                                 ("when", "Fourth Tuesday of each month, 7:00 PM")])
        self.passes("index.html", values=["Field Day planning", "Fourth Tuesday of each month, 7:00 PM"])

    def test_remove_the_extra_line(self):
        meetings = self.facts.get("meetings")
        with_extra = [i for i, m in enumerate(meetings) if "extra" in m]
        if not with_extra:
            # Today's data has none: adding one is the routine edit instead.
            self.facts.add_label("meetings", 0, label="extra", value="then coffee")
            self.passes("index.html", values=["then coffee"])
            return
        for i in reversed(with_extra):
            self.facts.remove_line("meetings", i, "extra")
        texts = self.passes("index.html", values=[meetings[0]["when"]])
        for i in with_extra:
            self.assertNotIn(meetings[i]["extra"], texts["index.html"])

    def test_change_the_meeting_place(self):
        self.facts.set("place", "name", value="Spokane Valley Fire Station 8")
        self.facts.set("place", "street", value="2320 N Argonne Rd")
        self.facts.set("place", "city", value="Spokane Valley")
        self.passes("index.html", values=["Spokane Valley Fire Station 8, 2320 N Argonne Rd, Spokane Valley"])

    def test_change_the_members_group_address(self):
        new = self.other(self.facts.get("groupsio"), "https://spokane-ares.groups.io/g/members",
                         "https://spokane-ares.groups.io/g/main")
        self.facts.set("groupsio", value=new)
        self.passes("members/index.html", values=[new])

    # -- contact and hosted files
    def test_change_contact_email_with_a_corrected_application(self):
        old = self.facts.get("contact", "email")
        new = "secretary@" + old.split("@", 1)[1]
        self.facts.set("contact", "email", value=new)
        changed = 0
        for f in sorted(self.files.glob("*.docx")):
            if old in docx_text_of(f):
                docx_rewrite(f, lambda name, t: t.replace(old, new))
                changed += 1
        self.passes("about/index.html", values=[new])

    def test_replace_a_hosted_file_with_a_new_version(self):
        entry = self.facts.get("files", 0)
        f = self.files / entry["file"]
        if f.suffix == ".docx":
            docx_rewrite(f, lambda name, t: t.replace("</w:body>", "<w:p><w:r><w:t>Revised.</w:t></w:r></w:p></w:body>")
                         if name == "word/document.xml" else t)
        else:
            f.write_bytes(f.read_bytes() + b"\n% revised\n")
        version = self.other(entry["version"], "March 3, 2025", "April 4, 2025")
        self.facts.set("files", 0, "version", value=version)
        self.passes("members/index.html", "about/index.html", values=[f"{entry['kind']}, {version}"])

    def test_change_a_hosted_file_from_word_to_pdf(self):
        files = self.facts.get("files")
        i = next((i for i, e in enumerate(files) if e["file"].endswith(".docx")), 0)
        entry = files[i]
        stem, ext = entry["file"].rsplit(".", 1)
        email = self.facts.get("contact", "email")
        (self.files / entry["file"]).unlink()
        if ext == "docx":
            name, kind = f"{stem}.pdf", "PDF"
            (self.files / name).write_bytes(minimal_pdf(f"Send it to {email}"))
        else:
            name, kind = f"{stem}.docx", "Word document"
            (self.files / name).write_bytes(minimal_docx(f"Send it to {email}"))
        version = self.other(entry["version"], "May 2025", "June 2025")
        self.facts.set("files", i, "file", value=name)
        self.facts.set("files", i, "kind", value=kind)
        self.facts.set("files", i, "version", value=version)
        self.passes("members/index.html", values=[f"{kind}, {version}", f"files/{name}"])

    # -- Resources
    def test_add_a_resource_link(self):
        self.resources.add_entry("groups", 0, "links", fields=[
            ("title", "ARRL Field Day"), ("url", "https://www.arrl.org/field-day"), ("opens", "ARRL"),
            ("note", "The yearly operating event in June.")])
        self.passes("resources/index.html", values=["ARRL Field Day", "https://www.arrl.org/field-day"])

    def test_change_a_resource_link(self):
        self.resources.set("groups", 0, "links", 0, "title", value="Courses from FEMA")
        self.resources.set("groups", 0, "links", 0, "note", value="Free courses you can take at home.")
        self.passes("resources/index.html", values=["Courses from FEMA", "Free courses you can take at home."])

    def test_remove_a_resource_link(self):
        links = self.resources.get("groups", 0, "links")
        if len(links) == 1:
            self.resources.add_entry("groups", 0, "links", fields=[
                ("title", "ARRL Field Day"), ("url", "https://www.arrl.org/field-day"), ("note", "Each June.")])
        gone = links[0]
        self.resources.remove_entry("groups", 0, "links", 0)
        texts = self.passes("resources/index.html")
        if sum(gone["url"] in str(g) for g in self.resources.get("groups")) == 0:
            self.assertNotIn(gone["url"], texts["resources/index.html"])

    def test_add_a_resource_group(self):
        self.resources.add_entry("groups", fields=[
            ("id", "e2e-preparedness"), ("title", "Getting prepared"),
            ("links", [[("title", "Ready.gov"), ("url", "https://www.ready.gov/"), ("opens", "FEMA"),
                        ("note", "Make a plan and a kit for your household.")]])])
        self.passes("resources/index.html", values=["Getting prepared", "Ready.gov"])


class MistakesStillRefused(RealSite):
    """T1: clear mistakes in the real data are refused with one plain line."""

    def test_personal_email(self):
        self.facts.set("contact", "email", value="bob.smith@gmail.com")
        self.refused("never a personal address")

    def test_placeholder_position(self):
        self.facts.set("leadership", "unit", 0, "callsign", value="vacant")
        self.refused("marks an empty position")

    def test_date_in_a_meeting_rule(self):
        self.facts.set("meetings", 0, "when", value="December 18, 6:00 PM")
        self.refused("printed date 'December 18'")

    def test_html_in_a_data_value(self):
        self.facts.set("meetings", 0, "name", value="<b>Workshop</b>")
        self.refused("are not allowed in page text")

    def test_html_typed_in_a_page(self):
        f = self.site / "content" / "members.md"
        f.write_text(f.read_text(encoding="utf-8") + "\nPress <kbd>Enter</kbd> to send.\n", encoding="utf-8")
        self.refused("HTML tags are not allowed in page text; remove <kbd>")


@unittest.skipIf(os.environ.get(NESTED), "already inside the full gate run by FullGate")
class FullGate(RealSite):
    """T1: the whole build.sh, its self-tests included, passes on real data
    after a year's worth of routine edits at once. This proves no self-test
    depends on today's data."""

    def test_full_gate_after_a_year_of_edits(self):
        f = self.facts
        for group in ("unit", "section"):
            for i in range(len(f.get("leadership", group))):
                f.set("leadership", group, i, "callsign", value=f"K7Y{'AB'[group == 'section']}{chr(65 + i)}")
        f.remove_entry("leadership", "unit", len(self.unit()) - 1)
        f.set("net", "day", value=self.other(f.get("net", "day"), "Wednesday", "Monday"))
        f.set("net", "time", value=self.other(f.get("net", "time"), "7:15 PM", "6:45 PM"))
        f.set("repeater", "primary", "call", value=self.other(f.get("repeater", "primary", "call"), "K7ZQC", "K7ZQD"))
        f.set("repeater", "primary", "tone", value="DCS 023")
        f.set("repeater", "alternate", "tone", value="no tone")
        f.set("winlink_nights", value=self.other(f.get("winlink_nights"), "first and third", "second and fourth"))
        f.set("meetings", 0, "when", value="First Monday of each month, 7:00 PM")
        old = f.get("contact", "email")
        new = "secretary@" + old.split("@", 1)[1]
        f.set("contact", "email", value=new)
        for doc in sorted(self.files.glob("*.docx")):
            if old in docx_text_of(doc):
                docx_rewrite(doc, lambda name, t: t.replace(old, new))
        self.resources.set("groups", 0, "links", 0, "title", value="Courses from FEMA")
        code, out = self.gate(self_tests=True)
        self.no_data_file_in(out)
        self.assertEqual(code, 0, "the full gate refused routine edits:\n" + "\n".join(out.splitlines()[-40:]))
        self.assertIn("== 4. Self-tests", out)
        self.assertIn("All checks passed", out)
        self.assertIn(new, page_text(self.site / "public" / "about" / "index.html"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
