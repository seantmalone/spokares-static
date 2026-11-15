#!/usr/bin/env python3
"""Checks site/data/facts.yaml and site/data/resources.yaml before the build.

Usage: check_data.py [data-dir]        (default: the site/data folder beside this script)

Hugo's own error for a typing mistake in these files is long and points at
the wrong place, so this runs first and prints one plain line per problem,
naming the file and the line, for example:

  site/data/facts.yaml line 7: a quote mark is missing; every value goes between two straight quote marks, like time: "8:00 PM"

It only understands the simple shape the two files use: labels with values
in double quotes, labels with more labels indented under them, lists of
entries starting with "- ", and comments starting with "#". Anything else is
refused. Then it checks each value: required labels are there, no unknown
labels, call signs look like call signs, file names and web addresses are
safe, and so on.

Standard library only. Exits 0 when both files are right, 1 otherwise.
Self-test: python3 site/tools/test_check_data.py
"""
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# The site's own domain: the contact address must be at it.
SITE_DOMAIN = "spokares.org"
# Outside links on Resources must be https. Add an address here only if the
# owner has agreed it cannot be had over https.
HTTP_ALLOWED = set()
NOT_ON_RESOURCES = ("groups.io", "ag7qp.com")


class DataError(Exception):
    """One problem, already worded for the person editing the file."""

    def __init__(self, where, line, msg):
        super().__init__(f"{where} line {line}: {msg}" if line else f"{where}: {msg}")


# ------------------------------------------------------------------ reading

KEY = r"[A-Za-z0-9_-]+"
# The unit a bare number was probably meant to have, for the hint.
UNITS = {"freq": "MHz", "tone": "Hz", "offset": "kHz"}
LINE = re.compile(rf"^(?P<key>{KEY}):(?:[ ]+(?P<rest>.*))?$")


CURLY = "“”„‘’"


def curly(key, q):
    return f"{key}: this line uses a curly quote {q} — retype it as a straight quote (\"), like {key}: \"...\""


def _value(where, n, key, rest):
    """Reads the text after "key:". Returns the string, or None for "nothing here"
    (more labels follow, indented). Raises DataError for anything else."""
    rest = rest.rstrip()
    if rest == "" or rest.startswith("#"):
        return None
    if rest[0] in CURLY:
        raise DataError(where, n, curly(key, rest[0]))
    if rest[0] != '"':
        shown = rest if len(rest) <= 40 else rest[:40] + "…"
        bare = shown.strip("'\"").strip()
        unit = UNITS.get(key)
        if unit and re.fullmatch(r"[+-]?\d+(?:\.\d+)?", bare):
            return_hint = f"{bare} {unit}"
            raise DataError(where, n, f"{key}: {shown} must be in double quotes, with its unit, like {key}: \"{return_hint}\"")
        raise DataError(where, n, f"{key}: {shown} must be in double quotes, like {key}: \"{bare}\"")
    out, i = [], 1
    while i < len(rest):
        c = rest[i]
        if c == "\\":
            nxt = rest[i + 1:i + 2]
            if nxt not in ('"', "\\"):
                raise DataError(where, n, f"{key}: a backslash (\\) is not allowed in a value; remove it")
            out.append(nxt)
            i += 2
            continue
        if c == '"':
            tail = rest[i + 1:].strip()
            if tail and not tail.startswith("#"):
                raise DataError(where, n, f"{key}: there is text after the closing quote mark ({tail[:30]}); "
                                          "a quote mark inside a value is written \\\"")
            return "".join(out)
        out.append(c)
        i += 1
    bent = next((c for c in rest if c in CURLY), None)
    if bent:
        raise DataError(where, n, curly(key, bent))
    raise DataError(where, n, f"{key}: a quote mark is missing; every value goes between two straight quote marks, "
                              f"like {key}: \"...\"")


