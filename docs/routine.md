# The morning routine prompt (Signal Seeker)

This is the exact text the daily Grok Bot routine should use to compile `edition.json` before
running `tools/publish.sh`. Keep it in sync with `papers/signal-seeker/paper.yaml`.

```text
Compile today's Signal Seeker (papers/signal-seeker/editions/<TODAY>/edition.json, schema in
docs/edition-schema.md). This paper replaces Chris's X feed. It is not a newspaper: no legacy-media
news at the top.

REQUESTS FIRST: with the cursor-github MCP tools (read-only), list OPEN issues in chrisjamesmedia/MediaBot
labelled edition-request (also catch open issues titled "Edition request:" in case the label didn't apply).
Each one is a reader asking for more on a topic. Use them to steer today's X searches (user-X
search_posts_all / search_posts_recent, last 7 days, read-only) and, where there is real material, put
what you find in the matching section (or a short extra item in Worth Your Time). Never invent coverage to
satisfy a request; if X has nothing good, say nothing. Record what you answered in edition.json
"requests" (see docs/edition-schema.md) so the paper lists them at the end. Do NOT close, label or comment
on issues (those are writes; Chris tidies them). Ignore requests for private, political or cut topics.

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
      --skip <id,id> (the next in line moves up). Then run it again with --write; it writes section "feed"
      after "front". Do this AFTER filling the other X sections so it de-dupes against them.
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
