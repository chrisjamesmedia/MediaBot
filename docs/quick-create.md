# Quick Create (`/create/`)

A static page that builds a finite paper in the browser: name it, pick and reorder sections (presets or your own topics),
set interests, favored and avoided sources, tone and a 3/5/10/15 minute length (which caps the item count), then generate.
The edition has a hard end ("That's the edition.") and at most one capped "One more helping" pull. Print or Save as PDF
uses the page's print stylesheet.

Built by `build.py` (`--create` rebuilds only this page; the full index build includes it):
`templates/create.html.j2` + `static/create.js`, styles in `static/site.css`. The sample for demo mode is cut from the newest
published Field Notes edition (or `docs/field-notes-v2-preview/`) and the latest Signal Seeker `x`, `tech`, `investments`
and `passage` items. Only content already public on this site goes in.

## Live generation
- Endpoint: `POST https://api.x.ai/v1/responses` (the Responses API; Chat Completions is the legacy endpoint and cannot run
  the built-in search tools). Default model `grok-4.7` (editable in the page). Tools: `x_search` (with `from_date`/`to_date`,
  `excluded_x_handles`, optional `allowed_x_handles`) and `web_search` (`excluded_domains`).
- One call per section, three at a time. Each returns JSON items; the page keeps an item only if it has text, an https URL,
  and that URL (an X post's status id) appears in `response.citations` or the tool output. Everything else is dropped, jokes
  and passages must be credited, and a section with nothing verified says so instead of filling in.
- The key is typed once, kept in `localStorage` (`mb:qc:key`) and sent only to api.x.ai (or an optional proxy URL).
  Exports, saved papers and share links never contain it. A Content-Security-Policy on the page limits network calls to
  api.x.ai, `*.workers.dev` and `*.vercel.app`.
- CORS: api.x.ai allows browser calls (`access-control-allow-origin: *`), so no proxy is needed. `proxy/` is an optional,
  undeployed Cloudflare Worker for the case that changes.

## Config
`{format: "mediabot-quick-create/1", config: {...}}` JSON (localStorage `mb:qc:papers`, Export/Import), a
`#c=<base64url JSON>` share link, and a `paper.yaml` download in the shape of `papers/*/paper.yaml`
(name, slug, sections with `max_items`, `sources.x.must_read/avoid`, plus a `quick_create:` block for tone, interests and per-section topics).
Section ids that already exist in a paper (`x`, `faith`, `science`, `ideas`, `people`, `craft`, `tech`, `humor`) can be adopted
by the daily pipeline as is; new ids (`business`, `health`, custom) need a source first.
