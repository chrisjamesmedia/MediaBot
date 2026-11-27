#!/usr/bin/env python3
"""Field Notes scripture: a pool of verified KJV passages and a daily pick.

    .venv/bin/python tools/fn_scripture.py --build            # (re)build papers/field-notes/scripture.json
    .venv/bin/python tools/fn_scripture.py 2026-11-26          # today's pick (dry; prints it)
    from tools.fn_scripture import pick                         # slow_signal.py --write calls pick(date, record=True)

Every passage is the King James text (public domain), fetched from bible-api.com at build time and stored
exactly as returned (whitespace tidied, nothing else). The 13 passages already verified for Signal Seeker are reused
as they are. Nothing is paraphrased or invented; a passage that fails to fetch is skipped, never guessed.
The pick rotates oldest-seen first, so nothing repeats until the whole pool has run (papers/field-notes/scripture_seen.json).
"""
import json, re, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "papers" / "field-notes"
SS = ROOT / "papers" / "signal-seeker"

# Short passages (about 15-90 words) chosen for calm reading: gratitude, creation, rest, wisdom, friendship, work, hope.
REFS = [
    "Psalm 100", "Psalm 23", "Psalm 121", "Psalm 46:10-11", "Psalm 8:3-9", "Psalm 1:1-3", "Psalm 139:13-16",
    "Psalm 104:10-18", "Psalm 127:1-2", "Psalm 133:1-3", "Proverbs 3:5-8", "Proverbs 15:1-4", "Proverbs 17:17",
    "Proverbs 27:17", "Proverbs 16:3", "Ecclesiastes 3:1-8", "Ecclesiastes 4:9-12", "Isaiah 55:8-12",
    "Isaiah 26:3-4", "Jeremiah 29:11-13", "Matthew 11:28-30", "Matthew 5:3-9", "Matthew 6:33-34",
    "John 1:1-5", "John 15:12-15", "Romans 12:9-12", "1 Corinthians 13:4-8", "Galatians 5:22-23",
    "Colossians 3:12-15", "1 Thessalonians 5:16-18", "Hebrews 11:1-3", "Hebrews 13:1-2", "James 1:5",
    "1 Peter 4:8-10", "Genesis 1:26-31", "Genesis 2:15", "Deuteronomy 8:7-10", "Habakkuk 3:17-18",
    "Ruth 1:16-17", "Job 38:4-7",
]


def tidy(t):
    return re.sub(r"\s+", " ", t).strip()


def fetch(ref):
    url = "https://bible-api.com/" + urllib.parse.quote(ref) + "?translation=kjv"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MediaBot/1.0"}), timeout=30) as r:
        d = json.load(r)
    text = tidy(" ".join(v["text"] for v in d["verses"]))
    if not text or d.get("translation_id") != "kjv": raise ValueError("not KJV / empty")
    shown = d["reference"].replace("-", "\u2013")
    return {"id": "bible-" + re.sub(r"\W+", "-", ref.lower()).strip("-"), "text": text, "author": "The Bible", "work": shown,
            "ref": shown, "translation": "KJV", "kind": "scripture", "category": "bible", "verified": True, "public_domain": True,
            "source_url": "https://www.biblegateway.com/passage/?search=" + urllib.parse.quote_plus(ref) + "&version=KJV"}


def build():
    pool = {p["id"]: p for p in json.loads((SS / "passages.json").read_text()) if p.get("category") == "bible" and p.get("verified")}
    for ref in REFS:
        try:
            p = fetch(ref)
        except Exception as e:
            print(f"  skip {ref}: {e}"); continue
        if p["id"] not in pool: pool[p["id"]] = p
    words = [len(p["text"].split()) for p in pool.values()]
    (FN / "scripture.json").write_text(json.dumps(list(pool.values()), indent=1, ensure_ascii=False) + "\n")
    print(f"scripture.json: {len(pool)} passages, {min(words)}-{max(words)} words")


def pick(date, record=True, min_words=25, max_words=150):
    pool = [p for p in json.loads((FN / "scripture.json").read_text()) if p.get("verified") and min_words <= len(p["text"].split()) <= max_words]
    sp = FN / "scripture_seen.json"
    seen = json.loads(sp.read_text()) if sp.exists() else {}
    again = [p for p in pool if seen.get(p["id"]) == date]
    if again: return again[0]
    # oldest-seen first (never seen = oldest); a stable hash of the date breaks ties so the order is not alphabetical
    import hashlib
    key = lambda p: (seen.get(p["id"], ""), hashlib.sha1((date + p["id"]).encode()).hexdigest())
    p = sorted(pool, key=key)[0]
    if record:
        seen[p["id"]] = date
        sp.write_text(json.dumps(seen, indent=1) + "\n")
    return p


def item(p):
    return {"type": "passage", "id": "fn-" + p["id"], "text": p["text"], "author": p["author"], "work": p["work"],
            "translation": p.get("translation", "KJV"), "kind": "scripture", "group": "faith"}


if __name__ == "__main__":
    if "--build" in sys.argv: build()
    elif len(sys.argv) > 1:
        p = pick(sys.argv[1], record=False); print(p["work"], "\n", p["text"])
    else: sys.exit(__doc__)
