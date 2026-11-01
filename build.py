#!/usr/bin/env python3
"""MediaBot build: one paper config + one edition.json -> web edition, print PDF, digital PDF.

    .venv/bin/python build.py signal-seeker 2026-10-31          # build one edition, refresh indexes
    .venv/bin/python build.py signal-seeker 2026-10-31 --weather   # refetch Boston weather first
    .venv/bin/python build.py signal-seeker 2026-10-31 --size small
    .venv/bin/python build.py --index                            # only regenerate root + paper indexes
    .venv/bin/python build.py signal-seeker 2026-10-31 --public-only  # skip the local private copy
    .venv/bin/python build.py --recipe recipes/x-substack-5.yaml 2026-11-01   # on-demand edition from a recipe
    .venv/bin/python build.py --editor                           # only rebuild the recipe editor (site/edit/)

Sections marked `private: true` in paper.yaml go only into site-private/ (gitignored, never published).

Reads   papers/<slug>/paper.yaml, papers/<slug>/editions/<date>/edition.json (+ images/, weather.json),
        papers/<slug>/feedback/*.json
Writes  site/<slug>/<date>/index.html, <slug>-<date>-print.pdf, <slug>-<date>-digital.pdf, images/
        site/<slug>/index.html, site/index.html, site/assets/, site/robots.txt (+ sitemap.xml once web_base is set)
        site/<slug>/latest/ (print.pdf, digital.pdf, latest.json, index.html redirect; public papers only,
        the stable URL tools/print-daily/ prints from)
        papers/<slug>/feedback/summary.json, papers/<slug>/evergreen_seen.json
Recipe builds (docs/recipes.md) write site/<slug>/custom/<recipe>/<date>/ and are not indexed.
"""
import datetime, hashlib, html, json, re, shutil, subprocess, sys, urllib.request
from pathlib import Path
from urllib.parse import urlparse

import yaml
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent
PAPERS, SITE, TPL, STATIC, CACHE = ROOT / "papers", ROOT / "site", ROOT / "templates", ROOT / "static", ROOT / ".build"
PRIVATE_SITE = ROOT / "site-private"    # full copy incl. private sections; gitignored, never published
# Money details that must never appear in public output (holdings show material news only).
FORBIDDEN_KEYS = {"shares", "share_count", "quantity", "qty", "value", "market_value", "position", "position_size",
                  "cost_basis", "avg_cost", "weight_pct", "allocation", "pnl", "gain", "balance"}
CHROME = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")

WMO = {0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy", 45: "Fog", 48: "Fog", 51: "Drizzle",
       53: "Drizzle", 55: "Drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle", 61: "Light rain", 63: "Rain",
       65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
       77: "Snow", 80: "Showers", 81: "Showers", 82: "Heavy showers", 85: "Snow showers", 86: "Snow showers",
       95: "Thunderstorms", 96: "Thunderstorms", 99: "Thunderstorms"}
PRINT_TYPE = {"small": 8.4, "medium": 9.2, "large": 10.2}     # body size in pt per print size
RECIPES = ROOT / "recipes"
# Where each section's content comes from; shown as a quiet tag in the recipe editor.
SOURCE_KIND = {"front": "X", "x": "X", "goats": "X", "investments": "X + News", "holdings": "News",
               "tech": "X + News", "reading": "X", "business": "News", "science": "News", "local": "News",
               "bigstuff": "News", "worth": "X + Web", "evergreen": "X (long-form)", "substack": "Substack", "youtube": "YouTube",
               "funnies": "Comics", "personal": "Private"}


def load_yaml(p):
    return yaml.safe_load(Path(p).read_text())


def public_base(url):
    host = (urlparse(url).hostname or "") if url else ""
    return url.rstrip("/") if host and host not in ("localhost", "127.0.0.1", "::1", "0.0.0.0") else ""


# ---------- weather ----------
def icon_kind(code):
    if code in (0, 1): return "sun"
    if code == 2: return "partly"
    if code in (45, 48): return "fog"
    if code in (71, 73, 75, 77, 85, 86): return "snow"
    if code >= 95: return "storm"
    if code >= 51: return "rain"
    return "cloud"


