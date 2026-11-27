#!/usr/bin/env python3
"""Pictures for an edition: real, credited images that belong to the source, nothing generated.

    .venv/bin/python tools/media.py signal-seeker 2026-11-27 /tmp/feed/p*.json /tmp/media/*.json   # dry run: print the pick
    ... --write                       download, shrink and attach the pick to edition.json (run BEFORE build.py)
    ... --list-missing                print X post ids in the edition that no dump has media info for (look them up
                                      with get_posts_by_ids, save the reply, pass it as another dump, rerun)
    ... --no-web                      skip article og:image lookups (X media only)

Where images come from (only these):
  * X post media. Photos use the media `url`; videos and GIFs use `preview_image_url` (a still, credited as a video
    still). Input is any raw reply of the read-only X tools saved outside the repo (timeline, search, Lists,
    get_posts_by_ids), one file per page. For the media to be in a reply ask for
        expansions=attachments.media_keys   media.fields=type,url,preview_image_url,alt_text,width,height
    The post's id is the key: story items whose first source is an x.com status link use the same media.
  * The article's own `og:image` (or twitter:image) for a story/long read whose source is a web page. Fetched
    from the page itself; a site that refuses the fetch, or has no usable image, simply gets no picture.
No image is ever made up, searched for elsewhere, or taken from an unrelated page. An item without one gets none.

Taste (papers/<slug>/paper.yaml `images:`): max_total pictures per edition, per_section (max per section), no two
pictures back to back in a section, the lead item first, then photos, then article images, then video stills.
Too-small images, logos/icons, extreme crops and the same picture on several items (a site's default share image)
are dropped. At most max_video_stills (default 1) video stills, since a still is sometimes only a title card.
print_max of the picks also get a small grayscale copy for the print PDF.

Output (idempotent; rerun replaces the earlier pick, never touching hand-set images, comics or funny posts):
  papers/<slug>/editions/<date>/images/<id>.jpg        color, at most 1200px wide (lead) / 960px, JPEG q80, EXIF stripped
  papers/<slug>/editions/<date>/images/<id>-print.jpg  grayscale, at most 640px wide, q72 (only for print_max picks)
  edition.json item["image"] = {"file","credit","alt","w","h","kind","auto":true,["print_file"],["lead"]}
build.py copies the folder into the published edition. Read-only toward X; the only network is image/page fetches.
"""
import hashlib, io, ipaddress, json, re, socket, sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 MediaBot/1.0 (personal paper)"
MAX_BYTES = 12_000_000
DEFAULTS = {"enabled": True, "max_total": 8, "per_section": 2, "print_max": 2, "lead_width": 1200, "width": 960,
            "print_width": 640, "min_width": 600, "x_min_width": 400, "min_ratio": 0.7, "max_ratio": 2.6,
            "web": True, "video_stills": True, "max_video_stills": 1, "sections": None}
LOGO = re.compile(r"(logo|favicon|icon|sprite|avatar|default|placeholder|blank|pixel|badge|wordmark|brand)", re.I)
FAKE_IP = ipaddress.ip_network("198.18.0.0/15")
STATUS = re.compile(r"(?:x|twitter)\.com/([^/\"\s]+)/status/(\d+)")


def load_yaml(p):
    import yaml
    return yaml.safe_load(Path(p).read_text())


def unwrap(d):
    return d["result"] if "data" not in d and isinstance(d.get("result"), dict) else d


def read_dumps(files):
    """tweet id -> {media: [media objects in attachment order], handle}. Understands timeline/search/lookup replies."""
    media, posts, users = {}, {}, {}
    for f in files:
        try:
            d = unwrap(json.loads(Path(f).read_text()))
        except Exception as e:
            print(f"  ! {f}: not readable ({e})"); continue
        inc = d.get("includes") or {}
        for m in inc.get("media", []) + d.get("media", []): media[m.get("media_key")] = m
        for u in inc.get("users", []) + d.get("users", []): users[u["id"]] = u
        rows = d.get("data") or []
        rows = [rows] if isinstance(rows, dict) else rows
        for t in rows + inc.get("posts", []) + inc.get("tweets", []) + d.get("posts", []) + d.get("tweets", []):
            if isinstance(t, dict) and t.get("id") and (t.get("attachments") or t["id"] not in posts):
                posts[t["id"]] = t
    out = {}
    for pid, t in posts.items():
        keys = (t.get("attachments") or {}).get("media_keys") or []
        out[pid] = {"media": [media[k] for k in keys if k in media], "known": True,
                    "handle": (users.get(t.get("author_id")) or {}).get("username")}
    return out


