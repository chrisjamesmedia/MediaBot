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
        papers/<slug>/feedback/summary.json
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
SOURCE_KIND = {"front": "News", "x": "X", "goats": "X", "investments": "X + News", "holdings": "News",
               "tech": "X + News", "reading": "X", "business": "News", "science": "News", "local": "News",
               "bigstuff": "News", "worth": "Web", "substack": "Substack", "youtube": "YouTube",
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
    d, c = data["daily"], data["current"]
    fetched = datetime.datetime.fromisoformat(data["fetched_at"])
    if w.get("timezone"):
        from zoneinfo import ZoneInfo
        fetched = fetched.astimezone(ZoneInfo(w["timezone"]))
    days = []
    for i in (1, 2):
        dt = datetime.date.fromisoformat(d["time"][i])
        days.append({"name": dt.strftime("%a"), "hi": round(d["temperature_2m_max"][i]), "lo": round(d["temperature_2m_min"][i]),
                     "cond": WMO.get(d["weather_code"][i], ""), "icon": icon_kind(d["weather_code"][i])})
    cond = WMO.get(c["weather_code"], "")
    if c.get("is_day") and cond in ("Clear", "Mostly clear"):
        cond = cond.replace("clear", "sunny").replace("Clear", "Sunny")
    t = fetched.strftime("%-I:%M %p").replace("AM", "a.m.").replace("PM", "p.m.")
    return {"ok": True, "label": w.get("label", ""), "now": round(c["temperature_2m"]), "cond": cond,
            "icon": icon_kind(c["weather_code"]), "hi": round(d["temperature_2m_max"][0]), "lo": round(d["temperature_2m_min"][0]),
            "days": days, "asof": t, "asof_full": fetched.strftime("%b %-d, %-I:%M %p %Z").strip()}


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
        if cfg.get("dedupe"):
            before = len(items)
            items = [it for it in items if not (item_urls(it) & seen)]
            if before - len(items):
                print(f"  {cfg['id']}: dropped {before - len(items)} of {before} links already in the paper")
        if cfg.get("max_items") and len(items) > cfg["max_items"]:
            print(f"  {cfg['id']}: {len(items)} items, trimmed to max_items {cfg['max_items']}")
            items = items[:cfg["max_items"]]
        for it in items:
            seen |= item_urls(it)
            if it.get("type", "story") == "post" and it.get("date"):
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
    e.filters.update(balance=balance, initials=initials, host=short_host, plain=plain, excerpt=excerpt)
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
    ctx = dict(paper=paper, site=site_cfg, private_copy=private, date=date, date_long=date_long, date_short=d.strftime("%b %-d, %Y"),
               note=rc["name"] if rc else ed.get("note", ""), coverage=ed.get("coverage", ""), weather=weather(paper, ed_dir, refresh_weather),
               base=base, url_path=url_path, pdfs=pdfs,
               title=f"{paper['name']} · {d.strftime('%B %-d, %Y')}: {lead.get('headline') or (rc or {}).get('name', '')}",
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

        def render(sheets=0, pad=False):
            h = E.get_template("print.html.j2").render(ctx, sections=psecs if kind == "print" else sections, mode=kind,
                                                       pt=PRINT_TYPE[size] + (0.6 if kind == "digital" else 0),
                                                       static=STATIC.resolve().as_uri(), qr=qr, sheets=sheets, pad=pad)
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
        if kind == "print":
            # Duplex: second pass with the real sheet count in the footer, plus one blank back when odd.
            pad = n % 2 == 1
            n = render((n + 1) // 2, pad)
            if n % 2: print(f"  ! print came out at {n} pages after padding")
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
    meta = {"date": date, "date_long": date_long, "lead": lead.get("headline", ""), "pages": pages,
            "pdfs": pdfs, "sections": [s["title"] for s in sections], "recipe": rc["name"] if rc else None, "built_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    (out / "edition.meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(f"  web: {(out / 'index.html').relative_to(ROOT)}  sections: {', '.join(meta['sections'])}")
    if rc: print(f"  pdf: {(out / pdfs[first]).resolve()}")
    return meta


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
