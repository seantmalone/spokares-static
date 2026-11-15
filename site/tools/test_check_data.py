#!/usr/bin/env python3
"""Self-test for check_data.py. Standard library only.

Run: python3 site/tools/test_check_data.py

Each test copies the frozen fixture copies of facts.yaml and resources.yaml
(site/tools/fixtures/data/, never the live site/data/ files, so a yearly edit
cannot break a test) into a temporary folder, makes one edit a volunteer might
make, and runs check_data.py on it as a subprocess, the way the build does. A
mistake must fail with one plain line naming the file and line, and never a
Python traceback. A failing test names the value, never prints the file.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
CHECKER = TOOLS / "check_data.py"
DATA = TOOLS / "fixtures" / "data"


class Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        for name in ("facts.yaml", "resources.yaml"):
            (self.dir / name).write_bytes((DATA / name).read_bytes())

    def tearDown(self):
        self._tmp.cleanup()

    def edit(self, name, old, new):
        f = self.dir / name
        text = f.read_text(encoding="utf-8")
        if old not in text:
            self.fail(f"test setup: {old!r} is not in the fixture {name}")
        f.write_text(text.replace(old, new, 1), encoding="utf-8")

    def run_checker(self):
        r = subprocess.run([sys.executable, str(CHECKER), str(self.dir)], capture_output=True, text=True)
        out = r.stdout + r.stderr
        self.assertNotIn("Traceback", out)
        return r.returncode, out

    def fails(self, name, old, new, *needles, line=None):
        self.edit(name, old, new)
        code, out = self.run_checker()
        self.assertEqual(code, 1, f"expected a failure; output:\n{out}")
        first = out.splitlines()[0]
        self.assertTrue(first.startswith(f"{self.dir}/{name} line "), first)
        if line is not None:
            self.assertTrue(first.startswith(f"{self.dir}/{name} line {line}:"), first)
        for n in needles:
            self.assertIn(n, first)
        return first

    def line_of(self, name, text):
        for n, line in enumerate((self.dir / name).read_text(encoding="utf-8").splitlines(), 1):
            if text in line:
                return n
        self.fail(f"{text!r} not in {name}")


F, R = "facts.yaml", "resources.yaml"


class FixtureFiles(Case):
    def test_fixture_files_pass(self):
        code, out = self.run_checker()
        self.assertEqual(code, 0, out)
        self.assertIn("look right", out)

    def test_default_folder_is_site_data(self):
        # A copy of the checker in <tmp>/site/tools reads <tmp>/site/data.
        tools, data = self.dir / "site" / "tools", self.dir / "site" / "data"
        tools.mkdir(parents=True)
        shutil.copy(CHECKER, tools / CHECKER.name)
        shutil.copytree(DATA, data)
        r = subprocess.run([sys.executable, str(tools / CHECKER.name)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (data / "facts.yaml").write_text('net:\n  day: "Tuesday\n', encoding="utf-8")
        r = subprocess.run([sys.executable, str(tools / CHECKER.name)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("site/data/facts.yaml line 2", r.stdout)

    def test_bad_arguments(self):
        r = subprocess.run([sys.executable, str(CHECKER), "--nope"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("usage", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_missing_folder(self):
        r = subprocess.run([sys.executable, str(CHECKER), str(self.dir / "nope")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("cannot be read", r.stdout)
        self.assertNotIn("Traceback", r.stdout + r.stderr)


class Syntax(Case):
    """M3: a typing mistake gives one line with the right line number."""

    def test_deleted_closing_quote(self):
        n = self.line_of(F, 'time: "8:00 PM"')
        self.fails(F, 'time: "8:00 PM"', 'time: "8:00 PM', "quote mark is missing", line=n)

    def test_deleted_opening_quote(self):
        n = self.line_of(F, 'time: "8:00 PM"')
        self.fails(F, 'time: "8:00 PM"', 'time: 8:00 PM"', "in double quotes", line=n)

    def test_curly_quotes(self):
        self.fails(F, 'time: "8:00 PM"', 'time: “8:00 PM”', "curly quote")

    def test_tab_indent(self):
        n = self.line_of(F, 'time: "8:00 PM"')
        self.fails(F, '  time: "8:00 PM"', '\ttime: "8:00 PM"', "tab", line=n)

    def test_duplicate_key(self):
        n = self.line_of(F, 'time: "8:00 PM"') + 1
        self.fails(F, '  time: "8:00 PM"', '  time: "8:00 PM"\n  time: "7:00 PM"', "given twice", line=n)

    def test_bad_indent(self):
        n = self.line_of(F, 'time: "8:00 PM"')
        self.fails(F, '  time: "8:00 PM"', '   time: "8:00 PM"', "line", line=n)

    def test_entry_label_not_lined_up(self):
        self.fails(F, '      callsign: "AA7RT, W7UWC"\n',
                   '      callsign: "AA7RT, W7UWC"\n    - role: "New role"\n    callsign: "K7NEW"\n', "entries")

    def test_label_with_nothing(self):
        self.fails(F, '      callsign: "AA7RT, W7UWC"\n',
                   '      callsign: "AA7RT, W7UWC"\n    - role: "New role"\n      callsign:\n', "nothing after it")

    def test_text_after_quote(self):
        self.fails(F, 'time: "8:00 PM"', 'time: "8:00" PM', "after the closing quote")

    def test_trailing_comment_is_fine(self):
        self.edit(F, 'time: "8:00 PM"', 'time: "8:00 PM"   # local time')
        code, out = self.run_checker()
        self.assertEqual(code, 0, out)

    def test_escaped_quote_is_fine(self):
        self.edit(R, 'note: "Forecasts and warnings for the Inland Northwest."',
                  'note: "Forecasts and \\"warnings\\" for the Inland Northwest."')
        code, out = self.run_checker()
        self.assertEqual(code, 0, out)

    def test_empty_list_brackets(self):
        self.fails(F, '  section:\n', '  section: []\n  old_section:\n', "in double quotes")

    def test_not_utf8(self):
        (self.dir / F).write_bytes(b'net:\n  day: "Tu\xe9sday"\n')
        code, out = self.run_checker()
        self.assertEqual(code, 1)
        self.assertIn("UTF-8", out)


class Unquoted(Case):
    """M1: a value typed without quotes is refused before Hugo sees it."""

    def test_number(self):
        self.fails(F, 'freq: "147.300 MHz"', 'freq: 147.300', "freq: 147.300 must be in double quotes")

    def test_integer(self):
        self.fails(F, 'tone: "100 Hz"', 'tone: 100', "must be in double quotes")

    def test_time(self):
        self.fails(F, 'time: "8:00 PM"', 'time: 20:00', "must be in double quotes")

    def test_yes(self):
        self.fails(F, 'day: "Tuesday"', 'day: yes', "must be in double quotes")

    def test_resource_url(self):
        self.fails(R, 'url: "https://hamstudy.org/"', 'url: https://hamstudy.org/', "must be in double quotes")


class Labels(Case):
    """m2: unknown or renamed labels are refused, required ones must be there."""

    def test_capitalised_label(self):
        self.fails(F, '  time: "8:00 PM"', '  Time: "8:00 PM"', 'unknown label "Time"', 'did you mean "time"')

    def test_extra_capitalised(self):
        self.fails(F, '    extra: "then', '    Extra: "then', 'unknown label "Extra"')

    def test_callsign_renamed(self):
        first = self.fails(F, '      callsign: "K7MHG"', '      call: "K7MHG"', 'unknown label "call"')
        self.assertIn("leadership.unit[3]", first)

    def test_misspelled_opens(self):
        self.fails(R, '        opens: "NWS Spokane"', '        open: "NWS Spokane"', 'unknown label "open"')

    def test_note_capitalised(self):
        self.fails(R, '        note: "Free practice', '        Note: "Free practice', 'unknown label "Note"')

    def test_missing_required(self):
        self.fails(F, '    version: "July 2024"\n', '', 'missing its "version"')

    def test_missing_note(self):
        self.fails(R, '        note: "Free practice for the license exams, with the real question pools."\n', '',
                   'missing its "note"')

    def test_all_section_positions_removed(self):
        text = (self.dir / F).read_text(encoding="utf-8")
        start = text.index("  section:\n")
        end = text.index("\ncontact:")
        (self.dir / F).write_text(text[:start] + "  section:\n" + text[end:], encoding="utf-8")
        code, out = self.run_checker()
        self.assertEqual(code, 1)
        self.assertIn('"section:" has nothing after it', out.splitlines()[0])


class Values(Case):
    def test_vacant(self):
        self.fails(F, 'callsign: "K7MHG"', 'callsign: "vacant"', "empty position")

    def test_tbd(self):
        self.fails(F, 'callsign: "K7MHG"', 'callsign: "TBD"', "empty position")

    def test_open_in_parentheses(self):
        self.fails(F, 'callsign: "K7MHG"', 'callsign: "(open)"', "empty position")

    def test_open_capital(self):
        self.fails(F, 'callsign: "K7MHG"', 'callsign: "Open"', "empty position")

    def test_position_open_in_role(self):
        self.fails(F, '"AEC, Hospital Coordinator"', '"AEC, Hospital Coordinator (position open)"', "empty position")

    def test_to_be_filled(self):
        self.fails(F, '"AEC, Hospital Coordinator"', '"AEC, Hospital Coordinator (to be filled soon)"', "empty position")

    def test_callsign_lower_case(self):
        self.fails(F, 'callsign: "NV2Z"', 'callsign: "nv2z"', "call sign")

    def test_callsign_list_ok(self):
        self.edit(F, 'callsign: "NV2Z"', 'callsign: "NV2Z, KA7LJQ"')
        code, out = self.run_checker()
        self.assertEqual(code, 0, out)

    def test_html_in_role(self):
        self.fails(F, '"AEC, Net Manager"', '"AEC, <b>Net</b> Manager"', "not allowed in page text")

    def test_markdown_in_title(self):
        self.fails(F, 'title: "ACS Position Task Book"', 'title: "ACS Position Task Book *new*"', "not allowed")

    def test_trailing_space_inside_quotes(self):
        self.fails(F, 'time: "8:00 PM"', 'time: "8:00 PM "', "space just inside")

    def test_empty_value(self):
        self.fails(F, 'time: "8:00 PM"', 'time: ""', "is empty")

    def test_weekday_lower_case(self):
        self.fails(F, 'day: "Tuesday"', 'day: "tuesday"', "day of the week")

    def test_freq_without_unit(self):
        self.fails(F, 'freq: "147.300 MHz"', 'freq: "147.300"', "frequency")

    def test_winlink_with_day(self):
        self.fails(F, 'winlink_nights: "second and fourth"', 'winlink_nights: "second and fourth Tuesdays"',
                   "the site adds the net day")

    def test_personal_email(self):
        self.fails(F, 'email: "info@spokares.org"', 'email: "bob.smith@gmail.com"', "site's own domain")

    def test_email_upper_case(self):
        self.fails(F, 'email: "info@spokares.org"', 'email: "Info@SpokARES.org"', "lower case")

    def test_groupsio_files(self):
        self.fails(F, 'groupsio: "https://spokaneares-acs.groups.io/g/main"',
                   'groupsio: "https://spokaneares-acs.groups.io/g/main/files"', "main page")

    def test_groupsio_javascript(self):
        self.fails(F, 'groupsio: "https://spokaneares-acs.groups.io/g/main"', 'groupsio: "javascript:alert(1)"',
                   "main page")


class Files(Case):
    def test_file_name_with_spaces(self):
        self.fails(F, 'file: "arrl-ares-task-book.pdf"', 'file: "ARRL ARES Task Book.pdf"', "file name")

    def test_file_name_with_parentheses(self):
        self.fails(F, 'file: "acs-task-book.docx"', 'file: "acs task book (v2).docx"', "file name")

    def test_file_name_with_ampersand(self):
        self.fails(F, 'file: "acs-task-book.docx"', 'file: "acs&task.docx"', "file name")

    def test_kind_does_not_match(self):
        self.fails(F, 'file: "ares-application.docx"', 'file: "ares-application.pdf"', "does not match")

    def test_kind_unknown(self):
        self.fails(F, 'kind: "PDF"', 'kind: "PDF file"', '"Word document" or "PDF"')

    def test_version_with_free_text(self):
        self.fails(F, 'version: "July 2024"', 'version: "July 2024; next revision due March 1, 2027"', "version like")

    def test_version_numeric(self):
        self.fails(F, 'version: "July 2024"', 'version: "Revised 7/1/2024"', "version like")

    def test_duplicate_id(self):
        self.fails(F, 'id: "acs-task-book"', 'id: "ares-application"', "used twice")


class Resources(Case):
    A = 'url: "https://hamstudy.org/"'

    def test_http(self):
        self.fails(R, self.A, 'url: "http://example.org/"', "https://")

    def test_space(self):
        self.fails(R, self.A, 'url: "https://example.org/a b"', "space")

    def test_quote(self):
        self.fails(R, self.A, 'url: "https://example.org/a\\"onmouseover=\\"alert(1)"', "quote")

    def test_percent(self):
        self.fails(R, self.A, 'url: "https://example.org/50%off"', "% sign")

    def test_javascript(self):
        self.fails(R, self.A, 'url: "javascript:alert(1)"', "https://")

    def test_no_scheme(self):
        self.fails(R, self.A, 'url: "www.example.org"', "https://")

    def test_mailto(self):
        self.fails(R, self.A, 'url: "mailto:bob@gmail.com"', "https://")

    def test_groups_io(self):
        self.fails(R, self.A, 'url: "https://groups.io/g/foo"', "groups.io")

    def test_groups_io_subdomain(self):
        self.fails(R, self.A, 'url: "https://spokaneares-acs.groups.io/g/main"', "groups.io")

    def test_ag7qp(self):
        self.fails(R, self.A, 'url: "https://WWW.AG7QP.COM/x"', "ag7qp.com")

    def test_userinfo(self):
        self.fails(R, self.A, 'url: "https://groups.io@evil.example/"', "not a normal web address")

    def test_duplicate_group_id(self):
        self.fails(R, '  - id: "weather"', '  - id: "training"', "used by two groups")

    def test_group_id_with_space(self):
        self.fails(R, '  - id: "weather"', '  - id: "weather radio"', "simple name")

    def test_group_without_links(self):
        self.fails(R, '  - id: "weather"', '  - id: "empty"\n    title: "Empty"\n    links:\n  - id: "weather"',
                   "nothing after it")

    def test_opens_empty(self):
        self.fails(R, '        opens: "NWS Spokane"', '        opens: ""', "is empty")

    def test_html_in_note(self):
        self.fails(R, 'note: "Forecasts and warnings for the Inland Northwest."', 'note: "a <i>c</i>"',
                   "not allowed in page text")


class EditorExperience(Case):
    """R7: honest values pass; mistakes get a message that leads to the fix."""

    def passes(self, name, old, new):
        self.edit(name, old, new)
        code, out = self.run_checker()
        self.assertEqual(code, 0, out)

    def test_open_as_an_ordinary_word(self):
        self.passes(F, '"AEC, Public Events; Winlink coordinator"', '"AEC, Public Events and Open House"')

    def test_none_as_an_ordinary_word(self):
        self.passes(F, '"AEC, Hospital Coordinator"', '"AEC, Hospital Coordinator (none of the above)"')

    def test_none_alone_is_refused(self):
        self.fails(F, 'callsign: "K7MHG"', 'callsign: "None"', "empty position")

    def test_no_tone(self):
        self.passes(F, 'tone: "123 Hz"', 'tone: "no tone"')

    def test_dcs_code(self):
        self.passes(F, 'tone: "123 Hz"', 'tone: "DCS 023"')

    def test_decimal_tone(self):
        self.passes(F, 'tone: "123 Hz"', 'tone: "136.5 Hz"')

    def test_list_at_the_same_indent(self):
        text = (self.dir / F).read_text(encoding="utf-8")
        start, end = text.index("meetings:\n") + len("meetings:\n"), text.index("\n# Where the meetings are")
        block = "\n".join(l[2:] if l.startswith("  ") else l for l in text[start:end].splitlines())
        (self.dir / F).write_text(text[:start] + block + "\n" + text[end:], encoding="utf-8")
        code, out = self.run_checker()
        self.assertEqual(code, 0, out)

    def test_slash_suffix_call_sign(self):
        self.passes(F, 'callsign: "NV2Z"', 'callsign: "NV2Z/AE"')

    def test_no_break_space(self):
        self.fails(F, 'time: "8:00 PM"', 'time: "8:00\u00a0PM"', "invisible character (a no-break space)",
                   "type an ordinary space")

    def test_missing_opening_quote_hint(self):
        first = self.fails(F, 'day: "Tuesday"', 'day: Tuesday"', "in double quotes")
        self.assertIn('like day: "Tuesday"', first)
        self.assertNotIn('""', first)

    def test_unquoted_frequency_hint_has_the_unit(self):
        self.fails(F, 'freq: "147.300 MHz"', "freq: 147.300", 'like freq: "147.300 MHz"')

    def test_unquoted_tone_hint_has_the_unit(self):
        self.fails(F, 'tone: "100 Hz"', "tone: 100", 'like tone: "100 Hz"')

    def test_role_line_deleted(self):
        self.fails(F, '    - role: "AEC, Hospital Coordinator"\n', "",
                   "this position has a call sign but no role")


if __name__ == "__main__":
    unittest.main(verbosity=2)