def weather(paper, ed_dir, refresh):
    w = (paper.get("masthead") or {}).get("weather")
    if not w:
        return {"ok": False}
    path = ed_dir / "weather.json"
    try:
        if refresh or not path.exists():
            q = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                 "&current=temperature_2m,weather_code,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min"
                 "&temperature_unit=fahrenheit&timezone={tz}&forecast_days=4").format(
                     lat=w["lat"], lon=w["lon"], tz=w.get("timezone", "auto").replace("/", "%2F"))
            data = json.load(urllib.request.urlopen(q, timeout=20))
            data["fetched_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            data["source_url"] = q
            path.write_text(json.dumps(data, indent=1))
        data = json.loads(path.read_text())
    except Exception as e:      # never invent numbers
        print("  weather unavailable:", e)
        return {"ok": False, "label": w.get("label", "")}
    c = data["current"]
    fetched = datetime.datetime.fromisoformat(data["fetched_at"])
    if w.get("timezone"):
        from zoneinfo import ZoneInfo
        fetched = fetched.astimezone(ZoneInfo(w["timezone"]))
    cond = WMO.get(c["weather_code"], "")
    if c.get("is_day") and cond in ("Clear", "Mostly clear"):
        cond = cond.replace("clear", "sunny").replace("Clear", "Sunny")
    # One compact block: now, today's high/low, tomorrow in a few words. Only what the fetched data has.
    now = round(c["temperature_2m"])
    line = f"{w.get('label', '')} · {now}°F" + (f", {cond[0].lower() + cond[1:]}" if cond else "")
    out = {"ok": True, "label": w.get("label", ""), "now": now, "cond": cond, "now_line": line,
           "asof_full": fetched.strftime("%b %-d, %-I:%M %p %Z").strip(),
           "asof_short": fetched.strftime("%-I:%M %p").strip()}
    dl = data.get("daily") or {}
    days = dl.get("time") or []
    today = fetched.date().isoformat()
    if today in days:
        i = days.index(today)
        try:
            out["hi"], out["lo"] = round(dl["temperature_2m_max"][i]), round(dl["temperature_2m_min"][i])
            if i + 1 < len(days):
                tc = WMO.get(dl["weather_code"][i + 1], "")
                out["tomorrow"] = {"cond": tc[0].lower() + tc[1:] if tc else "",
                                   "hi": round(dl["temperature_2m_max"][i + 1]), "lo": round(dl["temperature_2m_min"][i + 1])}
        except (KeyError, IndexError, TypeError):
            pass
    parts = [line]
    if "hi" in out: parts.append(f"High {out['hi']}° · Low {out['lo']}°")
    t = out.get("tomorrow")
    if t: parts.append(f"Tomorrow: {t['cond'] + ', ' if t['cond'] else ''}{t['hi']}°/{t['lo']}°")
    out["line"] = " · ".join(parts)
    return out


# ---------- feedback ----------
def feedback_summary(slug):
    """Fold every exported feedback file into feedback/summary.json, which the daily routine reads."""
    fdir = PAPERS / slug / "feedback"
    fdir.mkdir(exist_ok=True)
    files = sorted(p for p in fdir.glob("*.json") if p.name != "summary.json")
    S = {"format": "mediabot-feedback-summary/1", "paper": slug, "files": len(files), "editions": [],
         "by_section": {}, "more_like_this": [], "skipped": [], "knew": [], "notes": []}
    for p in files:
        try:
            f = json.loads(p.read_text())
        except Exception as e:
            print(f"  ! feedback {p.name} unreadable: {e}"); continue
        ed = f.get("edition", "")
        if ed not in S["editions"]: S["editions"].append(ed)
        if f.get("note"): S["notes"].append({"edition": ed, "note": f["note"]})
        for it in f.get("items", []):
            sec = S["by_section"].setdefault(it.get("section", "?"), {"read": 0, "knew": 0, "more": 0, "skip": 0})
            if it.get("read"): sec["read"] += 1
            r = it.get("reaction")
            if r in ("knew", "more", "skip"):
                sec[r] += 1
                key = {"more": "more_like_this", "skip": "skipped", "knew": "knew"}[r]
                S[key].append({"edition": ed, "section": it.get("section"), "title": it.get("title", ""), "url": it.get("url", "")})
    S["editions"].sort()
    (fdir / "summary.json").write_text(json.dumps(S, indent=1, ensure_ascii=False) + "\n")
    return S


# ---------- edition assembly ----------
def item_urls(it):
    urls = [s.get("url") for s in it.get("sources", [])]
    if it.get("url"): urls.append(it["url"])
    return {u.rstrip("/") for u in urls if u}


def check_public(sections):
    """Refuse to publish holding values, share counts or position sizes."""
    bad = []
    for sec in sections:
        for it in sec["items"]:
            hit = FORBIDDEN_KEYS & set(it)
            if hit: bad.append(f"{sec['id']}/{it.get('id')}: {', '.join(sorted(hit))}")
    if bad:
        sys.exit("refusing public build: position/value fields present -> " + "; ".join(bad))


def assemble(paper, ed, size, private=False):
    by_id = {s["id"]: s for s in ed.get("sections", [])}
    known = {c["id"] for c in paper["sections"]}
    left = [sid for sid in by_id if sid not in known]
    if left and paper.get("recipe"):
        print(f"  not in this recipe: {', '.join(left)}")
    else:
        for sid in left:
            print(f"  ! edition section '{sid}' is not in paper.yaml; skipped")
    holdings = {h["ticker"]: h["name"] for h in (paper.get("sources") or {}).get("holdings", [])}
    out, seen = [], set()
    for cfg in paper["sections"]:
        items = list((by_id.get(cfg["id"]) or {}).get("items", []))
        if cfg.get("types"):
            items = [it for it in items if it.get("type", "story") in cfg["types"]]
        acc = (paper.get("recipe") or {}).get("accounts")
        if acc:
            items = [it for it in items if it.get("type") != "post" or (it.get("handle") or "").lower() in acc]
        if not cfg.get("enabled", True) or not items:
            continue
        if cfg.get("private") and not private:
            print(f"  {cfg['id']}: private, left out of the public build")
            continue
        if cfg.get("dedupe") and not paper.get("news"):
            before = len(items)
            items = [it for it in items if not (item_urls(it) & seen)]
            if before - len(items):
                print(f"  {cfg['id']}: dropped {before - len(items)} of {before} links already in the paper")
        if cfg.get("max_items") and len(items) > cfg["max_items"] and not cfg.get("require_source") \
                and not (cfg.get("dedupe") and paper.get("news")):
            print(f"  {cfg['id']}: {len(items)} items, trimmed to max_items {cfg['max_items']}")
            items = items[:cfg["max_items"]]
        for it in items:
            seen |= item_urls(it)
            if it.get("type", "story") in ("post", "evergreen") and it.get("date"):
                dt = datetime.datetime.fromisoformat(it["date"].replace("Z", "+00:00")).astimezone()
                it["date_short"] = dt.strftime("%b %-d")
            if size == "small" and it.get("short"):
                it["print_text"] = it["short"]
            else:
                it["print_text"] = it.get("summary", "")
        if not items:
            continue
        sec = dict(cfg, items=items)
        g = cfg.get("group_by")
        if g:
            groups = {}
            for it in items:
                groups.setdefault(it.get("group") or "", []).append(it)
            order = list(holdings) if g == "ticker" else list(groups)
            sec["groups"] = [{"key": k, "title": holdings.get(k, k) if g == "ticker" else k, "items": groups[k]}
                             for k in order if k in groups]
        out.append(sec)
    return out


# ---------- selection rules: X-first front, News cap, topic cuts, Evergreen seen-list ----------
def regroup(sec):
    if sec.get("groups") is not None:
        ids = {id(i) for i in sec["items"]}
        sec["groups"] = [g2 for g2 in ({**g, "items": [i for i in g["items"] if id(i) in ids]} for g in sec["groups"]) if g2["items"]]


def first_sentence(s):
    s = " ".join((s or "").split())
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    return m.group(1) if m else s


def apply_selection(sections, paper):
    """paper.yaml `news:` and `front.require_source`: the front page comes from X, topics Chris skips are cut
    everywhere unless `major: true`, and every legacy/web news item is pooled into one small News section."""
    cfg = paper.get("news") or {}
    excl = {t.lower() for t in cfg.get("exclude_topics") or []}
    major_only = set(cfg.get("major_only_sections") or [])
    cut = []

    def label(it):
        return " ".join((it.get("headline") or it.get("title") or re.sub("<[^>]+>", "", it.get("text", ""))[:60]).split())

    def excluded(it):
        topics = it.get("topic") or []
        topics = [topics] if isinstance(topics, str) else topics
        return not it.get("major") and any(t.lower() in excl for t in topics)

    # 1. topic cuts, everywhere (X included): war, macro, politics… unless genuinely major
    for sec in sections:
        if sec.get("private") or sec["id"] == "funnies": continue
        keep = []
        for it in sec["items"]:
            if excluded(it): cut.append(f"{sec['id']}/{it.get('id')} ({'/'.join(it['topic']) if isinstance(it.get('topic'), list) else it.get('topic')}): {label(it)}")
            else: keep.append(it)
        sec["items"] = keep
        regroup(sec)

    # 2. front page must come from X; anything else drops into the News pool
    pool = []
    front = next((s for s in sections if s["id"] == "front"), None)
    fcfg = next((c for c in paper["sections"] if c["id"] == "front"), {})
    if front and fcfg.get("require_source") == "x":
        demoted = [it for it in front["items"] if not is_x_item(it)]
        front["items"] = [it for it in front["items"] if is_x_item(it)]
        pool += [("front", it) for it in demoted]
        if demoted: print(f"  front: {len(demoted)} non-X item(s) moved to News: {', '.join(it['id'] for it in demoted)}")
        cap = fcfg.get("max_items")
        if cap and len(front["items"]) > cap:
            print(f"  front: {len(front['items'])} X items, trimmed to max_items {cap}")
            front["items"] = front["items"][:cap]

    if cfg and not paper.get("recipe"):
        # 3. pool every news-source item (legacy/web stories and lines) outside Holdings
        skip = {"front", "holdings", "funnies", "evergreen", "substack", "youtube"}
        for sec in sections:
            if sec["id"] in skip or sec.get("private"): continue
            keep = []
            for it in sec["items"]:
                if item_source(sec, it) == "news":
                    if sec["id"] in major_only and not it.get("major"):
                        cut.append(f"{sec['id']}/{it.get('id')} (not major): {label(it)}")
                    else:
                        pool.append((sec["id"], it))
                else:
                    keep.append(it)
            sec["items"] = keep
            regroup(sec)
        pool.sort(key=lambda p: 0 if p[1].get("major") else 1)       # stable: major first, then front, then paper order
        cap = cfg.get("max_items", 4)
        for sid, it in pool[cap:]:
            cut.append(f"{sid}/{it.get('id')} (over News cap {cap}): {label(it)}")
        items = [it for _, it in pool[:cap]]
        for it in items:
            it["brief_text"] = it.get("short") or first_sentence(it.get("summary") or "")
            it["print_text"] = it["brief_text"]
        if items:
            news = {"id": "news", "title": cfg.get("title", "Headlines"), "weight": cfg.get("weight", 4),
                    "max_items": cap, "style": "brief", "items": items}
            at = next((i for i, s in enumerate(sections) if s["id"] == "holdings"), len(sections))
            sections.insert(at, news)
    elif pool:
        print(f"  front: {len(pool)} demoted item(s) dropped (no news: config or recipe build)")
    # 4. dedupe link sections against what is left in the paper (after the cuts, so a link whose twin was cut stays)
    if cfg:
        for sec in sections:
            c = next((c for c in paper["sections"] if c["id"] == sec["id"]), {})
            if not c.get("dedupe"): continue
            have = set().union(*[item_urls(i) for s2 in sections if s2 is not sec for i in s2["items"]])
            before = len(sec["items"])
            sec["items"] = [i for i in sec["items"] if not (item_urls(i) & have)]
            if before - len(sec["items"]):
                print(f"  {sec['id']}: dropped {before - len(sec['items'])} of {before} links already in the paper")
            if c.get("max_items") and len(sec["items"]) > c["max_items"]:
                print(f"  {sec['id']}: {len(sec['items'])} items, trimmed to max_items {c['max_items']}")
                sec["items"] = sec["items"][:c["max_items"]]
    sections[:] = [s for s in sections if s["items"]]
    for c in cut: print("  cut:", c)
    return cut


def apply_evergreen(sections, paper, date, record):
    """Evergreen items never repeat: papers/<slug>/evergreen_seen.json maps URL -> first edition date."""
    sec = next((s for s in sections if s["id"] == "evergreen"), None)
    path = PAPERS / paper["slug"] / "evergreen_seen.json"
    seen = json.loads(path.read_text()) if path.exists() else {}
    if not sec: return
    keep = []
    for it in sec["items"]:
        u = (it.get("url") or "").split("?")[0].rstrip("/")
        if not u:
            print(f"  ! evergreen {it.get('id')}: no url, dropped"); continue
        first = seen.get(u)
        if first and first < date:
            print(f"  evergreen: {it.get('id')} already ran {first}, dropped"); continue
        keep.append(it)
        if record and not first: seen[u] = date
    sec["items"] = keep
    if not keep: sections.remove(sec)
    if record:
        path.write_text(json.dumps(dict(sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))), indent=1) + "\n")


