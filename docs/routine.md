# The morning routine prompt (Signal Seeker)

This is the exact text the daily Grok Bot routine should use to compile `edition.json` before
running `tools/publish.sh`. Keep it in sync with `papers/signal-seeker/paper.yaml`.

```text
Compile today's Signal Seeker (papers/signal-seeker/editions/<TODAY>/edition.json, schema in
docs/edition-schema.md). This paper replaces Chris's X feed. It is not a newspaper: no legacy-media
news at the top.

TUNE FIRST: with the cursor-github MCP tools (read-only), list OPEN issues in chrisjamesmedia/MediaBot
labelled edition-request (also catch open issues titled "Edition request:" in case the label didn't apply).
They come from the "Tune tomorrow's paper" box at the end of the web edition. Body format:
    Edition: 2026-11-01
    Picked:
    - More AI infrastructure
    - Shorter paper
    Anything else:
    More on humanoid robots actually shipping
Parse the "- " lines under "Picked:" (ignore "(none)"; an older "- [x] label" form means the same) and the
free text under "Anything else:" (ignore "(nothing)"; stop at the "---" line). Options are labels from
paper.yaml web.tune (options + fixed). Act on them for TODAY's edition, newest issue wins on a conflict:
- "More <section>" (More investing, More long reads, More from Substack, More YouTube summaries, More
  science & health, More comics & puzzles, More on my holdings, More from the GOATs): fill that section
  to its max_items, and run one or two extra read-only X searches for it if it is thin.
- "Fewer <thing>" (Fewer market posts, Fewer headlines): keep that section/part to about half its usual
  count, the strongest items only.
- "More AI infrastructure": 2-3 extra read-only X searches (user-X search_posts_recent, last 7 days) on
  GPUs, data centers, power, neoclouds; put real finds in Tech & AI or Investments.
- "Keep: today's passage" / "Never again: today's passage": look up the "Edition:" date's passage in
  papers/signal-seeker/passages_seen.json (the id whose date is that edition) and append
  {"id", "author", "kind", "edition"} (author/kind from passages.json, or quote_bank.json for bank-* ids)
  to "keep" or "never" in papers/signal-seeker/taste.json. Never-ids are never picked again; that
  author is picked a third as often; kept authors three times as often (tools/passage.py reads it).
  Commit taste.json. If both were ticked, "never" wins.
- "Shorter paper": build size small (fewer items everywhere, front 2-3). "More new voices": prefer
  well-engaged accounts that are NOT already in his lists/GOATs for From Your X and the feed vetoes.
- Free text: treat as a topic ask. Steer today's X searches (user-X search_posts_all / search_posts_recent,
  last 7 days, read-only) and, where there is real material, put it in the matching section (or a short
  extra item in Worth Your Time).
Never invent coverage to satisfy a request; if X has nothing good, say nothing. Record each issue you
acted on in edition.json "requests" (see docs/edition-schema.md) with "answer" saying what you did
(e.g. "More AI infrastructure: 2 extra posts in Tech & AI; Shorter paper: small build"), and list the
same in your run notes. Do NOT close, label or comment on issues (those are writes; Chris tidies them).
Ignore requests for private, political or cut topics.

ORDER (paper.yaml sets it; fill these sections):
1. front "Front Page": 2–4 items, X ONLY. The lead must be an X post or a story whose sources are all
   x.com posts (the build demotes anything else to News). Pick what his feed was actually talking about.
1b. feed "Top of your feed": the most-engaged posts from his home timeline in the last 24 hours, a fixed
   handful (paper.yaml: max_items, enabled; tuning in sources.x.home_feed). Steps:
   a. user-X get_users_timeline, id 460613058 (@ChrisJamesUSA), max_results 100, exclude ["replies"],
      tweet_fields created_at,public_metrics,author_id,lang,conversation_id,referenced_tweets,note_tweet,
      in_reply_to_user_id, expansions author_id,referenced_tweets.id,referenced_tweets.id.author_id,
      user_fields username,name,verified,public_metrics. Follow meta.next_token until the oldest post is
      older than window_hours (about 14 pages at ~100 posts/hour). end_time, if set, must be >=10 s ago.
      Save each raw page as JSON OUTSIDE the repo (e.g. /tmp/feed/p01.json ...). Read-only: never like,
      repost, bookmark, follow or reply.
   b. Dry run: python tools/x_feed.py signal-seeker <TODAY> /tmp/feed/p*.json. It ranks posts by engagement
      (likes + reposts + quotes + bookmarks, damped for huge accounts, boosted when several people he
      follows reposted it, for bookmark-heavy "substance", topic match and his own source lists), drops
      replies, ads/promos, short memes, cut topics (skip_words), posts already in the edition, and reposts
      of strangers that only one person he follows shared. It prints the pick and the next in line.
   c. Read the pick. Veto anything off-topic, promotional, political or low-substance with
      --skip <id,id> (the next in line moves up). It also prints "One more helping": the next
      paper.yaml web.seconds.count posts (same filters, de-duped). Read and veto those too, with the same
      --skip list. Then run it again with --write; it writes section "feed" after "front" and
      edition.json "seconds".items (the hidden "One more helping" serving at the end of the web X part).
      Do this AFTER filling the other X sections so it de-dupes against them.
   c2. Optional: if Substack/YouTube are connected and there are good new items that did NOT make
      Worth Reading / Worth Your Time, put up to web.seconds.socials of them in edition.json
      "seconds".socials (same item shape, real URLs only). x_feed --write keeps that list.
   d. If the timeline can't be read, leave the section out and say so in your run notes.
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
6. Funnies (Sundays): run tools/funnies.py signal-seeker <TODAY> AFTER sections 1-5 are final: the
   word search takes its words only from headlines/titles that survive the build's cuts.
7. The Passage: run tools/passage.py signal-seeker <TODAY>. One item a day, never repeated
   (passages_seen.json), skipping taste.json "never" picks. Weekly rotation by weekday:
     Sun, Thu  the Bible (about 2 a week; KJV, less-worn passages, cited book chapter:verse + translation)
     Tue, Sat  "From your old quote bank" throwback (+ Mon on even ISO weeks: 2-3 a week)
     Wed       another ancient text (Tao Te Ching, Marcus Aurelius, Epictetus) on odd ISO weeks only;
               otherwise a writer
     Fri       a Tim Ferriss 5-Bullet Friday pick
     Mon (odd weeks)  a writer: Feynman, Whitman, Jed McKenna, Paul Millerd, Joe Hudson (Art of
               Accomplishment), Seneca/Montaigne deep cuts, Mary Oliver, Wendell Berry, founder letters
   An empty pool falls through to writers, then anything unseen.
   Pools: papers/signal-seeker/passages.json (committed; every item verified: text exactly as on its
   source_url, which you fetched, and which prints with it) and papers/signal-seeker/quote_bank.json
   (LOCAL ONLY, gitignored: Chris's old quote bank, extracted read-only from his Google Docs; it holds doc
   titles/ids, which never go in the paper; only text + author print, labelled "From your old quote
   bank"). If quote_bank.json is missing (a fresh checkout), bank days fall back to writers.
   ADDING to passages.json (when it runs low; check the count of ids not yet in passages_seen.json):
   fetch the source page, copy the text exactly, and set source_url to that page. Never invent or
   paraphrase a quote, an attribution or a URL; no quote-poster sites (Goodreads, BrainyQuote, AZ Quotes)
   and no clichés (no Gandhi, no over-used Einstein/Churchill/Rumi). Bible: public-domain text (KJV,
   WEB or ASV) from a Bible Gateway or eBible page you fetched, "ref" = book chapter:verse, "translation".
   Ancient texts: a public-domain translation (Project Gutenberg), checked against the text. In-copyright
   poems and books: a few lines only; public-domain works can run longer. Lean on the Bible more than
   other ancient texts.
8. Games: run tools/games.py signal-seeker <TODAY>. Mental math (3, rising; the last a Fermi estimate),
   a Wason four-card task with its explanation, a 5x5 mini crossword (real words, WordNet clues, checked
   to read back from the grid) and a classic riddle. All generated and checked; answers sit behind "Show
   answer" on the web and on the last page ("Answers") in print. Never write puzzle content by hand.

WEATHER: the --weather flag (below) makes the build fetch Boston from Open-Meteo (current temperature and
condition, today's daily max/min as High/Low, tomorrow's condition and high/low). Don't type weather
into edition.json; if the fetch fails the masthead leaves weather out.

NOTE: one useful line (an earnings date, a clock change), or nothing.

PRIVATE: emails, calendar, reminders and notes go only in the private "personal" section, never public.

BUILD AND PUBLISH: tools/publish.sh signal-seeker <TODAY> --weather. The public build also refreshes
site/signal-seeker/latest/ (print.pdf, digital.pdf, latest.json, and a redirect to today's edition),
which the scheduled printer job (tools/print-daily/) fetches, and it adds new evergreen URLs to
evergreen_seen.json. Read the build output: it lists every cut item and the page count (print must be
even, with "Sheet N of M" footers). Commit evergreen_seen.json, passages_seen.json and taste.json with
the edition (never quote_bank.json: it is gitignored and must stay private). The public build refuses
any item carrying quote-bank doc refs (source_doc_title / source_doc_id).
```
