#!/usr/bin/env python3
"""Build tests: the templates refuse bad input, and facts reach every page.

Run: python3 site/tools/test_build.py     (needs hugo 0.164.0 on the PATH)

Each test copies site/ to a temporary folder, makes one change, builds it
with the same hugo command CI uses and looks at the result. These cover what
check_data.py and check_site.py cannot see on their own: what the templates
do with a bad value that got past the data check, typed raw HTML inside a
designed block, and whether a changed fact reaches every page.
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
BASE = "/spokares-static"


class Build(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.site = self.root / "site"
        shutil.copytree(SITE, self.site, ignore=shutil.ignore_patterns("public", "resources", ".hugo_build.lock"))

    def tearDown(self):
        self._tmp.cleanup()

    def edit(self, rel, old, new, count=1):
        f = self.site / rel
        text = f.read_text(encoding="utf-8")
        self.assertIn(old, text, f"test setup: {old!r} not in {rel}")
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
    def test_real_site_builds_and_passes_the_checker(self):
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
            text = html.unescape(p.read_text(encoding="utf-8")).replace(" ", " ")
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
        how = html.unescape(self.page(self.built(), "how-it-works/index.html")).replace("\u00a0", " ")
        self.assertIn("146.880 MHz, −600 kHz, no tone<", how)
        self.assertIn("147.300 MHz, +600 kHz, DCS 023<", how)
        self.assertIn('data-copy-text="Alternate repeater 146.880 MHz, -600 kHz offset, no tone"', how)
        self.assertNotIn("tone tone", how)

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

    def test_form_numbers_do_not_break(self):
        pub = self.built()
        self.assertIn('<span class="nobr">(ICS-213RR)</span>', self.page(pub, "resources/index.html"))
        self.assertIn('<span class="nobr">ICS-213RR</span>', self.page(pub, "members/index.html"))
        self.assertNotIn('nobr"><span class="nobr', self.page(pub, "members/index.html"))


class BuildScript(unittest.TestCase):
    """R11: build.sh refuses arguments it does not understand, in one line."""

    def run_sh(self, *args):
        r = subprocess.run(["sh", str(TOOLS / "build.sh"), *args], capture_output=True, text=True, timeout=60)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