# ---------- source grouping ----------
# The edition reads by where content comes from; topics (paper.yaml sections) nest inside each source.
# Reading order: X first (it replaces the feed), then other long-form sources, Evergreen, the web, a small News
# section, and Funnies last.
SOURCES = [("x", "X"), ("substack", "Substack"), ("youtube", "YouTube"), ("evergreen", "Evergreen"),
           ("web", "Around the Web"), ("news", "News"), ("funnies", "Funnies"), ("private", "Odds & Ends")]


def is_x_url(u):
    return (urlparse(u or "").hostname or "").lower() in ("x.com", "www.x.com", "twitter.com", "mobile.twitter.com")


def is_x_item(it):
    """A post, a link to x.com, or a story/line whose sources are all X posts."""
    t = it.get("type", "story")
    if t == "post": return True
    if t == "link": return is_x_url(it.get("url"))
    srcs = it.get("sources") or []
    return bool(srcs) and all(is_x_url(s.get("url")) for s in srcs)


def item_source(sec, it):
    if sec.get("private"): return "private"
    if sec["id"] in ("substack", "youtube", "funnies", "evergreen", "news"): return sec["id"]
    if is_x_item(it): return "x"
    if sec.get("source_group"): return sec["source_group"]
    return {"link": "web"}.get(it.get("type", "story"), "news")