def x_pick(entry, cfg):
    """The best still of a post's own media: the first photo, else the first video/GIF preview."""
    if not entry: return None
    for m in entry["media"]:
        if m.get("type") == "photo" and m.get("url"):
            u = m["url"]
            if "pbs.twimg.com/media/" in u and "?" not in u: u += "?name=large"
            return {"url": u, "kind": "photo", "alt": (m.get("alt_text") or "").strip(), "n": len(entry["media"]),
                    "w": m.get("width"), "h": m.get("height")}
    if cfg["video_stills"]:
        for m in entry["media"]:
            if m.get("type") in ("video", "animated_gif") and m.get("preview_image_url"):
                return {"url": m["preview_image_url"], "kind": "video", "alt": (m.get("alt_text") or "").strip(), "n": len(entry["media"]),
                        "w": m.get("width"), "h": m.get("height")}
    return None


def safe_url(u):
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.hostname: return False
    try:
        for ai in socket.getaddrinfo(p.hostname, None):
            ip = ipaddress.ip_address(ai[4][0])
            if ip in FAKE_IP: continue          # 198.18.0.0/15: some sandboxes' DNS proxies answer with it
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved: return False
    except Exception:
        return False
    return True


def fetch(u, limit=MAX_BYTES, timeout=20, accept="*/*"):
    if not safe_url(u): raise ValueError("blocked url")
    with urlopen(Request(u, headers={"User-Agent": UA, "Accept": accept}), timeout=timeout) as r:
        data = r.read(limit + 1)
        if len(data) > limit: raise ValueError("too large")
        return data, r.headers.get("content-type", ""), r.geturl()


class Meta(HTMLParser):
    def __init__(self):
        super().__init__(); self.m = {}; self.title = ""; self._t = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            k = (a.get("property") or a.get("name") or "").lower()
            if k and a.get("content") and k not in self.m: self.m[k] = a["content"].strip()
        elif tag == "title": self._t = True
    def handle_data(self, d):
        if self._t: self.title += d
    def handle_endtag(self, tag):
        if tag == "title": self._t = False


def og_pick(url):
    data, ctype, final = fetch(url, limit=2_500_000, timeout=15, accept="text/html,application/xhtml+xml")
    if "html" not in ctype.lower() and b"<html" not in data[:2000].lower(): return None
    p = Meta(); p.feed(data.decode("utf-8", "replace"))
    m = p.m
    src = m.get("og:image:secure_url") or m.get("og:image") or m.get("twitter:image") or m.get("twitter:image:src")
    if not src or LOGO.search(Path(urlparse(src).path).name): return None
    return {"url": urljoin(final, src), "kind": "og", "alt": (m.get("og:image:alt") or m.get("twitter:image:alt") or "").strip(),
            "site": (m.get("og:site_name") or "").strip()}


def status_of(item):
    """(handle, status id) for a post item, or for a story whose first source is an x.com status."""
    if item.get("type") == "post" or item.get("type") == "funnypost":
        m = STATUS.search(item.get("url", ""))
        return (m.group(1), m.group(2)) if m else (item.get("handle"), None)
    for s in item.get("sources") or []:
        m = STATUS.search(s.get("url", ""))
        if m: return m.group(1), m.group(2)
        break
    return None, None


def web_url(item):
    if item.get("type") in ("story", "evergreen", "link"):
        urls = [item.get("url")] if item.get("url") else [s.get("url") for s in item.get("sources") or []][:1]
        for u in urls:
            if u and not STATUS.search(u) and u.startswith("http"): return u
    return None


def ahash(img):
    g = img.convert("L").resize((8, 8))
    px = list(g.tobytes()); avg = sum(px) / 64
    return "".join("1" if p > avg else "0" for p in px)


