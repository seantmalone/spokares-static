# Keeping the site current

This repository builds a static version of the Spokane County ARES-ACS
website. Today it is a **review preview**, published by GitHub Pages at
<https://seantmalone.github.io/spokares-static/> and hidden from search
engines. It is not yet the site at spokares.org. The items marked
"(after the move)" below apply only once it moves to spokares.org.

The site is built to be left alone. It only holds facts that change about
once a year. This page covers every change you are likely to need.

You need a GitHub account with write access to this repository. You do not
need to install anything.

## Change a fact (officers, meeting times, repeater settings, contact)

1. Open `site/data/facts.yaml` on GitHub and choose the pencil (Edit).
2. Change the words between the quotes. Leave the labels on the left alone.
3. Choose "Commit changes".

The site rebuilds and publishes itself in about two minutes.

- Every value goes between straight double quotes, even a number:
  `freq: "147.300 MHz"`, not `freq: 147.300`.
- Someone new in a position: change the call sign on that line.
- A position is empty: delete its two lines (the `role` line and the
  `callsign` line). Never write "open", "vacant" or "TBD".
- Never put a date in this file. Meetings are written as rules, such as
  "Second Saturday of each month, 9:00 AM to noon". The one exception is a
  file's `version` (see below). The check refuses the common ways of writing
  a date, such as "December 18" or "12/18/2026", but it is only a safety
  net: it cannot catch every way, so write the rule yourself.
- The net day, time and repeater call sign are used on every page that
  mentions them, so change them only in `facts.yaml`.
- The contact address (`contact.email`) is also printed inside the ARES
  application. If it changes, upload a corrected application in the same
  change (see the next section), or the check refuses it.

## Replace the application or a task book

The site keeps three files: `ares-application.docx`, `acs-task-book.docx`
and `arrl-ares-task-book.pdf`. The name in `facts.yaml` (`file`) and the
name of the uploaded file must always be the same, and the file and its
`version` should change together. Every commit to `main` publishes, so make
both changes on a side branch and publish them at once:

1. On your computer, rename the new file to the name the old one has. If it
   is a different kind (a PDF instead of a Word document), keep the same
   name with the new ending, for example `ares-application.pdf`.
2. On GitHub open `site/static/files/`, choose "Add file", then "Upload
   files", and add the file. Under "Commit changes" choose "Create a new
   branch for this commit and start a pull request", then "Propose
   changes" and "Create pull request". Nothing is published yet.
3. Still on that branch (the pull request page names it; pick it in the
   branch menu), open `site/data/facts.yaml`, choose Edit, and under
   `files` change that file's `version` (written like "November 7, 2024"
   or "July 2024"). If the ending changed, also change its `file` to the
   new name and its `kind` to "PDF" or "Word document", and delete the
   old file in `site/static/files/` on the same branch. Commit to the
   branch.
4. The pull request shows a check. If the ending changed, the check on the
   first commit fails because `facts.yaml` did not list the new name yet;
   that is expected and harmless. When the latest check is green, choose
   "Merge pull request". The file and its version are published together.

A document anywhere in the site that is not one of the files listed in
`facts.yaml`, or a listed file that is missing, stops the publish.

Word files are checked inside. The check refuses one that names a person
(tracked changes, comments, or author fields other than "Spokane County
ARES-ACS" or "Author") or that holds a personal e-mail address or phone
number. To clean one in Word: accept all changes, delete all comments, and
remove personal information from the file's properties (Word for Windows:
File › Info › Check for Issues › Inspect Document; Word for Mac: Tools ›
Protect Document › Remove personal information on save), then save and
upload again.

PDFs are not checked inside: the check can reliably read only a PDF's
author fields, and prints a note saying so. Read a PDF through before you upload it, and
make sure it holds no personal names, phone numbers or e-mail addresses.
For the group's own forms, upload a Word file.

These three files are the only documents the site holds. Everything else is
a link to whoever keeps it current.

## Add, change or remove a link on Resources