def by_source(sections):
    """[{id, title, subs: [section-with-only-that-source's-items + anchor]}], in SOURCES order. Front page stays apart."""
    parts = {}
    for sec in sections:
        if sec["id"] == "front":
            continue
        split = {}
        for it in sec["items"]:
            split.setdefault(item_source(sec, it), []).append(it)
        for src, items in split.items():
            sub = dict(sec, items=items, anchor=f"{src}-{sec['id']}" if sec["id"] != src else f"{src}-all")
            if sec.get("groups"):
                ids = {id(i) for i in items}
                sub["groups"] = [g2 for g2 in ({**g, "items": [i for i in g["items"] if id(i) in ids]} for g in sec["groups"]) if g2["items"]]
            parts.setdefault(src, []).append(sub)
    return [{"id": k, "title": t, "anchor": k, "subs": parts[k]} for k, t in SOURCES if k in parts]


def toc_entries(sections, parts):
    """Every anchor the contents block links to, in reading order."""
    out = [{"anchor": "front", "title": s["title"]} for s in sections if s["id"] == "front"]
    for p in parts:
        out.append({"anchor": p["anchor"], "title": p["title"]})
        if len(p["subs"]) > 1:
            out += [{"anchor": s["anchor"], "title": s["title"]} for s in p["subs"]]
    return out


