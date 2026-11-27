# Quick Create (`/create/`)

A phone-first page that builds a finite paper in the browser. The builder is in this order: **People you follow**, then **Topics**, then **Fun**, then a length (5 / 10 / 15 minutes), then **Delivery**, then **Make my paper**. The edition has a hard end ("That's the edition.") and at most one "3 more, then done" pull. A **← MediaBot** link at the top of the page and of every edition goes back to the site home. Print or Save as PDF uses the page's print stylesheet.

Built by `build.py` (`--create` rebuilds only this page; the full index build includes it):
`templates/create.html.j2` + `static/create.js`, styles in `static/site.css`. The sample for demo mode is cut from the newest
published Field Notes edition (or `docs/field-notes-v2-preview/`) and the latest Signal Seeker `x`, `tech`, `investments`
and `passage` items. Only content already public on this site goes in. A sample cannot fetch posts from people you typed in.

A line under the button says where content comes from: "Grok searches X and the web live. Only posts with a real source link are kept." Favor/avoid extras, tone, freshness, look-in, source links, model, proxy, and save/export live under a collapsed **More options** link. The xAI key field appears only when you press Make without a key already saved, with "Just show me a sample" as the other choice.

## People, Topics, Fun
- **People you follow** is first and most prominent. Add @handles or names. Their posts come first in the edition (live search is limited to those handles when you have them).
- **Topics**: a "What do you want to read about?" box plus chips (Faith & Scripture, Nature & Science, Books & Ideas, People & Stories, Craft & Work, Tech / AI, and "+ Add your own").
- **Fun**: Jokes, Memes, Game pick, Movie pick, Poem. Jokes are on by default. Fun items must be real and credited, never model-written; a game or movie pick must link the recommendation it came from. If a real source cannot be found, the section stays empty.

The edition always renders in that order: People, then Topics, then Fun. The UI never shows item caps ("up to N"); those stay internal.

In the edition, each section has a plain source line ("From X posts found by Grok search", "From the web, found by Grok search", or both; in a sample, "From your Field Notes and Signal Seeker papers."). Each item shows its @handle or site name, plus the date. A sample banner reads: "Sample — these are posts already printed in your Field Notes and Signal Seeker papers, not a fresh search."

## Delivery
How: On the site (default, works now) / Email / Text. When: Just now / Every morning at a time / Weekly on a day at a time. Times are Eastern. If you pick Email or Text, an email or phone field appears. Those contacts stay in this browser (localStorage). They are stripped from the share link, the JSON export, and `paper.yaml`.

The site is static, so scheduled email or text cannot actually send yet. When you pick Email, Text, or a schedule, the page says: "Scheduled email/text delivery is coming soon. For now we save your choice." It does not pretend to send.

`paper.yaml` includes a `delivery:` block with `how`, `when`, and (if scheduled) `time` and `weekday` only.

## Live generation
- Endpoint: `POST https://api.x.ai/v1/responses` (the Responses API; Chat Completions is the legacy endpoint and cannot run
  the built-in search tools). Default model `grok-4.7` (editable under More options). Tools: `x_search` (with `from_date`/`to_date`,
  `excluded_x_handles`, optional `allowed_x_handles`) and `web_search` (`excluded_domains`).
- One call per section, three at a time. Each returns JSON items; the page keeps an item only if it has text, an https URL,
  and that URL (an X post's status id) appears in `response.citations` or the tool output. Everything else is dropped, jokes
  and passages must be credited, and a section with nothing verified says so instead of filling in.
- The key is typed when needed, kept in `localStorage` (`mb:qc:key`) and sent only to api.x.ai (or an optional proxy URL).
  Exports, saved papers and share links never contain it. A Content-Security-Policy on the page limits network calls to
  api.x.ai, `*.workers.dev` and `*.vercel.app`.
- CORS: api.x.ai allows browser calls (`access-control-allow-origin: *`), so no proxy is needed. `proxy/` is an optional,
  undeployed Cloudflare Worker for the case that changes.

## Config
`{format: "mediabot-quick-create/1", config: {...}}` JSON (localStorage `mb:qc:papers`, Export/Import under More options), a
`#c=<base64url JSON>` share link, and a `paper.yaml` download in the shape of `papers/*/paper.yaml`
(name, slug, sections with `max_items`, `sources.x.must_read/avoid`, a `quick_create:` block, and `delivery:`).
Section ids that already exist in a paper (`faith`, `science`, `ideas`, `people`, `craft`, `tech`, `humor`) can be adopted
by the daily pipeline as is; `following` and the Fun picks (`memes`, `game`, `movie`, `poem`) and custom chips need a source first.
