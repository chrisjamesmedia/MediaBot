# edition.json (schema 1)

One file per edition at `papers/<slug>/editions/<YYYY-MM-DD>/edition.json`, next to an optional
`images/` folder and `weather.json` (the cached Open-Meteo reply). Grok Bot writes this file each
morning; `build.py` turns it into the web page and both PDFs. The build never invents content:
a section that is missing or empty is left out of the paper.

```json
{
  "schema": 1,
  "paper": "signal-seeker",
  "date": "2026-10-31",
  "coverage": "Covering roughly Oct 29–31, 2026. Compiled Saturday morning, ET.",
  "note": "Clocks fall back one hour at 2 a.m. Sunday.",        // optional, one line under the masthead
  "description": "…",                                            // optional SEO description; otherwise built from the lead
  "sections": [ { "id": "front", "items": [ … ] }, … ],
  "requests": [                                                  // optional: edition-request issues answered today
    { "issue": 12, "title": "Edition request: robotics", "url": "https://github.com/chrisjamesmedia/MediaBot/issues/12",
      "answer": "Tech & AI", "anchor": "x-tech" }                // answer: what was done / where; anchor: optional web jump link
  ],
  "seconds": {                                                   // optional: hidden "One more helping" serving (web only)
    "items": [ … ],                                              // written by tools/x_feed.py --write (next ranked feed posts)
    "socials": [ … ]                                             // optional: up to web.seconds.socials Substack/YouTube items
  }
}
```

`requests` is listed at the end of the paper ("Tuned from your notes", web and both PDFs). Only list
real open issues, and only when the edition really acted on them. The routine never closes or comments.

`sections[].id` must match a section `id` in `paper.yaml`. Order, titles, on/off and `max_items`
come from `paper.yaml`, not from this file. Sections in the file that the config doesn't know are
skipped with a warning.

## Item types

Every item has a unique `id` (used for reader feedback and anchors) and a `type`.

### story
```json
{ "type": "story", "id": "alphabet",
  "headline": "The AI spending bill comes due: …",
  "summary": "Two to five tight sentences.",
  "short": "One sentence, used by the small print size.",      // optional
  "sources": [ { "name": "CNBC", "url": "https://…" } ],      // at least one
  "image": { "file": "images/alphabet.jpg", "credit": "CNBC" }, // optional; web and digital only, never print
  "brief": true,                                               // optional; a bundle of short items (headline styled as a kicker)
  "group": "Hyperscalers & capex" }                            // only in sections with group_by
```

### post (an X post, drawn as a post card)
```json
{ "type": "post", "id": "x-1985977741808157030",
  "author": "Paul Graham", "handle": "paulg",
  "text": "Full post text, never paraphrased.",
  "url": "https://x.com/paulg/status/1985977741808157030",
  "date": "2026-10-30T01:23:11Z",                               // ISO 8601 UTC; shown in ET
  "image": { "file": "images/x-….jpg" },                       // optional, web only
  "group": "…" }                                               // optional
```
Optional `"quoted": {"author", "handle", "text", "url"}` for a quote post, drawn as a small inset
(name, @handle, ~140-char excerpt). It comes only from the X API `referenced_tweets` data; request
`expansions=author_id,referenced_tweets.id,referenced_tweets.id.author_id` and
`tweet.fields=created_at,note_tweet,referenced_tweets`, then run
`.venv/bin/python tools/x_quoted.py <slug> <date> <raw dumps…>`. Never write a quote by hand.

Posts can appear in any section (From Your X, The GOATs, Tech & AI…). Post dates can be read from
the status id: `ms = (id >> 22) + 1288834974657`.

### line (one-sentence item: Big Stuff box, holdings, briefs)
```json
{ "type": "line", "id": "bs-japan", "text": "<b>Japan:</b> The BoJ held at 1.25%…",
  "sources": [ { "name": "AP", "url": "…" } ], "group": "META" }
```
`text` may contain `<b>` only.

