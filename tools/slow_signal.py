#!/usr/bin/env python3
"""Field Notes (v2): pick a calm, varied read of 15-25 lasting X posts (plus one passage of Scripture), NOT about AI,
NOT about investing, NOT about politics or war. Sized to a 3-10 minute read (900-2,500 words).

    .venv/bin/python tools/slow_signal.py field-notes 2026-11-26 /tmp/feed/p*.json                           # dry run: show the pick
    ... --curated /tmp/slow/curated_*.json     searches of the curated accounts (papers/field-notes/sources/curated_accounts.json;
                                               tools/fn_queries.py prints the queries). Their default section is known.
    ... --evergreen /tmp/slow/bookmarks.json,/tmp/slow/likes.json   dumps whose posts may be older (bookmarks, likes)
    ... --write                                write papers/field-notes/editions/<date>/edition.json (and record the scripture pick)
    ... --skip ID,ID           veto posts after reading them (AI/finance in disguise, politics, ragebait, not lasting, a dud joke…)
    ... --pin ID,ID            make sure these candidates are in (they still pass the hard filters)
    ... --topic ID=section,... file a post under a section (faith, science, ideas, people, craft, humor)
    ... --cuts 40              print this many cut examples per reason (default 4)
    ... --full 60              print the top 60 survivors in full (with quoted text) so the worker can read them
    ... --no-scripture         leave out the daily passage

Input: raw replies of the read-only X tools, saved OUTSIDE the repo, one file per page. Positional dumps are the
reader's home timeline and Lists; --evergreen is bookmarks/likes (never labeled as such in the public paper); both
feed the opening "From Your Feed" section after AI / investing / politics cuts. --curated fills the topic sections.
and search_posts_all pages for the curated accounts). Both `note_tweet` and `note_post` (long-post text) are understood.

How the filter works (paper.yaml sources.x.slow), applied to the post AND to any post it quotes:
  1. Never printed: replies, the reader's own posts, hook accounts (mostly AI/markets/crypto), noise accounts, non-English, too short,
     too old, a post that already ran, near-duplicate text, promos (episodes, tickets, "read more"), hashtag spam.
  2. HARD words (exclude.ai / money / politics_war / ragebait): one whole-word hit cuts the post. These are only unambiguous words.
  3. SOFT words (exclude.soft): words that are fine alone ("judge", "border", "market", "trade", "token", "meta", "ice", "money") but
     together mean a post is drifting to politics, tech or finance. One soft hit is kept; two different ones cut it.
Topic: every section scores the post by how many of its topic words it uses; a curated account's default section counts too.
Selection: each section's minimum first (best score), then the best of what is left, one post per author (a second only if the paper
is still short), the section maximums, then stop at the count and word targets. Nothing is invented or shortened: full post text
(long-post note text) and full quoted text go into edition.json as posted; only t.co links and HTML entities (&amp;) are tidied.
The item keeps its real x.com URL for the record; Field Notes' templates never link it. Read-only: this only reads files.
"""
import datetime, html, json, math, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
CASHTAG = re.compile(r"(?<![\w$])\$[A-Za-z][A-Za-z.]{0,5}\b")
URL = re.compile(r"https?://\S+")
PROMO = re.compile(r"\b(new episode|in this episode|on today'?s episode|listen now|watch now|available now|out now|pre-?order|register (now|today)|"
                   r"tickets?|presale|read more|learn more|sign up|subscribe|join us|link in|click here|livestream|webinar|giveaway|use code|"
                   r"shop now|order now|apply now|new video|now streaming|new blog post|new article|in a new|this week on|on sale|"
                   r"free shipping|limited time|our mission to|get your copy|rsvp|conversation with|watch as|tune in|guided tours?|now open|"
                   r"open today|visit us|gift guide|gift ideas|black friday|sale|exhibition|holiday tradition|check (this|it|these|them) out|check out|"
                   r"follow (this|him|her)|my new (book|article|essay|podcast)|new (episode|season|issue|release|collection)|"
                   r"this (site|link|video|thread|article|episode))\b", re.I)


