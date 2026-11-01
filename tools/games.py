#!/usr/bin/env python3
"""Daily games for an edition: mental math (3, rising, the last a Fermi estimate), a Wason four-card task,
a 5x5 crossword and a classic riddle. Written into edition.json as the `games` section.

    .venv/bin/python tools/games.py signal-seeker 2026-11-01

Everything is generated here and checked before it is written: math answers are computed, the Wason answer
is derived from the rule, every crossword entry is a real word from tools/data/crossword_words.json
(common English words with WordNet clues; rebuild with tools/build_crossword_words.py) and reads back from
the grid. Seeded by the date, so a rebuild gives the same games. Riddles are traditional ones, one a day,
no repeats until the list runs out. Answers: web = "Show answer" toggles; print = the Answers block on the
last page.
"""
import datetime, json, random, sys, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS = json.loads((ROOT / "tools" / "data" / "crossword_words.json").read_text())


def n(x):
    return f"{x:,}"


# ---------- mental math ----------
def mental_math(rng):
    a, b = rng.randint(13, 29), rng.randint(4, 9)
    p1 = {"q": f"{a} × {b}", "a": n(a * b), "how": f"{a} × {b} = {(a // 10) * 10} × {b} + {a % 10} × {b} = {n(a * b)}"}
    pct, base = rng.choice([15, 35, 45, 65, 85]), rng.randrange(140, 980, 20)
    v = pct * base // 100
    p2 = {"q": f"{pct}% of {base}", "a": n(v),
          "how": f"10% is {base // 10}, so {pct}% = {pct // 10} × {base // 10} + half of {base // 10} = {n(v)}" if pct % 10 == 5 else f"{n(v)}"}
    k = rng.randrange(4)
    if k == 0:
        bpm = rng.choice([60, 65, 70, 75])
        v = bpm * 60 * 24 * 365
        p3 = {"q": f"Fermi: a resting heart beats about {bpm} times a minute. Roughly how many beats in a year?",
              "a": f"about {round(v / 1e6)} million",
              "how": f"{bpm} × 60 × 24 × 365 = {n(v)}"}
    elif k == 1:
        wpm, mins, words = rng.choice([200, 250, 300]), rng.choice([15, 20, 30]), rng.choice([60000, 75000, 90000, 120000])
        days = -(-words // (wpm * mins))
        p3 = {"q": f"Fermi: you read {wpm} words a minute for {mins} minutes a day. How many days for a {n(words)}-word book?",
              "a": f"{days} days", "how": f"{wpm} × {mins} = {n(wpm * mins)} words a day; {n(words)} ÷ {n(wpm * mins)} = {words / (wpm * mins):.1f}, so {days} days"}
    elif k == 2:
        reams = rng.choice([10, 20, 40])
        mm = reams * 500 * 0.1
        p3 = {"q": f"Fermi: a sheet of printer paper is about 0.1 mm thick. How tall is a stack of {reams} reams of 500 sheets?",
              "a": f"about {mm / 1000:g} m", "how": f"{reams} × 500 = {n(reams * 500)} sheets × 0.1 mm = {n(int(mm))} mm = {mm / 1000:g} m"}
    else:
        lit, yrs = rng.choice([1.5, 2, 2.5]), rng.choice([50, 70, 80])
        v = int(lit * 365 * yrs)
        p3 = {"q": f"Fermi: if you drink {lit:g} litres of water a day, roughly how many litres in {yrs} years?",
              "a": f"about {n(int(v / 1000 + 0.5) * 1000)} litres", "how": f"{lit:g} × 365 × {yrs} = {n(v)}"}
    return {"type": "mathq", "id": "mathq", "title": "Mental Math", "problems": [p1, p2, p3]}


# ---------- Wason four-card task ----------
WASON = [
    {"rule": "If a card has a vowel on one side, it has an even number on the other.",
     "p": ["A", "E", "U"], "np": ["K", "R", "T"], "q": ["4", "8", "2"], "nq": ["7", "3", "9"]},
    {"rule": "If a card is red on one side, it has a circle on the other.",
     "p": ["Red"], "np": ["Blue", "Green"], "q": ["Circle"], "nq": ["Square", "Triangle"]},
    {"rule": "If a person is drinking beer, they must be over 21.",
     "p": ["Drinking beer"], "np": ["Drinking soda", "Drinking water"], "q": ["Age 25", "Age 40"], "nq": ["Age 17", "Age 16"],
     "note": "Most people get this version right and the letters-and-numbers version wrong, though the logic is identical."},
    {"rule": "If a parcel is marked Express, it has a red sticker.",
     "p": ["Express"], "np": ["Standard"], "q": ["Red sticker"], "nq": ["Blue sticker", "No sticker"]},
    {"rule": "If a day's forecast says rain, the card shows an umbrella on the back.",
     "p": ["Rain"], "np": ["Sunny", "Snow"], "q": ["Umbrella"], "nq": ["Sunglasses", "Scarf"]},
]


def wason(rng, date):
    v = WASON[datetime.date.fromisoformat(date).toordinal() % len(WASON)]
    cards = [("p", rng.choice(v["p"])), ("np", rng.choice(v["np"])), ("q", rng.choice(v["q"])), ("nq", rng.choice(v["nq"]))]
    rng.shuffle(cards)
    P = next(c for k, c in cards if k == "p"); NQ = next(c for k, c in cards if k == "nq")
    Q = next(c for k, c in cards if k == "q"); NP = next(c for k, c in cards if k == "np")
    expl = (f"{P} could hide something that breaks the rule; {NQ} breaks it if the other side turns out to be {P}. "
            f"{Q} can't break it (the rule never says only those cards have it), and {NP} isn't covered by the rule at all. "
            "Most people pick the card that matches the rule's second half instead of the one that could falsify it.")
    if v.get("note"): expl += " " + v["note"]
    return {"type": "wason", "id": "wason", "title": "Four Cards", "rule": v["rule"], "cards": [c for _, c in cards],
            "answer": f"{P} and {NQ}", "explanation": expl}


# ---------- crossword ----------
PATTERNS = [["#...#", ".....", ".....", ".....", "#...#"]]


def slots(p):
    out = []
    size = len(p)
    for dirn in "AD":
        for i in range(size):
            j = 0
            while j < size:
                cell = lambda k: p[i][k] if dirn == "A" else p[k][i]
                if cell(j) == "#": j += 1; continue
                s = j
                while j < size and cell(j) != "#": j += 1
                if j - s >= 2:
                    out.append((dirn, [(i, k) if dirn == "A" else (k, i) for k in range(s, j)]))
    return out


def fill(p, rng, limit=6.0):
    sl = slots(p); bylen = defaultdict(list)
    for w in WORDS: bylen[len(w)].append(w)
    for l in bylen: rng.shuffle(bylen[l])
    grid, used, t0 = {}, set(), time.time()

    def cands(cells):
        return [w for w in bylen[len(cells)] if w not in used and all(grid.get(c, w[i]) == w[i] for i, c in enumerate(cells))]

    def rec():
        if time.time() - t0 > limit: raise TimeoutError
        best, done = None, []
        for s in sl:
            if all(c in grid for c in s[1]):
                w = "".join(grid[c] for c in s[1])
                if w not in WORDS or w in done: return False      # crossings spelled a non-word or a repeat
                done.append(w); continue
            cs = cands(s[1])
            if not cs: return False
            if best is None or len(cs) < len(best[1]): best = (s, cs)
        if not best: return True
        s, cs = best
        for w in cs[:80]:
            added = [c for c in s[1] if c not in grid]
            for i, c in enumerate(s[1]): grid[c] = w[i]
            used.add(w)
            if rec(): return True
            used.discard(w)
            for c in added: del grid[c]
        return False
    try:
        return grid if rec() else None
    except TimeoutError:
        return None


def crossword(rng):
    for tries in range(20):
        p = rng.choice(PATTERNS)
        g = fill(p, rng)
        if g: break
    else:
        raise SystemExit("crossword: no fill")
    size = len(p)
    sl = slots(p)
    starts = sorted({s[1][0] for s in sl})
    num = {c: i + 1 for i, c in enumerate(starts)}
    clues = {"across": [], "down": []}
    words = []
    for d, cells in sl:
        w = "".join(g[c] for c in cells)
        assert w in WORDS, w                                   # real word, has a clue
        words.append(w)
        clues["across" if d == "A" else "down"].append({"n": num[cells[0]], "clue": WORDS[w], "len": len(w), "answer": w})
    assert len(set(words)) == len(words)
    for k in clues: clues[k].sort(key=lambda c: c["n"])
    cells = [[{"b": True} if p[r][c] == "#" else {"n": num.get((r, c))} for c in range(size)] for r in range(size)]
    solution = ["".join(g.get((r, c), "#") for c in range(size)) for r in range(size)]
    return {"type": "crossword", "id": "crossword", "title": "Mini Crossword", "size": size, "cells": cells,
            "clues": clues, "solution": solution}


# ---------- riddle ----------
RIDDLES = [
    ("What has keys but can't open a single lock?", "A piano."),
    ("What has a neck but no head?", "A bottle."),
    ("What gets wetter the more it dries?", "A towel."),
    ("What has an eye but cannot see?", "A needle."),
    ("What has hands but cannot clap?", "A clock."),
    ("What can travel around the world while staying in a corner?", "A stamp."),
    ("The more you take, the more you leave behind. What are they?", "Footsteps."),
    ("What has to be broken before you can use it?", "An egg."),
    ("What goes up but never comes down?", "Your age."),
    ("I'm tall when I'm young and short when I'm old. What am I?", "A candle."),
    ("What has many teeth but can't bite?", "A comb."),
    ("What runs but never walks, has a mouth but never talks, has a bed but never sleeps?", "A river."),
    ("What can you catch but not throw?", "A cold."),
    ("What belongs to you, but other people use it more than you do?", "Your name."),
    ("What has cities but no houses, forests but no trees, and water but no fish?", "A map."),
    ("What is full of holes but still holds water?", "A sponge."),
    ("What walks on four legs in the morning, two at noon and three in the evening?", "A person: crawling as a baby, walking, then with a cane. (The riddle of the Sphinx.)"),
    ("Forward I am heavy, but backward I am not. What am I?", "A ton."),
    ("What word becomes shorter when you add two letters to it?", "Short."),
    ("What has a head and a tail but no body?", "A coin."),
    ("What comes once in a minute, twice in a moment, but never in a thousand years?", "The letter M."),
    ("What has a thumb and four fingers but is not alive?", "A glove."),
    ("What can fill a room but takes up no space?", "Light."),
    ("If you have me, you want to share me. If you share me, you haven't got me. What am I?", "A secret."),
    ("Some months have 31 days, some have 30. How many have 28?", "All twelve."),
    ("What is so fragile that saying its name breaks it?", "Silence."),
    ("What goes through cities and fields but never moves?", "A road."),
    ("What kind of band never plays music?", "A rubber band."),
    ("What has one head, one foot and four legs?", "A bed."),
    ("What can you keep after giving it to someone?", "Your word."),
]


def riddle(date):
    order = list(range(len(RIDDLES)))
    random.Random("riddles").shuffle(order)
    q, a = RIDDLES[order[datetime.date.fromisoformat(date).toordinal() % len(RIDDLES)]]
    return {"type": "riddle", "id": "riddle", "title": "Riddle", "q": q, "a": a}


def main(slug, date):
    ep = ROOT / "papers" / slug / "editions" / date / "edition.json"
    ed = json.loads(ep.read_text())
    rng = random.Random(f"{slug}-{date}-games")
    items = [mental_math(rng), wason(rng, date), crossword(rng), riddle(date)]
    for it in items: it["id"] = f"{it['id']}-{date}"
    ed["sections"] = [s for s in ed["sections"] if s["id"] != "games"] + [{"id": "games", "items": items}]
    ep.write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n")
    print(f"games: {', '.join(i['type'] for i in items)} -> {ep.relative_to(ROOT)}")
    cw = items[2]
    print("  crossword:", " / ".join(cw["solution"]))


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) < 2: sys.exit(__doc__)
    main(a[0], a[1])
