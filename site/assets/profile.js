// MediaBot reader profile: who and what a reader wants, kept in their own browser only.
// Shared by /start/, /profile/ and (optionally) /create/. Schema: docs/profile.md, docs/profile.schema.json.
//   localStorage "mediabot.profile.v1"  the profile (no keys, no tokens, nothing secret)
//   localStorage "mediabot.follows.v1"  optional list brought in from X or Bluesky, used to pre-fill People
//                                       (X rows: [handle, name, followers, bucket]; see docs/x-import.md)
// Usage: var p = MediaBotProfile.load();  MediaBotProfile.save(p);  MediaBotProfile.brief(p)  -> plain-text brief
(function (root) {
  "use strict";
  var KEY = "mediabot.profile.v1", FOLLOWS = "mediabot.follows.v1";
  var WEIGHTS = { 1: "A little", 2: "Normal", 3: "A lot" };
  var FUN = [
    { id: "jokes", label: "Jokes", help: "A real joke, credited to whoever told it" },
    { id: "memes", label: "Memes", help: "One funny post or picture going around" },
    { id: "game", label: "Game pick", help: "One game worth playing" },
    { id: "movie", label: "Movie pick", help: "One movie or show worth watching" },
    { id: "poem", label: "Poem", help: "A short poem by a real poet" }
  ];
  var PLATFORMS = ["x", "bluesky", "web"];
  var LIMITS = { people: 300, topics: 60 };

  function blank() {
    return { version: 1, updated: "", onboarded: false,
             accounts: { x: { handle: "", connected: false, imported: "" }, bluesky: { handle: "" } },
             people: [], topics: [],
             fun: { jokes: true, memes: false, game: false, movie: false, poem: true },
             priority: ["people", "topics", "fun"] };
  }
  function str(v, n) { return typeof v === "string" ? v.trim().slice(0, n || 80) : ""; }
  function w(v) { v = Math.round(Number(v)); return v >= 1 && v <= 3 ? v : 2; }
  function xHandle(h) { h = str(h, 40).replace(/^@+/, ""); return /^[A-Za-z0-9_]{1,15}$/.test(h) ? h : ""; }
  function bskyHandle(h) { h = str(h, 100).replace(/^@+/, "").toLowerCase(); return /^[a-z0-9][a-z0-9.-]{0,98}[a-z0-9]$/.test(h) && h.indexOf(".") > 0 ? h : ""; }

  // Make any stored or imported object a valid v1 profile (unknown fields are dropped).
  function normalize(o) {
    var p = blank();
    if (!o || typeof o !== "object") return p;
    p.updated = str(o.updated, 40); p.onboarded = !!o.onboarded;
    var a = o.accounts || {};
    if (a.x) { p.accounts.x.handle = xHandle(a.x.handle); p.accounts.x.connected = !!a.x.connected; p.accounts.x.imported = str(a.x.imported, 40); }
    if (a.bluesky) p.accounts.bluesky.handle = bskyHandle(a.bluesky.handle);
    var seen = {};
    (Array.isArray(o.people) ? o.people : []).forEach(function (x) {
      if (!x || p.people.length >= LIMITS.people) return;
      var plat = PLATFORMS.indexOf(x.platform) >= 0 ? x.platform : "web";
      var handle = plat === "x" ? xHandle(x.handle) : plat === "bluesky" ? bskyHandle(x.handle) : "";
      var name = str(x.name, 80);
      if (!handle && !name) return;
      var k = personKey({ platform: plat, handle: handle, name: name });
      if (seen[k]) return; seen[k] = 1;
      p.people.push({ name: name, handle: handle, platform: handle ? plat : "web", weight: w(x.weight), from: ["you", "x", "bluesky"].indexOf(x.from) >= 0 ? x.from : "you" });
    });
    seen = {};
    (Array.isArray(o.topics) ? o.topics : []).forEach(function (t) {
      if (!t || p.topics.length >= LIMITS.topics) return;
      var label = str(t.label, 40); if (!label || seen[label.toLowerCase()]) return;
      seen[label.toLowerCase()] = 1;
      p.topics.push({ label: label, weight: w(t.weight), from: ["you", "preset", "x"].indexOf(t.from) >= 0 ? t.from : "you" });
    });
    var f = o.fun || {};
    FUN.forEach(function (x) { if (typeof f[x.id] === "boolean") p.fun[x.id] = f[x.id]; });
    return p;
  }
  function personKey(x) { return x.handle ? x.platform + ":" + x.handle.toLowerCase() : "name:" + (x.name || "").toLowerCase(); }

  // "@paulg", "x.com/paulg", "https://bsky.app/profile/a.bsky.social", "name.bsky.social" or a plain name.
  function parsePerson(s) {
    s = str(s, 120); if (!s) return null;
    var m = s.match(/^(?:https?:\/\/)?(?:www\.|mobile\.)?(?:x|twitter)\.com\/@?([A-Za-z0-9_]{1,15})(?:[\/?#].*)?$/i);
    if (m) return { platform: "x", handle: m[1], name: "" };
    m = s.match(/^(?:https?:\/\/)?bsky\.app\/profile\/([^\/?#]+)/i);
    if (m && bskyHandle(m[1])) return { platform: "bluesky", handle: bskyHandle(m[1]), name: "" };
    if (/^@?[A-Za-z0-9_]{1,15}$/.test(s)) return { platform: "x", handle: s.replace(/^@/, ""), name: "" };
    if (/^@?[a-z0-9-]+(\.[a-z0-9-]+)+$/i.test(s) && bskyHandle(s)) return { platform: "bluesky", handle: bskyHandle(s), name: "" };
    return { platform: "web", handle: "", name: s.slice(0, 80) };
  }

  function load() {
    try { var raw = root.localStorage.getItem(KEY); return raw ? normalize(JSON.parse(raw)) : null; } catch (e) { return null; }
  }
  function save(p) {
    p = normalize(p); p.updated = new Date().toISOString();
    root.localStorage.setItem(KEY, JSON.stringify(p));
    return p;
  }
  function forget() { try { root.localStorage.removeItem(KEY); root.localStorage.removeItem(FOLLOWS); } catch (e) {} }
  function loadFollows() {
    try { var f = JSON.parse(root.localStorage.getItem(FOLLOWS)); return f && typeof f === "object" ? f : {}; } catch (e) { return {}; }
  }
  function saveFollows(f) { try { root.localStorage.setItem(FOLLOWS, JSON.stringify(f)); return true; } catch (e) { return false; } }

  function who(x) { return x.handle ? (x.platform === "bluesky" ? x.handle + " on Bluesky" : "@" + x.handle) + (x.name ? " (" + x.name + ")" : "") : x.name; }
  // A plain-text brief any generator (Grok, the daily routine) can follow. People > Topics > Fun, weights in words.
  function brief(p) {
    p = normalize(p);
    var by = function (list, n) { return list.filter(function (x) { return x.weight === n; }); };
    var out = ["Order the paper: people first, then topics, then the fun section last."];
    if (p.accounts.x.handle) out.push("The reader is @" + p.accounts.x.handle + " on X.");
    [3, 2, 1].forEach(function (n) {
      var ps = by(p.people, n); if (ps.length) out.push("People, " + WEIGHTS[n].toLowerCase() + ": " + ps.map(who).join(", ") + ".");
    });
    [3, 2, 1].forEach(function (n) {
      var ts = by(p.topics, n); if (ts.length) out.push("Topics, " + WEIGHTS[n].toLowerCase() + ": " + ts.map(function (t) { return t.label; }).join(", ") + ".");
    });
    var fun = FUN.filter(function (f) { return p.fun[f.id]; }).map(function (f) { return f.label.toLowerCase(); });
    out.push(fun.length ? "End with: " + fun.join(", ") + ". Only real, credited items; never write jokes or poems yourself." : "No fun section.");
    return out.join("\n");
  }
  // Share of a paper's items per group, from the weights: people get the most, then topics, then fun.
  function mix(p) {
    p = normalize(p);
    var sum = function (l) { return l.reduce(function (a, x) { return a + x.weight; }, 0); };
    var fun = FUN.filter(function (f) { return p.fun[f.id]; }).length;
    var raw = { people: p.people.length ? 5 + Math.min(sum(p.people), 15) / 3 : 0,
                topics: p.topics.length ? 3 + Math.min(sum(p.topics), 15) / 5 : 0,
                fun: fun ? 1 + fun / 2 : 0 };
    var t = raw.people + raw.topics + raw.fun || 1;
    return { people: Math.round(100 * raw.people / t), topics: Math.round(100 * raw.topics / t), fun: Math.round(100 * raw.fun / t) };
  }

  // ---------- private X follows import (no server, no X API) ----------
  // Rough, honest groups for the X list. Index = position in a link's rows; "other" is the default.
  var XBUCKETS = [["tech", "AI & tech"], ["invest", "Investing"], ["science", "Science & health"], ["culture", "Culture & ideas"], ["other", "Other"]]   // the CrowdHealth group is separate (follows.x_crowd);
  var BNAME = { ai_tech: 0, investing: 1, science_health: 2, culture: 3, other: 4 };
  function bucketIdx(b) { if (typeof b === "number") return b >= 0 && b < 5 ? b | 0 : 4; return BNAME.hasOwnProperty(b) ? BNAME[b] : 4; }
  // Accepts: our compact link payload {v,me,f:[[handle,name,followers,bucket]]}, the private file {follows:[{handle,name,followers,bucket}]},
  // or a raw X API reply {data:[{username,name,public_metrics}]}. Returns {me, list} (list sorted by followers) or null.
  function readXFollows(o) {
    if (!o || typeof o !== "object") return null;
    var rows = [];
    if (Array.isArray(o.f)) rows = o.f.map(function (r) { return Array.isArray(r) ? { h: r[0], n: r[1], c: r[2], b: r[3] } : null; });
    else if (Array.isArray(o.follows)) rows = o.follows.map(function (r) { return r && { h: r.handle, n: r.name, c: r.followers, b: r.bucket }; });
    else if (Array.isArray(o.following)) rows = o.following.map(function (r) { return Array.isArray(r) ? { h: r[0], n: r[1], c: r[2], b: r[3] } : null; });
    else if (Array.isArray(o.data)) rows = o.data.map(function (r) { return r && { h: r.username, n: r.name, c: r.public_metrics && r.public_metrics.followers_count, b: 4 }; });
    var seen = {}, list = [];
    rows.forEach(function (r) {
      if (!r) return; var h = xHandle(r.h); if (!h || seen[h.toLowerCase()]) return; seen[h.toLowerCase()] = 1;
      var c = Math.max(0, Math.round(Number(r.c)) || 0);
      list.push([h, str(r.n, 80), c, bucketIdx(r.b)]);
    });
    if (!list.length) return null;
    list.sort(function (a, b) { return b[2] - a[2]; });
    // Optional preselected group (e.g. CrowdHealth): link rows [handle,name,followers,weight,follows], file rows {handle,name,followers,weight,follows}.
    var grp = Array.isArray(o.ch) ? o.ch : Array.isArray(o.crowdhealth) ? o.crowdhealth : [], gs = {}, crowd = [];
    grp.forEach(function (r) {
      var a = Array.isArray(r) ? r : r && [r.handle, r.name, r.followers, r.weight, r.follows];
      if (!a) return; var h = xHandle(a[0]); if (!h || gs[h.toLowerCase()] || crowd.length >= 30) return; gs[h.toLowerCase()] = 1;
      crowd.push([h, str(a[1], 80), Math.max(0, Math.round(Number(a[2])) || 0), w(a[3]), a[4] ? 1 : 0]);
    });
    return { me: xHandle(o.me), list: list.slice(0, 5000), crowd: crowd };
  }
  // "#xf=z<base64url deflate-raw JSON>" (compressed) or "#xf=j<base64url JSON>" (plain). A full link or just the fragment works.
  function decodeXFragment(s) {
    var m = String(s || "").match(/#?xf=([zj])([A-Za-z0-9_-]+)/);
    if (!m) return Promise.reject(new Error("nolink"));
    var b = atob(m[2].replace(/-/g, "+").replace(/_/g, "/")), bytes = new Uint8Array(b.length);
    for (var i = 0; i < b.length; i++) bytes[i] = b.charCodeAt(i);
    var toJson = function (u8) { return JSON.parse(new TextDecoder().decode(u8)); };
    if (m[1] === "j") return Promise.resolve(toJson(bytes));
    if (typeof DecompressionStream === "undefined") return Promise.reject(new Error("nozip"));
    var ds = new DecompressionStream("deflate-raw");
    var w = ds.writable.getWriter(); w.write(bytes).catch(function () {}); w.close().catch(function () {});
    return new Response(ds.readable).arrayBuffer().then(function (buf) { return toJson(new Uint8Array(buf)); });
  }
  // The first n people worth showing by default: biggest accounts, skipping the Investing group.
  function topPicks(list, n) {
    return list.filter(function (r) { return r[3] !== 1; }).slice(0, n || 40);
  }

  root.MediaBotProfile = { KEY: KEY, FOLLOWS_KEY: FOLLOWS, WEIGHTS: WEIGHTS, FUN: FUN, LIMITS: LIMITS, blank: blank, normalize: normalize,
    load: load, save: save, forget: forget, loadFollows: loadFollows, saveFollows: saveFollows, parsePerson: parsePerson,
    personKey: personKey, XBUCKETS: XBUCKETS, readXFollows: readXFollows, decodeXFragment: decodeXFragment, topPicks: topPicks, xHandle: xHandle, bskyHandle: bskyHandle, brief: brief, mix: mix, who: who };
})(window);