def pdf_anchor_pages(pdf):
    """{anchor: page number} from the internal links of the contents block in a Chrome-made PDF."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return {}
    r = PdfReader(str(pdf))
    pages = {}
    for name, dest in (r.named_destinations or {}).items():
        try:
            pages[str(name).lstrip("/")] = r.get_destination_page_number(dest) + 1
        except Exception:
            pass
    return pages


def balance(items, n=2):
    """Split stories into n columns of similar height, keeping reading order."""
    cols, h = [[] for _ in range(n)], [0] * n
    for st in items:
        w = 140 + 1.7 * len(st.get("headline", "")) + len(st.get("summary", st.get("text", ""))) + (520 if st.get("image") else 0)
        i = h.index(min(h)); cols[i].append(st); h[i] += w
    return [c for c in cols if c]


def initials(name):
    parts = [p for p in re.split(r"\s+", name or "") if p and p[0].isalnum()]
    return ("".join(p[0] for p in parts[:2]) or "?").upper()


def short_host(url):
    return urlparse(url).netloc.replace("www.", "")


def excerpt(s, n=140):
    """Quoted-post preview: drop t.co links, collapse space, cut at a word near n chars."""
    s = " ".join(re.sub(r"https?://t\.co/\S+", "", s or "").split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def plain(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or ""))


def describe(paper, sections, date_long):
    lead = sections[0]["items"][0] if sections and sections[0]["items"] else {}
    others = [it.get("headline", "") for it in (sections[0]["items"][1:3] if sections else [])]
    d = f"{plain(lead.get('summary', ''))}"
    d = re.split(r"(?<=[.!?])\s", d)[0] + (" Also: " + "; ".join(others) + "." if others else "")
    return (d[:157].rsplit(" ", 1)[0] + "…") if len(d) > 158 else d


# ---------- recipes ----------
def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "custom"


def print_spec(paper, size):
    pr = paper.get("print") or {}
    return (pr.get("sizes") or {}).get(size) or {"small": {"target_sheets": [1, 2], "max_sheets": 2},
                                                 "medium": {"target_sheets": [4, 5], "max_sheets": 5},
                                                 "large": {"target_sheets": [6, 10], "max_sheets": 10}}[size]


def default_recipe(paper):
    """The paper's own settings, written as a recipe."""
    size = (paper.get("print") or {}).get("size", "medium")
    return {"recipe": 1, "name": f"Default ({paper['name']})", "paper": paper["slug"], "format": "print", "size": size,
            "pages": print_spec(paper, size)["max_sheets"] * 2,
            "sections": [{"id": c["id"], "max_items": c.get("max_items")} for c in paper["sections"] if c.get("enabled", True)],
            "accounts": []}


def apply_recipe(paper, r):
    """Return a copy of paper.yaml reshaped by a recipe: only the listed sections, in recipe order, with its caps."""
    import copy
    paper = copy.deepcopy(paper)
    by_id = {c["id"]: c for c in paper["sections"]}
    secs = []
    for e in r.get("sections") or []:
        e = {"id": e} if isinstance(e, str) else dict(e)
        if e["id"] not in by_id:
            print(f"  ! recipe section '{e['id']}' is not in paper.yaml; skipped"); continue
        c = dict(by_id[e["id"]], enabled=True)
        for k in ("max_items", "weight", "types", "title"):
            if e.get(k) is not None: c[k] = e[k]
        secs.append(c)
    paper["sections"] = secs
    size = r.get("size") or (paper.get("print") or {}).get("size", "medium")
    paper.setdefault("print", {})["size"] = size
    paper["recipe"] = {"name": r.get("name") or "Custom", "slug": r.get("slug") or slugify(r.get("name")),
                       "format": r.get("format", "print"), "pages": int(r.get("pages") or 0),
                       "accounts": {a.lower().lstrip("@") for a in (r.get("accounts") or [])}}
    return paper


