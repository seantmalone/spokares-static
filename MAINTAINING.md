# Keeping spokares.org current

The site is built to be left alone. It only holds facts that change about
once a year. This page covers every change you are likely to need.

You need a GitHub account with write access to this repository. You do not
need to install anything.

## Change a fact (officers, meeting times, repeater settings, contact)

1. Open `site/data/facts.yaml` on GitHub and choose the pencil (Edit).
2. Change the words between the quotes. Leave the labels on the left alone.
3. Choose "Commit changes".

The site rebuilds and publishes itself in about two minutes.

- Someone new in a position: change the call sign on that line.
- A position is empty: delete its two lines (the `role` line and the
  `callsign` line). Never write "open" or "vacant".
- Never put a date in this file. Meetings are written as rules, such as
  "Third Thursday of each month, 6:00 PM". The one exception is a file's
  `version` (see below).

## Replace the application or a task book

1. Name the new file exactly as the old one: `ares-application.docx`,
   `acs-task-book.docx` or `arrl-ares-task-book.pdf`.
2. In `site/static/files/` on GitHub choose "Add file", then "Upload files",
   and commit.
3. In `site/data/facts.yaml`, under `files`, change that file's `version`
   (for example "November 7, 2024"). If the new file is a different kind,
   say a PDF instead of a Word document, also change its `kind` and `file`.

These three files are the only documents the site holds. Everything else is
a link to whoever keeps it current.

## Add, change or remove a link on Resources

Edit `site/data/resources.yaml`. Each link has a `title`, an address (`url`)
and a `note`: one line saying what it is. Copy an existing link's four lines
and change them.

- Only link to pages anyone can open without signing in.
- Link to the organization that keeps the page current.
- Do not copy someone else's dates, times or fees onto the site; link to
  their page instead.
- Leave each group's `id` alone. Other pages link to it.

## Change wording on a page

Page text is in `site/content/` (one file per page). Lines that look like
`{{< net-settings >}}` place a designed piece of the page; leave those lines
as they are. Two things trip people up:

- Keep an empty line between a `{{< … >}}` line and ordinary text, above and
  below it. Without it the check refuses the change.
- Write links to other pages of the site starting with a slash, such as
  `[About](/about/)`, not `about/`.

## If a change does not appear

Open the "Actions" tab on GitHub. A red mark means the checks refused the
change, and the message says why. The published site is untouched until a
change passes. The usual causes are a deleted quote mark in `facts.yaml`, a
missing empty line next to a `{{< … >}}` line, a date where only a rule
belongs, or a broken link.

## Once a year

- [ ] Leadership in `facts.yaml` matches who holds each position.
- [ ] Meeting days, times and place are still right.
- [ ] The application and task books are the current versions.
- [ ] Open the latest run under "Actions" and read "Report on outside links".
      Fix or remove any link marked FAIL or SIGN-IN. A link marked CHECK is a
      site that refuses automatic checks: open it yourself in a private
      window, and keep it if it opens without signing in.
- [ ] `info@spokares.org` still forwards to someone who reads it.
- [ ] The domain `spokares.org` is paid up and set to renew by itself.
- [ ] At least two people have write access to this repository.

## For whoever looks after the machinery

- The site is built by Hugo, pinned to version 0.164.0 in
  `.github/workflows/pages.yml`, which builds, checks and publishes the
  review preview to GitHub Pages on every commit to `main`. Preview locally
  with `hugo server --source site`.
- `python3 site/tools/check_site.py site/public --base /spokares-static` is
  the test suite for a build made with
  `hugo --source site --baseURL http://localhost/spokares-static/`.
  `python3 site/tools/test_check_site.py` tests the checker itself.
- `python3 site/tools/check_links.py site/public` reports on every outside
  link.
- The earlier WordPress build is in the separate `spokane_ares` repository,
  at tag `v0.3.2`.