def load(path, where=None):
    """Parses one of the two data files into dicts, lists and strings."""
    where = where or str(path)
    try:
        raw = Path(path).read_bytes()
    except OSError as e:
        raise DataError(where, 0, f"cannot be read ({e.strerror})")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DataError(where, 0, "is not plain UTF-8 text; save it again as UTF-8")
    toks = []  # (line number, indent, text); a list item "- a: b" becomes two
    for n, line in enumerate(text.splitlines(), 1):
        body = line.rstrip()
        if not body.strip() or body.lstrip().startswith("#"):
            continue
        lead = body[: len(body) - len(body.lstrip())]
        if "\t" in lead:
            raise DataError(where, n, "starts with a tab; indent with spaces only, lined up with the lines around it")
        indent, content = len(lead), body.strip()
        if "\t" in content:
            raise DataError(where, n, "contains a tab; use spaces instead")
        if content == "-" or content.startswith("- "):
            toks.append((n, indent, "-"))
            content = content[1:].lstrip()
            if not content:
                continue
            indent += len(body.strip()) - len(content)
        toks.append((n, indent, content))
    if not toks:
        raise DataError(where, 0, "is empty")
    if toks[0][1] != 0:
        raise DataError(where, toks[0][0], "the first label must start at the left edge, with no spaces before it")
    value, i = _block(where, toks, 0, 0, "the top of the file")
    if i < len(toks):
        n, indent, _ = toks[i]
        raise DataError(where, n, "the indentation does not line up with the lines above it")
    return value


def _block(where, toks, i, indent, parent):
    if toks[i][2] == "-":
        return _list(where, toks, i, indent, parent)
    return _map(where, toks, i, indent)


def _list(where, toks, i, indent, parent, same_indent=False):
    items = []
    while i < len(toks) and toks[i][1] == indent:
        n, _, text = toks[i]
        if text != "-" and same_indent:
            break
        if text != "-":
            raise DataError(where, n, f"a label among the entries of {parent}; start each entry with \"- \" "
                                      "or line it up under the entry above")
        i += 1
        if i >= len(toks) or toks[i][1] <= indent:
            raise DataError(where, n, "an empty entry (a \"-\" with nothing after it); remove the line")
        item, i = _map(where, toks, i, toks[i][1])
        items.append(item)
    return items, i


def _map(where, toks, i, indent):
    out, seen = {}, {}
    while i < len(toks) and toks[i][1] == indent:
        n, _, text = toks[i]
        if text == "-":
            raise DataError(where, n, "an entry starting with \"-\" among labels; line it up with the other entries")
        m = LINE.match(text)
        if not m:
            if ":" not in text:
                raise DataError(where, n, f"\"{text[:40]}\" has no label; each line is a label, a colon, then a value in quotes")
            raise DataError(where, n, f"\"{text[:40]}\" is not a label and a value; write it like label: \"value\"")
        key = m.group("key")
        if key in seen:
            if key == "callsign":
                raise DataError(where, n, "this position has a call sign but no role; put back its role line "
                                          "(starting \"- role:\") above it, or delete this call sign line")
            raise DataError(where, n, f"\"{key}\" is given twice (also on line {seen[key]}); keep one")
        seen[key] = n
        v = _value(where, n, key, m.group("rest") or "")
        i += 1
        if v is None:
            if i >= len(toks) or toks[i][1] < indent or (toks[i][1] == indent and toks[i][2] != "-"):
                raise DataError(where, n, f"\"{key}:\" has nothing after it; give a value in quotes, like {key}: \"...\"")
            if toks[i][1] == indent and toks[i][2] == "-":
                # A list written at the same indent as its label (valid YAML).
                v, i = _list(where, toks, i, indent, f"\"{key}\"", same_indent=True)
            else:
                v, i = _block(where, toks, i, toks[i][1], f"\"{key}\"")
        elif i < len(toks) and toks[i][1] > indent:
            raise DataError(where, toks[i][0], "is indented more than the line above it; line it up")
        out[key] = (v, n)
    return out, i


# ------------------------------------------------------------------ checking

def strip(v):
    """Drops the line numbers that load() keeps beside every value."""
    if isinstance(v, dict):
        return {k: strip(x[0]) for k, x in v.items()}
    if isinstance(v, list):
        return [strip(x) for x in v]
    return v


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
# A call sign, with an optional portable prefix ("KL7/K7MHG") or suffix ("NV2Z/AE").
CALL = r"(?:[A-Z0-9]{1,4}/)?(?:[A-Z]{1,2}|[A-Z]\d|\d[A-Z])\d[A-Z]{1,4}(?:/[A-Z0-9]{1,4})?"
# Words that mark an empty position: a whole phrase anywhere, or a value that
# is nothing but one of the short words ("Open", "None").
PLACEHOLDER = re.compile(r"\b(?:vacant|tbd|tba|t\.b\.d|to be (?:filled|named|announced|determined)|unfilled|"
                         r"position open|open position|volunteer needed)\b|\((?:open|none|vacant)\)", re.I)