def load_yaml(p):
    import yaml
    return yaml.safe_load(Path(p).read_text())


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def word_re(words):
    pats = []
    for w in words:
        w = str(w).lower()
        exact = w.startswith("=")                    # "=trump" matches trump, not trumps
        if exact: w = w[1:]
        if exact: p = re.escape(w)
        elif w.endswith("*"): p = re.escape(w[:-1]) + r"[\w'’-]*"
        else: p = re.escape(w) + r"(?:s|es|'s|’s)?"
        pats.append((r"(?<![\w])" if re.match(r"\w", w) else "") + p + (r"(?![\w])" if re.search(r"\w\*?$", w) else ""))
    return re.compile("(" + "|".join(pats) + ")", re.I) if pats else None


def full_text(t):
    n = t.get("note_tweet") or t.get("note_post") or {}
    return (n.get("text") if isinstance(n, dict) else None) or t.get("text", "")


def tidy(text):
    """Exact post text; HTML entities decoded and t.co attachment links dropped (they are not words), whitespace around them tidied."""
    text = html.unescape(text)
    text = re.sub("[\u2060\u200b\u200c\u200d\ufeff]", "", text)          # invisible characters, not words
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)                    # stray markdown bold
    text = re.sub(r"[ \t]*https://t\.co/\w+", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def nwords(s):
    return len(re.findall(r"\b[\w'’-]+\b", s))


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())[:90]


def arg_list(argv, flag):
    out = []
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv): out += [x for x in argv[i + 1].split(",") if x]
    return out


