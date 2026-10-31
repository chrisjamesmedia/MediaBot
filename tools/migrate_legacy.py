#!/usr/bin/env python3
"""One-time migration: first-generation edition.json (/workspace/paper/YYYY-MM-DD) -> schema 1.

    .venv/bin/python tools/migrate_legacy.py /workspace/paper/2026-10-31 signal-seeker

Only moves, trims and drops. Nothing is written that is not in the legacy file, except
X post dates, which are decoded from each post's status ID (X IDs embed their timestamp).
"""
import json, re, shutil, sys, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOW_IMAGES = {"alphabet", "nasa-asks-industry-again-how-to-save-hub"}   # same opt-in set as the mockup
FROM_YOUR_X = {"paulg"}      # must-read / followed accounts. Thariq, Levie, Mollick are not followed -> Tech & AI


def slug(s, n=40):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n]


def x_date(url):
    sid = int(url.rstrip("/").rsplit("/", 1)[-1])
    ms = (sid >> 22) + 1288834974657
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main(src, paper):
    src = Path(src).resolve()
    old = json.loads((src / "edition.json").read_text())
    date = old["date_iso"]
    out = ROOT / "papers" / paper / "editions" / date
    (out / "images").mkdir(parents=True, exist_ok=True)

    def story(s, brief=False):
        sid = s.get("id") or slug(s["headline"])
        it = {"type": "story", "id": sid, "headline": s["headline"], "summary": s.get("summary", ""),
              "short": s.get("print_line", ""), "sources": s.get("sources", [])}
        if brief or s["headline"] in ("Briefly", "Around the region"):
            it["brief"] = True
        f = src / "images" / f"{sid}.jpg"
        if s.get("image") and sid in SHOW_IMAGES and f.exists():
            shutil.copy(f, out / "images" / f.name)
            it["image"] = {"file": f"images/{f.name}", "credit": s["image"].get("credit", "")}
        return it

    def post(p):
        return {"type": "post", "id": "x-" + p["url"].rsplit("/", 1)[-1], "author": p["author"],
                "handle": p["handle"], "text": p["text"], "url": p["url"], "date": x_date(p["url"])}

    secs = {k: [] for k in ("front", "x", "goats", "investments", "holdings", "tech", "reading",
                            "business", "science", "local", "bigstuff", "worth")}
    secs["front"] = [story(s) for s in old["front"]]
    for sec in old["sections"]:
        for s in sec["stories"]:
            h = s["headline"]
            if h.startswith("On X:"):
                continue                      # its posts run as post cards; DHH's full post is not in the file
            if sec["id"] == "tech":
                (secs["business"] if h.startswith("Microsoft offers") else secs["tech"]).append(story(s))
            elif sec["id"] == "business":
                if h.startswith("Amazon:"):
                    secs["holdings"].append(dict(story(s), group="AMZN"))
                elif h.startswith("Fed holds"):
                    secs["investments"].append(dict(story(s), group="Rates"))
                else:
                    secs["investments"].append(dict(story(s), group="Hyperscalers & capex"))
                    m = re.search(r"Meta (plans to raise [^;]+)", s.get("summary", ""))
                    if m:  # the Meta clause, word for word, as a holdings line
                        t = m.group(1).rstrip(".") + "."
                        secs["holdings"].append({"type": "line", "id": "meta-" + slug(t, 24), "group": "META",
                                                 "text": t[0].upper() + t[1:], "sources": s["sources"]})
            elif sec["id"] == "culture":
                secs["reading"].append(story(s))
            else:
                secs[sec["id"]].append(story(s))
    for p in old.get("x_pulse", []):
        (secs["x"] if p["handle"] in FROM_YOUR_X else secs["tech"]).append(post(p))
    secs["bigstuff"] = [{"type": "line", "id": "big-" + slug(re.sub("<[^>]+>", "", b["text"]), 24), "text": b["text"],
                         "sources": [{"name": b["src"], "url": b["url"]}]} for b in old.get("big_stuff", [])]
    secs["worth"] = [{"type": "link", "id": "w-" + slug(w["title"], 30), "title": w["title"], "url": w["url"],
                      "why": w.get("why", "")} for w in old.get("worth", [])]

    ed = {"schema": 1, "paper": paper, "date": date, "coverage": old.get("coverage", ""),
          "note": old.get("ear_right", {}).get("text", ""),
          "sections": [{"id": k, "items": v} for k, v in secs.items() if v]}
    (out / "edition.json").write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n")
    w = Path("/workspace/paper/site/data") / f"weather-{date}.json"
    if w.exists() and not (out / "weather.json").exists():
        shutil.copy(w, out / "weather.json")
    print("wrote", out / "edition.json", {k: len(v) for k, v in secs.items()})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "signal-seeker")
