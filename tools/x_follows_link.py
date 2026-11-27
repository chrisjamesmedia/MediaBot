#!/usr/bin/env python3
"""Make a private MediaBot import link (and a plain file) from a list of X follows. Nothing here is published.

  python3 tools/x_follows_link.py <follows.json> <out-dir> [--base https://chrisjamesmedia.github.io/MediaBot] [--me handle] [--group group.json]

--group: optional preselected group, {"group":[{"handle","name","followers","weight":1|2|3, ...}]}. Each row gets a flag for
whether the reader already follows it (checked against <follows.json>). The first row is shown first.

<follows.json> is either {"follows":[{"handle","name","followers","bucket"}]} (see docs/x-import.md) or a raw X API
reply {"data":[{"username","name","public_metrics"}]}. Writes into <out-dir> (keep it OUTSIDE the repo):
  x-follows-link.txt                 the one-tap link:  <base>/start/#xf=z<base64url(deflate-raw JSON)>
  mediabot-x-follows-import.json     the same data as a file for the "Choose a file" option
The part after # is a URL fragment: browsers never send it to a server.
"""
import base64, json, sys, zlib, pathlib

BUCKETS = {"ai_tech": 0, "investing": 1, "science_health": 2, "culture": 3, "other": 4}

def rows(doc):
    if "follows" in doc:
        return [[u["handle"], u.get("name", ""), int(u.get("followers") or 0), BUCKETS.get(u.get("bucket"), 4)] for u in doc["follows"]]
    return [[u["username"], u.get("name", ""), int((u.get("public_metrics") or {}).get("followers_count") or 0), 4] for u in doc["data"]]

def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    opt = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
    if len(args) < 2:
        print(__doc__); return 2
    doc = json.load(open(args[0])); out = pathlib.Path(args[1]); out.mkdir(parents=True, exist_ok=True)
    f = sorted(rows(doc), key=lambda r: -r[2])
    payload = {"v": 1, "f": f}
    if opt.get("--me"): payload["me"] = opt["--me"]
    if opt.get("--group"):
        have = {r[0].lower() for r in f}
        payload["ch"] = [[g["handle"], g.get("name", ""), int(g.get("followers") or 0), int(g.get("weight", 2)), int(g["handle"].lower() in have)]
                         for g in json.load(open(opt["--group"]))["group"]]
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    c = zlib.compressobj(9, zlib.DEFLATED, -15); z = c.compress(raw) + c.flush()
    b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    base = opt.get("--base", "https://chrisjamesmedia.github.io/MediaBot").rstrip("/")
    link = f"{base}/start/#xf=z{b64(z)}"
    (out / "x-follows-link.txt").write_text(link + "\n")
    (out / "mediabot-x-follows-import.json").write_text(raw.decode())
    for p in out.iterdir():
        if p.is_file(): p.chmod(0o600)
    print(f"{len(f)} follows | json {len(raw)} B | compressed {len(z)} B | link {len(link)} chars")
    if len(link) > 60000: print("WARNING: link is over 60 KB; use the file option")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
