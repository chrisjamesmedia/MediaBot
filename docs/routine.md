# The morning routine prompt (Signal Seeker)

This is the exact text the daily Grok Bot routine should use to compile `edition.json` before
running `tools/publish.sh`. Keep it in sync with `papers/signal-seeker/paper.yaml`.

```text
Compile today's Signal Seeker (papers/signal-seeker/editions/<TODAY>/edition.json, schema in
docs/edition-schema.md). This paper replaces Chris's X feed. It is not a newspaper: no legacy-media
news at the top.

ORDER (paper.yaml sets it; fill these sections):
1. front "Top of Your Feed": 2–4 items, X ONLY. The lead must be an X post or a story whose sources are all
   x.com posts (the build demotes anything else to News). Pick what his feed was actually talking about.
2. From Your X / The GOATs / Investments / Tech & AI: posts from his X timeline and lists.
3. Substack and YouTube: Worth Reading, plus new episodes and essays from the people he follows.
4. evergreen "Evergreen": 2–4 real long-form items from his X (X Articles, long threads, long posts) that
   he bookmarked, liked or saw. Read them with the user-X tools ONLY, read-only: never post, like,
   bookmark, follow, reply or DM. For each item give type (Post | Thread | X Article), title (the
   article title, or the first line), author, @handle, date, the real x.com URL, and a 2–3 sentence summary
   in your own words. Skip any URL already in papers/signal-seeker/evergreen_seen.json. Never invent an
   item. If X can't be read, leave the section out and say so in your run notes. Don't say in the paper
   that it came from his bookmarks or likes.
5. News: at most 4 short briefs, put in ordinary sections with "topic" tags; the build pools and caps them.
   KEEP: tech, AI, business/markets, science, health (metabolic, psychedelics), space, culture and ideas;
   plus material public news on his holdings (NBIS, MU, SNDK, AMZN, META) in Your Holdings, news only,
   NEVER values, share counts or position sizes.
   DROP: war, conflict, geopolitics, tankers/oil, macro/rates/Fed, politics/elections, crime, local news.
   Tag such items with "topic" (e.g. ["war","oil"]) so the build cuts them. Set "major": true ONLY if it is
   genuinely huge (a war starting or ending, a market crash or circuit breaker, a once-a-decade event);
   "major" bypasses the cut.
6. Funnies: run tools/funnies.py signal-seeker <TODAY>.

WEATHER: the --weather flag (below) makes the build fetch Boston from Open-Meteo (current temperature and
condition, today's daily max/min as High/Low, tomorrow's condition and high/low). Don't type weather
into edition.json; if the fetch fails the masthead leaves weather out.

NOTE: one useful line (an earnings date, a clock change), or nothing.

PRIVATE: emails, calendar, reminders and notes go only in the private "personal" section, never public.

BUILD AND PUBLISH: tools/publish.sh signal-seeker <TODAY> --weather. The public build also refreshes
site/signal-seeker/latest/ (print.pdf, digital.pdf, latest.json, and a redirect to today's edition),
which the scheduled printer job (tools/print-daily/) fetches, and it adds new evergreen URLs to
evergreen_seen.json. Read the build output: it lists every cut item and the page count (print must be
even, with "Sheet N of M" footers). Commit evergreen_seen.json with the edition.
```