Edit `site/data/resources.yaml`. Each link has a `title`, an address (`url`)
and a `note`: one line saying what it is. `opens` is optional: the short
name of whoever runs the linked site (for example "FEMA"). It is not shown
on the page; screen readers say "(opens FEMA)" after the link, and without
it they say the site's name from its address (such as "weather.gov").
Copy an existing link's lines and change them.

- Only link to pages anyone can open without signing in.
- Addresses start with `https://`. No groups.io or ag7qp.com links here.
- Link to the organization that keeps the page current.
- Do not copy someone else's dates, times or fees onto the site; link to
  their page instead.
- Leave each group's `id` alone. Other pages link to it.

## Change wording on a page

Most text is in `site/content/` (one file per page), but the designed parts
of each page keep their words in `site/layouts/`. Lines that look like
`{{< net-settings >}}` place one of those designed parts; leave those lines
as they are. These things trip people up in `site/content/`:

- Keep an empty line between a `{{< … >}}` line and ordinary text, above and
  below it. Outside the blocks (the lines between `{{< section … >}}` and
  `{{< /section >}}`, or `column`, `chapter`, `how-row`), the check refuses
  the change without it; inside them it works either way, but keep it for
  tidiness.
- Write links to other pages of the site starting with a slash, such as
  `[About](/about/)`, not `about/`.
- Do not type HTML tags (such as `<b>` or `<br>`); the check refuses them
  and names the line. Plain text such as "< 5 minutes" is fine.
- A line such as `{.lede}`, `{.m-line}` or `{.lines}` gives the paragraph
  or list just above it its look. Keep it directly under that paragraph or
  list, with no empty line between them.

### Where the words are

| Page and part | File |
|---|---|
| Every page: menu | `site/layouts/partials/header.html` |
| Every page: footer | `site/layouts/partials/footer.html` |
| Every page: the description search results show | the `description:` line at the top of the page's file in `site/content/` |
| Home: photo, headline, buttons | `site/layouts/shortcodes/home-hero.html` |
| Home: What we do | `site/layouts/shortcodes/home-what-we-do.html` |
| Home: Come visit (from home, in person) | `site/layouts/partials/net-from-home.html`, `site/layouts/partials/meetings.html` (times and place from `facts.yaml`) |
| Home: Join in four steps | `site/layouts/shortcodes/home-join.html` |
| How it works: opening scenario and its drawing | `site/layouts/shortcodes/how-opener.html`, `site/layouts/partials/message-path.html` |
| How it works: the weekly net, its steps, When no one has called yet | `site/content/how-it-works.md` |
| How it works: net settings box (also on For members) | `site/layouts/shortcodes/net-settings.html` (values from `facts.yaml`) |
| How it works: Winlink nights line | `site/layouts/shortcodes/other-nets.html` (weeks from `facts.yaml`) |
| How it works: When the county calls | `site/layouts/shortcodes/how-activation-steps.html` |
| How it works: Readiness levels | `site/layouts/shortcodes/how-readiness.html` |
| How it works: How a message moves | `site/layouts/shortcodes/how-messages.html` |
| How it works: Training and exercises | `site/layouts/shortcodes/how-exercises.html` |
| How it works: Roles members take | `site/layouts/shortcodes/how-roles.html` |
| About: page headings, Who we serve, Agreements, Joining, Equipment, the W7GBU story, Contact | `site/content/about.md` |
| About: ARES, ACS, RACES, AUXCOMM definitions | `site/layouts/shortcodes/about-ares-acs.html` |
| About: the legal basis table | `site/layouts/shortcodes/about-legal-basis.html` |
| About: organization chart | `site/layouts/shortcodes/about-chains.html` |
| About: leadership tables | `site/layouts/shortcodes/leadership.html` (names and call signs from `facts.yaml`) |
| About: the ACS path | `site/layouts/shortcodes/about-acs-path.html` |
| About: ACS task-book table | `site/layouts/shortcodes/about-training.html` |
| About: ARRL ARES levels | `site/layouts/shortcodes/about-arrl-levels.html` |
| About: ways to study, where to take the exam | `site/layouts/shortcodes/about-licensing.html` |
| About: timeline | `site/layouts/shortcodes/about-timeline.html` |
| About: the contact address | `site/layouts/shortcodes/contact.html` (address from `facts.yaml`) |
| For members: headings and lines | `site/content/members.md` |
| For members: members' group card | `site/layouts/shortcodes/members-group.html` |
| For members: list of files | `site/layouts/shortcodes/hosted-files.html` (from `facts.yaml`) |
| Resources: heading and lede | `site/content/resources.md` (the links: `site/data/resources.yaml`) |
| Page not found | `site/layouts/404.html` |