def build_editor(site_cfg):
    """site/edit/: a static page that turns the default settings into a recipe. Section names only, never content."""
    papers = []
    for pdir in sorted(p for p in PAPERS.iterdir() if (p / "paper.yaml").exists()):
        paper = load_yaml(pdir / "paper.yaml")
        if not paper.get("public"):
            continue
        papers.append({"slug": paper["slug"], "name": paper["name"], "default": default_recipe(paper),
                       "sizes": list(((paper.get("print") or {}).get("sizes") or PRINT_TYPE).keys()),
                       "sections": [{"id": c["id"], "title": c["title"], "max_items": c.get("max_items"),
                                     "private": bool(c.get("private")), "kind": c.get("source") or SOURCE_KIND.get(c["id"], "")}
                                    for c in paper["sections"]]})
    presets = []
    for f in sorted(RECIPES.glob("*.yaml")):
        r = load_yaml(f)
        if r.get("preset"):
            presets.append({k: r.get(k) for k in ("name", "paper", "format", "size", "pages", "sections", "accounts")})
    presets.sort(key=lambda r: (not r["name"].startswith("Default"), r["name"]))
    data = json.dumps({"papers": papers, "presets": presets}, ensure_ascii=False).replace("</", "<\\/")
    out = SITE / "edit"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(env().get_template("edit.html.j2").render(
        site=site_cfg, base=public_base(site_cfg.get("web_base", "")), root="../", url_path="/edit/", data=Markup(data)))
    print(f"editor: site/edit/index.html ({len(presets)} presets)")


# ---------- rendering ----------
def env():
    e = Environment(loader=FileSystemLoader(TPL), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    e.filters.update(by_source=by_source, balance=balance, initials=initials, host=short_host, plain=plain, excerpt=excerpt)
    return e


def render_pdf(html_path, pdf_path):
    subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=10000",
                    f"--print-to-pdf={pdf_path}", html_path.as_uri()], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def page_count(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    m = re.search(r"Pages:\s+(\d+)", out)
    return int(m.group(1)) if m else -1


def make_qr(url, dest):
    import qrcode, qrcode.image.svg
    qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1).save(str(dest))
    return dest


def trim_lowest(sections):
    """Drop the last item of the lowest-weight section that still has more than one item (front is never trimmed)."""
    cands = [s for s in sections if s["id"] != "front" and len(s["items"]) > 1]
    if not cands:
        cands = [s for s in sections if s["id"] != "front"]
    if not cands:
        return None
    s = min(cands, key=lambda s: (s.get("weight", 5), -sections.index(s)))
    it = s["items"].pop()
    for g in s.get("groups", []):
        if it in g["items"]: g["items"].remove(it)
    s["groups"] = [g for g in s.get("groups", []) if g["items"]] if "groups" in s else None
    if s["groups"] is None: s.pop("groups")
    if not s["items"]: sections.remove(s)
    return f"{s['id']}: {' '.join((it.get('headline') or it.get('title') or it.get('text', '')[:40]).split())}"