def main(argv):
    flags = ("--skip", "--pin", "--topic", "--evergreen", "--curated", "--cuts", "--full")
    args, i = [], 0
    while i < len(argv):
        if argv[i] in flags: i += 2; continue
        if not argv[i].startswith("--"): args.append(argv[i])
        i += 1
    if len(args) < 2: sys.exit(__doc__)
    write = "--write" in argv
    skip_ids, pin_ids = set(arg_list(argv, "--skip")), arg_list(argv, "--pin")
    topic_of = dict(x.split("=", 1) for x in arg_list(argv, "--topic"))
    evergreen, curated_files = arg_list(argv, "--evergreen"), arg_list(argv, "--curated")
    ncuts = int((arg_list(argv, "--cuts") or ["4"])[0])
    nfull = int((arg_list(argv, "--full") or ["0"])[0])
    slug, date, dumps = args[0], args[1], args[2:]
    pdir = ROOT / "papers" / slug
    paper = load_yaml(pdir / "paper.yaml")
    xs = (paper.get("sources") or {}).get("x") or {}
    cfg = xs.get("slow") or {}
    count = int(cfg.get("count", 20)); min_count = int(cfg.get("min_count", 15)); max_count = int(cfg.get("max_count", 25))
    wcfg = cfg.get("words") or {}
    w_min, w_target, w_max = int(wcfg.get("min", 900)), int(wcfg.get("target", 1800)), int(wcfg.get("max", 2500))
    per_author_max = int(cfg.get("max_per_author", 2))
    min_chars = int(cfg.get("min_chars", 100)); min_chars_voice = int(cfg.get("min_chars_voice", 55))
    ed_day = datetime.datetime.fromisoformat(date + "T23:59:59+00:00")
    max_age = datetime.timedelta(days=float(cfg.get("max_age_days", 3)))
    cur_age = datetime.timedelta(days=float(cfg.get("curated_age_days", 7)))
    ever_age = datetime.timedelta(days=float(cfg.get("evergreen_age_days", 400)))
    reader = (xs.get("reader_handle") or "").lstrip("@").lower()
    lower = lambda xs_: {h.lstrip("@").lower() for h in xs_ or []}
    noise, prefer = lower(cfg.get("noise")), lower(cfg.get("prefer"))
    hooks = set()
    if cfg.get("hook_accounts") and (pdir / cfg["hook_accounts"]).exists():
        hooks = lower(json.loads((pdir / cfg["hook_accounts"]).read_text())["handles"])
    reg = {}                                    # handle -> (default section, kind)
    if cfg.get("curated_accounts") and (pdir / cfg["curated_accounts"]).exists():
        for sec, g in json.loads((pdir / cfg["curated_accounts"]).read_text()).items():
            if sec.startswith("_"): continue
            for kind in ("voices", "orgs"):
                for h in g.get(kind) or []: reg.setdefault(h.lower(), (sec, "org" if kind == "orgs" else "voice"))
    ex_cfg = dict(cfg.get("exclude") or {})
    soft_words = ex_cfg.pop("soft", [])
    soft_rx, soft_hits = word_re(soft_words), int(cfg.get("soft_hits", 2))
    excl = {k: word_re(v) for k, v in ex_cfg.items()}
    topics = {k: word_re(v) for k, v in (cfg.get("topics") or {}).items()}
    sec_cfg = [s for s in paper["sections"] if s.get("enabled", True)]
    sections = [s["id"] for s in sec_cfg]
    max_per = {s["id"]: int(s.get("max_items") or 99) for s in sec_cfg}
    min_per = {s["id"]: int(s.get("min_items") or 0) for s in sec_cfg}
    target_per = {s["id"]: int(s.get("target_items") or (s.get("min_items") or 0) + 1) for s in sec_cfg}
    hashtag = re.compile(r"(?<!\w)#\w+")

    ran = set()                                  # never repeat a post that ran in an earlier Field Notes edition
    for p in (pdir / "editions").glob("*/edition.json"):
        if p.parent.name != date:
            ran |= set(re.findall(r"/status/(\d+)", p.read_text()))

    posts, users, cands, source_of, why, rows, origin = {}, {}, {}, {}, {}, 0, {}
    for f, kind in [(d, "home") for d in dumps] + [(d, "evergreen") for d in evergreen] + [(d, "curated") for d in curated_files]:
        d = json.loads(Path(f).read_text())
        if "data" not in d and isinstance(d.get("result"), dict): d = d["result"]
        inc = d.get("includes") or {}
        for u in inc.get("users", []) + d.get("users", []): users[u["id"]] = u
        def keep_fuller(t):                                # the same post can appear cut in one dump and in full in another
            old = posts.get(t["id"])
            if old is None or len(full_text(t)) >= len(full_text(old)): posts[t["id"]] = t
        for t in inc.get("posts", []) + inc.get("tweets", []): keep_fuller(t)
        for t in d.get("data") or []:
            rows += 1
            keep_fuller(t)
            kinds = {r["type"]: r["id"] for r in t.get("referenced_tweets") or []}
            pid = kinds.get("reposted", t["id"])         # a repost stands for the original
            if pid not in cands:
                cands[pid] = {kind}
                source_of[pid] = Path(f).name
            else:
                cands[pid].add(kind)            # a post in his feed stays feed-eligible even if a curated search also hit it
            if "replied_to" in kinds and "reposted" not in kinds: why[pid] = "reply"

    def handle(t): return (users.get(t.get("author_id")) or {}).get("username", "")

    def quoted_of(t):
        q = next((r["id"] for r in t.get("referenced_tweets") or [] if r["type"] == "quoted"), None)
        return posts.get(q) if q else None

    allow_rx = re.compile("|".join(re.escape(p_) for p_ in cfg.get("allow_phrases") or []), re.I) if cfg.get("allow_phrases") else None

    def excluded(text):
        if allow_rx: text = allow_rx.sub(" ", text)
        if CASHTAG.search(text): return "money", CASHTAG.search(text).group(0)
        for k, rx in excl.items():
            m = rx and rx.search(text)
            if m: return k, m.group(1).lower()
        if soft_rx:
            hits = {re.sub(r"(?:['’]s|s)$", "", m.group(1).lower()) for m in soft_rx.finditer(text)}
            if len(hits) >= soft_hits: return "soft", "+".join(sorted(hits)[:4])
        return None

    cut_ex, scored, seen_text = {}, [], {}
    by_author = {}                                # engagement per author across the dumps: a post is judged against its author's usual
    for pid_, t_ in posts.items():
        m_ = t_.get("public_metrics") or {}
        by_author.setdefault(t_.get("author_id"), []).append(m_.get("like_count", 0) + 2 * (m_.get("repost_count", 0) or m_.get("retweet_count", 0)) + 4 * m_.get("bookmark_count", 0))
    def usual(a):
        v = sorted(by_author.get(a) or [0]); return v[len(v) // 2]
    for pid, kinds in cands.items():
        is_ever = "evergreen" in kinds
        t = posts.get(pid)
        if not t: why[pid] = "original not in dump"; continue
        h = handle(t).lower()
        dflt, who = reg.get(h, (None, None))
        text = tidy(full_text(t))
        q = quoted_of(t)
        qtext = tidy(full_text(q)) if q else ""
        bare = re.sub(r"https?://\S+|@\w+", "", text).strip()
        age = ed_day - ts(t["created_at"])
        limit = datetime.timedelta(0)
        if "home" in kinds: limit = max(limit, max_age)
        if "curated" in kinds or dflt: limit = max(limit, cur_age)
        if "evergreen" in kinds: limit = max(limit, ever_age)
        if not limit: limit = max_age
        reason = why.get(pid)
        need = (min_chars_voice if who == "voice" else (min_chars + 25 if who == "org" else min_chars))
        if reason: pass
        elif not h: reason = "author unknown"
        elif pid in skip_ids: reason = "skipped by editor"
        elif pid in ran: reason = "ran in an earlier edition"
        elif reader and h == reader: reason = "reader's own post"
        elif t.get("in_reply_to_user_id") and t.get("in_reply_to_user_id") != t.get("author_id"): reason = "reply"
        elif h in hooks: reason = "hook account (AI/markets)"
        elif q and handle(q).lower() in hooks: reason = "quotes a hook account (AI/markets)"
        elif h in noise: reason = "noise account"
        elif age > limit: reason = "too old"
        elif t.get("lang") not in (None, "en"): reason = "not English"
        elif len(bare) < need: reason = "too short"
        elif PROMO.search(text): reason = f"promo ({PROMO.search(text).group(0).lower()})"
        elif len(hashtag.findall(text)) >= 3: reason = "hashtag spam"
        elif 270 <= len(full_text(t)) <= 310 and not (t.get("note_tweet") or t.get("note_post")) and not re.search(r"[.!?…\"”’’»)\]»]\s*(https://t\.co/\w+\s*)*$", full_text(t)):
            reason = "cut off at ~300 characters (re-read with get_posts_by_ids and pass that file last in --curated)"
        elif bare.endswith(":"): reason = "incomplete (ends in a colon: the rest is a link or an image)"
        elif URL.search(full_text(t)) and dflt != "humor" and not re.search(r"[.!?…\"”’)\]]$", bare): reason = "promo (cut-off teaser)"
        elif URL.search(full_text(t)) and nwords(bare) < 12: reason = "link caption (too little text)"
        elif re.search(r"\[(?:\U0001F4F9|\U0001F39E|\U0001F3A5|\U0001F4F7)", text) and nwords(re.sub(r"\[[^\]]*\]", " ", bare)) < 12:
            reason = "media caption (video credit tag, too little text)"
        else:
            ex = excluded(text) or (excluded(f"@{handle(q)} {qtext}") if q else None)
            if ex: reason = f"{ex[0]} ({ex[1]})"
        if not reason:
            nk = norm(text)
            if nk in seen_text and seen_text[nk] != pid: reason = "duplicate text"
            else: seen_text[nk] = pid
        if reason and pid in pin_ids and reason.split(" (")[0] in {
            "cut off at ~300 characters", "link caption", "media caption", "promo", "incomplete",
            "too short", "soft"}:
            reason = None          # editor has pinned it after reading the full post
        if reason:
            why[pid] = reason
            key = reason.split(" (")[0]
            cut_ex.setdefault(key, []).append((h, pid, reason, " ".join(text.split())[:110]))
            continue
        both = text + "\n" + qtext
        hits = {k: len({m.group(1).lower() for m in rx.finditer(both)}) for k, rx in topics.items() if rx and k in sections}
        if dflt in sections: hits[dflt] = hits.get(dflt, 0) + 2
        if topic_of.get(pid): topic = topic_of[pid]
        elif dflt == "humor": topic = "humor"                      # humor comes only from the humor accounts
        else:
            best = max(hits.items(), key=lambda kv: (kv[1], -sections.index(kv[0]))) if hits else None
            topic = best[0] if best and best[1] > 0 else None
            if dflt and (not topic or hits.get(topic, 0) < hits.get(dflt, 0) + 2): topic = dflt   # default wins unless clearly elsewhere
        if topic == "humor" and dflt != "humor" and pid not in topic_of: topic = None
        if topic and not dflt and h not in prefer and pid not in topic_of and pid not in pin_ids and hits.get(topic, 0) < 2:
            topic = None                                           # outside the curated accounts a post must clearly be on topic
        m = t.get("public_metrics") or {}
        likes, bms = m.get("like_count", 0), m.get("bookmark_count", 0)
        eng = likes + 1.5 * (m.get("repost_count", 0) or m.get("retweet_count", 0)) + 4 * bms + m.get("quote_count", 0)
        fol = ((users.get(t["author_id"]) or {}).get("public_metrics") or {}).get("followers_count", 0)
        lasting = 1 + min(bms / (likes + 1), 0.6)                  # people save it to come back to
        body = 1 + min(len(bare), 900) / 600                        # substance over one-liners
        voice = 1.35 if (who == "voice" or h in prefer) else (0.7 if who == "org" else 1)
        rel = min(max((eng + 3) / (usual(t["author_id"]) + 3), 0.4), 4) ** 0.5   # this author's better-than-usual posts rise
        score = math.log1p(eng) ** 0.7 * rel / (1 + fol / 1e5) ** 0.1 * lasting * body * (1.15 if is_ever else 1) * voice \
            * (1 if topic else 0.5) + (100 if pid in pin_ids else 0)
        feed_age = ever_age if is_ever else max_age
        feed_ok = (("home" in kinds or "evergreen" in kinds) and age <= feed_age)
        scored.append((score, pid, t, topic, q, who, feed_ok))
    scored.sort(key=lambda x: -x[0])

    # ---- selection: section minimums, then best of the rest, with author / section / word limits
    def words_of(t, q): return nwords(tidy(full_text(t))) + (nwords(tidy(full_text(q))) if q and handle(q) else 0)
    pick, per_sec, per_auth, total_w = [], Counter(), Counter(), 0
    scripture = None
    if "--no-scripture" not in argv and (cfg.get("scripture", True)):
        import fn_scripture
        scripture = fn_scripture.pick(date, record=False)
        total_w += nwords(scripture["text"])

    def take(s, author_cap, force=None):
        nonlocal total_w
        score, pid, t, topic, q, who, feed_ok = s if len(s) == 7 else (*s, False)
        topic = force or topic
        if not topic or any(p[1] == pid for p in pick): return False
        if per_auth[t["author_id"]] >= author_cap or per_sec[topic] >= max_per.get(topic, 99): return False
        w = words_of(t, q)
        if total_w + w > w_max or len(pick) >= max_count: return False
        per_auth[t["author_id"]] += 1; per_sec[topic] += 1; total_w += w
        pick.append((score, pid, t, topic, q, who, feed_ok))
        return True

    if "feed" in sections:                                       # 0. From Your Feed first (his home, Lists, bookmarks, likes)
        for cap in (1, per_author_max):
            want = min_per.get("feed", 4) if cap == 1 else target_per.get("feed", 6)
            for s in scored:
                if per_sec["feed"] >= want: break
                if s[6]: take(s, cap, force="feed")
        for s in scored:
            if per_sec["feed"] >= target_per.get("feed", 6): break
            if s[6]: take(s, per_author_max, force="feed")

    rest = [sid for sid in sections if sid != "feed"]
    for sid in rest:                                             # 1. each curated section's minimum
        for s in scored:
            if per_sec[sid] >= min_per[sid]: break
            if s[3] == sid: take(s, 1)
    for sid in rest:                                             # 1b. a thin section may take a second post from one author
        for s in scored:
            if per_sec[sid] >= target_per[sid]: break
            if s[3] == sid: take(s, per_author_max)
    for sid in rest:                                             # 1c. still-thin section: more posts from a voice already in it, up to the section target
        for s in scored:
            if per_sec[sid] >= target_per[sid]: break
            if s[3] == sid: take(s, max(per_author_max, 4))
    for cap in (1, per_author_max):                             # 2. best of the rest; a second post per author only if still short
        for s in scored:
            if len(pick) >= count or total_w >= w_target: break
            if s[3] and s[3] != "feed": take(s, cap)
        if len(pick) >= min_count and total_w >= w_min: break

    def to_item(pid, t, topic, q):
        u = users[t["author_id"]]
        it = {"type": "post", "id": f"slow-{pid}", "author": u.get("name") or u["username"], "handle": u["username"],
              "text": tidy(full_text(t)), "url": f"https://x.com/{u['username']}/status/{pid}",
              "date": ts(t["created_at"]).strftime("%Y-%m-%dT%H:%M:%SZ"), "group": topic}
        if q and handle(q):
            qu = users[q["author_id"]]
            it["quoted"] = {"author": qu.get("name") or qu["username"], "handle": qu["username"],
                            "text": tidy(full_text(q)), "url": f"https://x.com/{qu['username']}/status/{q['id']}"}
        return it

    reasons = Counter(r.split(" (")[0] for r in why.values())
    print(f"{rows} rows, {len(cands)} distinct posts → {len(scored)} pass the filter "
          f"({sum(1 for s in scored if s[3])} with a section), {len(why)} cut")
    print("cut: " + ", ".join(f"{k} {v}" for k, v in reasons.most_common()))
    for key in ("hook account", "ai", "money", "politics_war", "crude", "ragebait", "soft", "promo", "incomplete", "cut off at ~300 characters", "link caption", "media caption", "quotes a hook account"):
        ex = cut_ex.get(key, [])
        if ex:
            print(f"\n  {key} ({len(ex)}), e.g.:")
            for h, pid, r, txt in ex[:ncuts]:
                print(f"    @{h:<16} {r:<28} {txt}")
    refetch = [r_[1] for r_ in cut_ex.get("cut off at ~300 characters", []) if reg.get(r_[0])]
    if refetch:
        print(f"\nREFETCH ({len(refetch)} curated posts cut at ~300 characters; get_posts_by_ids, then pass that file LAST in --curated): " + ",".join(refetch[:100]))
    print(f"\nField Notes pick: {len(pick)} posts" + (" + 1 passage" if scripture else "") + f" · {total_w} words ≈ {read_minutes(total_w)} min read "
          f"(targets: {min_count}-{max_count} posts, {w_min}-{w_max} words)")
    for sid in sections:
        rows_ = [p for p in pick if p[3] == sid]
        if not rows_ and not (sid == "faith" and scripture): continue
        print(f"\n  == {sid} ({len(rows_)}; min {min_per[sid]}, max {max_per[sid]})")
        if sid == "faith" and scripture: print(f"       passage  {scripture['work']} (KJV)")
        for score, pid, t, topic, q, who, *rest in rows_:
            txt = " ".join(tidy(full_text(t)).split())
            print(f"  {score:5.2f} @{handle(t):<16} {pid} {words_of(t, q):>3}w  {txt[:150]}"
                  + (f"\n          ⤷ quotes @{handle(q)}: {' '.join(tidy(full_text(q)).split())[:100]}" if q else ""))
    for sid in sections:
        if per_sec[sid] < min_per[sid]: print(f"\nSECTION {sid} is under its minimum ({per_sec[sid]} < {min_per[sid]}): pull more of its accounts, or --topic a post into it.")
    taken = {p[1] for p in pick}
    print("\nnext in line (swap with --skip / --pin):")
    for score, pid, t, topic, q, who, *rest in [s for s in scored if s[1] not in taken and s[3]][:16]:
        print(f"  {score:5.2f} [{topic:<7}] @{handle(t):<16} {pid}  {' '.join(tidy(full_text(t)).split())[:110]}")
    untop = [s for s in scored if not s[3]]
    print(f"\nno section ({len(untop)}; read, file with --topic ID=section if it belongs):")
    for score, pid, t, topic, q, who, *rest in untop[:10]:
        print(f"  {score:5.2f} @{handle(t):<16} {pid}  {' '.join(tidy(full_text(t)).split())[:120]}")
    if nfull:
        print(f"\nTop {nfull} survivors in full:")
        for score, pid, t, topic, q, who, *rest in scored[:nfull]:
            print(f"\n--- {score:5.2f} [{topic}] @{handle(t)} {pid} {t['created_at'][:10]} {source_of[pid]}\n{tidy(full_text(t))}"
                  + (f"\n   >> quotes @{handle(q)}: {tidy(full_text(q))}" if q else ""))
    taken = {p[1] for p in pick}
    unused_feed = [s for s in scored if s[6] and s[1] not in taken]
    if unused_feed:
        print(f"\nunused From Your Feed ({len(unused_feed)}; --pin to promote, --skip to veto):")
        for score, pid, t_, topic, q, who, *rest in unused_feed[:20]:
            print(f"  {score:5.2f} @{handle(t_):<16} {pid}  {' '.join(tidy(full_text(t_)).split())[:120]}")

    # Exactly one closer joke: a fresh humor post may win; otherwise the rotating bank (tools/fn_jokes.py).
    joke = None
    if "--no-joke" not in argv:
        import fn_jokes
        humor_handles = {h for h, v in reg.items() if v[0] == "humor"}
        # Prefer an unused humor-account post; if none, a humor-section pick may move to the closer.
        unused, used_humor = [], []
        taken_ids = {p[1] for p in pick}
        for s in scored:
            score, pid, t, topic, q, who, *rest = s
            if handle(t).lower() not in humor_handles:
                continue
            it = to_item(pid, t, "humor", q)
            (used_humor if pid in taken_ids else unused).append(it)
        joke = fn_jokes.pick(date, post_candidates=unused or used_humor, record=False)
        if joke.get("post_id") and any(p[1] == joke["post_id"] for p in pick):
            pick[:] = [p for p in pick if p[1] != joke["post_id"]]
            per_sec["humor"] = max(0, per_sec.get("humor", 0) - 1)
            # backfill humor if it dropped under its minimum
            for s in scored:
                if per_sec.get("humor", 0) >= min_per.get("humor", 0): break
                if s[3] == "humor": take(s, per_author_max)
        total_w += nwords(joke["text"])
        credit = joke.get("where") or joke.get("source") or ""
        print(f"\nCloser joke: {joke['author']}" + (f" — {credit}" if credit else ""))
        print(f"  {joke['text']}")

    if len(pick) < min_count or total_w < w_min:
        print(f"\nTHIN: {len(pick)} posts / {total_w} words (wants {min_count}+ and {w_min}+): pull more pages of the curated accounts before writing.")
    if write:
        if not pick: sys.exit("nothing to write")
        ep = pdir / "editions" / date / "edition.json"
        ep.parent.mkdir(parents=True, exist_ok=True)
        ed = json.loads(ep.read_text()) if ep.exists() else {"schema": 1, "paper": slug, "date": date}
        secs = []
        for sid in sections:
            items = [to_item(pid, t, topic, q) for _, pid, t, topic, q, *_ in pick if topic == sid]
            if sid == "faith" and scripture:
                import fn_scripture
                items.insert(0, fn_scripture.item(fn_scripture.pick(date, record=True)))
            if items: secs.append({"id": sid, "items": items})
        ed["sections"] = secs
        days = sorted(ts(t["created_at"]) for _, _, t, *_ in pick)
        voices = len({handle(t).lower() for _, _, t, *_ in pick})
        if joke:
            import fn_jokes
            # record the bank joke as seen only on --write (a post closer is not a bank id)
            if joke.get("id", "").startswith("joke-") and not joke.get("post_id"):
                fn_jokes.pick(date, record=True)
            ed["joke"] = joke
        elif "joke" in ed:
            ed.pop("joke", None)
        extra = (" and one passage of Scripture" if scripture else "") + (" and one credited joke" if joke else "")
        ed["coverage"] = (f"{len(pick)} posts from {voices} voices" + extra +
                          f", {days[0]:%B} {days[0].day} to {days[-1]:%B} {days[-1].day}, 2026. About {read_minutes(total_w)} minutes.")
        ed["words"] = total_w
        ed["description"] = (f"A calm {read_minutes(total_w)}-minute read: " + ", ".join(s["title"] for s in sec_cfg if s["id"] in {x["id"] for x in secs}) +
                             (". Ends with a real, credited joke." if joke else "."))
        ep.write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n")
        print(f"\nwrote {sum(len(s['items']) for s in secs)} items in {len(secs)} sections" +
              (" + closer joke" if joke else "") + f" to {ep.relative_to(ROOT)}")


def read_minutes(words, wpm=230):
    return max(1, round(words / wpm))


if __name__ == "__main__":
    main(sys.argv[1:])
