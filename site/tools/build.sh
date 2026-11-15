#!/bin/sh
# Builds and checks the site: the one command CI and people both run.
#
#   site/tools/build.sh                        preview build for http://localhost/spokares-static/
#   site/tools/build.sh https://<account>.github.io/spokares-static/   (what CI runs)
#   site/tools/build.sh https://spokares.org/ --live                   the real site, no noindex
#
# Steps, stopping at the first that fails:
#   1. check_data.py   facts.yaml and resources.yaml (one plain line per mistake)
#   2. hugo            the build, warnings treated as errors
#   3. check_site.py   the built pages and hosted files
#   4. self_test.py    the self-tests of the checkers and templates, run on a
#                      copy of site/ whose data, pages and hosted files are
#                      garbage, so no edit to them can make this step fail
# The output is in site/public. Needs python3 and hugo 0.164.0, nothing else.
set -eu
cd "$(dirname "$0")/../.."

usage="usage: site/tools/build.sh [http(s)://address/ [--live]]   (default http://localhost/spokares-static/)"
base_url="${1:-http://localhost/spokares-static/}"
case "$base_url" in
  http://*|https://*) ;;
  *) echo "build.sh: the first argument must be the site's address, starting with http:// or https://. $usage" >&2; exit 2 ;;
esac
mode="--preview"
preview=true
case "${2:-}" in
  "") ;;
  --live) mode="--live"; preview=false ;;
  *) echo "build.sh: unknown argument ${2}. $usage" >&2; exit 2 ;;
esac
if [ $# -gt 2 ]; then echo "build.sh: too many arguments. $usage" >&2; exit 2; fi
if [ "$preview" = false ]; then
  # The live build is for the real site: a real address, not the github.io preview.
  host=$(python3 -c 'import sys, urllib.parse; print((urllib.parse.urlparse(sys.argv[1]).hostname or "").lower())' "${1:-}")
  case "$host" in
    "") echo "build.sh: --live needs the real site's address, like https://spokares.org/. $usage" >&2; exit 2 ;;
    github.io|*.github.io) echo "build.sh: a github.io address is the preview; build it without --live. $usage" >&2; exit 2 ;;
  esac
fi
case "$base_url" in */) ;; *) base_url="$base_url/" ;; esac
base_path=$(python3 -c 'import sys, urllib.parse; print(urllib.parse.urlparse(sys.argv[1]).path.rstrip("/"))' "$base_url")

echo "== 1. Checking the data files"
python3 site/tools/check_data.py

echo "== 2. Building with Hugo for $base_url"
HUGO_PARAMS_PREVIEW=$preview hugo --source site --cleanDestinationDir --panicOnWarning --baseURL "$base_url"

echo "== 3. Checking the built site"
if [ -n "$base_path" ]; then
  python3 site/tools/check_site.py site/public --base "$base_path" "$mode"
else
  python3 site/tools/check_site.py site/public "$mode"
fi

if [ "${BUILD_SKIP_SELF_TESTS:-}" = 1 ]; then
  # Only for tests that run this script on a copy of the site (test_build.py's
  # BuildScript and dev-check.sh's edits): they must not start step 4 again.
  echo "== Steps 1 to 3 passed; self-tests skipped (BUILD_SKIP_SELF_TESTS=1)."
  exit 0
fi

echo "== 4. Self-tests of the checkers and templates"
if ! python3 site/tools/self_test.py; then
  exit 1
fi
echo "== All checks passed. The site is in site/public."