PLACEHOLDER_ONLY = re.compile(r"\W*(?:open|none|nobody|n/?a|-+)\W*", re.I)
# ...or a role or call sign that ends in one: "AEC, Hospital: open", "(N/A)",
# "seeking volunteer", "(position currently open)".
PLACEHOLDER_END = re.compile(r"(?:\b(?:open|n/a|vacant|tbd|to be filled)|\bseeking\b.*)\W*$", re.I)
MARKUP = re.compile(r"[<>*_`\[\]{}\\]")
FILE_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.(docx|pdf)$")
ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
KINDS = {"docx": "Word document", "pdf": "PDF"}
VERSION = re.compile(rf"^(?:{'|'.join(MONTHS)})(?: [1-9]\d?,)? (?:19|20)\d\d$")

SCHEMA_FACTS = {
    "net": {"day": "weekday", "time": "time"},
    "repeater": {
        "primary": {"call": "call", "freq": "freq", "offset": "offset", "tone": "tone"},
        "alternate": {"freq": "freq", "offset": "offset", "tone": "tone"},
        "weather": {"call": "weather_call", "freq": "freq"},
    },
    "winlink_nights": "nights",
    "meetings": [{"name": "text", "when": "text", "extra?": "text"}],
    "place": {"name": "text", "street": "text", "city": "text"},
    "leadership": {
        "unit": [{"role": "role", "callsign": "callsigns"}],
        "section": [{"role": "role", "callsign": "callsigns"}],
    },
    "contact": {"email": "email"},
    "groupsio": "groupsio",
    "files": [{"id": "id", "title": "text", "file": "file", "kind": "kind", "version": "version"}],
}
SCHEMA_RESOURCES = {
    "groups": [{"id": "id", "title": "text",
                "links": [{"title": "text", "url": "url", "opens?": "text", "note": "text"}]}],
}


def placeholder(v):
    return bool(PLACEHOLDER.search(v) or PLACEHOLDER_ONLY.fullmatch(v) or PLACEHOLDER_END.search(v))


