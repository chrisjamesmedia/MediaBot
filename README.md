# MediaBot

MediaBot makes small daily papers. Each paper has its own name, design, sources and preferences,
and each edition is finite: a front page, a handful of sections, and a clear end. There is no
infinite scroll, no ads and no rabbit holes. It is meant to replace a morning of scrolling X with
one calm read.

MediaBot is three parts:
- **Grok Bot**, which reads the sources each morning and writes one `edition.json`.
- **This repo**: deterministic Python that turns that file into a web edition, a print PDF and a
  digital PDF.
- **A simple static site** listing the papers and their archives.

The first paper is **Signal Seeker** (`papers/signal-seeker/`), Chris James's paper.
(A possible later brand for the system is "Personal Press".)

## Layout
```
build.py                    the one build command
site.yaml                   site name, one-line about, web_base (https://chrisjamesmedia.github.io/mediabot)
papers/<slug>/paper.yaml    a paper: name, sections, sources, print size, public/private
papers/<slug>/sources/      account lists (X tiers)
papers/<slug>/editions/<date>/edition.json (+ images/, weather.json)
papers/<slug>/feedback/     exported reader feedback (+ summary.json written by the build)
templates/  static/         Jinja templates, CSS, JS, fonts
docs/edition-schema.md      the edition.json format
docs/feedback.md            the feedback format and the sign-in plan
tools/migrate_legacy.py     one-off: the old Oct 31 file into schema 1
tools/screenshots.sh        headless screenshots of the local site
tools/publish.sh            the daily publish: build, index, secret scan, commit, push
tools/secret_scan.sh        fails on tokens, keys, cookies or raw dumps in files to be committed
.github/workflows/pages.yml deploys site/ to GitHub Pages on each push to main
site/                       the generated PUBLIC site (this is what gets published)
site-private/               local-only full copy incl. private sections (gitignored, never pushed)
```

