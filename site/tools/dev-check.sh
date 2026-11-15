#!/bin/sh
# A developer's check, run by hand after changing a template or a tool. It is
# NOT part of the publish gate: neither build.sh nor the workflow runs it.
#
#   sh site/tools/dev-check.sh
#
#   1. build.sh      the whole gate, as CI runs it
#   2. live_edits.py each routine yearly edit, made to a copy of the REAL
#                    site with its real data, passes the real build.sh, and
#                    each clear mistake is refused with one plain line
#
# Step 2 reads today's data, pages and hosted files, so it can fail after a
# data change it did not foresee; that is a reason to look at the test, never
# a reason the site did not publish. Needs python3 and hugo 0.164.0.
set -eu
cd "$(dirname "$0")/../.."
sh site/tools/build.sh
echo "== Developer check: routine edits and mistakes on a copy of the real site"
python3 site/tools/live_edits.py