class Checker:
    def __init__(self, where):
        self.where = where
        self.problems = []

    def add(self, line, msg):
        self.problems.append(str(DataError(self.where, line, msg)))

    def walk(self, schema, node, line, path):
        """node is the (value, line) structure from load()."""
        name = ".".join(path) or "the file"
        if isinstance(schema, dict):
            if not isinstance(node, dict):
                self.add(line, f"\"{name}\" should have labels indented under it, not a list or a value")
                return
            allowed = {k.rstrip("?"): k.endswith("?") for k in schema}
            for k, (v, n) in node.items():
                if k not in allowed:
                    near = [a for a in allowed if a.lower() == k.lower()]
                    hint = f"did you mean \"{near[0]}\"? Labels are lower case" if near else \
                        "the labels allowed here are " + ", ".join(sorted(allowed))
                    self.add(n, f"unknown label \"{k}\" under \"{name}\"; {hint}")
            for k, optional in allowed.items():
                if k not in node:
                    if not optional:
                        self.add(line, f"\"{name}\" is missing its \"{k}\" line; put it back")
                    continue
                v, n = node[k]
                self.walk(schema[k + "?" if optional else k], v, n, path + [k])
        elif isinstance(schema, list):
            if not isinstance(node, list):
                self.add(line, f"\"{name}\" should be a list of entries, each starting with \"- \"")
                return
            if not node:
                self.add(line, f"\"{name}\" has no entries; keep at least one")
            for idx, item in enumerate(node, 1):
                first = min((n for _, n in item.values()), default=line)
                self.walk(schema[0], item, first, path[:-1] + [f"{path[-1]}[{idx}]"])
        else:
            if not isinstance(node, str):
                self.add(line, f"\"{name}\" should be one value in quotes, not more labels or a list")
                return
            self.leaf(schema, node, line, name)

    def leaf(self, kind, v, line, name):
        key = name.rsplit(".", 1)[-1].split("[")[0]
        if v.strip() == "":
            self.add(line, f"{key}: is empty; fill in the value between the quotes")
            return
        if v != v.strip():
            self.add(line, f"{key}: has a space just inside a quote mark; remove it")
            return
        bad = re.search(r"[\u00a0\u2000-\u200f\u202f\u205f\u2060\ufeff]", v)
        if bad:
            names = {"\u00a0": "a no-break space", "\u202f": "a narrow no-break space", "\u200b": "a zero-width space",
                     "\ufeff": "a zero-width no-break space", "\u2060": "a word joiner"}
            what = names.get(bad.group(0), "an unusual space")
            self.add(line, f"{key}: \"{v}\" contains an invisible character ({what}), probably pasted; delete the "
                           "space around it and type an ordinary space")
            return
        if any(ord(c) < 32 for c in v):
            self.add(line, f"{key}: contains a control character; retype the value")
            return
        if kind != "url" and MARKUP.search(v):
            self.add(line, f"{key}: \"{v}\" contains {MARKUP.search(v).group(0)!r}; the characters < > * _ ` [ ] {{ }} \\ "
                           "are not allowed in page text")
            return
        bad = getattr(self, "k_" + kind)(v)
        if bad:
            self.add(line, f"{key}: \"{v}\" {bad}")

    # Each returns None when the value is right, or the rest of a sentence.
    def k_text(self, v):
        return None

    def k_weekday(self, v):
        if v not in WEEKDAYS:
            return "is not a day of the week; write one day with a capital letter, like \"Tuesday\""

    def k_time(self, v):
        if not re.fullmatch(r"(?:[1-9]|1[0-2]):[0-5]\d (?:AM|PM)", v):
            return "is not a time like \"8:00 PM\" (hour, colon, minutes, a space, then AM or PM)"

    def k_freq(self, v):
        if not re.fullmatch(r"\d{2,4}\.\d{1,4} MHz", v):
            return "is not a frequency like \"147.300 MHz\" (with a space before MHz)"

    def k_offset(self, v):
        if not re.fullmatch(r"[+-]\d+(?:\.\d+)? (?:kHz|MHz)", v):
            return "is not an offset like \"+600 kHz\" or \"-600 kHz\" (a plus or minus sign first)"

    def k_tone(self, v):
        if re.fullmatch(r"\d{2,3}(?:\.\d)? Hz|DCS \d{3}", v) or v.lower() == "no tone":
            return None
        m = re.fullmatch(r"DCS\s*(\d{1,3})", v, re.I)
        if m:
            return f"is a DCS code; write three digits: \"DCS {int(m.group(1)):03d}\""
        return "is not a tone like \"100 Hz\" (with a space before Hz), a code like \"DCS 023\", or \"no tone\""

    def k_call(self, v):
        if not re.fullmatch(CALL, v):
            return "does not look like a call sign; write it in capitals, like \"W7GBU\""

    def k_weather_call(self, v):
        if not re.fullmatch(r"[A-Z]{3}\d{2,3}", v):
            return "does not look like a weather radio station, like \"WXL86\""

    def k_nights(self, v):
        if re.search(r"\d|day", v, re.I):
            return ("should name the weeks only, like \"second and fourth\"; "
                    "the site adds the net day itself")

    def k_role(self, v):
        if placeholder(v):
            return ("marks an empty position; when a position is empty, delete its two lines "
                    "(role and callsign) instead")

    def k_callsigns(self, v):
        if placeholder(v):
            return ("marks an empty position; when a position is empty, delete its two lines "
                    "(role and callsign) instead")
        for c in v.split(","):
            if not re.fullmatch(CALL, c.strip()):
                return ("does not look like a call sign (or several, separated by commas); "
                        "write call signs in capitals, like \"AA7RT, W7UWC\"")

    def k_email(self, v):
        if not re.fullmatch(rf"[a-z0-9._%+-]+@{re.escape(SITE_DOMAIN)}", v):
            return (f"must be an address at the site's own domain, in lower case, like \"info@{SITE_DOMAIN}\"; "
                    "never a personal address")

    def k_groupsio(self, v):
        u = urlparse(v)
        if not (u.scheme == "https" and (u.hostname or "").endswith(".groups.io")
                and re.fullmatch(r"/g/[a-z0-9-]+", u.path) and not (u.query or u.fragment or "@" in u.netloc)):
            return "must be the group's main page, like \"https://spokaneares-acs.groups.io/g/main\""

    def k_id(self, v):
        if not ID.match(v):
            return "is not a simple name; use lower-case letters, digits and single hyphens, like \"acs-task-book\""

    def k_file(self, v):
        if not FILE_NAME.match(v):
            return ("is not a usable file name; use lower-case letters, digits and hyphens, "
                    "ending .docx or .pdf, like \"acs-task-book.docx\"")

    def k_kind(self, v):
        if v not in KINDS.values():
            return "must be \"Word document\" or \"PDF\""

    def k_version(self, v):
        if not VERSION.match(v):
            return "is not a version like \"November 7, 2024\" or \"July 2024\" (month spelled out, then the year)"

    def k_url(self, v):
        if re.search(r"[\s\"'<>\\`{}|^]", v):
            return "contains a space, quote mark or other character not allowed in a web address; copy it again"
        if re.search(r"%(?![0-9A-Fa-f]{2})", v):
            return "contains a % sign that is not followed by two hex digits; copy the address again from the page"
        u = urlparse(v)
        if u.scheme != "https" and v not in HTTP_ALLOWED:
            return "must start with https:// (pages that only work over http are not linked)"
        host = (u.hostname or "").lower()
        if "@" in u.netloc or "." not in host:
            return "is not a normal web address; copy it again from the page"
        for h in NOT_ON_RESOURCES:
            if host == h or host.endswith("." + h):
                return f"is on {h}, which is not linked from Resources"


