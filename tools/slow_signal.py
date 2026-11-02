#!/usr/bin/env python3
"""Slow Signal: pick a few calm, lasting X posts that are NOT about AI and NOT about investing.

    .venv/bin/python tools/slow_signal.py slow-signal 2026-11-01 /tmp/feed/p*.json                 # dry run: show the pick
    .venv/bin/python tools/slow_signal.py slow-signal 2026-11-01 /tmp/feed/p*.json --write         # write edition.json
    ... --evergreen /tmp/x/bookmarks.json,/tmp/x/likes.json   extra dumps whose posts may be older (bookmarks, likes)
    ... --skip ID,ID           veto posts after reading them (AI/finance in disguise, politics, not lasting, …)
    ... --pin ID,ID            make sure these candidates are in (still one per author, still filtered)
    ... --topic ID=books,...   file a post under a topic section (needed for posts with no topic word)
    ... --cuts 40              print this many cut examples per reason (default 4)
    ... --full 60              print the top 60 survivors in full (with quoted text) so the worker can read them

Input: raw replies of the read-only user-X MCP tools, saved OUTSIDE the repo, one file per page:
get_users_timeline (home timeline), get_list_posts (his Lists), get_users_bookmarks / get_users_liked_posts.
Ask for post.fields=created_at,public_metrics,author_id,lang,referenced_tweets,note_tweet,in_reply_to_user_id and
expansions=author_id,referenced_tweets.id,referenced_tweets.id.author_id so reposted and quoted posts come with text.

The filter (paper.yaml sources.x.slow), applied to the post AND to any post it quotes:
  - hook accounts (sources/hook_accounts.json: accounts that mostly post AI, markets, crypto or Tesla) and noise accounts
  - exclude word lists: ai, money, politics_war, ragebait (whole words; `x*` = any ending), plus any $CASHTAG
  - replies, the reader's own posts, non-English, too short, too old
Survivors are sorted into topic sections by topic words; posts with none need --topic after the worker reads them.
Ranking favors posts people save (bookmarks) and longer, substantive text over raw likes. One post per author.

Nothing is invented or shortened: the full post text (long-post note_tweet text) and the full quoted text go into
edition.json exactly as posted; only trailing t.co attachment links and HTML entities (&amp;) are tidied. The item
keeps its real x.com URL for the record, but Slow Signal's templates never link it. Read-only: this only reads files.
"""
import datetime, html, json, math, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASHTAG = re.compile(r"(?<![\w$])\$[A-Za-z][A-Za-z.]{0,5}\b")


def load_yaml(p):
    import yaml
    return yaml.safe_load(Path(p).read_text())


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def word_re(words):
    pats = []
    for w in words:
        w = str(w).lower()
        if w.endswith("*"): p = re.escape(w[:-1]) + r"[\w'’-]*"
        else: p = re.escape(w) + r"(?:s|es|'s|’s)?"
        # word boundaries only where the word starts/ends with a word character
        pats.append((r"(?<![\w])" if re.match(r"\w", w) else "") + p + (r"(?![\w])" if re.search(r"\w\*?$", w) else ""))
    return re.compile("(" + "|".join(pats) + ")", re.I) if pats else None


def full_text(t):
    return (t.get("note_tweet") or {}).get("text") or t.get("text", "")


def tidy(text):
    """Exact post text; only HTML entities are decoded and trailing t.co attachment links dropped (they are not words)."""
    text = html.unescape(text)
    text = re.sub(r"(\s*https://t\.co/\w+)+\s*$", "", text)
    return text.strip()


def arg_list(argv, flag):
    out = []
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv): out += [x for x in argv[i + 1].split(",") if x]
    return out


