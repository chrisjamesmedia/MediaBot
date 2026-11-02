#!/usr/bin/env python3
""""Top of your feed": rank the reader's X home timeline and write a small, fixed-size `feed` section.

    .venv/bin/python tools/x_feed.py signal-seeker 2026-11-01 /tmp/feed/p*.json            # dry run: print the pick
    .venv/bin/python tools/x_feed.py signal-seeker 2026-11-01 /tmp/feed/p*.json --write    # write it into edition.json
    ... --skip 2116...,2116...   veto posts by id (off-topic for the paper), the next ones move up
    ... --media /tmp/feed/media.json   photos for posts: a saved get_posts_by_ids reply (expansions=attachments.media_keys,
                                       media.fields=type,url,alt_text), for when the timeline dump has no media

Funny candidates: short or off-topic posts used to be dropped, but that is where the jokes and memes are. Posts
cut only for "too short" or "off your topics" (still not replies, promo, cut topics, noise accounts or reposts of
strangers; text at most 400 chars) are ranked by the same score and listed as "Funny candidates". With --write the
top 40 go to edition.json "funny_candidates" (not printed anywhere by themselves). On Funnies days the routine
reads that list, judges which are actually funny, and tools/funnies.py puts 1-2 of them in the Funnies section
(--skip there vetoes the rest). Nothing is rewritten: real handle, exact text, real x.com link.

Input: raw replies of the user-X MCP tool `get_users_timeline` (the reader's home timeline, reverse-chronological;
the algorithmic For You feed is not in the API), one file per page, saved outside the repo. Request:
    exclude=replies  max_results=100  start_time=<now-24h>  end_time=<now-1min>
    post.fields=created_at,public_metrics,author_id,lang,conversation_id,referenced_tweets,note_tweet,in_reply_to_user_id
    expansions=author_id,referenced_tweets.id,referenced_tweets.id.author_id,attachments.media_keys
    user.fields=name,username,verified,public_metrics   media.fields=type,url,alt_text   (media is optional:
    with it, a funny post's photo can run in the Funnies)
and follow meta.next_token until it is absent or the posts are older than the window.

Config (paper.yaml): the `feed` section's `enabled` and `max_items` (the count), and `sources.x.home_feed`
(window_hours, per_author, min_chars, skip_words). With `web.seconds` on, the next `web.seconds.count` posts in
the same ranking (same filters, one per author across both) go to edition.json "seconds", the web edition's
one-time "One more helping". Nothing is invented: every item is a real post from the dump,
with its full text and real x.com URL. Read-only: this only reads files.
"""
import json, math, re, sys, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMO = re.compile(r"\b(giveaway|use code|promo code|discount code|link in bio|sponsored|#ad|airdrop|presale|"
                   r"like (and|&) (rt|repost)|hit me in (the )?replies|drop your|comment below|reply with|tag a friend|bookmark this|save this|follow (me|us) for|dm me|join my|sign up (now|today)|webinar)\b", re.I)


def load_yaml(p):
    import yaml
    return yaml.safe_load(Path(p).read_text())


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def status_ids(obj):
    """Every x.com status id mentioned anywhere in the edition (items, sources, quoted)."""
    return set(re.findall(r"(?:x|twitter)\.com/[^/\"\s]+/status/(\d+)", json.dumps(obj)))


def full_text(t):
    return (t.get("note_tweet") or {}).get("text") or t.get("text", "")


