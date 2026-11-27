// MediaBot reader profile: who and what a reader wants, kept in their own browser only.
// Shared by /start/, /profile/ and (optionally) /create/. Schema: docs/profile.md, docs/profile.schema.json.
//   localStorage "mediabot.profile.v1"  the profile (no keys, no tokens, nothing secret)
//   localStorage "mediabot.follows.v1"  optional list brought in from X or Bluesky, used to pre-fill People
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

  root.MediaBotProfile = { KEY: KEY, FOLLOWS_KEY: FOLLOWS, WEIGHTS: WEIGHTS, FUN: FUN, LIMITS: LIMITS, blank: blank, normalize: normalize,
    load: load, save: save, forget: forget, loadFollows: loadFollows, saveFollows: saveFollows, parsePerson: parsePerson,
    personKey: personKey, xHandle: xHandle, bskyHandle: bskyHandle, brief: brief, mix: mix, who: who };
})(window);
