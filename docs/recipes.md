# Recipes

A recipe is a one-off paper made from content MediaBot already fetched for a date. It picks
sections, caps each one, and sets a page limit. The build trims the lowest-weight items to fit,
and never pads to fill.

```yaml
recipe: 1
name: X + Substack, 5 pages
paper: signal-seeker        # whose edition.json to read
format: print               # print | web  (web trims the digital PDF instead)
size: medium                # type size: small | medium | large
pages: 5                    # max pages for the chosen format
sections:                   # in paper order; anything not listed is left out
  - {id: x, max_items: 10}
  - {id: investments, max_items: 6, types: [post]}   # types: post | story | line | link | comic …
  - {id: funnies, max_items: 4, title: Puzzles}       # optional title and weight overrides
accounts: [paulg, naval]    # optional: keep only posts from these X handles
```

Build:

    .venv/bin/python build.py --recipe recipes/<file>.yaml <date> [--public-only]

Output: `site/<paper>/custom/<recipe-file-name>/<date>/` (web page, print PDF, digital PDF), marked
`noindex`. Private sections stay out of the public build, as always.

Presets (`preset: true`) show in the editor: Default, Sunday, X + Substack (5 pages), Legacy media
only, Comics + YouTube.

The editor (`site/edit/`) is a static page. It saves your choices in your browser and gives you
the recipe to copy or download. Send it to MediaBot to build: the site can't run a build itself.

A section with no source yet (Substack, YouTube) simply comes out empty and is skipped.

## Layout of a recipe edition
A recipe edition uses the same templates as the daily paper. Its sections are regrouped by source
(X, Substack, YouTube, News, Around the Web, Funnies) and get an "In this edition" contents block
when there is more than one part or topic. Recipe editions are not listed on the paper's Editions
page; they live under `site/<slug>/custom/<recipe>/<date>/`.
