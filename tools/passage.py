#!/usr/bin/env python3
"""Pick today's Passage (one quote, poem, scripture or short speech excerpt) and write it into the edition.

    .venv/bin/python tools/passage.py signal-seeker 2026-11-01          # pick + record as seen
    .venv/bin/python tools/passage.py signal-seeker 2026-11-01 --dry    # show the pick, write nothing

Pools (papers/<slug>/):
  passages.json    verified items: text exactly as on source_url (fetched), author, work, kind, category
                   (bible | ancient | writer | ferriss-5bf | founder). Committed.
  quote_bank.json  Chris's old quote bank, extracted read-only from his Google Docs. LOCAL ONLY (gitignored):
                   it holds doc titles/ids. Only text + author ever reach the edition, marked
                   "From your old quote bank". Missing file = no throwbacks; the rotation falls back to writers.
  passages_seen.json  id -> first edition date. Nothing repeats.
  taste.json       {"keep": [...], "never": [...]} from the "Keep / Never again: today's passage" chips.
                   Never ids are skipped; authors with a never are picked a third as often; kept authors 3x.

Weekly rotation (weekday of the edition):
  Sun, Thu = Bible (about 2 a week)           Tue, Sat = old quote bank (+ Mon on even ISO weeks: 2-3 a week)
  Wed      = another ancient text on odd ISO weeks (rare), otherwise a writer
  Fri      = Tim Ferriss 5-Bullet Friday pick  Mon (odd weeks) = writer (writers, founders, Ferriss)
An empty pool falls through to writers, then anything unseen.
"""
import datetime, json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRITERS = ("writer", "founder", "ferriss-5bf")


def want(date):
    d = datetime.date.fromisoformat(date)
    wd, wk = d.weekday(), d.isocalendar()[1]
    if wd in (6, 3): return ["bible"]
    if wd in (1, 5) or (wd == 0 and wk % 2 == 0): return ["bank"]
    if wd == 2 and wk % 2 == 1: return ["ancient"]
    if wd == 4: return ["ferriss-5bf"]
    return list(WRITERS)


def load(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def pool(pdir):
    items = [dict(it) for it in load(pdir / "passages.json", []) if it.get("verified")]
    for q in load(pdir / "quote_bank.json", []):
        if q.get("use", True) and q.get("text") and q.get("author"):
            items.append({"id": q["id"], "text": q["text"], "author": q.get("author_display") or q["author"],
                          "kind": "quote", "category": "bank"})
    return items


def pick(slug, date, record=True):
    pdir = ROOT / "papers" / slug
    seen = load(pdir / "passages_seen.json", {})
    taste = load(pdir / "taste.json", {"keep": [], "never": []})
    never_ids = {t["id"] for t in taste.get("never", [])}
    never_auth = {t.get("author") for t in taste.get("never", [])}
    keep_auth = {t.get("author") for t in taste.get("keep", [])}
    items = pool(pdir)
    again = [it for it in items if seen.get(it["id"]) == date]           # rebuilding the same day: same pick
    if again: return again[0], seen
    fresh = [it for it in items if it["id"] not in seen and it["id"] not in never_ids]
    rng = random.Random(f"{slug}-{date}-passage")
    for cats in (want(date), list(WRITERS), None):
        c = [it for it in fresh if cats is None or it["category"] in cats]
        if c: break
    else:
        sys.exit("passage: every item has run; add more to passages.json")
    w = [3.0 if it["author"] in keep_auth else (1 / 3 if it["author"] in never_auth else 1.0) for it in c]
    it = rng.choices(c, weights=w)[0]
    if record:
        seen[it["id"]] = date
        (pdir / "passages_seen.json").write_text(json.dumps(seen, indent=1) + "\n")
    return it, seen


def edition_item(it):
    out = {"type": "passage", "id": it["id"], "text": it["text"], "author": it["author"], "kind": it["kind"]}
    if it["category"] == "bank":
        out["label"] = "From your old quote bank"
    else:
        out.update(work=it.get("work") or "", source_url=it["source_url"],
                   sources=[{"name": it["source_url"].split("/")[2].removeprefix("www."), "url": it["source_url"]}])
        if it.get("translation"): out["translation"] = it["translation"]
        out["label"] = {"bible": "Scripture", "ancient": "From the ancients"}.get(it["category"], "")
    return out


def main(slug, date, dry=False):
    it, _ = pick(slug, date, record=not dry)
    item = edition_item(it)
    print(f"passage {date} ({'/'.join(want(date))}): {item['author']}{' · ' + item.get('work', '') if item.get('work') else ''} [{it['id']}]")
    if dry: return
    ep = ROOT / "papers" / slug / "editions" / date / "edition.json"
    ed = json.loads(ep.read_text())
    ed["sections"] = [s for s in ed["sections"] if s["id"] != "passage"] + [{"id": "passage", "items": [item]}]
    ep.write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) < 2: sys.exit(__doc__)
    main(a[0], a[1], "--dry" in sys.argv)
