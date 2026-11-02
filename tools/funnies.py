#!/usr/bin/env python3
"""Fill an edition's Funnies section: real comic strips, two verified one-liners, 1-2 funny posts from the
reader's X feed, plus a generated sudoku and word search.

    .venv/bin/python tools/funnies.py signal-seeker 2026-11-01                       # everything
    .venv/bin/python tools/funnies.py signal-seeker 2026-11-01 --no-comic            # offline: no comic feeds
    ... --posts 2116...,2116...   the funny posts to run, by id, from edition.json "funny_candidates" (x_feed.py);
                                  "--posts none" runs none. Without it the top 2 candidates run.
    ... --skip <id,id>            veto anything by id: a comic's link, a joke id, a post id. The next in line moves up.

Nothing funny is written here. Comics come from the artists' own feeds (image downloaded at build time, title,
creator and link kept); jokes come from papers/<slug>/jokes.json, where every line is copied exactly from a fetched
source page (tools/jokes_check.py re-checks them); posts are real posts with real handles, exact text and x.com links.
Seen lists (comics_seen.json, jokes_seen.json, id -> date) stop repeats; the same date always gives the same picks.
Puzzles are generated and checked: the sudoku has exactly one solution; every word-search word is placed in the
grid, and every word comes from a headline or title that survives the edition's cuts. Both are seeded by the date.
"""
import datetime, html, json, random, re, sys, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Comic feeds. xkcd runs every time; two of ROTATE run each edition, turning by date. Each one was checked to carry
# the comic image in its feed. Licenses, as each site states them (we reprint for a personal, non-commercial paper,
# always with title, creator and a link back):
FEEDS = [
    # CC BY-NC 2.5 (https://xkcd.com/license.html)
    {"name": "xkcd", "byline": "Randall Munroe", "rss": "https://xkcd.com/rss.xml"},
]
ROTATE = [
    # © Reza Farazmand; the site has offered strips under CC BY-NC 3.0
    {"name": "Poorly Drawn Lines", "byline": "Reza Farazmand", "rss": "https://feeds.feedburner.com/PoorlyDrawnLines"},
    # © Ryan North; qwantz.com: "comics are meant for sharing ... You don't need permission"
    {"name": "Dinosaur Comics", "byline": "Ryan North", "rss": "https://www.qwantz.com/rssfeed.php"},
    # © David Malki !; wondermark.com: "Permission to hotlink and embed is granted, if you link back"
    {"name": "Wondermark", "byline": "David Malki !", "rss": "https://wondermark.com/feed/"},
    # © Nicholas Gurewitch; no stated license: personal non-commercial reprint with credit and link
    {"name": "The Perry Bible Fellowship", "byline": "Nicholas Gurewitch", "rss": "https://pbfcomics.com/feed/"},
    # © Li Chen; no stated license: personal non-commercial reprint with credit and link
    {"name": "Extra Ordinary", "byline": "Li Chen", "rss": "https://www.exocomics.com/feed/"},
]
# Tried and left out: SMBC (very tall strips that shrink to nothing in print, often adult), The Oatmeal (feed has
# thumbnails only), poorlydrawnlines.com/feed (bot wall; feedburner works), Savage Chickens, Buttersafe, Lunarbaboon,
# Incidental Comics, MonkeyUser (feeds dead or no image).
UA = {"User-Agent": "MediaBot/1 (personal newspaper; links back to every comic)"}
GRIM = re.compile(r"STAB|KILL|DEAD|DEATH|SHOOT|MURDER|WAR|BOMB|ATTACK|CRASH|VICTIM|ABUSE|RAPE|TERROR")
GRIM_WORDS = re.compile(r"\b(stab\w*|kill\w*|dead|death\w*|die[sd]?|dying|shoot\w*|shot|murder\w*|war|wars|bomb\w*|attack\w*|"
                        r"crash\w*|victim\w*|abuse\w*|rape\w*|terror\w*|suicide\w*|corpse\w*|funeral\w*|cancer)\b", re.I)