## Build
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # once; also needs google-chrome + poppler-utils
.venv/bin/python build.py signal-seeker 2026-10-31            # one edition, plus all indexes
.venv/bin/python build.py signal-seeker 2026-10-31 --weather  # refetch the Boston weather first
.venv/bin/python build.py signal-seeker 2026-10-31 --size small   # override the print size
.venv/bin/python build.py --index                              # only the root page and paper pages
```
One edition writes:
- `site/<slug>/<date>/index.html`: the web edition, with its images.
- `site/<slug>/<date>/<slug>-<date>-print.pdf` and `-digital.pdf`.
- `site/<slug>/index.html`: the paper page (latest edition, then the archive).
- `site/index.html`: the root page (one line, then the list of public papers).
- `site/assets/`, `robots.txt`, and `sitemap.xml` once `web_base` is set.
- The same edition again under `site-private/`, with private sections included (skip it with
  `--public-only`). That copy has no canonical/og URLs, is `noindex`, and is never pushed.

Preview locally: `cd site && python3 -m http.server 8765`, then open http://localhost:8765/.

## The daily edition
Grok Bot starts each edition around **7:15 AM ET**, and it is ready by **8 AM ET**. You can also
build one on demand at any time. Each run:
1. Reads `paper.yaml`, the source lists, and `feedback/summary.json`.
2. Gathers from X (lists, must-reads, GOATs, followed accounts, with the noise list and caps
   applied), then web and legacy outlets.
3. Writes `papers/<slug>/editions/<date>/edition.json`, along with any images and the weather.
4. Runs `build.py <slug> <date>`.

Sections with nothing worth printing are left out. Nothing is ever padded to reach a length.

## Make or edit a paper
Copy `papers/example/` to `papers/<new-slug>/` and edit `paper.yaml`:
- `name`, `slug`, `public`, `description`. The description becomes the paper page's
  meta description.
- `masthead.weather`: a label plus lat/lon/timezone, fetched from Open-Meteo. Only the current conditions are
  shown, as one line ("Boston · 32°F, sunny"); there is no forecast. Delete it for no weather.
- `print.size`: `small`, `medium` or `large`. The sheet targets and maximums are in `print.sizes`.
  Medium is 4–5 sheets duplex. The build trims the lowest-weight sections if an edition would go
  over the maximum, and warns (but never pads) when it is under.
- `sections`: the order is the paper's order. Each has `enabled`, `weight` (higher = more room and
  last to be trimmed in print) and `max_items`. Optional fields: `group_by: theme|ticker`,
  `style: box|links`, `dedupe`.
- `sources`: X lists, must-reads, GOATs, noise accounts, per-account caps, holdings, outlets.

A fork is the same thing: copy someone's `paper.yaml` under a new slug.

`public: false` keeps a paper off the root page and adds `noindex`. It is **not** access control:
anyone with the URL can still open it (see docs/feedback.md, "Sign-in later").

## Signal Seeker: what's on and off
- **Live sources in v1:** X, plus the web and legacy outlets.
- **Section order:** Front Page, From Your X, The GOATs, Investments (by theme), Your Holdings
  (by company), Tech & AI, Worth Reading, Business, Science & Health, Local, The Big Stuff (box),
  Worth Your Time (links). That is the order in paper.yaml and the order trimming works on.
- **Reading order (by source):** each edition is regrouped at render time by where items came
  from: Front Page, then X, Substack, YouTube, News, Around the Web, Funnies. Topics are subgroups
  inside each source (`build.py: item_source / by_source`; a section can set `source_group:` to
  override). An "In this edition" contents block sits under the masthead: anchor links on the web
  (with a quiet "↑ Contents" link after each part), internal links with page numbers in the digital
  PDF, and a compact list with page numbers in print (page numbers come from a second render pass
  that reads the PDF's named destinations with pypdf).
- **Masthead:** the paper name, left-aligned, with no version string; the date line; a one-line
  weather strip. On the web, a Print button (opens the print PDF in a new tab) and a smaller
  Digital PDF link sit on the date line. They are hidden when the page itself is printed.
- **Site pages:** the root page is "Papers"; each paper page is "Editions", a plain list of dates,
  newest first, with Print / Digital links per row and a small "with Funnies" tag on Sundays.
- **Off in config:** Substack and YouTube. They need real sources before they are switched on;
  nothing is faked for them. Odds & Ends is private (below).
- **Sundays:** the `sunday:` block in paper.yaml makes the paper large and turns on Funnies (an
  xkcd comic from its RSS feed, a sudoku and a word search). Run `tools/funnies.py <slug> <date>`
  before `build.py` on Sundays. There is no public notes section, so Sunday adds no notes.
- **Print:** pure white, black ink, no fills. Footer "Sheet N of M · Front/Back · p. N"; an odd page
  count gets one blank back so it duplexes cleanly. Web and digital PDF use a warm paper tone.
- **Quoted posts:** drawn as a small inset when edition.json carries `quoted` (tools/x_quoted.py).
- **Reader feedback:** stored per browser, with an exported JSON file (docs/feedback.md). There are
  no accounts yet.

## Recipes: an on-demand paper
A recipe is a small YAML file that picks sections, caps and a page limit from the content already
fetched for a day. See docs/recipes.md. Presets live in `recipes/`; the editor at `site/edit/`
writes one.

    .venv/bin/python build.py --recipe recipes/x-substack-5.yaml 2026-11-01 --public-only

## Private sections and money details
- Any section in `paper.yaml` can carry `private: true`. A private section is left out of the public
  web edition, both public PDFs, the meta description/og tags and the sitemap. It appears only in
  the local private copy in `site-private/`, which `.gitignore` excludes and the Pages workflow
  refuses to publish.
- In Signal Seeker, Odds & Ends (`personal`: emails, calendar, birthdays, reminders, notes) is
  `private: true`. Any future personal section must be marked private too.
- **Holding values, share counts and position sizes are never shown anywhere public.** "Your
  Holdings" is public (Chris's OK) and carries material news only about NBIS, MU, SNDK, AMZN and
  META. The public build refuses to run if any item carries money fields (`shares`, `quantity`,
  `value`, `market_value`, `position`, `position_size`, `cost_basis`, `avg_cost`, `weight_pct`,
  `allocation`, `pnl`, `gain`, `balance`); keep such data out of edition.json altogether.

## Publishing (GitHub Pages, approved by Chris)
Target: repo `chrisjamesmedia/mediabot` (public), site `https://chrisjamesmedia.github.io/mediabot/`.
- `site.yaml` has `web_base: https://chrisjamesmedia.github.io/mediabot`, which turns on canonical URLs,
  og:url/og:image, the sitemap and the print QR code (it points at the edition URL).
- `site/` is committed. `.github/workflows/pages.yml` uploads it to Pages on each push to `main`
  (repo Settings → Pages → Source: **GitHub Actions**). `site/.nojekyll` is written by every build.
- Daily publish command (the morning routine runs this ~7:15 AM ET):
  ```
  tools/publish.sh                          # signal-seeker, today's date in ET
  tools/publish.sh signal-seeker 2026-10-31 # a given date
  NO_PUSH=1 tools/publish.sh                # build + commit, don't push
  ```
  It builds the edition and indexes, checks `site-private/` is untracked, runs
  `tools/secret_scan.sh`, commits and runs `git push origin main` with whatever git credential the
  machine already has (Chris's own `gh auth login` + `gh auth setup-git`). It never handles tokens.
- Never committed: `.venv/`, `.build/`, `site-private/`, `screenshots/`, feedback exports, `.env`,
  keys, cookies, tokens, and raw X dumps (those live outside this folder).

Cloudflare Pages remains an option later (same `site/`), and is the better fit once sign-in
arrives (Pages Functions, D1, Access).

**Sign-in later** (docs/feedback.md): GitHub OAuth or magic links, a small serverless function,
and one feedback table in D1 or Supabase. Cloudflare Access can make private papers truly private.