def main(argv):
    flags = ("--skip", "--pin", "--topic", "--evergreen", "--cuts", "--full")
    args, i = [], 0
    while i < len(argv):
        if argv[i] in flags: i += 2; continue
        if not argv[i].startswith("--"): args.append(argv[i])
        i += 1
    if len(args) < 3: sys.exit(__doc__)
    write = "--write" in argv
    skip_ids, pin_ids = set(arg_list(argv, "--skip")), arg_list(argv, "--pin")
    topic_of = dict(x.split("=", 1) for x in arg_list(argv, "--topic"))
    evergreen = arg_list(argv, "--evergreen")
    ncuts = int((arg_list(argv, "--cuts") or ["4"])[0])
    nfull = int((arg_list(argv, "--full") or ["0"])[0])
    slug, date, dumps = args[0], args[1], args[2:]
    pdir = ROOT / "papers" / slug
    paper = load_yaml(pdir / "paper.yaml")
    xs = (paper.get("sources") or {}).get("x") or {}
    cfg = xs.get("slow") or {}
    count = int(cfg.get("count", 8)); min_count = int(cfg.get("min_count", 6))
    count = min(count, int(paper.get("total_max") or count))
    min_chars = int(cfg.get("min_chars", 100))
    ed_day = datetime.datetime.fromisoformat(date + "T23:59:59+00:00")
    max_age = datetime.timedelta(days=float(cfg.get("max_age_days", 3)))
    ever_age = datetime.timedelta(days=float(cfg.get("evergreen_age_days", 400)))
    reader = (xs.get("reader_handle") or "").lstrip("@").lower()
    noise = {h.lstrip("@").lower() for h in cfg.get("noise") or []}
    prefer = {h.lstrip("@").lower() for h in cfg.get("prefer") or []}
    hooks = set()
    if cfg.get("hook_accounts") and (pdir / cfg["hook_accounts"]).exists():
        hooks = {h.lstrip("@").lower() for h in json.loads((pdir / cfg["hook_accounts"]).read_text())["handles"]}
    excl = {k: word_re(v) for k, v in (cfg.get("exclude") or {}).items()}
    topics = {k: word_re(v) for k, v in (cfg.get("topics") or {}).items()}
    sections = [s["id"] for s in paper["sections"] if s.get("enabled", True)]
    max_per = {s["id"]: int(s.get("max_items") or 99) for s in paper["sections"]}

    # never repeat a post that ran in an earlier Slow Signal edition
    ran = set()
    for p in (pdir / "editions").glob("*/edition.json"):
        if p.parent.name != date:
            ran |= set(re.findall(r"/status/(\d+)", p.read_text()))

    posts, users, cands, source_of, why, rows = {}, {}, {}, {}, {}, 0
    for f in dumps + evergreen:
        d = json.loads(Path(f).read_text())
        if "data" not in d and isinstance(d.get("result"), dict): d = d["result"]
        inc = d.get("includes") or {}
        for u in inc.get("users", []) + d.get("users", []): users[u["id"]] = u
        for t in inc.get("posts", []) + inc.get("tweets", []): posts.setdefault(t["id"], t)
        for t in d.get("data") or []:
            rows += 1
            posts[t["id"]] = t
            kinds = {r["type"]: r["id"] for r in t.get("referenced_tweets") or []}
            pid = kinds.get("reposted", t["id"])         # a repost stands for the original
            if pid not in cands:
                cands[pid] = f in evergreen
                source_of[pid] = Path(f).name
            if "replied_to" in kinds and "reposted" not in kinds: why[pid] = "reply"

    def handle(t): return (users.get(t.get("author_id")) or {}).get("username", "")

    def quoted_of(t):
        q = next((r["id"] for r in t.get("referenced_tweets") or [] if r["type"] == "quoted"), None)
        return posts.get(q) if q else None

    def excluded(text):
        if CASHTAG.search(text): return "money", CASHTAG.search(text).group(0)
        for k, rx in excl.items():
            m = rx and rx.search(text)
            if m: return k, m.group(1).lower()
        return None

    cut_ex = {}
    scored = []
    for pid, is_ever in cands.items():
        t = posts.get(pid)
        if not t: why[pid] = "original not in dump"; continue
        h = handle(t).lower()
        text = tidy(full_text(t))
        q = quoted_of(t)
        qtext = tidy(full_text(q)) if q else ""
        bare = re.sub(r"https?://\S+|@\w+", "", text).strip()
        age = ed_day - ts(t["created_at"])
        reason = why.get(pid)
        if reason: pass
        elif not h: reason = "author unknown"
        elif pid in skip_ids: reason = "skipped by editor"
        elif pid in ran: reason = "ran in an earlier edition"
        elif reader and h == reader: reason = "reader's own post"
        elif t.get("in_reply_to_user_id") and t.get("in_reply_to_user_id") != t.get("author_id"): reason = "reply"
        elif h in hooks: reason = "hook account (AI/markets)"
        elif q and handle(q).lower() in hooks: reason = "quotes a hook account (AI/markets)"
        elif h in noise: reason = "noise account"
        elif age > (ever_age if is_ever else max_age): reason = "too old"
        elif t.get("lang") not in (None, "en"): reason = "not English"
        elif len(bare) < min_chars: reason = "too short"
        else:
            ex = excluded(text) or (excluded(f"@{handle(q)} {qtext}") if q else None)
            if ex: reason = f"{ex[0]} ({ex[1]})"
        if reason:
            why[pid] = reason
            key = reason.split(" (")[0]
            cut_ex.setdefault(key, []).append((h, pid, reason, " ".join(text.split())[:110]))
            continue
        both = text + "\n" + qtext
        topic = topic_of.get(pid) or next((k for k in sections if topics.get(k) and topics[k].search(both)), None)
        m = t.get("public_metrics") or {}
        likes, bms = m.get("like_count", 0), m.get("bookmark_count", 0)
        eng = likes + 1.5 * m.get("repost_count", 0) + 4 * bms + m.get("quote_count", 0)
        fol = ((users.get(t["author_id"]) or {}).get("public_metrics") or {}).get("followers_count", 0)
        lasting = 1 + min(bms / (likes + 1), 0.6)                  # people save it to come back to
        body = 1 + min(len(bare), 900) / 900                        # substance over one-liners
        score = math.log1p(eng) / (1 + fol / 1e5) ** 0.15 * lasting * body * (1.15 if is_ever else 1) * (1.5 if h in prefer else 1) \
            * (1 if topic else 0.6) + (100 if pid in pin_ids else 0)
        scored.append((score, pid, t, topic, q))
    scored.sort(key=lambda x: -x[0])

    pick, authors, per_sec, untopical = [], set(), Counter(), []
    for s in scored:
        score, pid, t, topic, q = s
        if t["author_id"] in authors: continue
        if not topic: untopical.append(s); continue
        if per_sec[topic] >= max_per.get(topic, 99): continue
        authors.add(t["author_id"]); per_sec[topic] += 1; pick.append(s)
        if len(pick) >= count: break

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
          f"({sum(1 for s in scored if s[3])} with a topic word), {len(why)} cut")
    print("cut: " + ", ".join(f"{k} {v}" for k, v in reasons.most_common()))
    for key in ("hook account", "ai", "money", "politics_war", "ragebait", "quotes a hook account"):
        ex = cut_ex.get(key, [])
        if ex:
            print(f"\n  {key} ({len(ex)}), e.g.:")
            for h, pid, r, txt in ex[:ncuts]:
                print(f"    @{h:<16} {r:<28} {txt}")
    print(f"\nSlow Signal pick ({len(pick)} of {count}; one per author):")
    for score, pid, t, topic, q in pick:
        txt = " ".join(tidy(full_text(t)).split())
        print(f"  {score:5.2f} [{topic:<7}] @{handle(t):<16} {pid} {source_of[pid]}\n          {txt[:170]}"
              + (f"\n          ⤷ quotes @{handle(q)}: {' '.join(tidy(full_text(q)).split())[:100]}" if q else ""))
    taken = {p[1] for p in pick}
    print("\nnext in line (swap with --skip / --pin):")
    for score, pid, t, topic, q in [s for s in scored if s[1] not in taken and s[3]][:14]:
        print(f"  {score:5.2f} [{topic:<7}] @{handle(t):<16} {pid}  {' '.join(tidy(full_text(t)).split())[:110]}")
    print("\nno topic word (read; file with --topic ID=section if it belongs):")
    for score, pid, t, topic, q in untopical[:14]:
        print(f"  {score:5.2f} @{handle(t):<16} {pid}  {' '.join(tidy(full_text(t)).split())[:120]}")
    if nfull:
        print(f"\nTop {nfull} survivors in full:")
        for score, pid, t, topic, q in scored[:nfull]:
            print(f"\n--- {score:5.2f} [{topic}] @{handle(t)} {pid} {t['created_at'][:10]} {source_of[pid]}\n{tidy(full_text(t))}"
                  + (f"\n   >> quotes @{handle(q)}: {tidy(full_text(q))}" if q else ""))
    if len(pick) < min_count:
        print(f"\nONLY {len(pick)} posts (< {min_count}): pull more (Lists, bookmarks, likes) before writing.")
    if write:
        if not pick: sys.exit("nothing to write")
        ep = pdir / "editions" / date / "edition.json"
        ep.parent.mkdir(parents=True, exist_ok=True)
        ed = json.loads(ep.read_text()) if ep.exists() else {"schema": 1, "paper": slug, "date": date}
        secs = []
        for sid in sections:
            items = [to_item(pid, t, topic, q) for _, pid, t, topic, q in pick if topic == sid]
            if items: secs.append({"id": sid, "items": items})
        ed["sections"] = secs
        ep.write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n")
        print(f"\nwrote {sum(len(s['items']) for s in secs)} posts in {len(secs)} topic sections to {ep.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