FALLBACK_WORDS = "COMPUTE SIGNAL QUIET LEDGER CANDLE HARBOR AUTUMN ORCHARD BRIDGE COMPASS LANTERN MEADOW".split()


# ---------- sudoku ----------
def _solve(g, limit=2):
    """Count solutions of a 81-cell grid (0 = empty), stopping at `limit`."""
    try:
        i = g.index(0)
    except ValueError:
        return 1
    r, c = divmod(i, 9)
    used = {g[r * 9 + k] for k in range(9)} | {g[k * 9 + c] for k in range(9)} | \
           {g[(r // 3 * 3 + a) * 9 + c // 3 * 3 + b] for a in range(3) for b in range(3)}
    n = 0
    for v in range(1, 10):
        if v not in used:
            g[i] = v
            n += _solve(g, limit - n)
            g[i] = 0
            if n >= limit: break
    return n


def _fill(g, rng):
    try:
        i = g.index(0)
    except ValueError:
        return True
    r, c = divmod(i, 9)
    vals = list(range(1, 10)); rng.shuffle(vals)
    for v in vals:
        if all(g[r * 9 + k] != v and g[k * 9 + c] != v for k in range(9)) and \
           all(g[(r // 3 * 3 + a) * 9 + c // 3 * 3 + b] != v for a in range(3) for b in range(3)):
            g[i] = v
            if _fill(g, rng): return True
            g[i] = 0
    return False


def sudoku(rng, givens=30):
    sol = [0] * 81; _fill(sol, rng)
    puz = sol[:]
    cells = list(range(81)); rng.shuffle(cells)
    for i in cells:
        if sum(1 for v in puz if v) <= givens: break
        keep = puz[i]; puz[i] = 0
        if _solve(puz[:]) != 1: puz[i] = keep
    assert _solve(puz[:]) == 1
    row = lambda g, r: "".join(str(v) if v else "." for v in g[r * 9:r * 9 + 9])
    return {"grid": [row(puz, r) for r in range(9)], "solution": [row(sol, r) for r in range(9)]}


# ---------- word search ----------
def words_from(slug, date, rng, n=8):
    """Words from headlines and titles that actually run in the public edition (after the topic cuts and the
    News cap), so the word search never hides a word from a story that was cut."""
    sys.path.insert(0, str(ROOT))
    from build import surviving_sections
    seen, out = set(), []
    for sec in surviving_sections(slug, date):
        if sec["id"] in ("funnies", "games", "passage"): continue
        for it in sec.get("items", []):
            for w in re.findall(r"\b[A-Za-z]{5,9}\b", " ".join(it.get(k) or "" for k in ("headline", "title"))):
                w = w.upper()
                if w not in seen and not GRIM.search(w) and w not in {"ABOUT", "AFTER", "THEIR", "THERE", "WHICH", "WOULD", "COULD", "SHOULD", "AGAIN", "STILL", "WHILE", "THESE", "THOSE"}:
                    seen.add(w); out.append(w)
    rng.shuffle(out)
    out = out[:n]
    for w in FALLBACK_WORDS:
        if len(out) >= n: break
        if w not in out: out.append(w)
    return sorted(out, key=lambda w: (-len(w), w))


def word_search(words, rng, size=12):
    dirs = [(0, 1), (1, 0), (1, 1), (-1, 1)]
    for _ in range(200):
        g = [[""] * size for _ in range(size)]; placed = []
        for w in words:
            spots = [(r, c, d) for d in dirs for r in range(size) for c in range(size)
                     if 0 <= r + d[0] * (len(w) - 1) < size and c + d[1] * (len(w) - 1) < size
                     and all(g[r + d[0] * k][c + d[1] * k] in ("", w[k]) for k in range(len(w)))]
            if not spots: break
            r, c, d = rng.choice(spots)
            for k in range(len(w)): g[r + d[0] * k][c + d[1] * k] = w[k]
            placed.append({"word": w, "cells": [[r + d[0] * k, c + d[1] * k] for k in range(len(w))]})
        if len(placed) == len(words): break
    else:
        raise SystemExit("word search: could not place all words")
    mask = [["." ] * size for _ in range(size)]
    for p in placed:
        for r, c in p["cells"]: mask[r][c] = g[r][c]
    letters = "ABCDEFGHIJKLMNOPRSTUVWY"
    grid = ["".join(ch or rng.choice(letters) for ch in row) for row in g]
    for p in placed:   # check every word reads back from the final grid
        assert "".join(grid[r][c] for r, c in p["cells"]) == p["word"]
    return {"grid": grid, "words": words, "solution": ["".join(r) for r in mask]}


# ---------- comics ----------
def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read()


def feed_items(feed):
    """Items of an RSS, RDF or Atom feed, newest first: title, link, and the first image in its html."""
    root = ET.fromstring(_get(feed["rss"]))
    out = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("item", "entry"): continue
        kids = {c.tag.split("}")[-1]: c for c in el}
        title = html.unescape((kids["title"].text or "") if "title" in kids else "").strip()
        link = kids["link"].text if "link" in kids else ""
        if not (link or "").strip() and "link" in kids: link = kids["link"].get("href", "")
        body = " ".join((kids[k].text or "") for k in ("encoded", "content", "description", "summary") if k in kids)
        body = html.unescape(body) if "&lt;img" in body else body
        img = re.search(r"<img\b[^>]*>", body)
        if not img: continue
        attr = lambda k: (re.search(k + r"""=(["'])(.*?)\1""", img.group(0), re.S) or [None] * 3)[2]
        hover, alt = attr("title"), attr("alt")
        alt = hover if hover and " " in hover else alt    # xkcd-style hover text first, else the image's alt text
        if attr("src"): out.append({"title": title, "link": link.strip(), "src": html.unescape(attr("src")),
                                    "alt": html.unescape(alt or "")})
    return out


def pick_comic(feed, img_dir, seen, date, skip):
    """The newest strip in the feed that has not run before (or ran on this same date), is not vetoed, and has no
    grim word in its title or hover text."""
    for c in feed_items(feed)[:10]:
        if c["link"] in skip or (c["link"] in seen and seen[c["link"]] != date): continue
        if GRIM_WORDS.search(c["title"] + " " + c["alt"]): continue
        img_dir.mkdir(exist_ok=True)
        fid = re.sub(r"[^a-z0-9]+", "-", feed["name"].lower())
        name = f"comic-{fid}-" + re.sub(r"[^A-Za-z0-9._-]+", "-", Path(c["src"].split("?")[0]).name)[-60:]
        try: data = _get(c["src"].replace("http://", "https://", 1))   # some feeds still list http:// images
        except Exception: data = _get(c["src"])
        (img_dir / name).write_bytes(data)
        title = c["title"] if c["title"].lower().startswith(feed["name"].lower()) else f"{feed['name']}: {c['title']}"
        return {"type": "comic", "id": f"comic-{fid}", "title": title,
                "byline": feed["byline"], "url": c["link"], "alt": c["alt"] if c["alt"] != c["title"] else "",
                "image": {"file": f"images/{name}", "credit": feed["name"], "src": c["src"]},
                "sources": [{"name": feed["name"], "url": c["link"]}]}
    return None


def comics(slug, date, img_dir, skip):
    sp = ROOT / "papers" / slug / "comics_seen.json"
    seen = json.loads(sp.read_text()) if sp.exists() else {}
    k = datetime.date.fromisoformat(date).toordinal() // 7   # one step per week: Funnies run on Sundays
    order = FEEDS + [ROTATE[(k * 2 + i) % len(ROTATE)] for i in range(len(ROTATE))]
    out = []
    for f in order:
        if len(out) >= 1 + 2: break
        try:
            c = pick_comic(f, img_dir, seen, date, skip)
            if c: out.append(c); seen[c["url"]] = date
            else: print(f"  comic {f['name']}: nothing new")
        except Exception as e:
            print(f"  comic {f['name']} unavailable: {e}")
    sp.write_text(json.dumps(seen, indent=1, sort_keys=True) + "\n")
    return out


# ---------- one-liners (verified jokes) ----------
def jokes(slug, date, skip, n=2):
    """n jokes from jokes.json: no repeats until the bank runs out, then it starts over. Same date, same jokes."""
    bank = [j for j in json.loads((ROOT / "papers" / slug / "jokes.json").read_text())["jokes"] if j["id"] not in skip]
    sp = ROOT / "papers" / slug / "jokes_seen.json"
    seen = json.loads(sp.read_text()) if sp.exists() else {}
    today = [j for j in bank if seen.get(j["id"]) == date]
    if len(today) < n:
        fresh = [j for j in bank if j["id"] not in seen]
        if len(fresh) < n - len(today):
            seen = {k: v for k, v in seen.items() if v == date}; fresh = [j for j in bank if j["id"] not in seen]
        today += random.Random(f"{slug}-{date}-jokes").sample(fresh, n - len(today))
    for j in today: seen[j["id"]] = date
    sp.write_text(json.dumps(seen, indent=1, sort_keys=True) + "\n")
    return [{"type": "joke", "id": f"joke-{j['id']}", "text": j["text"], "author": j["author"], "where": j.get("where", ""),
             "url": j["source_url"], "source_name": j["source_name"]} for j in today[:n]]


# ---------- funny posts (from x_feed.py's candidates) ----------
def posts(ed, img_dir, pick, skip, n=2):
    cands = {c["id"].split("-", 1)[-1]: c for c in ed.get("funny_candidates") or []}
    if pick is None: ids = [i for i in cands if i not in skip][:n]
    else: ids = [i for i in pick if i in cands and i not in skip]
    for i in pick or []:
        if i not in cands: print(f"  ! post {i} is not in funny_candidates; skipped")
    out = []
    for pid in ids:
        c = dict(cands[pid]); c["type"] = "funnypost"; c.pop("score", None)
        u = c.pop("image_url", None); alt = c.pop("image_alt", "")
        if u:
            try:
                name = f"funny-{pid}{Path(u.split('?')[0]).suffix or '.jpg'}"
                img_dir.mkdir(exist_ok=True); (img_dir / name).write_bytes(_get(u))
                c["image"] = {"file": f"images/{name}", "credit": f"@{c['handle']}", "src": u, "alt": alt}
                # the trailing t.co link of a photo post only points at that photo, which runs here
                c["text"] = re.sub(r"\s*https://t\.co/\w+\s*$", "", c["text"])
            except Exception as e:
                print(f"  post {pid}: photo unavailable: {e}")
        c["sources"] = [{"name": f"X @{c['handle']}", "url": c["url"]}]
        out.append(c)
    return out


def main(slug, date, comic=True, pick=None, skip=frozenset()):
    ed_dir = ROOT / "papers" / slug / "editions" / date
    ep = ed_dir / "edition.json"
    ed = json.loads(ep.read_text())
    rng = random.Random(f"{slug}-{date}")
    strips = comics(slug, date, ed_dir / "images", skip) if comic else []
    s = sudoku(rng)
    w = word_search(words_from(slug, date, rng), rng)
    # Order matters only when print runs long: build.py trims a section from its last item, so the extra strips go last.
    items = strips[:1] + jokes(slug, date, skip) + posts(ed, ed_dir / "images", pick, skip) + \
        [{"type": "sudoku", "id": f"sudoku-{date}", "title": "Sudoku", **s},
         {"type": "wordsearch", "id": f"wordsearch-{date}", "title": "Word Search", **w}] + strips[1:]
    ed["sections"] = [x for x in ed["sections"] if x["id"] != "funnies"] + [{"id": "funnies", "items": items}]
    ep.write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n")
    print(f"funnies: {', '.join(i.get('title') or i.get('author') or i['type'] for i in items)} -> {ep.relative_to(ROOT)}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    opt = lambda k: argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else None
    a = [x for x in argv if not x.startswith("--") and x not in (opt("--posts"), opt("--skip"))]
    if len(a) < 2: sys.exit(__doc__)
    p = opt("--posts")
    main(a[0], a[1], "--no-comic" not in argv, None if p is None else [x for x in p.split(",") if x and x != "none"],
         frozenset((opt("--skip") or "").split(",")) - {""})
