#!/usr/bin/env python3
"""Print the read-only X search queries that pull Field Notes' curated accounts (papers/field-notes/sources/curated_accounts.json).

    .venv/bin/python tools/fn_queries.py [--json]        # one query per line (or a JSON list of {section, query})

Each query is `(from:a OR from:b ...) -is:reply -is:retweet lang:en`, under X's 1,024-character limit, one or two per section.
Run each with search_posts_all (start_time = the edition date minus 7 days; page 1-3 with next_token; sort_order recency
and also relevancy), post.fields created_at,public_metrics,author_id,lang,referenced_tweets,note_post,in_reply_to_user_id,
conversation_id, expansions author_id,referenced_posts,referenced_posts.author_id, and save each raw page OUTSIDE the repo
(/tmp/slow/curated_<section>_<n>.json). slow_signal.py reads them with --curated.
"""
import json, sys
from pathlib import Path

REG = Path(__file__).resolve().parent.parent / "papers" / "field-notes" / "sources" / "curated_accounts.json"
SUFFIX = " -is:reply -is:retweet lang:en"


def queries():
    reg = json.loads(REG.read_text())
    out = []
    for sec, g in reg.items():
        if sec.startswith("_"): continue
        for kind in ("voices", "orgs"):         # voices and orgs are searched apart so an org's volume cannot crowd a voice out
            hs, cur = g.get(kind) or [], []
            for h in hs + [None]:
                q = "(" + " OR ".join("from:" + x for x in cur + ([h] if h else [])) + ")" + SUFFIX
                if h is None or len(q) > 1000:
                    if cur: out.append({"section": sec, "kind": kind, "query": "(" + " OR ".join("from:" + x for x in cur) + ")" + SUFFIX})
                    cur = [h] if h else []
                else: cur.append(h)
    return out


if __name__ == "__main__":
    qs = queries()
    if "--json" in sys.argv: print(json.dumps(qs, indent=1))
    else:
        for q in qs: print(f"{q['section']}\t{q['kind']}\t{q['query']}")
