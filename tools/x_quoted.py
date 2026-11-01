#!/usr/bin/env python3
"""Add quoted-post data to X post items in an edition.json, from raw X API v2 replies.

    .venv/bin/python tools/x_quoted.py papers/signal-seeker/editions/2026-11-01/edition.json /path/to/x-dump-*.json

The daily routine should request quoted posts with every X read:
    expansions=author_id,referenced_tweets.id,referenced_tweets.id.author_id
    tweet.fields=created_at,note_tweet,referenced_tweets   user.fields=name,username
Then the reply's includes.tweets (or includes.posts) carries each quoted post and includes.users its author.
Nothing is invented: a post gets `quoted` only when the quoted post itself is in a dump.
Raw dumps stay outside this repo.
"""
import json, sys
from pathlib import Path


def load(p):
    try:
        d = json.loads(Path(p).read_text())
    except Exception:
        return None
    if isinstance(d, dict) and "data" not in d and isinstance(d.get("result"), dict):
        d = d["result"]
    return d if isinstance(d, dict) else None


def main(edition, dumps):
    posts, users, refs = {}, {}, {}
    for f in dumps:
        d = load(f)
        if not d: continue
        inc = d.get("includes") or {}
        for u in inc.get("users", []): users[u["id"]] = u
        data = d.get("data") or []
        for t in (data if isinstance(data, list) else [data]) + inc.get("tweets", []) + inc.get("posts", []):
            posts.setdefault(t["id"], t)
            for r in t.get("referenced_tweets") or []:
                if r.get("type") == "quoted": refs[t["id"]] = r["id"]
    ep = Path(edition); ed = json.loads(ep.read_text()); n = 0
    for sec in ed["sections"]:
        for it in sec["items"]:
            if it.get("type") != "post" or it.get("quoted"): continue
            sid = it.get("url", "").rstrip("/").rsplit("/", 1)[-1]
            q = posts.get(refs.get(sid, ""))
            if not q: continue
            u = users.get(q.get("author_id"), {})
            if not u.get("username"): continue
            text = (q.get("note_tweet") or {}).get("text") or q.get("text", "")
            it["quoted"] = {"author": u.get("name") or u["username"], "handle": u["username"], "text": text,
                            "url": f"https://x.com/{u['username']}/status/{q['id']}"}
            n += 1
    ep.write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n")
    print(f"quoted posts added: {n}")


if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