### link (Worth Your Time)
```json
{ "type": "link", "id": "w-1", "title": "…", "url": "…", "why": "One short clause." }
```
Sections with `dedupe: true` drop links whose URL appears elsewhere in the finished paper (checked after
the News and topic cuts, so a link whose twin story was cut stays).

### Funnies (`funnies` section; `tools/funnies.py <slug> <date>` writes it)
```json
{ "type": "comic", "id": "comic-xkcd-3318", "title": "xkcd: Earth Sized Planets", "byline": "Randall Munroe",
  "url": "https://xkcd.com/3318/", "alt": "…", "image": { "file": "images/comic-xkcd-….png", "credit": "xkcd.com, CC BY-NC 2.5" } }
{ "type": "sudoku", "id": "sudoku-2026-11-01", "title": "Sudoku", "grid": ["7...1...2", …], "solution": ["7…", …] }
{ "type": "wordsearch", "id": "ws-2026-11-01", "title": "Word Search", "grid": ["KBNT…", …], "words": ["…"], "solution": ["K..T…", …] }
```
Comics come only from real feeds (xkcd RSS today), credited and linked; never invented. Puzzles are
generated and checked (the sudoku has exactly one solution; word-search words come only from headlines
and titles that survive the build's cuts, via `build.surviving_sections`). Solutions: on the web behind
"Show answers"; in print and the digital PDF in the Answers block on the last page.

### games (`games` section, daily; `tools/games.py <slug> <date>` writes it)
```json
{ "type": "mathq", "id": "mathq-2026-11-01", "title": "Mental Math",
  "problems": [{ "q": "24 × 8", "a": "192", "how": "24 × 8 = 20 × 8 + 4 × 8 = 192" }, …] }   // 3, rising; last = Fermi
{ "type": "wason", "id": "wason-…", "title": "Four Cards", "rule": "If a card is red on one side, …",
  "cards": ["Triangle", "Red", "Circle", "Green"], "answer": "Red and Triangle", "explanation": "…" }
{ "type": "crossword", "id": "crossword-…", "title": "Mini Crossword", "size": 5,
  "cells": [[{"b": true}, {"n": 1}, {"n": 2}, …], …], "solution": ["#RIB#", "RIVAL", …],
  "clues": { "across": [{ "n": 1, "clue": "A teasing remark", "len": 3, "answer": "RIB" }, …], "down": [ … ] } }
{ "type": "riddle", "id": "riddle-…", "title": "Riddle", "q": "What has many teeth but can't bite?", "a": "A comb." }
```
Crossword words and clues come from `tools/data/crossword_words.json` (common English words that are
WordNet lemmas, each with its WordNet gloss; rebuilt by `tools/build_crossword_words.py`); every entry is
checked to be a listed word and to read back from the grid. Web: each game has a "Show answer" toggle.
Print: an Answers page closes the paper (after any blank pad page, so it is always the last page).
Games and the passage are never trimmed for length.

### passage (`passage` section, daily; `tools/passage.py <slug> <date>` writes it)
```json
{ "type": "passage", "id": "bible-lam-3-22", "kind": "scripture", "label": "Scripture",
  "text": "It is of the LORD's mercies …", "author": "The Bible", "work": "Lamentations 3:22–23", "translation": "KJV",
  "source_url": "https://www.biblegateway.com/passage/?search=Lamentations+3%3A22-23&version=KJV",
  "sources": [{ "name": "biblegateway.com", "url": "…" }] }
{ "type": "passage", "id": "bank-032", "kind": "quote", "label": "From your old quote bank", "text": "…", "author": "…" }
```
Pools: `papers/<slug>/passages.json` (verified: text exactly as on the fetched `source_url`; fields id, text,
author, work, source_url, kind, category, verified, plus ref/translation for scripture) and
`papers/<slug>/quote_bank.json` (local only, gitignored; doc titles/ids never leave it). The source URL
prints under every non-bank passage. `passages_seen.json` (id → date) keeps anything from repeating;
`taste.json` holds the "Keep / Never again: today's passage" picks.

### evergreen (`evergreen` section): long-form from Chris's own X
```json
{ "type": "evergreen", "id": "ev-patrickc-agents-economy", "kind": "Post",      // Post | Thread | X Article
  "title": "Assorted things I've been mulling over regarding agents in the economy",
  "author": "Patrick Collison", "handle": "patrickc", "date": "2026-10-09",
  "url": "https://x.com/patrickc/status/2108706907859116280",
  "summary": "Two or three sentences in our words: what it argues and why it lasts." }
```
Only real items Chris bookmarked, liked or saw on X (X Articles, long threads, long posts), read
through the read-only X tools, 2–4 per edition. Never invented; if X can't be read that day, leave the
section out. `papers/<slug>/evergreen_seen.json` (url → first date) is updated by public builds, and
an item already used on an earlier date is dropped, so nothing repeats. The paper never says that an
item came from Chris's bookmarks or likes.

## Selection fields: `topic` and `major`

Any story, line or link can carry `"topic": ["war", "oil"]` and `"major": true`. `paper.yaml`'s `news:`
block uses them:

- An item whose topic is in `news.exclude_topics` (war, conflict, geopolitics, macro, rates, oil,
  politics, local, …) is cut from every public section unless it has `"major": true`. "Major" means
  `news.major_means`, which is rare: a war starting or ending, a market crash, a once-a-decade event.
- `feed` ("Top of your feed") holds `post` items written by `tools/x_feed.py` from the home
  timeline (ids `feed-<post id>`); it renders as the first block of the X part. Don't hand-edit it.
- `front` has `require_source: x`, so only X items (posts, or stories whose sources are all x.com)
  can be the lead. Other front items move to News.
- News: news-sourced stories from the topic sections plus Big Stuff and Local are pooled. Big Stuff
  and Local (`major_only_sections`) keep only `major` items. Then `major` items are sorted first,
  and the pool is cut to `news.max_items` (4) and rendered as one-paragraph briefs under the
  `news.title` ("Headlines"). `short` is used as the brief text if present, otherwise the first
  sentence of `text`. Your Holdings sits under the same News part.
- `build.py` prints every cut, so the morning routine can see what was left out.
- Recipe builds skip the News pooling (they have their own section lists).

## Grouping

`group_by: theme` (Investments) shows items under their `group` heading in first-seen order.
`group_by: ticker` (Your Holdings) uses `group` = ticker, ordered and named by `sources.holdings`
in `paper.yaml`. Holdings with no material news are simply absent; the paper never says
"nothing today" unless that was checked.

## Private sections
A section is made private in `paper.yaml`, not in edition.json:

```yaml
- {id: personal, title: Odds & Ends, enabled: false, weight: 1, max_items: 6, private: true}
```

- Public build (`site/`): private sections are dropped before anything is rendered, so they never
  reach the web edition, the print or digital PDF, the meta description, og tags or the sitemap.
- Private copy (`site-private/`, built by default alongside; `--public-only` skips it): every
  enabled section, `noindex`, no public URLs or QR. Local only; gitignored; never pushed.
- Personal material (emails, calendar, birthdays, reminders, notes) always goes in a private section.

## Money fields are not allowed in public items
Holdings items carry news only (headline/text, ticker, sources). The public build stops with an
error if any item in a public section has one of these keys: `shares`, `share_count`, `quantity`,
`qty`, `value`, `market_value`, `position`, `position_size`, `cost_basis`, `avg_cost`,
`weight_pct`, `allocation`, `pnl`, `gain`, `balance`. Never write holding values, share counts or
position sizes into item text either.

`seconds` items use the normal item shape. The build drops any that duplicate a URL already in the
edition, caps them at `web.seconds.count` / `socials`, and runs the same public-safety check. They show
only on the web, behind the "One more helping" button at the end of the X part.