def build_edition(slug, date, refresh_weather=False, size=None, site_cfg=None, private=False, recipe=None):
    """private=False: the public build into site/. private=True: full copy into site-private/ (local only).
    recipe: an on-demand edition (dict) built from the same edition.json into site/<slug>/custom/<recipe>/<date>/."""
    site_dir = PRIVATE_SITE if private else SITE
    pdir = PAPERS / slug
    paper = load_yaml(pdir / "paper.yaml")
    if recipe:
        paper = apply_recipe(paper, recipe)
    rc = paper.get("recipe")
    sun = paper.get("sunday")
    if sun and not rc and datetime.date.fromisoformat(date).weekday() == 6:
        size = size or sun.get("size")      # Sunday: the bigger paper, with its extra sections switched on
        for c in paper["sections"]:
            if c["id"] in (sun.get("enable") or []): c["enabled"] = True
    ed_dir = pdir / "editions" / date
    ed = json.loads((ed_dir / "edition.json").read_text())
    size = size or (paper.get("print") or {}).get("size", "medium")
    d = datetime.date.fromisoformat(date)
    date_long = d.strftime("%A, %B %-d, %Y")
    print(f"{paper['name']} {date}{' · ' + rc['name'] if rc else ''} ({size}, {'private copy' if private else 'public'})")
    fb = feedback_summary(slug)
    print(f"  feedback: {fb['files']} file(s), {len(fb['more_like_this'])} more-like-this, {len(fb['skipped'])} skips")

    sections = assemble(paper, ed, size, private)
    apply_selection(sections, paper)
    apply_evergreen(sections, paper, date, record=not private and not rc)
    if not sections:
        sys.exit("  edition has no content in enabled sections")
    if not private:
        check_public(sections)
    out = site_dir / slug / "custom" / rc["slug"] / date if rc else site_dir / slug / date
    if out.exists(): shutil.rmtree(out)
    (out / "images").mkdir(parents=True)
    for sec in sections:
        for it in sec["items"]:
            img = it.get("image")
            if img and img.get("file"):
                src = ed_dir / img["file"]
                if src.exists():
                    shutil.copy(src, out / "images" / src.name)
                    img["web"] = f"images/{src.name}"
                    img["abs"] = src.resolve().as_uri()
                else:
                    print(f"  ! missing image {src}"); it.pop("image")

    base = "" if private else public_base(site_cfg.get("web_base", ""))
    url_path = f"/{slug}/custom/{rc['slug']}/{date}/" if rc else f"/{slug}/{date}/"
    stem = f"{slug}-{rc['slug']}-{date}" if rc else f"{slug}-{date}"
    pdfs = {"print": f"{stem}-print.pdf", "digital": f"{stem}-digital.pdf"}
    lead = sections[0]["items"][0]
    lead_title = lead.get("headline") or lead.get("title") or (f"{lead['author']} on X" if lead.get("author") else "")
    ctx = dict(paper=paper, site=site_cfg, private_copy=private, date=date, date_long=date_long, date_short=d.strftime("%b %-d, %Y"),
               note=rc["name"] if rc else ed.get("note", ""), coverage=ed.get("coverage", ""), weather=weather(paper, ed_dir, refresh_weather),
               base=base, url_path=url_path, pdfs=pdfs,
               title=f"{paper['name']} · {d.strftime('%B %-d, %Y')}: {lead_title or (rc or {}).get('name', '')}",
               noindex=bool(rc), home="../../../" if rc else "../", edition_key=f"{date}~{rc['slug']}" if rc else date,
               description=ed.get("description") or describe(paper, sections, date_long))
    E = env()

    # print + digital PDFs
    CACHE.mkdir(exist_ok=True)
    work = CACHE / ("private" if private else "public") / slug / date
    work.mkdir(parents=True, exist_ok=True)
    qr = None
    if base and (paper.get("print") or {}).get("qr", True):
        qr = make_qr(base + url_path, work / "qr.svg").resolve().as_uri()
    spec = print_spec(paper, size)
    import copy
    psecs = copy.deepcopy(sections)
    pages = {}
    # Daily build: the print PDF is trimmed to max_sheets; web and digital keep everything.
    # Recipe build: the primary format (print or digital) is trimmed to `pages`, and every output uses that cut.
    first = "digital" if rc and rc["format"] == "web" else "print"
    max_pages = (rc and rc["pages"]) or spec["max_sheets"] * 2
    if rc: sections = psecs
    for kind in (first, "digital" if first == "print" else "print"):
        trimmed = []
        pdf = out / pdfs[kind]

        def render(sheets=0, pad=False, toc_pages=None):
            h = E.get_template("print.html.j2").render(ctx, sections=psecs if kind == "print" else sections, mode=kind,
                                                       pt=PRINT_TYPE[size] + (0.6 if kind == "digital" else 0),
                                                       static=STATIC.resolve().as_uri(), qr=qr, sheets=sheets, pad=pad,
                                                       toc_pages=toc_pages or {})
            hp = work / f"{kind}.html"
            hp.write_text(h)
            render_pdf(hp, pdf)
            return page_count(pdf)
        while True:
            n = render()
            if kind != first or n <= max_pages:
                break
            t = trim_lowest(psecs)
            if not t: break
            trimmed.append(t)
        # Final pass(es): contents page numbers read back from the PDF's own anchors; print also gets the
        # real sheet count in the duplex footer, plus one blank back when odd.
        pad = kind == "print" and n % 2 == 1
        nsheets = (n + 1) // 2 if kind == "print" else 0
        tp = pdf_anchor_pages(pdf)
        for _ in range(2):
            n = render(nsheets, pad, tp)
            again = pdf_anchor_pages(pdf)
            if again == tp: break
            tp = again
        if kind == "print" and n % 2: print(f"  ! print came out at {n} pages after padding")
        pages[kind] = n
        sheets = (n + 1) // 2
        msg = f"  {kind}: {pdf.relative_to(ROOT)}  {n} pages" + (" (last back blank)" if kind == "print" and pad else "")
        if kind == "print" and not rc:
            lo, hi = spec["target_sheets"]
            msg += f" = {sheets} sheet(s) duplex; {size} target {lo}-{hi} sheets, max {spec['max_sheets']}"
            if sheets < lo: msg += "  (thin edition: under target, not padded)"
        if rc and kind == first:
            msg += f"; recipe max {max_pages} pages" + ("  (under, not padded)" if n < max_pages else "")
        if trimmed: msg += f"\n    trimmed to fit: " + "; ".join(trimmed)
        print(msg)
        subprocess.run(["pdftoppm", "-r", "90", "-f", "1", "-l", "1", "-png", "-singlefile", str(pdf),
                        str(work / f"{kind}-p1")], check=True)

    # web edition
    (out / "index.html").write_text(E.get_template("edition.html.j2").render(ctx, sections=sections, root="../../../../" if rc else "../../", pages=pages))
    meta = {"date": date, "date_long": date_long, "lead": lead_title, "pages": pages,
            "pdfs": pdfs, "sections": [s["title"] for s in sections], "recipe": rc["name"] if rc else None, "built_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    (out / "edition.meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(f"  web: {(out / 'index.html').relative_to(ROOT)}  sections: {', '.join(meta['sections'])}")
    if rc: print(f"  pdf: {(out / pdfs[first]).resolve()}")
    return meta


def write_latest(pdir, ed, base, slug):
    """site/<slug>/latest/: stable URLs for the newest daily edition, for a scheduled printer job.
    print.pdf and digital.pdf are copies (GitHub Pages has no redirects for binaries); latest.json names the date."""
    d = pdir / "latest"
    if d.exists(): shutil.rmtree(d)
    d.mkdir()
    src = pdir / ed["date"]
    for kind in ("print", "digital"):
        f = src / ed["pdfs"][kind]
        if f.exists(): shutil.copy(f, d / f"{kind}.pdf")
    info = {"format": "mediabot-latest/1", "paper": slug, "date": ed["date"], "date_long": ed["date_long"],
            "pages": ed.get("pages", {}), "built_at": ed.get("built_at"),
            "edition": f"../{ed['date']}/", "print_pdf": "print.pdf", "digital_pdf": "digital.pdf",
            "edition_print_pdf": f"../{ed['date']}/{ed['pdfs']['print']}"}
    if base:
        info["absolute"] = {"edition": f"{base}/{slug}/{ed['date']}/", "print_pdf": f"{base}/{slug}/latest/print.pdf",
                            "digital_pdf": f"{base}/{slug}/latest/digital.pdf"}
    (d / "latest.json").write_text(json.dumps(info, indent=1, ensure_ascii=False) + "\n")
    (d / "index.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex">'
        f'<meta http-equiv="refresh" content="0; url=../{ed["date"]}/"><title>Latest edition</title>'
        f'<link rel="canonical" href="../{ed["date"]}/"></head><body><p><a href="../{ed["date"]}/">'
        f'{html.escape(ed["date_long"])}</a> · <a href="print.pdf">Print PDF</a></p></body></html>\n')


def build_indexes(site_cfg, private=False):
    E = env()
    SITE = PRIVATE_SITE if private else globals()["SITE"]
    base = "" if private else public_base(site_cfg.get("web_base", ""))
    SITE.mkdir(exist_ok=True)
    if (SITE / "assets").exists(): shutil.rmtree(SITE / "assets")
    shutil.copytree(STATIC, SITE / "assets")
    listed, urls = [], []
    for pdir in sorted(p for p in PAPERS.iterdir() if (p / "paper.yaml").exists()):
        paper = load_yaml(pdir / "paper.yaml")
        slug = paper["slug"]
        eds = []
        for m in sorted((SITE / slug).glob("*/edition.meta.json"), reverse=True):
            eds.append(json.loads(m.read_text()))
        if not eds:
            continue
        (SITE / slug / "index.html").write_text(E.get_template("paper.html.j2").render(
            paper=paper, site=site_cfg, editions=eds, base=base, root="../", url_path=f"/{slug}/", private_copy=private))
        if not private:
            write_latest(SITE / slug, eds[0], base, slug)
        if paper.get("public") or private:
            listed.append({"paper": paper, "latest": eds[0]})
            urls += [f"/{slug}/"] + [f"/{slug}/{e['date']}/" for e in eds]
    (SITE / "index.html").write_text(E.get_template("root.html.j2").render(site=site_cfg, papers=listed, base=base, root="", url_path="/", private_copy=private))
    if private:
        (SITE / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
        print("indexes: site-private/ (local only)")
        return
    robots = "User-agent: *\nAllow: /\n"
    sm = SITE / "sitemap.xml"
    if base:
        sm.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                      + "".join(f"  <url><loc>{base}{u}</loc></url>\n" for u in ["/"] + urls) + "</urlset>\n")
        robots += f"Sitemap: {base}/sitemap.xml\n"
    elif sm.exists():
        sm.unlink()
    (SITE / "robots.txt").write_text(robots)
    (SITE / ".nojekyll").write_text("")
    build_editor(site_cfg)
    print(f"indexes: site/index.html ({len(listed)} public paper(s))")


def main(argv):
    site_cfg = load_yaml(ROOT / "site.yaml")
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]
    size = None
    if "--size" in argv:
        size = argv[argv.index("--size") + 1]; args.remove(size)
    recipe = None
    if "--recipe" in argv:
        rp = argv[argv.index("--recipe") + 1]; args.remove(rp)
        recipe = load_yaml(rp)
        recipe["slug"] = slugify(recipe.get("slug") or Path(rp).stem)
        if not args or not (PAPERS / args[0]).is_dir():
            args.insert(0, recipe.get("paper") or "signal-seeker")
    if "--editor" in flags:
        build_editor(site_cfg); return
    if "--web-base" in argv:
        wb = argv[argv.index("--web-base") + 1]; args.remove(wb); site_cfg["web_base"] = wb
    if "--index" not in flags:
        if len(args) < 1:
            sys.exit(__doc__)
        slug = args[0]
        date = args[1] if len(args) > 1 else datetime.date.today().isoformat()
        if not (PAPERS / slug / "editions" / date / "edition.json").exists():
            sys.exit(f"no edition at papers/{slug}/editions/{date}/edition.json")
        build_edition(slug, date, "--weather" in flags, size, site_cfg, recipe=recipe)
        if "--public-only" not in flags:
            build_edition(slug, date, False, size, site_cfg, private=True, recipe=recipe)
        if recipe:
            return          # on-demand editions are not listed in the indexes
    build_indexes(site_cfg)
    if "--public-only" not in flags:
        build_indexes(site_cfg, private=True)


if __name__ == "__main__":
    main(sys.argv[1:])