def clip(text, n):
    """Long posts are cut at a paragraph or sentence end before n chars (marked with an ellipsis); the full post is a click away."""
    if not n or len(text) <= n:
        return text
    cut = text[:n]
    for sep in ("\n\n", ". ", "? ", "! ", "\n"):
        i = cut.rfind(sep)
        if i > n * 0.5:
            return cut[:i + (1 if sep[0] in ".?!" else 0)].rstrip() + " …"
    return cut[:cut.rfind(" ")].rstrip() + " …"


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    write = "--write" in argv
    skip_ids = set()
    for i, a in enumerate(argv):
        if a == "--skip" and i + 1 < len(argv): skip_ids |= set(argv[i + 1].split(","))
    if "--skip" in argv: args.remove(argv[argv.index("--skip") + 1])
    media_files = argv[argv.index("--media") + 1].split(",") if "--media" in argv else []
    if "--media" in argv: args.remove(argv[argv.index("--media") + 1])
    if len(args) < 3: sys.exit(__doc__)
    slug, date, dumps = args[0], args[1], args[2:]
    pdir = ROOT / "papers" / slug
    paper = load_yaml(pdir / "paper.yaml")
    sec_cfg = next((c for c in paper["sections"] if c["id"] == "feed"), None)
    if not sec_cfg or not sec_cfg.get("enabled", True):
        sys.exit("feed section is off in paper.yaml; nothing to do")
    count = int(sec_cfg.get("max_items") or 8)
    sc = (paper.get("web") or {}).get("seconds") or {}
    extra = int(sc.get("count", 8)) if sc.get("enabled") else 0   # "One more helping": the next posts in line
    xs = (paper.get("sources") or {}).get("x") or {}
    hf = xs.get("home_feed") or {}
    window = float(hf.get("window_hours", 24))
    per_author = int(hf.get("per_author", 1))
    min_chars = int(hf.get("min_chars", 80))
    max_chars = int(hf.get("max_chars", 600))
    words = [w.lower() for w in hf.get("skip_words") or []]
    pats = [re.escape(w[:-1]) + r"\w*" if w.endswith("*") else re.escape(w) + r"(?:s|es)?\b" for w in words]
    skip_re = re.compile(r"\b(" + "|".join(pats) + r")", re.I) if words else None
    noise = {h.lstrip("@").lower() for h in xs.get("noise") or []}
    kw = [w.lower() for w in hf.get("topic_words") or []]
    kpats = [re.escape(w[:-1]) + r"\w*" if w.endswith("*") else re.escape(w) + r"(?:s|es)?\b" for w in kw]
    topic_re = re.compile(r"\b(" + "|".join(kpats) + r")", re.I) if kw else None
    require_topic = bool(hf.get("require_topic"))
    min_reposters = int(hf.get("min_reposters", 2))
    listed = {h.lstrip("@").lower() for h in (xs.get("must_read") or []) + (xs.get("goats") or [])}
    af = xs.get("accounts_file")
    if af and (pdir / af).exists():
        listed |= {a["handle"].lstrip("@").lower() for a in json.loads((pdir / af).read_text())}
    reader = (hf.get("reader_handle") or "").lstrip("@").lower()

    ep = pdir / "editions" / date / "edition.json"
    ed = json.loads(ep.read_text())
    ed_wo_feed = dict(ed, sections=[s for s in ed["sections"] if s["id"] != "feed"])
    in_edition = status_ids(ed_wo_feed)

    posts, users, media, seen_rows = {}, {}, {}, 0
    reposters = {}            # original id -> set of followed accounts that reposted it in the window
    timeline = []             # (kind, post) rows from data[]
    newest = None
    for f in dumps:
        d = json.loads(Path(f).read_text())
        if "data" not in d and isinstance(d.get("result"), dict): d = d["result"]
        inc = d.get("includes") or {}
        for u in inc.get("users", []): users[u["id"]] = u
        for m_ in inc.get("media", []): media[m_.get("media_key")] = m_
        for t in inc.get("posts", []) + inc.get("tweets", []): posts.setdefault(t["id"], t)
        for t in d.get("data") or []:
            seen_rows += 1
            posts[t["id"]] = t
            kinds = [r["type"] for r in t.get("referenced_tweets") or []]
            timeline.append((kinds, t))
            c = ts(t["created_at"])
            newest = c if newest is None or c > newest else newest
    attach = {}               # post id -> media keys, from --media lookups (photos only; never ranked)
    for f in media_files:
        d = json.loads(Path(f).read_text())
        if "data" not in d and isinstance(d.get("result"), dict): d = d["result"]
        for m_ in (d.get("includes") or {}).get("media", []): media[m_.get("media_key")] = m_
        for t in d.get("data") or []: attach[t["id"]] = (t.get("attachments") or {}).get("media_keys") or []
    if not timeline: sys.exit("no timeline posts in the dumps")
    start = newest - datetime.timedelta(hours=window)

    cands, why_out, followed = {}, {}, set()
    for kinds, t in timeline:
        if ts(t["created_at"]) < start: continue
        if "reposted" in kinds:
            oid = next(r["id"] for r in t["referenced_tweets"] if r["type"] == "reposted")
            reposters.setdefault(oid, set()).add(t["author_id"])
            if oid in posts: cands.setdefault(oid, posts[oid])
            continue
        if "replied_to" in kinds or t.get("in_reply_to_user_id"):
            why_out[t["id"]] = "reply"; continue
        cands.setdefault(t["id"], t)
        followed.add(t["author_id"])

    def handle(t): return (users.get(t.get("author_id")) or {}).get("username", "")

    def score_of(pid, t, h, text):
        m = t.get("public_metrics") or {}
        eng = (m.get("like_count", 0) + 2 * m.get("repost_count", 0) + 2 * m.get("quote_count", 0)
               + 3 * m.get("bookmark_count", 0) + 0.5 * m.get("reply_count", 0))
        fol = ((users.get(t["author_id"]) or {}).get("public_metrics") or {}).get("followers_count", 0)
        net = len(reposters.get(pid, set()) - {t["author_id"]})
        substance = 1 + min(m.get("bookmark_count", 0) / (m.get("like_count", 0) + 1), 0.5)
        on_topic = 1.3 if topic_re and topic_re.search(text) else 1.0
        mine = 1.3 if h in listed else 1.0
        return math.log1p(eng) / (1 + fol / 1e5) ** 0.15 * (1 + 0.25 * min(net, 4)) * substance * on_topic * mine, net

    def photo(t):
        for k in (t.get("attachments") or {}).get("media_keys") or attach.get(t["id"]) or []:
            m_ = media.get(k) or {}
            if m_.get("type") == "photo" and m_.get("url"): return m_
        return None

    scored, humor = [], []
    for pid, t in cands.items():
        h = handle(t).lower()
        text = full_text(t)
        bare = re.sub(r"https?://\S+|@\w+", "", text).strip()
        reason = None
        if not h: reason = "author unknown"
        elif pid in in_edition: reason = "already in the edition"
        elif pid in skip_ids: reason = "skipped by editor"
        elif h in noise: reason = "noise account"
        elif reader and h == reader: reason = "reader's own post"
        elif ts(t["created_at"]) < start: reason = "older than window"
        elif t.get("lang") not in (None, "en"): reason = f"lang {t.get('lang')}"
        elif t.get("in_reply_to_user_id") and t.get("in_reply_to_user_id") != t.get("author_id"): reason = "reply"
        elif len(bare) < min_chars: reason = "too short"
        elif PROMO.search(text): reason = "promo"
        elif skip_re and skip_re.search(text): reason = f"cut topic ({skip_re.search(text).group(1).lower()})"
        elif t["author_id"] not in followed and h not in listed and len(reposters.get(pid, set())) < min_reposters:
            reason = "repost of an account you don't follow"
        elif require_topic and not (topic_re and topic_re.search(text)) and h not in listed: reason = "off your topics"
        if reason in ("too short", "off your topics") and len(text) <= 400 and (len(bare) >= 15 or photo(t)) \
                and not PROMO.search(text) and not (skip_re and skip_re.search(text)) \
                and (t["author_id"] in followed or h in listed or len(reposters.get(pid, set())) >= min_reposters):
            humor.append((*score_of(pid, t, h, text)[:1], pid, t, 0))     # a funny candidate, not a feed pick
        if reason:
            why_out[pid] = reason; continue
        score, net = score_of(pid, t, h, text)
        scored.append((score, pid, t, net))
    scored.sort(key=lambda x: -x[0])

    pick, per = [], {}
    for score, pid, t, net in scored:
        a = t["author_id"]
        if per.get(a, 0) >= per_author: continue
        per[a] = per.get(a, 0) + 1
        pick.append((score, pid, t, net))
        if len(pick) >= count + extra: break
    pick, more = pick[:count], pick[count:]

    def to_item(score, pid, t, net, prefix="feed"):
        u = users[t["author_id"]]
        it = {"type": "post", "id": f"{prefix}-{pid}", "author": u.get("name") or u["username"], "handle": u["username"],
              "text": clip(full_text(t), max_chars), "url": f"https://x.com/{u['username']}/status/{pid}",
              "date": ts(t["created_at"]).strftime("%Y-%m-%dT%H:%M:%SZ")}
        q = next((r["id"] for r in t.get("referenced_tweets") or [] if r["type"] == "quoted"), None)
        if q and q in posts and (users.get(posts[q].get("author_id")) or {}).get("username"):
            qu = users[posts[q]["author_id"]]
            it["quoted"] = {"author": qu.get("name") or qu["username"], "handle": qu["username"],
                            "text": clip(full_text(posts[q]), max_chars // 2), "url": f"https://x.com/{qu['username']}/status/{q}"}
        ph = photo(t)
        if ph: it["image_url"], it["image_alt"] = ph["url"], ph.get("alt_text") or ""
        return it
    items = [to_item(*p) for p in pick]
    more_items = [to_item(*p, prefix="more") for p in more]
    humor.sort(key=lambda x: -x[0])
    funny, fper = [], set()
    for p in humor:
        if p[2]["author_id"] in fper: continue
        fper.add(p[2]["author_id"]); funny.append(dict(to_item(*p, prefix="funny"), score=round(p[0], 2)))
        if len(funny) >= 40: break

    from collections import Counter
    print(f"home timeline: {seen_rows} rows, {len(cands)} candidate posts, window {start:%Y-%m-%d %H:%M}Z → {newest:%Y-%m-%d %H:%M}Z")
    print("left out: " + ", ".join(f"{k} {v}" for k, v in Counter(why_out.values()).most_common()))
    print(f"\nTop of your feed ({len(items)} of {count}):")
    for (score, pid, t, net), it in zip(pick, items):
        print(f"  {score:5.2f}  @{it['handle']:<18} {' +%d reposts in feed' % net if net else ''}\n         {it['url']}\n         {' '.join(it['text'].split())[:150]}")
    if extra:
        print(f"\nOne more helping (seconds, {len(more_items)} of {extra}):")
        for (score, pid, t, net), it in zip(more, more_items):
            print(f"  {score:5.2f}  @{it['handle']:<18} {pid}\n         {' '.join(it['text'].split())[:150]}")
    print("\nnext in line (for --skip swaps):")
    taken = {p[1] for p in pick + more}
    for score, pid, t, net in [s for s in scored if s[1] not in taken][:8]:
        print(f"  {score:5.2f}  @{handle(t):<18} {pid}  {' '.join(full_text(t).split())[:90]}")
    print("\nFunny candidates (short / off-topic posts, same ranking; judge which are really funny):")
    for it in funny:
        print(f"  {it['score']:5.2f}  @{it['handle']:<18} {it['id'][6:]}{'  [photo]' if it.get('image_url') else ''}\n         {' '.join(it['text'].split())[:150]}")
    if write:
        ed["funny_candidates"] = funny
        ed["sections"] = [s for s in ed["sections"] if s["id"] != "feed"]
        ed["sections"].insert(min(1, len(ed["sections"])), {"id": "feed", "items": items})
        if extra:   # web-only, hidden until the reader asks; keeps any socials extras the routine added
            ed["seconds"] = dict(ed.get("seconds") or {}, items=more_items)
        ep.write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n")
        print(f"\nwrote {len(items)} items to {ep.relative_to(ROOT)} (section 'feed')"
              + (f" and {len(more_items)} to 'seconds'" if extra else "") + f"; {len(funny)} funny candidates")


if __name__ == "__main__":
    main(sys.argv[1:])
