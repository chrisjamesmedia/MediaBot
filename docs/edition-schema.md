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
      "answer": "Tech & AI", "anchor": "x-tech" }                // answer: where it is; anchor: optional web jump link
  ]
}
```

`requests` is listed at the end of the paper ("Requests answered today", web and both PDFs). Only list
real open issues, and only when the edition really covers them. The routine never closes or comments.

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
generated and checked (the sudoku has exactly one solution). Solutions print small and upside down;
on the web they sit behind "Solutions". No crossword: good clues can't be generated without making
things up.

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