def check_relations(c, facts, resources):
    """Checks that need more than one value at a time."""
    if facts is not None:
        files = facts.get("files", ([], 0))[0]
        if isinstance(files, list):
            for field in ("id", "file"):
                seen = {}
                for item in files:
                    if isinstance(item, dict) and field in item and isinstance(item[field][0], str):
                        v, n = item[field]
                        if v in seen:
                            c.add(n, f"{field}: \"{v}\" is used twice (also on line {seen[v]}); each file needs its own")
                        seen[v] = n
            for item in files:
                if not (isinstance(item, dict) and "file" in item and "kind" in item):
                    continue
                (f, _), (k, n) = item["file"], item["kind"]
                ext = f.rsplit(".", 1)[-1] if isinstance(f, str) else ""
                if ext in KINDS and k != KINDS[ext]:
                    c.add(n, f"kind: \"{k}\" does not match the file {f}; a .{ext} file is \"{KINDS[ext]}\"")
    if resources is not None:
        groups = resources.get("groups", ([], 0))[0]
        if isinstance(groups, list):
            seen, urls = {}, {}
            for g in groups:
                if not isinstance(g, dict):
                    continue
                if "id" in g and isinstance(g["id"][0], str):
                    v, n = g["id"]
                    if v in seen:
                        c.add(n, f"id: \"{v}\" is used by two groups (also on line {seen[v]}); each group needs its own")
                    seen[v] = n
                links = g.get("links", ([], 0))[0]
                for link in links if isinstance(links, list) else []:
                    if isinstance(link, dict) and "url" in link and isinstance(link["url"][0], str):
                        v, n = link["url"]
                        if v in urls:
                            c.add(n, f"url: \"{v}\" is listed twice (also on line {urls[v]}); keep one")
                        urls[v] = n


def check(data_dir, label=None):
    """Returns the list of problems (one line each) for both files."""
    data_dir = Path(data_dir)
    label = label or str(data_dir)
    problems, trees = [], {}
    for name, schema in (("facts.yaml", SCHEMA_FACTS), ("resources.yaml", SCHEMA_RESOURCES)):
        where = f"{label}/{name}"
        try:
            tree = load(data_dir / name, where)
        except DataError as e:
            problems.append(str(e))
            trees[name] = None
            continue
        c = Checker(where)
        c.walk(schema, tree, 1, [])
        check_relations(c, tree if name == "facts.yaml" else None, tree if name == "resources.yaml" else None)
        problems += c.problems
        trees[name] = tree
    return problems


def main():
    args = sys.argv[1:]
    if len(args) > 1 or any(a.startswith("-") for a in args):
        sys.exit("usage: check_data.py [data-dir]")
    if args:
        data_dir, label = Path(args[0]), args[0].rstrip("/")
    else:
        data_dir = Path(__file__).resolve().parent.parent / "data"
        label = "site/data"
    problems = check(data_dir, label)
    for p in problems:
        print(p)
    if problems:
        print(f"{len(problems)} problem(s) in the data files; nothing was published")
        sys.exit(1)
    print("facts.yaml and resources.yaml look right")


if __name__ == "__main__":
    main()
