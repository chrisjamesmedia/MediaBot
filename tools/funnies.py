#!/usr/bin/env python3
"""Fill an edition's Funnies section: today's xkcd (from its RSS feed) plus a sudoku and a word search.

    .venv/bin/python tools/funnies.py signal-seeker 2026-11-01            # comic + puzzles
    .venv/bin/python tools/funnies.py signal-seeker 2026-11-01 --no-comic # puzzles only (offline)

Puzzles are generated here and checked: the sudoku has exactly one solution; every word-search word
is placed in the grid. Both are seeded by the date, so a rebuild gives the same puzzles.
Comics come only from real feeds, shown with credit and a link; nothing is drawn or invented.
xkcd is CC BY-NC 2.5 (https://xkcd.com/license.html).
"""
import datetime, json, random, re, sys, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEEDS = [{"name": "xkcd", "byline": "Randall Munroe", "rss": "https://xkcd.com/rss.xml"}]
UA = {"User-Agent": "MediaBot/1 (personal newspaper; links back to every comic)"}
GRIM = re.compile(r"STAB|KILL|DEAD|DEATH|SHOOT|MURDER|WAR|BOMB|ATTACK|CRASH|VICTIM|ABUSE|RAPE|TERROR")
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
def words_from(ed, rng, n=8):
    seen, out = set(), []
    for sec in ed.get("sections", []):
        for it in sec.get("items", []):
            for w in re.findall(r"\b[A-Za-z]{5,9}\b", it.get("headline", "")):
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
def latest_comic(feed, img_dir):
    req = urllib.request.Request(feed["rss"], headers=UA)
    root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
    item = root.find("./channel/item")
    title, link = item.findtext("title"), item.findtext("link")
    desc = item.findtext("description") or ""
    m = re.search(r'src="([^"]+)"', desc)
    if not m: return None
    alt = re.search(r'title="([^"]*)"', desc)
    src = m.group(1)
    img_dir.mkdir(exist_ok=True)
    name = f"comic-{feed['name']}-{Path(src).name}"
    data = urllib.request.urlopen(urllib.request.Request(src, headers=UA), timeout=20).read()
    (img_dir / name).write_bytes(data)
    import html
    return {"type": "comic", "id": f"comic-{feed['name']}", "title": f"{feed['name']}: {html.unescape(title)}",
            "byline": feed["byline"], "url": link, "alt": html.unescape(alt.group(1)) if alt else "",
            "image": {"file": f"images/{name}", "credit": feed["name"], "src": src},
            "sources": [{"name": feed["name"], "url": link}]}


def main(slug, date, comic=True):
    ed_dir = ROOT / "papers" / slug / "editions" / date
    ep = ed_dir / "edition.json"
    ed = json.loads(ep.read_text())
    rng = random.Random(f"{slug}-{date}")
    items = []
    if comic:
        for f in FEEDS:
            try:
                c = latest_comic(f, ed_dir / "images")
                if c: items.append(c)
            except Exception as e:
                print(f"  comic {f['name']} unavailable: {e}")
    s = sudoku(rng)
    items.append({"type": "sudoku", "id": f"sudoku-{date}", "title": "Sudoku", **s})
    w = word_search(words_from(ed, rng), rng)
    items.append({"type": "wordsearch", "id": f"wordsearch-{date}", "title": "Word Search", **w})
    ed["sections"] = [x for x in ed["sections"] if x["id"] != "funnies"] + [{"id": "funnies", "items": items}]
    ep.write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n")
    print(f"funnies: {', '.join(i['type'] for i in items)} -> {ep.relative_to(ROOT)}")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) < 2: sys.exit(__doc__)
    main(a[0], a[1], "--no-comic" not in sys.argv)
