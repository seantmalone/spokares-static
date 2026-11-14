# Stable static site: design

Date: 2026-11-14
Status: approved in conversation; under review as a preview (see below)

## Review phase (added 2026-11-14)

The direction is not final. Until the owner decides:

- This work lives in its own repository, `spokares-static`. The WordPress
  repository (`spokane_ares`), its deploy workflow and the Enhance website are
  left exactly as they are. The WordPress code is read as a source only.
- The preview is published with GitHub Pages at
  `https://<account>.github.io/spokares-static/`, marked `noindex`.
- Because that address has a path prefix, no template or content file may
  rely on a bare root-relative address; every internal address goes through
  one helper so the same source builds for the preview and for
  `spokares.org`.
- GitHub Pages cannot do redirects or custom headers. Everything under
  "Hosting and deploy" (Enhance, old-address redirects, headers, mail, DNS),
  "The WordPress build" and go-live is deferred to a second part of the plan,
  to be done only if this direction is chosen.

## Why

The group cannot commit to updating dynamic content. The WordPress build
(tag `v0.3.2`, never made live on spokares.org) was designed around a weekly
Net Control Schedule, dated exercises and a documents library, and its seeded
schedule content was already out of date within weeks.

This design keeps the same visual design ("Carry the Message") and limits the
site to content that does not change more than about once a year. It assumes
nobody may touch the site for a year at a time, and that the yearly editor may
be a volunteer who is not a developer.

## Decisions

| # | Decision |
|---|---|
| 1 | Platform is Hugo, producing plain static files. No PHP application, database or login on the host. |
| 2 | Same visual output as the WordPress theme. Markup is taken from the WordPress-rendered pages, not the round-3 mockup, so accessibility and QA fixes carry over. |
| 3 | Members content collapses to one short "For members" page. Exercises & events, Documents & forms and site search are removed. |
| 4 | A new Resources page links to public, authoritative emergency communications sources. |
| 5 | The only hosted documents are the ARES application and the task books. Everything else is a link. |
| 6 | No link may require signing in. The single exception is one link to the main groups.io group, on the members page only. |
| 7 | No links to net scripts (they live in groups.io). |
| 8 | Leadership keeps every call sign, held in the facts file. |
| 9 | Contact is one role address, `info@spokares.org`, forwarded to the current holder. No contact form. |
| 10 | Deploys run automatically on a commit to `main` once checks pass. No single-person approval gate. |

## Pages

| Page | Path | Contents |
|---|---|---|
| Home | `/` | As designed. Meetings shown as rules, with no computed "Next:" date. No staff meeting line. |
| How it works | `/how-it-works/` | As designed. The "Dates: Exercises & events" link becomes a line pointing to the members page. |
| About | `/about/` | As designed, with the content rules below. The copied exam schedule table is replaced by links on Resources. |
| For members | `/members/` | Net settings; what to bring to an exercise and what to do after one; the application and task books; recurring public-service events without dates; one groups.io link. |
| Resources | `/resources/` | Grouped links: ARRL (ARES, training, Section page), FEMA courses and ICS forms, NWS Spokane and SKYWARN, county emergency management and ALERT Spokane, getting licensed and exam-session finders. |
| Not found | `404.html` | Kept, with links re-pointed to pages that still exist. |

The menu is: How it works, About, Resources, For members, and the "Join the
team" button. The members sub-menu is removed.

## Content rules

1. **Meetings** are stated as recurrence rules only, followed once by "Changes
   are announced on the Tuesday net." No dates are computed or printed.
2. **The Tuesday net** time and repeater settings are stated once in the facts
   file and reused wherever they appear.
3. **Other nets:** Winlink nights stay as a rule (2nd and 4th Tuesdays). The
   simplex and GMRS nets are left out unless confirmed as standing.
4. **Leadership:** unit positions and Section officials with call signs, from
   the facts file. No "open position" rows; an unfilled role is omitted.
5. **Contact:** the role address appears once on About; other pages link to
   that section.
6. **Orientation:** "held regularly; ask at a meeting or on the net for the
   next date."
7. **Wording that ages is removed:** "Schedule as of", "Last reviewed",
   "Soon", "being recovered", "new website", "this week", "next up",
   "later this season".
8. **Version dates** of hosted documents are stated once, beside the download
   link, and nowhere in running text.
9. **Third-party schedules and fees** (exam sessions, class dates, exam fees)
   are never copied; link to the organiser.
10. **No links to ag7qp.com** for Spokane content. Section-level documents
    (for example the Section standing order) may be linked only if no more
    authoritative public source exists, and are listed on Resources.
11. Existing owner rules still apply: say each fact once; plain wording a
    volunteer would say out loud.

## Structure

A new top-level `site/` folder holds the Hugo project.

```
site/
  hugo.toml
  data/
    facts.yaml        net, repeater, meetings, place, leadership, contact, groups.io
    resources.yaml    Resources page links: group, title, url, one-line description
  content/
    _index.md         Home
    how-it-works.md
    about.md
    members.md
    resources.md
  layouts/
    _default/baseof.html, single.html
    index.html, 404.html
    partials/         head, header, footer, brand (seal), message-path (inline SVG)
    shortcodes/       net-settings, net-from-home, other-nets, meetings,
                      leadership, contact, hosted-files, resources-list,
                      and one per designed section that cannot be Markdown
  assets/ or static/
    css/site.css      carried over from the theme, WordPress-only selectors removed
    js/               menu toggle, copy button
    fonts/            the three self-hosted woff2 files
    img/              seal, hero
    files/            ARES application, ACS task book, ARRL ARES task book
```

