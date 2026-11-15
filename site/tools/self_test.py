#!/usr/bin/env python3
"""Step 4 of build.sh: the self-tests of the checkers and templates.

Run: python3 site/tools/self_test.py        (needs hugo 0.164.0 on the PATH)

The self-tests use only the frozen fixtures in site/tools/fixtures/ and the
current templates and tools. To make sure of that, this never runs them in
the real site/ folder: it copies site/ to a temporary folder, replaces the
live data files, every page file and every hosted file there with garbage,
and runs the four test files in that copy. A test that read the live data
would fail here at once, so no edit to site/data/, site/content/ or
site/static/files/ can ever make this step fail.

If a self-test fails, the first line printed says it is not the editor's
fault; the test output follows.

Standard library only. Exits 0 when every self-test passes, 1 otherwise.
"""
import shutil
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
SITE = TOOLS.parent
TESTS = ("test_check_data.py", "test_check_site.py", "test_check_links.py", "test_build.py")
NOT_YOUR_EDIT = ("The site's own self-tests failed. This is not caused by your edit; ask whoever looks after "
                 "the machinery (see MAINTAINING.md).")
GARBAGE = "GARBAGE: the self-tests must not read this file\n: [ { \"\n"
# What the self-tests may not read: the live data, the pages and the hosted files.
LIVE = ("data", "content", "static/files")
IGNORE = shutil.ignore_patterns("public", "resources", ".hugo_build.lock", ".reference", "__pycache__")


def prepare(dest, site=SITE):
    """Copies site/ to dest/site with every file under LIVE replaced by garbage.
    Returns the copy's site folder."""
    copy = Path(dest) / "site"
    shutil.copytree(site, copy, ignore=IGNORE)
    for part in LIVE:
        for f in sorted((copy / part).rglob("*")):
            if f.is_file():
                f.write_text(GARBAGE, encoding="utf-8")
    return copy


def run(tests=TESTS, site=SITE):
    """Runs the test files in a garbled copy of site/. Returns (ok, report lines)."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = prepare(tmp, site)

        # The tests must behave the same on a laptop and on GitHub: the checkers
        # print "::notice::" / "::warning::" prefixes when GITHUB_ACTIONS is set,
        # so it is removed here. A test that wants that mode sets it itself.
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}

        def one(name):
            r = subprocess.run([sys.executable, str(copy / "tools" / name), "-q"], cwd=tmp,
                               capture_output=True, text=True, env=env)
            return name, r.returncode, r.stdout + r.stderr

        with ThreadPoolExecutor(len(tests)) as ex:
            results = list(ex.map(one, tests))
    failed = [(n, out) for n, code, out in results if code != 0]
    if not failed:
        return True, [f"{n}: " + next((l for l in out.splitlines() if l.startswith("Ran ")), "OK")
                      for n, _, out in results]
    lines = [NOT_YOUR_EDIT]
    for n, out in failed:
        lines += [f"--- {n} ---", out.rstrip()]
    return False, lines


def main():
    if sys.argv[1:]:
        sys.exit("usage: self_test.py")
    try:
        ok, lines = run()
    except Exception as e:  # the step itself broke: still not the editor's fault
        ok, lines = False, [NOT_YOUR_EDIT, f"self_test.py: {type(e).__name__}: {e}"]
    print("\n".join(lines))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
