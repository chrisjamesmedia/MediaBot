#!/usr/bin/env python3
"""One-off: build tools/data/crossword_words.json (word -> clue) for tools/games.py.

    .venv/bin/python tools/build_crossword_words.py

Words: common English words (wordfreq Zipf >= 3.3) of 3-5 letters that are WordNet lemmas.
Clue: the WordNet gloss of the word's first sense, skipped when the gloss gives the word away.
Needs nltk's WordNet data (python -m nltk.downloader wordnet) and wordfreq; the daily routine only reads the JSON.
"""
import json, re, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
from nltk.corpus import wordnet as wn
from wordfreq import top_n_list, zipf_frequency

OUT = Path(__file__).resolve().parent / "data" / "crossword_words.json"
BLOCK = set("""sex sexy anal anus porn nude nazi rape kill dead died dies death gun guns drug drugs bomb war wars
hell damn crap shit fuck piss tit tits cock dick slut whore bitch arse ass butt kkk jew jews gay gays fag homo
negro coke meth heroin drunk booze shoot stab knife slave slaves naked nudes bra pee poop vomit suck sucks
lust kinky pimp gore grave tomb coffin corpse""".split())


def clue(w):
    for s in wn.synsets(w):
        names = [l.name() for l in s.lemmas()]
        if w not in names: continue
        d = s.definition().strip()
        if re.search(r"\b" + re.escape(w[:4]), d, re.I) or len(d) > 70 or len(d) < 8: continue
        d = re.sub(r"\s*\(.*?\)\s*", " ", d).strip(" ;")
        return d[0].upper() + d[1:]
    return None


def main():
    out = {}
    for w in top_n_list("en", 60000):
        if not (w.isalpha() and w.isascii() and w.islower() and 3 <= len(w) <= 5): continue
        if w in BLOCK or zipf_frequency(w, "en") < 3.3: continue
        c = clue(w)
        if c: out[w.upper()] = c
    OUT.write_text(json.dumps(dict(sorted(out.items())), indent=0, ensure_ascii=False) + "\n")
    from collections import Counter
    print(len(out), Counter(len(w) for w in out))


if __name__ == "__main__":
    main()
