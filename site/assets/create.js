// Quick Create: build a finite paper in the browser.
// Live mode calls the xAI Responses API (web_search + x_search) with the reader's own key, kept in localStorage and
// sent only to api.x.ai (or an optional proxy URL the reader sets). Demo mode renders items already published on this site.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var API = "https://api.x.ai/v1/responses", DEFAULT_MODEL = "grok-4.7";
  var K = {key: "mb:qc:key", model: "mb:qc:model", proxy: "mb:qc:proxy", draft: "mb:qc:draft", papers: "mb:qc:papers"};
  var CAPS = {3: 8, 5: 14, 10: 28, 15: 40}, WPM = 230, HELPING = 3, CONCURRENCY = 3;
  var TONES = ["wholesome", "based", "insightful", "funny", "calm", "curious", "practical", "bold"];

  // Presets. id matches a pipeline section id where one exists (papers/*/paper.yaml) so an export can be adopted.
  // src: where the section may look; w: share of the item budget; max: ceiling; rules: fixed instructions, not editable.
  var PRESETS = [
    {id: "x", title: "From X topics", brief: "Thoughtful, lasting posts on X about the reader's interests. Skip breaking news, outrage and promotion.", src: ["x"], w: 1.5},
    {id: "faith", title: "Faith & Scripture", brief: "Scripture and faith: one short Bible passage with its reference and a link to where it is published, then posts of real faith, gratitude and wisdom.", src: ["x", "web"], w: 1,
      rules: "A Scripture passage (kind \"passage\") must be quoted exactly from a page you opened and linked."},
    {id: "science", title: "Nature & Science", brief: "Wonder from the natural world and honest science: studies, animals, space, seasons, history of discovery.", src: ["x", "web"], w: 1},
    {id: "ideas", title: "Books & Ideas", brief: "Books, essays, poetry, philosophy and ideas worth slowing down for.", src: ["x", "web"], w: 1},
    {id: "people", title: "People & Stories", brief: "Real stories about real people: kindness, family, history, craft, perseverance.", src: ["x", "web"], w: 1},
    {id: "craft", title: "Craft & Work", brief: "Making, building, cooking, gardening, design and the dignity of good work.", src: ["x", "web"], w: 1},
    {id: "tech", title: "Tech / AI", brief: "Useful, concrete technology and AI news and ideas, with the substance and not the hype.", src: ["x", "web"], w: 1},
    {id: "business", title: "Business", brief: "Business, markets and money explained plainly: what happened and why it matters.", src: ["x", "web"], w: 1},
    {id: "health", title: "Health", brief: "Health, sleep, food, movement and mental wellbeing, from credible clinicians and researchers.", src: ["x", "web"], w: 1},
    {id: "humor", title: "Something Light", brief: "A real joke or a funny line, posted by an identifiable person or account.", src: ["x", "web"], w: 0.5, max: 3,
      rules: "Jokes (kind \"joke\"): only a real joke that appears word for word in a post or page you retrieved, credited to who posted it. Never write, adapt or complete a joke yourself. If you cannot find a real one, return no items."},
    {id: "puzzles", title: "Puzzles", brief: "A real puzzle, riddle or brain teaser someone published, worth a minute.", src: ["x", "web"], w: 0.5, max: 2,
      rules: "Puzzles (kind \"puzzle\"): quote the puzzle exactly as published. Include \"answer\" only if the source itself gives it; never solve or invent one."},
    {id: "quote", title: "Quote / Passage", brief: "One memorable passage from a classic or a living writer, with the work it comes from.", src: ["web", "x"], w: 0.5, max: 2,
      rules: "Quotes and passages (kind \"passage\"): exact words, with author, work, and a link to a page that contains them. If you cannot link the exact words, drop it."}
  ];
  var DEFAULT_ON = {x: 1, faith: 1, science: 1, ideas: 1, people: 1, craft: 1, humor: 1};
  var P = {}; PRESETS.forEach(function (p) { P[p.id] = p; });

  var sample = {items: [], label: ""};
  try { sample = JSON.parse($("qc-sample").textContent); } catch (e) {}

  // ---------- state ----------
  function fresh() {
    return {v: 1, name: "", minutes: 5, tone: ["wholesome", "insightful"], interests: "", favor: "", avoid: "", fresh: 7,
            x: true, web: true, only: false, links: true,
            sections: PRESETS.slice().sort(function (a, b) { return !!DEFAULT_ON[b.id] - !!DEFAULT_ON[a.id]; })
              .map(function (p) { return {id: p.id, title: p.title, on: !!DEFAULT_ON[p.id], brief: p.brief, custom: false}; })};
  }
  var st = fresh();

  function str(v, n) { return typeof v === "string" ? v.slice(0, n) : ""; }
  // Accepts any parsed JSON and returns a clean config; never trusts shape or length.
  function normalize(c) {
    var d = fresh();
    if (!c || typeof c !== "object") return d;
    var out = {v: 1, name: str(c.name, 60), minutes: CAPS[c.minutes] ? +c.minutes : d.minutes,
      tone: Array.isArray(c.tone) ? c.tone.filter(function (t) { return TONES.indexOf(t) >= 0; }) : d.tone,
      interests: str(c.interests, 400), favor: str(c.favor, 300), avoid: str(c.avoid, 300),
      fresh: [3, 7, 14, 30].indexOf(+c.fresh) >= 0 ? +c.fresh : d.fresh,
      x: c.x !== false, web: c.web !== false, only: !!c.only, links: c.links !== false, sections: []};
    if (!out.x && !out.web) out.web = true;
    var seen = {}, list = Array.isArray(c.sections) ? c.sections.slice(0, 30) : [];
    list.forEach(function (s) {
      if (!s || typeof s !== "object") return;
      var id = str(s.id, 40).replace(/[^a-z0-9_-]/gi, "").toLowerCase();
      if (!id || seen[id]) return;
      var preset = P[id] && !s.custom;
      if (!preset && !s.custom) return;
      seen[id] = 1;
      out.sections.push({id: id, title: preset ? P[id].title : str(s.title, 40) || "Custom", on: s.on !== false,
        brief: str(s.brief, 400) || (preset ? P[id].brief : ""), custom: !preset});
    });
    PRESETS.forEach(function (p) {   // presets missing from the file come back switched off, at the end
      if (!seen[p.id]) out.sections.push({id: p.id, title: p.title, on: false, brief: p.brief, custom: false});
    });
    return out;
  }
  function saveDraft() { try { localStorage.setItem(K.draft, JSON.stringify(st)); } catch (e) {} }
  function loadDraft() { try { return JSON.parse(localStorage.getItem(K.draft)); } catch (e) { return null; } }

  // ---------- helpers ----------
  function slugify(s) { return (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "my-paper"; }
  function words(s) { return (String(s || "").match(/\S+/g) || []).length; }
  function setStatus(msg, bad) { var e = $("qc-status"); e.textContent = msg || ""; e.className = "qc-help" + (bad ? " bad" : ""); }
  function handles(s) { return (String(s || "").match(/@[A-Za-z0-9_]{1,15}/g) || []).map(function (h) { return h.slice(1); }); }
  function domains(s) { return (String(s || "").match(/\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}\b/gi) || []).map(function (d) { return d.toLowerCase(); }); }
  function active() { return st.sections.filter(function (s) { return s.on; }); }

  // Item budget: the length picks a total; sections share it by weight (at least one each); the total is a hard cap.
  function allocate(secs, total) {
    var n = secs.length, a = {};
    if (!n) return a;
    var w = secs.map(function (s) { return P[s.id] ? P[s.id].w : 1; }), sum = w.reduce(function (x, y) { return x + y; }, 0);
    var raw = w.map(function (x) { return total * x / sum; }), got = raw.map(function (r, i) {
      var m = P[secs[i].id] && P[secs[i].id].max; return Math.max(1, Math.min(m || 99, Math.floor(r)));
    });
    var used = got.reduce(function (x, y) { return x + y; }, 0), guard = 0;
    while (used < total && guard++ < 200) {          // hand out the remainder, biggest fractions first
      var best = -1, bf = -1;
      raw.forEach(function (r, i) { var m = P[secs[i].id] && P[secs[i].id].max; var f = r - got[i]; if ((!m || got[i] < m) && f > bf) { bf = f; best = i; } });
      if (best < 0) break; got[best]++; used++;
    }
    while (used > total) {                           // more sections than items: drop from the end, never exceed the cap
      var j = got.lastIndexOf(Math.max.apply(null, got)); if (got[j] <= 1) break; got[j]--; used--;
    }
    secs.forEach(function (s, i) { a[s.id] = got[i]; });
    return a;
  }
  function budgetFor(secs) {
    var total = CAPS[st.minutes], a = allocate(secs, total), sum = 0;
    secs.forEach(function (s) { sum += a[s.id]; });
    if (sum > total) {  // more sections than the cap: keep the first ones
      var left = total; secs = secs.filter(function (s) { if (left > 0) { left--; return true; } return false; });
      a = allocate(secs, total);
    }
    return {total: total, per: a, secs: secs};
  }

  // ---------- builder UI ----------
  function renderSecs() {
    var ol = $("qc-secs"); ol.innerHTML = "";
    var b = budgetFor(active());
    st.sections.forEach(function (s, i) {
      var li = document.createElement("li"); li.className = s.on ? "" : "off";
      var top = document.createElement("div"); top.className = "qc-sechead";
      var cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = s.on; cb.id = "qc-s-" + s.id;
      cb.setAttribute("aria-label", "Include " + s.title);
      var lab = document.createElement("label"); lab.htmlFor = cb.id; lab.className = "qc-sectitle"; lab.textContent = s.title;
      var cnt = document.createElement("span"); cnt.className = "qc-seccount";
      cnt.textContent = s.on && b.per[s.id] ? "up to " + b.per[s.id] : "";
      var mv = document.createElement("span"); mv.className = "qc-mv";
      var up = document.createElement("button"); up.type = "button"; up.textContent = "↑"; up.setAttribute("aria-label", "Move " + s.title + " up"); up.disabled = i === 0;
      var dn = document.createElement("button"); dn.type = "button"; dn.textContent = "↓"; dn.setAttribute("aria-label", "Move " + s.title + " down"); dn.disabled = i === st.sections.length - 1;
      mv.appendChild(up); mv.appendChild(dn);
      top.appendChild(cb); top.appendChild(lab); top.appendChild(cnt); top.appendChild(mv);
      var bi = document.createElement("textarea"); bi.rows = 2; bi.maxLength = 400; bi.value = s.brief;
      bi.setAttribute("aria-label", s.title + " topic"); bi.className = "qc-brief";
      li.appendChild(top); li.appendChild(bi);
      if (s.custom) {
        var rm = document.createElement("button"); rm.type = "button"; rm.className = "qc-link"; rm.textContent = "Remove this section";
        rm.onclick = function () { st.sections.splice(i, 1); changed(true); };
        li.appendChild(rm);
      }
      cb.onchange = function () { s.on = cb.checked; changed(true); };
      var fit = function () { bi.style.height = "auto"; bi.style.height = (bi.scrollHeight + 2) + "px"; };
      bi.oninput = function () { s.brief = bi.value; saveDraft(); fit(); };
      up.onclick = function () { swap(i, -1); }; dn.onclick = function () { swap(i, 1); };
      ol.appendChild(li); fit();
    });
  }
  function swap(i, d) { var a = st.sections, t = a[i]; a[i] = a[i + d]; a[i + d] = t; changed(true); }
  function renderForm() {
    $("qc-name").value = st.name; $("qc-interests").value = st.interests; $("qc-favor").value = st.favor; $("qc-avoid").value = st.avoid;
    $("qc-fresh").value = String(st.fresh); $("qc-sx").checked = st.x; $("qc-sw").checked = st.web; $("qc-only").checked = st.only; $("qc-links").checked = st.links;
    var t = $("qc-tone"); t.innerHTML = "";
    TONES.forEach(function (name) {
      var l = document.createElement("label"), i = document.createElement("input"), s = document.createElement("span");
      i.type = "checkbox"; i.checked = st.tone.indexOf(name) >= 0; s.textContent = name;
      i.onchange = function () { st.tone = TONES.filter(function (n) { return n === name ? i.checked : st.tone.indexOf(n) >= 0; }); saveDraft(); };
      l.appendChild(i); l.appendChild(s); t.appendChild(l);
    });
    var m = $("qc-min"); m.innerHTML = "";
    [3, 5, 10, 15].forEach(function (n) {
      var l = document.createElement("label"), i = document.createElement("input"), s = document.createElement("span");
      i.type = "radio"; i.name = "qc-minutes"; i.value = n; i.checked = st.minutes === n; s.textContent = n + " min";
      i.onchange = function () { st.minutes = n; changed(); };
      l.appendChild(i); l.appendChild(s); m.appendChild(l);
    });
    renderSecs(); renderCap(); renderSaved(); renderMode();
  }
  function renderCap() {
    var b = budgetFor(active());
    $("qc-cap").textContent = b.secs.length ? "Up to " + b.total + " items across " + b.secs.length + " section" + (b.secs.length === 1 ? "" : "s") + ". The edition ends there." : "Pick at least one section.";
    if (b.secs.length < active().length) $("qc-cap").textContent += " (Only the first " + b.secs.length + " sections fit this length.)";
  }
  function changed(rerender) { saveDraft(); if (rerender) renderSecs(); renderCap(); }
  function renderMode() {
    var k = getKey();
    $("qc-mode").textContent = k ? "Generates with Grok (" + getModel() + ") using your key. Costs a little on your xAI account." : "No key yet, so Generate shows a labeled sample. Add your xAI key below for a real edition.";
    $("qc-go").textContent = k ? "Generate edition" : "Generate (sample mode)";
  }
  function readForm() {
    st.name = $("qc-name").value.trim(); st.interests = $("qc-interests").value; st.favor = $("qc-favor").value.trim(); st.avoid = $("qc-avoid").value.trim();
    st.fresh = +$("qc-fresh").value; st.x = $("qc-sx").checked; st.web = $("qc-sw").checked; st.only = $("qc-only").checked; st.links = $("qc-links").checked;
    if (!st.x && !st.web) { st.web = true; $("qc-sw").checked = true; }
    saveDraft();
  }

  // ---------- key, model, proxy (device-only settings; never exported) ----------
  function ls(k) { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } }
  function getKey() { return ls(K.key); }
  function getModel() { return ls(K.model) || DEFAULT_MODEL; }

  // ---------- Grok calls ----------
  function normUrl(u) {
    try {
      var x = new URL(u), host = x.hostname.toLowerCase().replace(/^www\./, "").replace(/^(mobile|m)\./, "");
      var m = x.pathname.match(/\/status(?:es)?\/(\d+)/);
      if ((host === "x.com" || host === "twitter.com") && m) return "x:" + m[1];
      return host + x.pathname.replace(/\/+$/, "").toLowerCase();
    } catch (e) { return ""; }
  }
  // URLs the search tools actually returned: response.citations, annotations, and tool-call output. Never the model's own text.
  function citedSet(resp) {
    var set = {};
    function add(u) { var n = normUrl(u); if (n) set[n] = 1; }
    function walk(o, depth) {
      if (depth > 8 || o == null) return;
      if (typeof o === "string") { (o.match(/https?:\/\/[^\s"'<>)\]]+/g) || []).forEach(add); return; }
      if (Array.isArray(o)) { o.forEach(function (v) { walk(v, depth + 1); }); return; }
      if (typeof o === "object") {
        if (o.type === "output_text") { walk(o.annotations, depth + 1); return; }       // skip the model's words, keep its annotations
        if (o.type === "reasoning") return;
        Object.keys(o).forEach(function (k) { walk(o[k], depth + 1); });
      }
    }
    if (resp) { walk(resp.citations, 0); walk(resp.output, 0); }
    return set;
  }
  function outputText(resp) {
    var t = "";
    (resp && resp.output || []).forEach(function (it) {
      if (it && it.type === "message") (it.content || []).forEach(function (c) { if (c && c.type === "output_text" && c.text) t += c.text; });
    });
    if (!t && resp && typeof resp.output_text === "string") t = resp.output_text;
    return t;
  }
  function parseItems(text) {
    text = String(text || "").replace(/\[\[\d+\]\]\([^)]*\)/g, "").replace(/```(?:json)?/gi, "");
    var a = text.indexOf("{"), b = text.lastIndexOf("}");
    if (a < 0 || b <= a) return [];
    try { var j = JSON.parse(text.slice(a, b + 1)); return Array.isArray(j.items) ? j.items : []; } catch (e) { return []; }
  }
  var KINDS = ["post", "article", "passage", "joke", "puzzle"];
  // Every item must have real text, an https link, and a link the search tools returned. Anything else is dropped.
  function vetItems(items, cited) {
    var out = [], dropped = 0;
    (items || []).forEach(function (it) {
      if (!it || typeof it !== "object") { dropped++; return; }
      var url = str(it.url, 500), ok = /^https:\/\/[^\s]+$/.test(url) && str(it.text, 4000).trim();
      if (ok) { try { new URL(url); } catch (e) { ok = false; } }
      if (ok && !cited[normUrl(url)]) ok = false;
      if (!ok) { dropped++; return; }
      var kind = KINDS.indexOf(it.kind) >= 0 ? it.kind : "post";
      var o = {kind: kind, text: str(it.text, 4000).trim(), headline: str(it.headline, 200).trim(), author: str(it.author, 120).trim(),
               handle: str(it.handle, 40).replace(/^@/, "").replace(/[^A-Za-z0-9_]/g, ""), outlet: str(it.outlet, 120).trim(), url: url,
               date: /^\d{4}-\d{2}-\d{2}/.test(it.date || "") ? it.date.slice(0, 10) : "", answer: str(it.answer, 600).trim()};
      if ((kind === "joke" || kind === "passage") && !(o.author || o.handle)) { dropped++; return; }   // jokes and quotes must be credited
      out.push(o);
    });
    return {items: out, dropped: dropped};
  }
  function ymd(d) { var z = function (n) { return (n < 10 ? "0" : "") + n; }; return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()); }
  function toolsFor(sec, opts) {
    var want = (P[sec.id] ? P[sec.id].src : ["x", "web"]).filter(function (s) { return s === "x" ? st.x : st.web; });
    if (!want.length) want = [st.x ? "x" : "web"];
    var tools = [];
    if (want.indexOf("x") >= 0) {
      var t = {type: "x_search", from_date: ymd(new Date(Date.now() - st.fresh * 864e5)), to_date: ymd(new Date())};
      var av = handles(st.avoid).slice(0, 20), fv = handles(st.favor).slice(0, 20);
      if (av.length) t.excluded_x_handles = av;
      else if (st.only && fv.length) t.allowed_x_handles = fv;
      tools.push(t);
    }
    if (want.indexOf("web") >= 0) {
      var w = {type: "web_search"}, ad = domains(st.avoid).slice(0, 5);
      if (ad.length) w.excluded_domains = ad;
      tools.push(w);
    }
    return tools;
  }
  var SYSTEM = [
    "You are the research editor of a small finite paper that replaces an endless feed. You find real items with the search tools and return them as JSON.",
    "Hard rules:",
    "1. Use only what the search tools returned in this request. Never rely on memory for quotes, posts, authors, dates, jokes or links.",
    "2. Every item needs the exact URL of the post or page you retrieved. No URL you did not retrieve. If you cannot source an item, drop it. Returning fewer items, or none, is correct.",
    "3. X posts: copy the post text verbatim, with no edits, and credit the author and handle. Web items: a neutral one or two sentence summary in your own words, with the outlet, and a short quote only if exact.",
    "4. Never invent or rewrite quotes, authors, jokes, statistics or links. Never write jokes yourself.",
    "5. No more than two items from the same author. No duplicates. Skip ads, giveaways, outrage bait and anything crude or hateful.",
    "6. Reply with one JSON object and nothing else: {\"items\":[{\"kind\":\"post|article|passage|joke|puzzle\",\"headline\":\"web items only, else empty\",\"text\":\"...\",\"author\":\"...\",\"handle\":\"X handle without @, or empty\",\"outlet\":\"publication or site, or empty\",\"url\":\"https://...\",\"date\":\"YYYY-MM-DD or empty\",\"answer\":\"puzzles only, only if the source gives it\"}]}"
  ].join("\n");
  function userPrompt(sec, n, tools, used, extra) {
    var L = ["Section: " + sec.title, "Topic: " + (sec.brief || sec.title), "Find up to " + n + " item" + (n === 1 ? "" : "s") + " for this section."];
    if (st.interests.trim()) L.push("Reader's interests: " + st.interests.trim());
    if (st.favor.trim()) L.push("Prefer these accounts or sources when they fit: " + st.favor.trim());
    if (st.avoid.trim()) L.push("Never use these accounts or sources: " + st.avoid.trim());
    if (st.tone.length) L.push("Choose items with this tone: " + st.tone.join(", ") + ".");
    if (tools.some(function (t) { return t.type === "x_search"; })) L.push("X posts should be from " + tools[0].from_date + " to " + tools[0].to_date + ".");
    L.push("Today is " + ymd(new Date()) + ".");
    if (P[sec.id] && P[sec.id].rules) L.push(P[sec.id].rules);
    if (used.length) L.push("Do not repeat these URLs: " + used.slice(0, 60).join(" "));
    if (extra) L.push(extra);
    return L.join("\n");
  }
  function describeError(status, body, e) {
    if (e && e.name === "AbortError") return "Cancelled or timed out.";
    if (!status) return "Could not reach api.x.ai from this browser (network or CORS). Try again, or set a proxy URL under Grok key and connection.";
    var msg = ""; try { var j = JSON.parse(body); msg = (j.error && (j.error.message || j.error)) || j.message || j.detail || ""; if (typeof msg !== "string") msg = JSON.stringify(msg); } catch (x) { msg = String(body || "").slice(0, 160); }
    if (status === 401) return "xAI rejected the key (401). Check it under Grok key and connection.";
    if (status === 403) return "xAI refused the request (403): " + (msg || "the key may lack credits or access to this model.");
    if (status === 429) return "Rate limited by xAI (429). Wait a moment and try again.";
    return "xAI error " + status + (msg ? ": " + msg.slice(0, 200) : "");
  }
  function callGrok(sec, n, used, extra, signal) {
    var tools = toolsFor(sec, {});
    var body = {model: getModel(), input: [{role: "system", content: SYSTEM}, {role: "user", content: userPrompt(sec, n, tools, used, extra)}],
                tools: tools, max_output_tokens: 6000};
    var url = ls(K.proxy) || API, attempt = 0;
    function go() {
      attempt++;
      return fetch(url, {method: "POST", signal: signal, headers: {"Content-Type": "application/json", "Authorization": "Bearer " + getKey()}, body: JSON.stringify(body)})
        .then(function (r) {
          return r.text().then(function (t) {
            if (!r.ok) {
              if ((r.status === 429 || r.status >= 500) && attempt < 2) return new Promise(function (ok) { setTimeout(ok, 2500); }).then(go);
              throw {status: r.status, body: t};
            }
            var resp; try { resp = JSON.parse(t); } catch (e) { throw {status: r.status, body: "Unreadable response"}; }
            var vet = vetItems(parseItems(outputText(resp)), citedSet(resp));
            return vet;
          });
        }, function (e) { throw {status: 0, err: e}; });
    }
    return go();
  }

  // ---------- run ----------
  var run = null;
  function newRun() { return {abort: typeof AbortController !== "undefined" ? new AbortController() : {signal: undefined, abort: function () {}}, cancelled: false, items: {}, used: [], authors: {}}; }
  function dedupeInto(r, secId, list, n) {
    var out = [];
    list.forEach(function (it) {
      if (out.length >= n) return;
      var key = normUrl(it.url), au = (it.handle || it.author || "").toLowerCase();
      if (r.used.indexOf(key) >= 0) return;
      if (r.mode !== "demo" && au && (r.authors[au] || 0) >= 2) return;
      r.used.push(key); if (au) r.authors[au] = (r.authors[au] || 0) + 1; out.push(it);
    });
    return out;
  }
  function generate(mode) {
    readForm();
    var b = budgetFor(active());
    if (!b.secs.length) { setStatus("Pick at least one section.", true); return; }
    if (run) run.abort.abort();
    var r = run = newRun(); r.mode = mode; r.cfg = JSON.parse(JSON.stringify(st)); r.budget = b; r.helpingUsed = false; r.failed = {};
    r.secs = b.secs.map(function (s) { return {id: s.id, title: s.title, brief: s.brief, custom: s.custom}; });
    setStatus(""); beginEdition(r);
    var queue = r.secs.slice(), done = 0, active_ = 0;
    function next() {
      if (r.cancelled) return;
      if (!queue.length) { if (active_ === 0) finish(r); return; }
      var sec = queue.shift(); active_++; markSection(r, sec, "working");
      var p;
      if (mode === "demo") p = Promise.resolve(demoSection(r, sec, b.per[sec.id]));
      else p = callGrok(sec, b.per[sec.id], r.used.slice(), "", r.abort.signal).then(function (v) { return {items: v.items, dropped: v.dropped}; });
      p.then(function (v) {
        if (r.cancelled) return;
        var items = dedupeInto(r, sec.id, v.items, b.per[sec.id]);
        r.items[sec.id] = items; r.failed[sec.id] = items.length ? "" : (v.note || (v.dropped ? "Nothing Grok returned could be linked to a real source, so it was dropped." : "No sourced items found for this section."));
        markSection(r, sec, "done"); fillSection(r, sec);
      }, function (e) {
        if (r.cancelled) return;
        r.items[sec.id] = []; r.failed[sec.id] = describeError(e && e.status, e && e.body, e && e.err); r.fatal = r.fatal || (e && (e.status === 401 || e.status === 403) ? r.failed[sec.id] : "");
        markSection(r, sec, "done"); fillSection(r, sec);
      }).then(function () { active_--; done++; progress(r, done); if (r.fatal && queue.length) { queue.length = 0; } next(); });
    }
    progress(r, 0);
    for (var i = 0; i < Math.min(mode === "demo" ? 1 : CONCURRENCY, r.secs.length); i++) next();
  }

  // Demo: real items from published editions, chosen by section; reserve kept for the one helping.
  function demoPool(secId) { return sample.items.filter(function (i) { return i.sec === secId; }); }
  function demoSection(r, sec, n) {
    var pool = demoPool(sec.id);
    if (sec.id === "faith") pool = pool.slice().sort(function (a, b) { return (b.kind === "passage") - (a.kind === "passage"); });
    var out = pool.slice(0, n);
    r.demoTaken = r.demoTaken || {}; r.demoTaken[sec.id] = out.length;
    return {items: out.map(function (i) { var c = JSON.parse(JSON.stringify(i)); delete c.sec; return c; }), dropped: 0,
            note: P[sec.id] && !sample.items.some(function (i) { return i.sec === sec.id; }) ? "The sample has nothing for this section. With your Grok key it would be filled." : (sec.custom ? "Custom sections need your Grok key. The sample can't write to a topic." : "")};
  }

  // ---------- edition view ----------
  var el = {};
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function beginEdition(r) {
    var box = $("qc-edition"); box.innerHTML = ""; el = {};
    var head = h("header", "qc-ehead");
    el.title = h("h2", "qc-etitle", r.cfg.name || "Your paper");
    el.meta = h("p", "qc-emeta", "");
    el.progress = h("p", "qc-progress", "");
    var cancel = h("button", "qc-btn quiet qc-cancel", "Cancel"); cancel.type = "button";
    cancel.onclick = function () { r.cancelled = true; r.abort.abort(); setStatus("Cancelled."); el.progress.textContent = "Cancelled. What arrived is below."; cancel.remove(); finish(r, true); };
    el.cancel = cancel;
    head.appendChild(el.title); head.appendChild(el.meta);
    if (r.mode === "demo") {
      var sb = h("p", "qc-sample", "SAMPLE: real posts from the latest " + (sample.label || "published editions") + ". Not generated from your interests, tone or topics. Add your Grok key to generate your own edition.");
      sb.setAttribute("role", "note"); head.appendChild(sb);
    }
    head.appendChild(el.progress); head.appendChild(cancel);
    box.appendChild(head);
    el.body = h("div", "qc-ebody"); box.appendChild(el.body);
    el.secs = {};
    r.secs.forEach(function (s) {
      var sec = h("section", "qc-esec"); sec.id = "qc-e-" + s.id;
      var hh = h("h3", "qc-esechead", s.title); sec.appendChild(hh);
      var stream = h("div", "qc-stream"); stream.appendChild(h("p", "qc-wait", "Waiting…")); sec.appendChild(stream);
      el.body.appendChild(sec); el.secs[s.id] = {sec: sec, stream: stream};
    });
    el.foot = h("div", "qc-efoot"); box.appendChild(el.foot);
    updateMeta(r);
    box.scrollIntoView({behavior: "smooth", block: "start"}); box.focus({preventScroll: true});
  }
  function markSection(r, sec, state) { var e = el.secs[sec.id]; if (!e) return; if (state === "working") { e.stream.innerHTML = ""; e.stream.appendChild(h("p", "qc-wait", "Finding sources…")); } }
  function itemNode(it, links) {
    var art = h("article", "qc-item");
    var who = h("p", "qc-who");
    var name = it.author || (it.handle ? "@" + it.handle : "") || it.outlet;
    if (it.headline) { art.appendChild(h("h4", "qc-ihead", it.headline)); }
    if (name) { var b = h("b", "", name); who.appendChild(b); }
    var bits = [];
    if (it.handle && it.author) bits.push("@" + it.handle);
    if (it.outlet && it.outlet !== name) bits.push(it.outlet);
    if (it.date) bits.push(it.date);
    if (it.kind === "joke") bits.push("joke");
    if (bits.length) who.appendChild(document.createTextNode((name ? " · " : "") + bits.join(" · ")));
    if (name || bits.length) art.appendChild(who);
    String(it.text).split(/\n\s*\n/).forEach(function (p) {
      var pe = h("p", it.kind === "passage" ? "qc-passage" : "");
      p.split("\n").forEach(function (line, i) { if (i) pe.appendChild(document.createElement("br")); pe.appendChild(document.createTextNode(line)); });
      art.appendChild(pe);
    });
    if (it.answer) { var d = h("details", "qc-answer"); d.appendChild(h("summary", "", "Answer, from the source")); d.appendChild(h("p", "", it.answer)); art.appendChild(d); }
    if (links) {
      var a = h("a", "qc-src", "Source: " + hostOf(it.url)); a.href = it.url; a.target = "_blank"; a.rel = "noopener noreferrer"; art.appendChild(a);
    }
    return art;
  }
  function hostOf(u) { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return "link"; } }
  function fillSection(r, sec) {
    var e = el.secs[sec.id]; if (!e) return; e.stream.innerHTML = "";
    var items = r.items[sec.id] || [];
    items.forEach(function (it) { e.stream.appendChild(itemNode(it, r.cfg.links)); });
    if (!items.length) e.stream.appendChild(h("p", "qc-empty", r.failed[sec.id] || "Nothing to show here."));
    else if (r.failed[sec.id]) e.stream.appendChild(h("p", "qc-empty", r.failed[sec.id]));
    updateMeta(r);
  }
  function allItems(r) { var a = []; r.secs.forEach(function (s) { (r.items[s.id] || []).forEach(function (i) { a.push(i); }); }); return a.concat(r.helping || []); }
  function updateMeta(r) {
    var items = allItems(r), w = items.reduce(function (n, i) { return n + words(i.text) + words(i.headline) + words(i.author) + 3; }, 0);
    r.words = w; r.count = items.length;
    var min = Math.max(1, Math.round(w / WPM));
    el.meta.textContent = new Date().toLocaleDateString(undefined, {weekday: "long", month: "long", day: "numeric", year: "numeric"}) + " · " + items.length + " item" + (items.length === 1 ? "" : "s") + " · " + (items.length ? min + " min read" : "building");
  }
  function progress(r, done) { if (el.progress && !r.finished) el.progress.textContent = "Section " + Math.min(done + 1, r.secs.length) + " of " + r.secs.length + (r.mode === "demo" ? "" : ". Grok is searching, this takes a minute or two."); }

  function finish(r, early) {
    if (r.finished) return; r.finished = true;
    if (el.cancel) el.cancel.remove();
    var n = allItems(r).length;
    el.progress.textContent = r.fatal ? r.fatal : "";
    el.foot.innerHTML = "";
    var end = h("p", "qc-end", n ? "That’s the edition." : "Nothing sourced this time.");
    el.foot.appendChild(end);
    var sum = h("p", "qc-endnote", n ? n + " item" + (n === 1 ? "" : "s") + " · " + Math.max(1, Math.round(r.words / WPM)) + " min read · every item has a source link. Nothing more to scroll." : "Every item had to link to a real source, and none did. Try again or loosen the topics.");
    el.foot.appendChild(sum);
    if (r.mode !== "demo" && r.cfg.links === false) el.foot.appendChild(h("p", "qc-endnote", "Source links are hidden in this view. They are all still real."));
    var acts = h("div", "qc-actions qc-eactions");
    if (n) { var pb = h("button", "qc-btn", "Print or save PDF"); pb.type = "button"; pb.onclick = printEdition; acts.appendChild(pb); }
    var again = h("a", "qc-btn quiet", "Change settings"); again.href = "#qc-name"; acts.appendChild(again);
    el.foot.appendChild(acts);
    if (n && !early && !r.cancelled && canHelp(r)) {
      var more = h("div", "qc-more"); var mb = h("button", "qc-btn", "One more helping (up to " + HELPING + " items, once)"); mb.type = "button";
      mb.onclick = function () { oneMore(r, mb, more); };
      more.appendChild(mb); el.foot.appendChild(more);
    }
  }
  function canHelp(r) { return r.mode === "demo" ? demoReserve(r).length > 0 : true; }
  function demoReserve(r) {
    var out = [];
    r.secs.forEach(function (s) { demoPool(s.id).slice(r.demoTaken && r.demoTaken[s.id] || 0).forEach(function (i) { out.push(i); }); });
    return out.filter(function (i) { return r.used.indexOf(normUrl(i.url)) < 0; }).slice(0, HELPING);
  }
  function oneMore(r, btn, wrap) {
    if (r.helpingUsed) return; r.helpingUsed = true; btn.disabled = true; btn.textContent = "Finding one more helping…";
    var done = function (items, note) {
      wrap.innerHTML = "";
      items = dedupeInto(r, "helping", items, HELPING); r.helping = items;
      if (items.length) {
        var s = h("section", "qc-esec qc-helping"); s.appendChild(h("h3", "qc-esechead", "One more helping"));
        var st_ = h("div", "qc-stream"); items.forEach(function (it) { st_.appendChild(itemNode(it, r.cfg.links)); }); s.appendChild(st_); wrap.appendChild(s);
        wrap.appendChild(h("p", "qc-end", "That’s really the edition."));
      } else wrap.appendChild(h("p", "qc-endnote", note || "No more sourced items found. That’s the edition."));
      updateMeta(r);
    };
    if (r.mode === "demo") { done(demoReserve(r).map(function (i) { var c = JSON.parse(JSON.stringify(i)); delete c.sec; return c; })); return; }
    var picks = r.secs.filter(function (s) { return s.id !== "humor" && s.id !== "puzzles"; }), sec = picks[0] || r.secs[0];
    var combined = {id: sec.id, title: "One more helping", brief: "Up to " + HELPING + " more items that fit this paper, each from a different section topic: " + r.secs.map(function (s) { return s.title; }).join(", ") + "."};
    callGrok(combined, HELPING, r.used.slice(), "Each item must be about something different from the others.", r.abort.signal).then(function (v) {
      done(v.items, v.dropped ? "Nothing Grok returned could be linked to a real source. That’s the edition." : "");
    }, function (e) { done([], describeError(e && e.status, e && e.body, e && e.err)); });
  }
  function printEdition() {
    var old = document.title; document.title = (run && run.cfg.name || "Quick Create") + " · " + ymd(new Date());
    document.body.classList.add("qc-printing");
    var restore = function () { document.title = old; document.body.classList.remove("qc-printing"); window.removeEventListener("afterprint", restore); };
    window.addEventListener("afterprint", restore); window.print();
  }

  // ---------- export / import / share ----------
  function download(name, text, type) {
    var a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], {type: type})); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  function exportConfig() { var c = JSON.parse(JSON.stringify(st)); return {format: "mediabot-quick-create/1", saved: ymd(new Date()), config: c}; }
  function q(s) { return JSON.stringify(String(s)); }   // a JSON string is a valid YAML double-quoted scalar
  function toYaml(c) {
    c = normalize(c);
    var secs = c.sections.filter(function (s) { return s.on; }), b = budgetFor(secs), name = c.name || "My Paper", slug = slugify(name);
    var weights = {}; secs.forEach(function (s, i) { weights[s.id] = Math.max(1, 10 - i); });
    var L = ["# " + name + ": a paper made with MediaBot Quick Create (exported " + ymd(new Date()) + ").",
      "# Same shape as papers/*/paper.yaml. To adopt: copy to papers/" + slug + "/paper.yaml, set `reader`, then wire sources for new section ids.",
      "# Section ids that match an existing paper (x, faith, science, ideas, people, craft, tech, humor, games, passage) already have pipeline sources;",
      "# others (business, health, custom ids) need a source added. Per-section topics are kept under quick_create.briefs.",
      "",
      "name: " + q(name), "slug: " + slug, "public: false", "reader: " + q("You"),
      "layout: slow",
      "description: " + q("A " + c.minutes + "-minute paper: " + (b.secs.map(function (s) { return s.title; }).join(", ") || "no sections") + ". Finite, sourced, with a clear end."),
      "",
      "masthead:", "  style: slow", "",
      "print:", "  size: medium", "  photos: false", "  qr: false", "",
      "web:", "  images: false", "  x_links: " + (c.links ? "true" : "false"), "  end_line: " + q("That’s the edition."), "  read_time: true", "",
      "total_max: " + b.total, "sections:"];
    c.sections.forEach(function (s) {
      var on = s.on && b.per[s.id] != null;
      L.push("  - {id: " + s.id + ", title: " + q(s.title) + ", enabled: " + (on ? "true" : "false") + ", weight: " + (on ? weights[s.id] : 1) + ", max_items: " + (on ? b.per[s.id] : 0) + (s.custom ? ", custom: true" : "") + "}");
    });
    var fav = handles(c.favor).map(function (h_) { return q("@" + h_); }), avoid = handles(c.avoid).map(function (h_) { return q("@" + h_); });
    L.push("", "sources:", "  x:", "    must_read: [" + fav.join(", ") + "]", "    avoid: [" + avoid.join(", ") + "]",
      "  web: [" + domains(c.favor).map(q).join(", ") + "]", "  web_avoid: [" + domains(c.avoid).map(q).join(", ") + "]", "",
      "filters:", "  novelty: strict", "", "quick_create:", "  version: 1", "  minutes: " + c.minutes,
      "  tone: [" + c.tone.map(q).join(", ") + "]", "  interests: " + q(c.interests.trim()), "  freshness_days: " + c.fresh,
      "  search: {x: " + c.x + ", web: " + c.web + ", only_favored_x: " + c.only + "}", "  briefs:");
    c.sections.forEach(function (s) { L.push("    " + s.id + ": " + q(s.brief)); });
    return L.join("\n") + "\n";
  }
  function b64e(s) { var by = new TextEncoder().encode(s), bin = ""; by.forEach(function (x) { bin += String.fromCharCode(x); }); return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); }
  function b64d(s) { s = s.replace(/-/g, "+").replace(/_/g, "/"); while (s.length % 4) s += "="; var bin = atob(s), by = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) by[i] = bin.charCodeAt(i); return new TextDecoder().decode(by); }
  function shareUrl() { return location.origin + location.pathname + "#c=" + b64e(JSON.stringify(st)); }
  function fromHash() {
    var m = /[#&]c=([A-Za-z0-9_-]+)/.exec(location.hash || ""); if (!m) return null;
    try { return normalize(JSON.parse(b64d(m[1]))); } catch (e) { return null; }
  }

  // saved papers
  function papers() { try { return JSON.parse(localStorage.getItem(K.papers)) || {}; } catch (e) { return {}; } }
  function renderSaved() {
    var sel = $("qc-saved"), p = papers(), names = Object.keys(p).sort(); sel.innerHTML = "";
    var o = document.createElement("option"); o.value = ""; o.textContent = names.length ? "Choose a saved paper" : "None saved yet"; sel.appendChild(o);
    names.forEach(function (n) { var x = document.createElement("option"); x.value = n; x.textContent = n; sel.appendChild(x); });
  }
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text);
    return new Promise(function (ok, no) { var t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); try { document.execCommand("copy") ? ok() : no(); } catch (e) { no(e); } t.remove(); });
  }

  // ---------- wiring ----------
  function init() {
    var h0 = fromHash(), d = loadDraft();
    st = h0 || (d ? normalize(d) : fresh());
    $("qc-key").value = ""; $("qc-model").value = getModel(); $("qc-proxy").value = ls(K.proxy);
    if (getKey()) $("qc-key").placeholder = "Key saved on this device";
    renderForm();
    if (h0) setStatus("Loaded the paper from a shared link. Not saved until you press Save.");
    ["qc-name", "qc-interests", "qc-favor", "qc-avoid"].forEach(function (id) { $(id).addEventListener("input", readForm); });
    ["qc-fresh", "qc-sx", "qc-sw", "qc-only", "qc-links"].forEach(function (id) { $(id).addEventListener("change", readForm); });
    $("qc-cadd").onclick = function () {
      var n = $("qc-cname").value.trim(), br = $("qc-cbrief").value.trim();
      if (!n) { setStatus("Name your section first.", true); return; }
      var id = "c-" + slugify(n), base = id, i = 2; while (st.sections.some(function (s) { return s.id === id; })) id = base + "-" + i++;
      st.sections.push({id: id, title: n.slice(0, 40), on: true, brief: (br || n).slice(0, 400), custom: true});
      $("qc-cname").value = ""; $("qc-cbrief").value = ""; changed(true); setStatus("Added " + n + ".");
    };
    $("qc-go").onclick = function () { generate(getKey() ? "live" : "demo"); };
    $("qc-demo").onclick = function () { generate("demo"); };
    $("qc-keysave").onclick = function () {
      var k = $("qc-key").value.trim(), m = $("qc-model").value.trim() || DEFAULT_MODEL, p = $("qc-proxy").value.trim();
      try {
        if (k) localStorage.setItem(K.key, k);
        localStorage.setItem(K.model, m);
        if (p && !/^https:\/\//.test(p)) { setStatus("The proxy URL must start with https://", true); return; }
        p ? localStorage.setItem(K.proxy, p) : localStorage.removeItem(K.proxy);
      } catch (e) { setStatus("This browser would not save settings.", true); return; }
      $("qc-key").value = ""; $("qc-key").placeholder = getKey() ? "Key saved on this device" : "xai-…"; renderMode(); setStatus("Settings saved on this device.");
    };
    $("qc-keyclear").onclick = function () { try { localStorage.removeItem(K.key); } catch (e) {} $("qc-key").value = ""; $("qc-key").placeholder = "xai-…"; renderMode(); setStatus("Key removed from this browser."); };
    $("qc-save").onclick = function () {
      readForm(); var n = st.name || "My Paper", p = papers(); p[n] = st;
      try { localStorage.setItem(K.papers, JSON.stringify(p)); } catch (e) { setStatus("This browser would not save.", true); return; }
      renderSaved(); $("qc-saved").value = n; setStatus("Saved “" + n + "” in this browser.");
    };
    $("qc-load").onclick = function () { var n = $("qc-saved").value, p = papers(); if (!n || !p[n]) { setStatus("Choose a saved paper first.", true); return; } st = normalize(p[n]); renderForm(); saveDraft(); setStatus("Loaded “" + n + "”."); };
    $("qc-del").onclick = function () { var n = $("qc-saved").value, p = papers(); if (!n || !p[n]) return; delete p[n]; try { localStorage.setItem(K.papers, JSON.stringify(p)); } catch (e) {} renderSaved(); setStatus("Deleted “" + n + "”."); };
    $("qc-json").onclick = function () { readForm(); download(slugify(st.name) + ".quickcreate.json", JSON.stringify(exportConfig(), null, 2) + "\n", "application/json"); setStatus("Downloaded the config. It never includes your key."); };
    $("qc-import").onclick = function () { $("qc-file").click(); };
    $("qc-file").onchange = function () {
      var f = this.files && this.files[0]; if (!f) return;
      if (f.size > 200000) { setStatus("That file is too big to be a paper config.", true); return; }
      var rd = new FileReader();
      rd.onload = function () { try { var j = JSON.parse(rd.result); st = normalize(j && j.config ? j.config : j); renderForm(); saveDraft(); setStatus("Imported “" + (st.name || "paper") + "”."); } catch (e) { setStatus("That isn't a Quick Create JSON file.", true); } };
      rd.readAsText(f); this.value = "";
    };
    $("qc-yaml").onclick = function () { readForm(); download("paper.yaml", toYaml(st), "text/yaml"); setStatus("Downloaded paper.yaml. See the header comment for how to adopt it."); };
    $("qc-link").onclick = function () {
      readForm(); var u = shareUrl();
      try { history.replaceState(null, "", u.slice(location.origin.length)); } catch (e) {}
      copyText(u).then(function () { setStatus("Share link copied. It holds the config only, never your key."); }, function () { setStatus("Copy the link from your address bar.", false); });
    };
  }
  window.__qc = {normalize: normalize, normUrl: normUrl, citedSet: citedSet, vetItems: vetItems, parseItems: parseItems, outputText: outputText,
                 allocate: allocate, toYaml: toYaml, CAPS: CAPS, state: function () { return st; }, setState: function (s) { st = normalize(s); renderForm(); }};
  init();
})();