## If a change does not appear

Open the "Actions" tab on GitHub. A red mark means the checks refused the
change, and the first lines of the failed step say why, naming the file
and the line (for example
`site/data/facts.yaml line 7: time: a quote mark is missing; …`).
The published site is untouched until a change passes. The usual causes
are a deleted quote mark in `facts.yaml`, a value typed without quotes, a
missing empty line next to a `{{< … >}}` line, a date where only a rule
belongs, or a broken link.

## Once a year

- [ ] Leadership in `facts.yaml` matches who holds each position.
- [ ] Meeting days, times and place are still right.
- [ ] The application and ACS task book are the current versions.
- [ ] Compare the ARRL ARES Task Book with the one offered at
      <https://www.arrl.org/ares>; if ARRL has a newer one, replace the file
      and its `version`.
- [ ] Open each PDF in `site/static/files/` and read it through: it must
      hold no personal names, phone numbers or e-mail addresses (the check
      cannot read inside a PDF).
- [ ] Open the latest run under "Actions" and read "Report on outside links".
      Fix or remove any link marked FAIL or SIGN-IN. A link marked CHECK is a
      site that refuses automatic checks: open it yourself in a private
      window, and keep it if it opens without signing in.
- [ ] Re-read each `note` in `site/data/resources.yaml` against the page it
      links to; the note must still describe what is there.
- [ ] Check the facts that live in page text, not in `facts.yaml`: the
      agreements (`site/content/about.md`), the ACS task-book table
      (`site/layouts/shortcodes/about-training.html`), the timeline
      (`site/layouts/shortcodes/about-timeline.html`), the legal basis table
      (`site/layouts/shortcodes/about-legal-basis.html`), the readiness
      levels (`site/layouts/shortcodes/how-readiness.html`) and the ARRL
      levels (`site/layouts/shortcodes/about-arrl-levels.html`), which must
      agree with the hosted ARRL task book.
- [ ] The W7GBU club licence is current (look it up by call sign in the
      FCC's license search); its trustee renews it.
- [ ] At least two people have write access to this repository.
- [ ] (after the move) `info@spokares.org` still forwards to someone who
      reads it.
- [ ] (after the move) The domain `spokares.org` is paid up and set to
      renew by itself, and an uptime and certificate monitor (set up at the
      move) alerts `info@spokares.org`.

## For whoever looks after the machinery

- The site is built by Hugo, pinned to version 0.164.0 in
  `.github/workflows/pages.yml`. On every commit to `main` the workflow runs
  `site/tools/build.sh` and publishes `site/public` to GitHub Pages. A pull
  request (also from a fork) runs the same build and checks but never
  publishes and gets no write permission.
- One command builds and checks everything, the same way CI does:

      site/tools/build.sh

  It runs, stopping at the first failure: `site/tools/check_data.py` (the
  two data files), Hugo with `--panicOnWarning`, `site/tools/check_site.py`
  (the built pages and hosted files) and the self-tests
  `site/tools/test_check_data.py`, `site/tools/test_check_site.py`,
  `site/tools/test_check_links.py` and `site/tools/test_build.py`. The
  output is in `site/public`. Preview it locally with
  `hugo server --source site`.
- Preview or live: `params.preview` in `site/hugo.toml` is `true`, which
  marks every page `noindex`. For the real spokares.org build, turn it off
  with the environment: `site/tools/build.sh https://spokares.org/ --live`
  (this sets `HUGO_PARAMS_PREVIEW=false` and checks with
  `check_site.py --live`, which requires that no page says `noindex`).
- `python3 site/tools/check_links.py site/public` reports on every outside
  link (in CI with `--strict`; the step never blocks publishing).
- The earlier WordPress build is in the separate `spokane_ares` repository,
  at tag `v0.3.2`.
