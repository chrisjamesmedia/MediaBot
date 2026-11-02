#!/usr/bin/env python3
"""Re-check the joke bank: fetch every source_url in papers/<slug>/jokes.json and confirm the joke's exact text is
on that page (whitespace aside). Run it after adding a joke; a joke that fails must be fixed or removed, never
reworded to fit.

    .venv/bin/python tools/jokes_check.py signal-seeker
"""
import json, re, sys, urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (personal newspaper; checking a quoted joke against its source)"}


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.out, self.skip = [], 0
    def handle_starttag(self, tag, a):
        if tag in ("script", "style", "noscript"): self.skip += 1
        elif tag in ("p", "li", "br", "div", "dd", "h2", "h3", "blockquote"): self.out.append(" ")
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip: self.skip -= 1
    def handle_data(self, d):
        if not self.skip: self.out.append(d)


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def main(slug):
    jokes = json.loads((ROOT / "papers" / slug / "jokes.json").read_text())["jokes"]
    pages, bad = {}, 0
    for j in jokes:
        u = j["source_url"]
        if u not in pages:
            try:
                p = Text(); p.feed(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode("utf-8", "replace"))
                pages[u] = norm("".join(p.out))
            except Exception as e:
                pages[u] = None; print(f"  ? {u}: {e}")
        page = pages[u]
        ok = page is not None and norm(j["text"]) in page
        bad += not ok
        print(("ok  " if ok else "FAIL") + f" {j['id']:<14} {j['author'][:20]:<20} {norm(j['text'])[:60]}")
    print(f"{len(jokes) - bad}/{len(jokes)} found on their source pages")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1])