Boundaries:

- **`data/facts.yaml` is the only file a yearly editor normally changes.** Each
  value has a plain-language comment. Templates fail the build if a required
  fact is missing, so a bad edit cannot publish a half-empty page.
- **Content files** hold prose. Designed components are inserted with
  shortcodes that take no arguments where possible.
- **Layouts** hold all markup and are not touched in a routine edit.
- The table of contents on About is generated by Hugo at build time; the
  WordPress `toc.js` is not carried over.
- The mobile menu is rebuilt with a small script, because the current one
  depends on WordPress's navigation block.

Hugo is pinned to one exact version in the workflow and recorded in
`MAINTAINING.md`. No Node or npm dependency is required to build the site.

## Hosting and deploy

- **Host:** a new plain website on the existing Enhance reseller account,
  created beside the WordPress preview so the two can be compared. No PHP
  application, no database.
- **Workflow:** on a commit to `main` that touches `site/`: build with the
  pinned Hugo version, run the checks in "Verification", then `rsync --delete`
  the output to the web root over the existing SSH deploy path, excluding
  `.well-known`.
- **Old URLs:** `research/redirects.csv` is turned into web-server rewrite
  rules in a generated `.htaccess` (301 for moved pages, 410 for removed and
  spam paths, with a catch-all 410 for old Joomla paths). Entries that pointed
  at removed pages (`/members/exercises/`, `#rota` and similar) are re-pointed.
- **Web server type is unconfirmed** (LiteSpeed Enterprise or OpenLiteSpeed).
  The first implementation step is a test on the new site's preview address:
  do rewrite rules, `Header set` and `ErrorDocument` take effect?
  - If all work: redirects, security headers and cache headers go in
    `.htaccess`.
  - If only rewrite rules work: redirects stay in `.htaccess`; the content
    security policy moves to a `<meta>` tag; HTTPS is forced in the panel; the
    custom 404 is set in the panel.
  - If rewrite rules do not work: a single dependency-free `index.php`
    reusing the existing redirect map is the fallback. This is the only case
    in which PHP is used.
- **Mail:** `info@spokares.org` is created as a forwarder on Enhance. This
  requires mail for the domain to move off the old host, which is a DNS change
  and happens only with the owner's explicit go-ahead.
- **DNS and go-live** are unchanged in principle from the existing runbook:
  nothing is re-pointed without the owner's go-ahead. Nameservers should move
  to Enhance before the site is left unattended, because certificate renewal
  depends on DNS following the host.

## The WordPress build

- It remains in git history at tag `v0.3.2`.
- `wordpress/` and the WordPress CI and deploy workflows are removed from
  `main` once the static site passes verification. The redirect CSVs and
  generator are kept and adapted.
- The WordPress preview website on Enhance, its database and its secrets are
  deleted only after the static site is verified, and only with the owner's
  go-ahead.
- `research/` and `design/` are kept as they are.

## Keeping it alive unattended

- **`MAINTAINING.md`** (one page, plain language): how to change a fact on
  GitHub, replace a hosted file, add or remove a resource link; what happens
  after a commit; a yearly checklist (officers, meeting rules, hosted file
  versions, link check results, domain renewal, forwarder target).
- **Link check on every deploy.** A broken internal link fails the build. A
  broken external link is reported but does not block an unrelated edit.
- **External uptime and certificate monitor** alerting the role address.
  Certificate renewal is automatic but silent.
- No scheduled GitHub workflow is relied on, because GitHub disables schedules
  in inactive public repositories after 60 days.

## Verification

1. The Hugo build completes with no warnings and every required fact present.
2. HTML validation passes on every page.
3. Screenshot comparison of Home, How it works and About against the
   WordPress render at phone and desktop widths. Differences are limited to
   the content changes listed in this document.
4. Automated accessibility check on every page, plus a keyboard pass of the
   menu.
5. Every external link returns a public page without a sign-in, apart from
   the one groups.io link.
6. The site makes no third-party requests when loading.
7. The full redirect list is tested with `curl` against the preview address.
8. A search of the built output finds none of the removed wording from
   content rule 7, and no personal phone numbers or personal e-mail addresses.

## Items that need people, not code

| Item | Needed from |
|---|---|
| Third Thursday meeting time; whether December has a meeting | Emergency Coordinator |
| Alternate repeater details; whether the Winlink gateway line stays; "no dues" | Emergency Coordinator / Net Manager |
| Whether simplex and GMRS nets are standing | Net Manager |
| Current versions of the application and ACS task book files | Emergency Coordinator |
| Who receives `info@spokares.org` | Owner |
| Moving mail and nameservers off the old host | Owner go-ahead |
| Domain renewal (expires 2027-03-10): who holds the registrar account, is auto-renew on | Owner |
| A second person with GitHub write access | Owner |
| W7GBU licence renewal (expires 2027-02-15) | Trustee; outside the site, but the call sign is on every page |

Until a fact in the first four rows is confirmed, the site uses the value in
the current build if the research supports it and otherwise leaves the detail
out.

## Out of scope

- Any content that needs updating more than once a year.
- A contact form, site search, member login or members-only content.
- Changes to the visual design beyond what the content changes require.
- Editing content through the hosting panel; all edits go through GitHub.
