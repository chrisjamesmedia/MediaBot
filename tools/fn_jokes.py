#!/usr/bin/env python3
"""Field Notes closer: exactly one real, credited joke.

    A fresh real post from the day's humor voices may win (exact text, named author).
    Otherwise the next unseen joke from papers/field-notes/jokes.json is used
    (oldest-seen first; jokes_seen.json records the date). Every bank joke was
    copied exactly from its source_url; tools/jokes_check.py field-notes re-checks them.
    Nothing is invented or rewritten.
"""
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "papers" / "field-notes"


def nwords(s):
    return len(re.findall(r"\b[\w'’-]+\b", s or ""))


def post_is_joke(it):
    """A short, complete, credited post that can close the paper (never a teaser)."""
    text = (it.get("text") or "").strip()
    if not text or not it.get("author"):
        return False
    w = nwords(text)
    if w < 8 or w > 80:
        return False
    bare = re.sub(r"https?://\S+", "", text).strip()
    if bare.endswith(":") or bare.endswith("…") or bare.endswith("..."):
        return False
    if not re.search(r"[.!?…”'»)\]]$", bare):
        return False
    return True


def from_post(it):
    handle = it.get("handle") or ""
    return {
        "type": "joke", "id": "joke-post-" + re.sub(r"^slow-", "", it.get("id") or it.get("post_id") or ""),
        "text": it["text"].strip(), "author": it["author"], "handle": handle,
        "where": "on X" + (f", @{handle}" if handle else ""),
        "source": "a post by " + (f"@{handle}" if handle else it["author"]),
        "post_id": re.sub(r"^slow-", "", it.get("id") or ""),
    }


def from_bank(j):
    return {
        "type": "joke", "id": "joke-" + j["id"], "text": j["text"], "author": j["author"],
        "where": j.get("where") or "", "source_url": j.get("source_url") or "",
        "source": ((j.get("where") + ", " if j.get("where") else "") + j["author"]).strip(", "),
    }


def pick(date, post_candidates=None, record=False):
    """Prefer a fresh real humor post; otherwise rotate the bank (stable for a given date)."""
    for it in post_candidates or []:
        if post_is_joke(it):
            return from_post(it)
    pool = json.loads((FN / "jokes.json").read_text())["jokes"]
    sp = FN / "jokes_seen.json"
    seen = json.loads(sp.read_text()) if sp.exists() else {}
    again = [j for j in pool if seen.get(j["id"]) == date]
    if again:
        return from_bank(again[0])
    key = lambda j: (seen.get(j["id"], ""), hashlib.sha1((date + j["id"]).encode()).hexdigest())
    j = sorted(pool, key=key)[0]
    if record:
        seen[j["id"]] = date
        sp.write_text(json.dumps(seen, indent=1) + "\n")
    return from_bank(j)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        j = pick(sys.argv[1], record=False)
        print(j["author"], "—", j.get("where") or j.get("source"))
        print(j["text"])
    else:
        sys.exit(__doc__)
