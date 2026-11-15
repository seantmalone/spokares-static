#!/usr/bin/env python3
"""Developer's check (NOT part of the publish gate): routine yearly edits to
the REAL site pass the real build.sh, and clear mistakes are refused.

Run: sh site/tools/dev-check.sh     (or python3 site/tools/live_edits.py)

Each test copies the real site/ with its real data, pages and hosted files,
makes one routine edit a volunteer makes (worked out from whatever the data
says today, never from fixed values), and runs the real site/tools/build.sh
on the copy (steps 1 to 3; BUILD_SKIP_SELF_TESTS=1). Each edit must pass and
its new value must be on the built page; each clear mistake must be refused
with one plain line. Run it after changing a template or a tool. Because it
reads today's data, a failure here can mean the data changed in a way the
test did not foresee; the gate itself never runs these tests.

A failing test never prints a data file: messages name the file and the value.
"""
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
IGNORE = shutil.ignore_patterns("public", "resources", ".hugo_build.lock", ".reference", "__pycache__")

sys.path.insert(0, str(TOOLS))
import check_data  # noqa: E402  (same folder; standard library only)
import check_site  # noqa: E402
from test_build import change_every_fact, page_text, small_docx, stale_values  # noqa: E402


def copy_real_site(dest):
    site = dest / "site"
    shutil.copytree(SITE, site, ignore=IGNORE)
    return site


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


def docx_paragraphs(path):
    """The text of a Word file as the checker reads it, one paragraph per line
    (however Word split the words into runs)."""
    text, _, err = check_site.docx_text(path)
    assert not err, f"{path.name}: {err}"
    return [l for l in text.splitlines() if l.strip()]


def minimal_pdf(text=""):
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    return (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n"
            b"4 0 obj<</Length " + str(len(stream)).encode() + b">>stream\n" + stream + b"\nendstream endobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF\n")


def minimal_docx(*paragraphs):
    """A small, clean Word file with these paragraphs of text."""
    from xml.sax.saxutils import escape
    body = "".join(f"<w:p><w:r><w:t>{escape(p)}</w:t></w:r></w:p>" for p in paragraphs)
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f"<w:document><w:body>{body}</w:body></w:document>")
        z.writestr("docProps/core.xml", "<cp:coreProperties><dc:creator>Spokane County ARES-ACS</dc:creator>"
                                        "<cp:lastModifiedBy></cp:lastModifiedBy></cp:coreProperties>")
    return b.getvalue()


class RealSite(unittest.TestCase):
    """A copy of the real site with its real data, built with the real build.sh."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.site = copy_real_site(self.root)
        self.facts = DataFile(self.site / "data" / "facts.yaml")
        self.resources = DataFile(self.site / "data" / "resources.yaml")
        self.files = self.site / "static" / "files"

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self):
        env = {**os.environ, "BUILD_SKIP_SELF_TESTS": "1"}
        r = subprocess.run(["sh", str(self.site / "tools" / "build.sh")], capture_output=True, text=True, env=env,
                           timeout=900)
        return r.returncode, r.stdout + r.stderr

    def no_data_file_in(self, out):
        for name in ("facts.yaml", "resources.yaml"):
            lines = [l for l in DataFile(self.site / "data" / name).lines() if l.strip()][:4]
            for form in ("".join(lines), "\\n".join(l.rstrip("\n") for l in lines)):
                if form in out:
                    self.fail(f"the output printed {name}")

    def passes(self, *pages, values=()):
        """Runs the gate; it must pass and every value must be on one of the pages."""
        code, out = self.gate()
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

    def unused(self, value):
        """value, or value with a number added, so that it is not already in
        the data files (an added link or group must not repeat one)."""
        text = (self.site / "data" / "facts.yaml").read_text(encoding="utf-8") + \
            (self.site / "data" / "resources.yaml").read_text(encoding="utf-8")
        n, cand = 1, value
        while f'"{cand}"' in text:
            n += 1
            cand = f"{value}{n}" if not value.endswith("/") else f"{value}{n}/"
        return cand

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
        # The corrected form, made from the text of today's form with the new
        # address (Word may split an address over several runs, so the XML is
        # not edited in place).
        for f in sorted(self.files.glob("*.docx")):
            paragraphs = docx_paragraphs(f)
            if any(old in p for p in paragraphs):
                f.write_bytes(minimal_docx(*(p.replace(old, new) for p in paragraphs)))
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
        url = self.unused("https://www.arrl.org/field-day")
        self.resources.add_entry("groups", 0, "links", fields=[
            ("title", "ARRL Field Day"), ("url", url), ("opens", "ARRL"),
            ("note", "The yearly operating event in June.")])
        self.passes("resources/index.html", values=["ARRL Field Day", url])

    def test_change_a_resource_link(self):
        self.resources.set("groups", 0, "links", 0, "title", value="Courses from FEMA")
        self.resources.set("groups", 0, "links", 0, "note", value="Free courses you can take at home.")
        self.passes("resources/index.html", values=["Courses from FEMA", "Free courses you can take at home."])

    def test_remove_a_resource_link(self):
        links = self.resources.get("groups", 0, "links")
        if len(links) == 1:
            self.resources.add_entry("groups", 0, "links", fields=[
                ("title", "ARRL Field Day"), ("url", self.unused("https://www.arrl.org/field-day")),
                ("note", "Each June.")])
        gone = links[0]
        self.resources.remove_entry("groups", 0, "links", 0)
        texts = self.passes("resources/index.html")
        if sum(gone["url"] in str(g) for g in self.resources.get("groups")) == 0:
            self.assertNotIn(gone["url"], texts["resources/index.html"])

    def test_add_a_resource_group(self):
        self.resources.add_entry("groups", fields=[
            ("id", self.unused("e2e-preparedness")), ("title", "Getting prepared"),
            ("links", [[("title", "Ready.gov"), ("url", self.unused("https://www.ready.gov/")), ("opens", "FEMA"),
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



class EveryFactChangedOnTheRealSite(RealSite):
    """F1: every fact in the real facts.yaml changed at once passes the gate,
    and no old value stays on the site except the text listed in
    test_build.STAYS (history, and names that are not the fact)."""

    def test_no_old_value_is_left(self):
        changed = change_every_fact(self.site, small_docx)
        self.passes("about/index.html", values=[new for path, _, new in changed if path.startswith("leadership")])
        left = stale_values(self.site / "public", changed)
        self.assertEqual(left, [], "\n".join(left))


class FixturesMatchTheRealFiles(unittest.TestCase):
    """G4: the fixture data files carry the same comments as the real ones, so
    the self-tests read like the files a volunteer edits."""

    def test_comments(self):
        for name in ("facts", "resources"):
            real = (SITE / "data" / f"{name}.yaml").read_text(encoding="utf-8")
            fixture = (TOOLS / "fixtures" / "data" / f"{name}.fixture.yaml").read_text(encoding="utf-8")
            comments = [[l for l in t.splitlines() if l.lstrip().startswith("#") and "TEST DATA" not in l]
                        for t in (real, fixture)]
            self.assertEqual(comments[0], comments[1], f"the comments in {name}.fixture.yaml differ from {name}.yaml")


if __name__ == "__main__":
    unittest.main(verbosity=2)