def process(raw, width, print_width, make_print):
    """Decode, drop EXIF/alpha, resize, recompress. Returns (jpeg bytes, w, h, print jpeg bytes or None, ahash) or None."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        sys.exit("Pillow is missing: .venv/bin/pip install -r requirements.txt")
    img = Image.open(io.BytesIO(raw)); img.load()
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA"); bg = Image.new("RGB", img.size, "white"); bg.paste(img, mask=img.split()[-1]); img = bg
    img = img.convert("RGB")
    w0, h0 = img.size
    h = ahash(img)
    def shrink(im, w):
        if im.width > w: im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
        return im
    big = shrink(img, width)
    b = io.BytesIO(); big.save(b, "JPEG", quality=80, optimize=True, progressive=True)
    pb = None
    if make_print:
        g = ImageOps.autocontrast(shrink(img, print_width).convert("L"), cutoff=1)
        q = io.BytesIO(); g.save(q, "JPEG", quality=72, optimize=True); pb = q.getvalue()
    return b.getvalue(), big.width, big.height, pb, h, (w0, h0)


def slug_id(i):
    return re.sub(r"[^A-Za-z0-9_-]+", "-", i).strip("-")[:60] or hashlib.md5(i.encode()).hexdigest()[:10]


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    write, list_missing, no_web = "--write" in argv, "--list-missing" in argv, "--no-web" in argv
    if len(args) < 2: sys.exit(__doc__)
    slug, date, dumps = args[0], args[1], args[2:]
    pdir = ROOT / "papers" / slug
    paper = load_yaml(pdir / "paper.yaml")
    cfg = dict(DEFAULTS, **(paper.get("images") or {}))
    ep = pdir / "editions" / date / "edition.json"
    ed = json.loads(ep.read_text())
    img_dir = ep.parent / "images"
    if not cfg["enabled"]:
        print("images are off in paper.yaml"); return
    xmedia = read_dumps(dumps)

    # Drop the last automatic pick (and its files); hand-set images stay.
    for sec in ed["sections"]:
        for it in sec["items"]:
            if (it.get("image") or {}).get("auto"):
                for k in ("file", "print_file"):
                    f = it["image"].get(k)
                    if f and (ep.parent / f).exists() and write: (ep.parent / f).unlink()
                it.pop("image")
    seen_ids = {}
    for sec in ed["sections"]:
        for it in sec["items"]:
            for m in STATUS.finditer(json.dumps({k: it.get(k) for k in ("url", "sources")})): seen_ids[m.group(2)] = True
    if list_missing:
        miss = [i for i in seen_ids if i not in xmedia]
        print(",".join(miss) if miss else "(none: every X post in the edition is covered)")
        print(f"{len(miss)} of {len(seen_ids)} X post ids have no media info", file=sys.stderr); return

    allowed = cfg["sections"]
    order = [s for s in ed["sections"] if s["id"] != "passage" and (not allowed or s["id"] in allowed)]
    cands, lead_item = [], None
    for si, sec in enumerate(order):
        for ii, it in enumerate(sec["items"]):
            if it.get("type") in ("comic", "funnypost", "joke", "sudoku", "wordsearch", "mathq", "wason", "crossword", "riddle", "passage", "line"):
                continue
            if it.get("image"): continue
            handle, pid = status_of(it)
            lead = (si == 0 and ii == 0)
            pick = None
            if pid and pid in xmedia: pick = x_pick(xmedia[pid], cfg)
            if not pick and it.get("image_url"):          # x_feed.py kept a photo url on the item
                pick = {"url": it["image_url"], "kind": "photo", "alt": it.get("image_alt", ""), "n": 1}
            if pick:
                credit_src = f"@{handle}" if handle else "X"
                cands.append(dict(sec=sec["id"], si=si, ii=ii, item=it, pick=pick, lead=lead, handle=handle,
                                  credit=("Video still: " if pick["kind"] == "video" else "Photo: ") + credit_src))
            elif cfg["web"] and not no_web and (u := web_url(it)):
                cands.append(dict(sec=sec["id"], si=si, ii=ii, item=it, pick=None, web=u, lead=lead, handle=handle, credit=None))
    print(f"{slug} {date}: {len(cands)} items could carry a picture "
          f"({sum(1 for c in cands if c['pick'] and c['pick']['kind']=='photo')} X photos, "
          f"{sum(1 for c in cands if c['pick'] and c['pick']['kind']=='video')} video stills, "
          f"{sum(1 for c in cands if not c['pick'])} article pages to check)")

    def base_score(c):
        k = c["pick"]["kind"] if c["pick"] else "og"
        s = {"photo": 6, "og": 4, "video": 3}[k]
        if c["pick"] and c["pick"].get("alt"): s += 0.5
        if c["pick"] and (c["pick"].get("w") or 0) >= 1000: s += 0.5
        if c["lead"]: s += 10
        return s
    cands.sort(key=lambda c: -base_score(c))

    chosen, per_sec, used_hash, tried = [], {}, {}, 0
    taken = set()          # (section, index) of picked items: no two back to back
    for c in cands:
        if len(chosen) >= cfg["max_total"]: break
        if per_sec.get(c["sec"], 0) >= cfg["per_section"] and not c["lead"]: continue
        if c["pick"] and c["pick"]["kind"] == "video" and sum(1 for k in chosen if k["kind"] == "video") >= cfg["max_video_stills"]: continue
        if not c["lead"] and ((c["sec"], c["ii"] - 1) in taken or (c["sec"], c["ii"] + 1) in taken): continue
        pk = c["pick"]
        try:
            if pk is None:
                tried += 1
                pk = og_pick(c["web"])
                if not pk: print(f"  - {c['item'].get('id')}: no usable og:image on {urlparse(c['web']).hostname}"); continue
            raw, ctype, _ = fetch(pk["url"], accept="image/*")
            lead = c["lead"]
            res = process(raw, cfg["lead_width"] if lead else cfg["width"], cfg["print_width"], True)
        except Exception as e:
            print(f"  - {c['item'].get('id')}: picture skipped ({type(e).__name__}: {e})"); continue
        jpg, w, h, pjpg, ah, (w0, h0) = res
        minw = cfg["x_min_width"] if pk["kind"] in ("photo", "video") else cfg["min_width"]
        ratio = w0 / h0
        if w0 < minw: print(f"  - {c['item'].get('id')}: too small ({w0}px)"); continue
        if not (cfg["min_ratio"] <= ratio <= cfg["max_ratio"]): print(f"  - {c['item'].get('id')}: odd shape ({w0}x{h0})"); continue
        if ah in used_hash:
            print(f"  - {c['item'].get('id')}: same picture as {used_hash[ah]} (a default share image?)"); continue
        used_hash[ah] = c["item"].get("id")
        if pk["kind"] == "og":
            site = pk.get("site") or ((c["item"].get("sources") or [{}])[0].get("name")) or urlparse(c["web"]).hostname.removeprefix("www.")
            title = c["item"].get("headline") or c["item"].get("title") or ""
            c["credit"] = f"Image: {site}"
            alt = pk["alt"] or f"Image from {site}’s article “{title}”"
        else:
            who = f"@{c['handle']}" if c["handle"] else "the post"
            alt = pk["alt"] or (f"Video still from {who}’s post" if pk["kind"] == "video" else
                                f"Photo from {who}’s post" + (f" (first of {pk['n']})" if pk.get("n", 1) > 1 else ""))
        c.update(jpg=jpg, w=w, h=h, pjpg=pjpg, alt=alt, kind=pk["kind"], src=pk["url"])
        chosen.append(c); per_sec[c["sec"]] = per_sec.get(c["sec"], 0) + 1; taken.add((c["sec"], c["ii"]))
    # print picks: the best print_max (lead first)
    chosen_sorted = sorted(chosen, key=lambda c: -base_score(c))
    for k, c in enumerate(chosen_sorted): c["print"] = k < cfg["print_max"]
    total = 0
    print(f"\npicked {len(chosen)} (max {cfg['max_total']}):")
    for c in sorted(chosen, key=lambda c: (c["si"], c["ii"])):
        n = slug_id(c["item"]["id"])
        total += len(c["jpg"]) + (len(c["pjpg"]) if c["print"] else 0)
        print(f"  {c['sec']:<10} {c['item']['id'][:34]:<34} {c['kind']:<5} {c['w']}x{c['h']} {len(c['jpg'])//1024} KB"
              f"{' +print ' + str(len(c['pjpg'])//1024) + ' KB' if c['print'] else ''}{'  LEAD' if c['lead'] else ''}  [{c['credit']}]")
        if write:
            img_dir.mkdir(exist_ok=True)
            (img_dir / f"{n}.jpg").write_bytes(c["jpg"])
            im = {"file": f"images/{n}.jpg", "credit": c["credit"], "alt": c["alt"], "w": c["w"], "h": c["h"], "kind": c["kind"], "auto": True}
            if c["print"]:
                (img_dir / f"{n}-print.jpg").write_bytes(c["pjpg"]); im["print_file"] = f"images/{n}-print.jpg"
            if c["lead"]: im["lead"] = True
            c["item"]["image"] = im
    print(f"total image bytes: {total/1024/1024:.2f} MB")
    if write:
        ep.write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n")
        print(f"wrote {len(chosen)} images to {img_dir.relative_to(ROOT)} and edition.json")
    else:
        print("(dry run: nothing downloaded to the repo; add --write)")


if __name__ == "__main__":
    main(sys.argv[1:])
