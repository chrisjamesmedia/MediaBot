// Quick Create: a one-screen builder for a finite paper.
// Live mode calls the xAI Responses API (web_search + x_search) with the reader's own key, kept in localStorage and
// sent only to api.x.ai (or an optional proxy URL the reader sets). Demo mode renders items already published on this site.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var API = "https://api.x.ai/v1/responses", DEFAULT_MODEL = "grok-4.7";
  var K = {key: "mb:qc:key", model: "mb:qc:model", proxy: "mb:qc:proxy", draft: "mb:qc:draft", papers: "mb:qc:papers"};
  var CAPS = {5: 14, 10: 28, 15: 40}, WPM = 230, HELPING = 3, CONCURRENCY = 3;
  var TONES = ["wholesome", "based", "insightful", "funny", "calm", "curious", "practical", "bold"];

  // Topics and Fun are chips. People you follow is a first-class list, not a chip.
  // src/w/max/rules stay internal; the chip UI never mentions item caps.
  var FOLLOWING = {id: "following", title: "People you follow", group: "people",
    brief: "Recent posts and writing by the people the reader follows, quoted as they wrote them.",
    src: ["x", "web"], w: 2, max: 8,
    rules: "Only posts or pages by these people, quoted verbatim, with a link to the exact post or page. Never invent a post or quote. If you cannot source it, drop it."};
  var TOPICS = [
    {id: "faith", title: "Faith & Scripture", group: "topic", brief: "Scripture and faith: one short Bible passage with its reference and a link to where it is published, then posts of real faith, gratitude and wisdom.", src: ["x", "web"], w: 1,
      rules: "A Scripture passage (kind \"passage\") must be quoted exactly from a page you opened and linked."},
    {id: "science", title: "Nature & Science", group: "topic", brief: "Wonder from the natural world and honest science: studies, animals, space, seasons, history of discovery.", src: ["x", "web"], w: 1},
    {id: "ideas", title: "Books & Ideas", group: "topic", brief: "Books, essays, poetry, philosophy and ideas worth slowing down for.", src: ["x", "web"], w: 1},
    {id: "people", title: "People & Stories", group: "topic", brief: "Real stories about real people: kindness, family, history, craft, perseverance.", src: ["x", "web"], w: 1},
    {id: "craft", title: "Craft & Work", group: "topic", brief: "Making, building, cooking, gardening, design and the dignity of good work.", src: ["x", "web"], w: 1},
    {id: "tech", title: "Tech / AI", group: "topic", brief: "Useful, concrete technology and AI news and ideas, with the substance and not the hype.", src: ["x", "web"], w: 1}
  ];
  var FUN = [
    {id: "humor", title: "Jokes", group: "fun", brief: "A real joke or a funny line, posted by an identifiable person or account.", src: ["x", "web"], w: 0.5, max: 3,
      rules: "Jokes (kind \"joke\"): only a real joke that appears word for word in a post or page you retrieved, credited to who posted it. Never write, adapt or complete a joke yourself. If you cannot find a real one, return no items."},
    {id: "memes", title: "Memes", group: "fun", brief: "A real meme or funny post someone actually published, with credit.", src: ["x", "web"], w: 0.4, max: 2,
      rules: "Memes (kind \"post\"): only a real meme or funny post you retrieved. Credit the poster and link the exact post or page. Never invent, describe or recreate a meme. If there is no sourced post, return no items."},
    {id: "game", title: "Game pick", group: "fun", brief: "One real game recommendation someone published.", src: ["x", "web"], w: 0.3, max: 1,
      rules: "Game pick (kind \"article\"): one real recommendation or review you retrieved. Quote or summarize only what that source says, and link it. Never invent a game, review or rating. If you cannot source one, return no items."},
    {id: "movie", title: "Movie pick", group: "fun", brief: "One real movie or show recommendation someone published.", src: ["x", "web"], w: 0.3, max: 1,
      rules: "Movie pick (kind \"article\"): one real recommendation or review you retrieved. Quote or summarize only what that source says, and link it. Never invent a title, review or rating. If you cannot source one, return no items."},
    {id: "poem", title: "Poem", group: "fun", brief: "A real poem or a short passage of verse, quoted exactly.", src: ["web", "x"], w: 0.4, max: 1,
      rules: "Poem (kind \"passage\"): exact words from a page you opened, with author, work, and a link to a page that contains them. If you cannot link the exact words, drop it. Never write or complete a poem yourself."}
  ];
  var PRESETS = TOPICS.concat(FUN);
  var DEFAULT_ON = {faith: 1, science: 1, ideas: 1, people: 1, craft: 1, humor: 1};
  var P = {following: FOLLOWING}; PRESETS.forEach(function (p) { P[p.id] = p; });
  var FUN_IDS = {}; FUN.forEach(function (p) { FUN_IDS[p.id] = 1; });

  var sample = {items: [], label: ""};
  try { sample = JSON.parse($("qc-sample").textContent); } catch (e) {}

  function fresh() {
    return {v: 2, name: "", topic: "", minutes: 5, tone: ["wholesome", "insightful"], favor: "", avoid: "", fresh: 7,
            x: true, web: true, only: false, links: true, people: [],
            delivery: {how: "site", when: "now", time: "07:15", weekday: "Monday", email: "", phone: ""},
            sections: PRESETS.map(function (p) { return {id: p.id, title: p.title, on: !!DEFAULT_ON[p.id], brief: p.brief, custom: false, group: p.group}; })};
  }
  var st = fresh();

  function str(v, n) { return typeof v === "string" ? v.slice(0, n) : ""; }
  function minutesOf(v) { return CAPS[v] ? +v : (v === 3 ? 5 : 5); }
  var HOWS = ["site", "email", "text"], WHENS = ["now", "daily", "weekly"];
  var WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  function normalizeDelivery(d) {
    d = d && typeof d === "object" ? d : {};
    var time = str(d.time, 5);
    if (!/^\d{2}:\d{2}$/.test(time)) time = "07:15";
    var day = WEEKDAYS.indexOf(d.weekday) >= 0 ? d.weekday : "Monday";
    return {how: HOWS.indexOf(d.how) >= 0 ? d.how : "site", when: WHENS.indexOf(d.when) >= 0 ? d.when : "now",
            time: time, weekday: day, email: str(d.email, 120).trim(), phone: str(d.phone, 24).trim()};
  }
  function deliveryPublic(d) {
    d = normalizeDelivery(d);
    return {how: d.how, when: d.when, time: d.time, weekday: d.weekday};
  }
  function needsDeliveryNote(d) { d = d || st.delivery; return d.how !== "site" || d.when !== "now"; }
  function normalize(c) {
    var d = fresh();
    if (!c || typeof c !== "object") return d;
    var topic = str(c.topic, 400) || str(c.interests, 400);
    var out = {v: 2, name: str(c.name, 60), topic: topic, minutes: minutesOf(c.minutes),
      tone: Array.isArray(c.tone) ? c.tone.filter(function (t) { return TONES.indexOf(t) >= 0; }) : d.tone,
      favor: str(c.favor, 300), avoid: str(c.avoid, 300),
      fresh: [3, 7, 14, 30].indexOf(+c.fresh) >= 0 ? +c.fresh : d.fresh,
      x: c.x !== false, web: c.web !== false, only: !!c.only, links: c.links !== false, people: [],
      delivery: normalizeDelivery(c.delivery), sections: []};
    if (!out.x && !out.web) out.web = true;
    (Array.isArray(c.people) ? c.people : []).slice(0, 30).forEach(function (p) {
      var person = normalizePerson(p);
      if (person && !out.people.some(function (x) { return x.key === person.key; })) out.people.push(person);
    });
    var seen = {}, list = Array.isArray(c.sections) ? c.sections.slice(0, 30) : [];
    list.forEach(function (s) {
      if (!s || typeof s !== "object") return;
      var id = str(s.id, 40).replace(/[^a-z0-9_-]/gi, "").toLowerCase();
      if (!id || seen[id] || id === "following") return;
      var preset = P[id] && !s.custom;
      if (!preset && !s.custom) return;          // drop retired presets rather than show them
      seen[id] = 1;
      out.sections.push({id: id, title: preset ? P[id].title : str(s.title, 40) || "Custom", on: s.on !== false,
        brief: preset ? P[id].brief : (str(s.brief, 400) || str(s.title, 40)), custom: !preset, group: preset ? P[id].group : "topic"});
    });
    PRESETS.forEach(function (p) {
      if (!seen[p.id]) out.sections.push({id: p.id, title: p.title, on: false, brief: p.brief, custom: false, group: p.group});
    });
    return out;
  }
  function saveDraft() { try { localStorage.setItem(K.draft, JSON.stringify(st)); } catch (e) {} }
  function loadDraft() { try { return JSON.parse(localStorage.getItem(K.draft)); } catch (e) { return null; } }

  function slugify(s) { return (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "my-paper"; }
  function words(s) { return (String(s || "").match(/\S+/g) || []).length; }
  function setStatus(msg, bad) { var e = $("qc-status"); e.textContent = msg || ""; e.className = "qc-help" + (bad ? " bad" : ""); }
  function handles(s) { return (String(s || "").match(/@[A-Za-z0-9_]{1,15}/g) || []).map(function (h) { return h.slice(1); }); }
  function domains(s) { return (String(s || "").match(/\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}\b/gi) || []).map(function (d) { return d.toLowerCase(); }); }
  function normalizePerson(p) {
    if (typeof p === "string") p = {raw: p};
    if (!p || typeof p !== "object") return null;
    var raw = str(p.raw || p.label || p.handle || p.name, 40).trim();
    if (!raw) return null;
    var hm = raw.match(/^@?([A-Za-z0-9_]{1,15})$/);
    var handle = str(p.handle, 15).replace(/^@/, "").replace(/[^A-Za-z0-9_]/g, "") || (hm ? hm[1] : "");
    var name = hm ? "" : (str(p.name, 40) || raw.replace(/^@/, ""));
    if (!handle && !name) return null;
    var label = handle ? "@" + handle : name;
    return {handle: handle, name: name, label: label, key: (handle || name).toLowerCase()};
  }
  function peopleHandles() { return st.people.map(function (p) { return p.handle; }).filter(Boolean); }
  function peopleLabels() { return st.people.map(function (p) { return p.label; }).join(", "); }
  function followingSec() {
    return {id: "following", title: FOLLOWING.title, on: true, brief: FOLLOWING.brief, custom: false, group: "people"};
  }
  // Edition order: People you follow, then Topics, then Fun.
  function active() {
    var topics = [], fun = [];
    st.sections.forEach(function (s) {
      if (!s.on) return;
      if (s.group === "fun" || (!s.custom && FUN_IDS[s.id])) fun.push(s);
      else topics.push(s);
    });
    return (st.people.length ? [followingSec()] : []).concat(topics, fun);
  }
  function paperName() { return (st.name || "").trim() || (st.topic || "").trim().split(/[\n,.]/)[0].slice(0, 40) || "Your paper"; }

  function allocate(secs, total) {
    var n = secs.length, a = {};
    if (!n) return a;
    var w = secs.map(function (s) { return P[s.id] ? P[s.id].w : 1; }), sum = w.reduce(function (x, y) { return x + y; }, 0);
    var raw = w.map(function (x) { return total * x / sum; }), got = raw.map(function (r, i) {
      var m = P[secs[i].id] && P[secs[i].id].max; return Math.max(1, Math.min(m || 99, Math.floor(r)));
    });
    var used = got.reduce(function (x, y) { return x + y; }, 0), guard = 0;
    while (used < total && guard++ < 200) {
      var best = -1, bf = -1;
      raw.forEach(function (r, i) { var m = P[secs[i].id] && P[secs[i].id].max; var f = r - got[i]; if ((!m || got[i] < m) && f > bf) { bf = f; best = i; } });
      if (best < 0) break; got[best]++; used++;
    }
    while (used > total) {
      var j = got.lastIndexOf(Math.max.apply(null, got)); if (got[j] <= 1) break; got[j]--; used--;
    }
    secs.forEach(function (s, i) { a[s.id] = got[i]; });
    return a;
  }
  function budgetFor(secs, minutes) {
    var total = CAPS[minutes || st.minutes] || CAPS[5], a = allocate(secs, total), sum = 0;
    secs.forEach(function (s) { sum += a[s.id]; });
    if (sum > total) {
      var left = total; secs = secs.filter(function (s) { if (left > 0) { left--; return true; } return false; });
      a = allocate(secs, total);
    }
    return {total: total, per: a, secs: secs};
  }

  // ---------- builder UI ----------
  var adding = false;
  function chipButton(s, i, after) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "qc-chip" + (s.on ? " on" : "");
    b.setAttribute("aria-pressed", s.on ? "true" : "false");
    b.textContent = s.title;
    b.onclick = function () { s.on = !s.on; saveDraft(); after(); };
    if (s.custom) {
      var x = document.createElement("span"); x.className = "qc-chipx"; x.setAttribute("aria-label", "Remove " + s.title); x.textContent = "×";
      x.onclick = function (e) { e.stopPropagation(); st.sections.splice(i, 1); saveDraft(); after(); };
      b.appendChild(x);
    }
    return b;
  }
  function renderPeople() {
    var box = $("qc-plist"); box.innerHTML = "";
    st.people.forEach(function (p, i) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "qc-chip on"; b.setAttribute("role", "listitem");
      b.textContent = p.label;
      var x = document.createElement("span"); x.className = "qc-chipx"; x.setAttribute("aria-label", "Remove " + p.label); x.textContent = "×";
      x.onclick = function (e) { e.stopPropagation(); st.people.splice(i, 1); saveDraft(); renderPeople(); };
      b.onclick = function () { st.people.splice(i, 1); saveDraft(); renderPeople(); };
      b.appendChild(x); box.appendChild(b);
    });
  }
  function addPeople(raw) {
    var parts = String(raw || "").split(/[,\n]+/);
    var added = 0;
    parts.forEach(function (part) {
      var person = normalizePerson(part);
      if (!person || st.people.some(function (p) { return p.key === person.key; })) return;
      if (st.people.length >= 20) return;
      st.people.push(person); added++;
    });
    if (added) { saveDraft(); renderPeople(); }
    return added;
  }
  function renderTopicChips() {
    var box = $("qc-chips"); box.innerHTML = "";
    st.sections.forEach(function (s, i) {
      if (s.group === "fun" || (!s.custom && FUN_IDS[s.id])) return;
      box.appendChild(chipButton(s, i, renderTopicChips));
    });
    if (adding) {
      var inp = document.createElement("input");
      inp.type = "text"; inp.className = "qc-chipadd"; inp.maxLength = 40; inp.placeholder = "Name this topic";
      inp.setAttribute("aria-label", "Name your topic");
      var finished = false;
      var done = function () {
        if (finished) return; finished = true;
        var n = inp.value.trim(); adding = false;
        if (n) {
          var id = "c-" + slugify(n), base = id, k = 2;
          while (st.sections.some(function (s) { return s.id === id; })) id = base + "-" + k++;
          st.sections.push({id: id, title: n.slice(0, 40), on: true, brief: n.slice(0, 400), custom: true, group: "topic"});
          saveDraft();
        }
        renderTopicChips();
      };
      inp.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); done(); } if (e.key === "Escape") { adding = false; renderTopicChips(); } });
      inp.addEventListener("blur", function () { setTimeout(done, 50); });
      box.appendChild(inp);
      setTimeout(function () { inp.focus(); }, 0);
    } else {
      var add = document.createElement("button");
      add.type = "button"; add.className = "qc-chip add"; add.textContent = "+ Add your own";
      add.onclick = function () { adding = true; renderTopicChips(); };
      box.appendChild(add);
    }
  }
  function renderFunChips() {
    var box = $("qc-funchips"); box.innerHTML = "";
    st.sections.forEach(function (s, i) {
      if (!(s.group === "fun" || FUN_IDS[s.id])) return;
      box.appendChild(chipButton(s, i, renderFunChips));
    });
  }
  function renderDelivery() {
    var d = st.delivery, how = $("qc-dhow"), when = $("qc-dwhen");
    how.innerHTML = "";
    [{id: "site", label: "On the site"}, {id: "email", label: "Email"}, {id: "text", label: "Text"}].forEach(function (o) {
      var l = document.createElement("label"), i = document.createElement("input"), sp = document.createElement("span");
      i.type = "radio"; i.name = "qc-dhow"; i.value = o.id; i.checked = d.how === o.id; sp.textContent = o.label;
      i.onchange = function () { d.how = o.id; saveDraft(); renderDelivery(); };
      l.appendChild(i); l.appendChild(sp); how.appendChild(l);
    });
    when.innerHTML = "";
    [{id: "now", label: "Just now"}, {id: "daily", label: "Every morning"}, {id: "weekly", label: "Weekly"}].forEach(function (o) {
      var l = document.createElement("label"), i = document.createElement("input"), sp = document.createElement("span");
      i.type = "radio"; i.name = "qc-dwhen"; i.value = o.id; i.checked = d.when === o.id; sp.textContent = o.label;
      i.onchange = function () { d.when = o.id; saveDraft(); renderDelivery(); };
      l.appendChild(i); l.appendChild(sp); when.appendChild(l);
    });
    $("qc-dwhen-extra").hidden = d.when === "now";
    $("qc-dday-wrap").hidden = d.when !== "weekly";
    $("qc-dtime").value = d.time;
    var sel = $("qc-dday");
    if (!sel.options.length) WEEKDAYS.forEach(function (day) { var o = document.createElement("option"); o.value = day; o.textContent = day; sel.appendChild(o); });
    sel.value = d.weekday;
    $("qc-dcontact").hidden = d.how === "site";
    $("qc-demail-wrap").hidden = d.how !== "email";
    $("qc-dphone-wrap").hidden = d.how !== "text";
    $("qc-demail").value = d.email; $("qc-dphone").value = d.phone;
    $("qc-dnote").hidden = !needsDeliveryNote(d);
  }
  function renderForm() {
    $("qc-topic").value = st.topic; $("qc-name").value = st.name; $("qc-favor").value = st.favor; $("qc-avoid").value = st.avoid;
    $("qc-fresh").value = String(st.fresh); $("qc-sx").checked = st.x; $("qc-sw").checked = st.web; $("qc-only").checked = st.only; $("qc-links").checked = st.links;
    var t = $("qc-tone"); t.innerHTML = "";
    TONES.forEach(function (name) {
      var l = document.createElement("label"), i = document.createElement("input"), s = document.createElement("span");
      i.type = "checkbox"; i.checked = st.tone.indexOf(name) >= 0; s.textContent = name;
      i.onchange = function () { st.tone = TONES.filter(function (n) { return n === name ? i.checked : st.tone.indexOf(n) >= 0; }); saveDraft(); };
      l.appendChild(i); l.appendChild(s); t.appendChild(l);
    });
    var m = $("qc-min"); m.innerHTML = "";
    [5, 10, 15].forEach(function (n) {
      var l = document.createElement("label"), i = document.createElement("input"), s = document.createElement("span");
      i.type = "radio"; i.name = "qc-minutes"; i.value = n; i.checked = st.minutes === n; s.textContent = n + " min";
      i.onchange = function () { st.minutes = n; saveDraft(); };
      l.appendChild(i); l.appendChild(s); m.appendChild(l);
    });
    renderPeople(); renderTopicChips(); renderFunChips(); renderDelivery(); renderSaved();
  }
  function readForm() {
    st.topic = $("qc-topic").value; st.name = $("qc-name").value.trim(); st.favor = $("qc-favor").value.trim(); st.avoid = $("qc-avoid").value.trim();
    st.fresh = +$("qc-fresh").value; st.x = $("qc-sx").checked; st.web = $("qc-sw").checked; st.only = $("qc-only").checked; st.links = $("qc-links").checked;
    if (!st.x && !st.web) { st.web = true; $("qc-sw").checked = true; }
    st.delivery.time = $("qc-dtime").value || st.delivery.time;
    st.delivery.weekday = $("qc-dday").value || st.delivery.weekday;
    st.delivery.email = $("qc-demail").value.trim();
    st.delivery.phone = $("qc-dphone").value.trim();
    saveDraft();
  }

  function ls(k) { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } }
  function getKey() { return ls(K.key); }
  function getModel() { return ls(K.model) || DEFAULT_MODEL; }
  function showKeyPrompt(open) {
    var box = $("qc-keyprompt");
    if (open) {
      box.hidden = false; $("qc-key").value = ""; $("qc-key").placeholder = "xai-…";
      $("qc-key").focus(); box.scrollIntoView({behavior: "smooth", block: "nearest"});
    } else box.hidden = true;
  }
  function saveConn(key) {
    var m = $("qc-model").value.trim() || DEFAULT_MODEL, p = $("qc-proxy").value.trim();
    if (p && !/^https:\/\//.test(p)) { setStatus("The proxy URL must start with https://", true); return false; }
    try {
      if (key) localStorage.setItem(K.key, key);
      localStorage.setItem(K.model, m);
      p ? localStorage.setItem(K.proxy, p) : localStorage.removeItem(K.proxy);
    } catch (e) { setStatus("This browser would not save settings.", true); return false; }
    return true;
  }

  // ---------- Grok calls ----------
  function normUrl(u) {
    try {
      var x = new URL(u), host = x.hostname.toLowerCase().replace(/^www\./, "").replace(/^(mobile|m)\./, "");
      var m = x.pathname.match(/\/status(?:es)?\/(\d+)/);
      if ((host === "x.com" || host === "twitter.com") && m) return "x:" + m[1];
      return host + x.pathname.replace(/\/+$/, "").toLowerCase();
    } catch (e) { return ""; }
  }
  function isXUrl(u) {
    try { var h = new URL(u).hostname.toLowerCase().replace(/^www\./, ""); return h === "x.com" || h === "twitter.com"; } catch (e) { return false; }
  }
  function hostOf(u) { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return "link"; } }
  function citedSet(resp) {
    var set = {};
    function add(u) { var n = normUrl(u); if (n) set[n] = 1; }
    function walk(o, depth) {
      if (depth > 8 || o == null) return;
      if (typeof o === "string") { (o.match(/https?:\/\/[^\s"'<>)\]]+/g) || []).forEach(add); return; }
      if (Array.isArray(o)) { o.forEach(function (v) { walk(v, depth + 1); }); return; }
      if (typeof o === "object") {
        if (o.type === "output_text") { walk(o.annotations, depth + 1); return; }
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
      if ((kind === "joke" || kind === "passage") && !(o.author || o.handle)) { dropped++; return; }
      out.push(o);
    });
    return {items: out, dropped: dropped};
  }
  function ymd(d) { var z = function (n) { return (n < 10 ? "0" : "") + n; }; return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()); }
  function toolsFor(sec) {
    var want = (P[sec.id] ? P[sec.id].src : ["x", "web"]).filter(function (s) { return s === "x" ? st.x : st.web; });
    if (!want.length) want = [st.x ? "x" : "web"];
    var tools = [];
    if (want.indexOf("x") >= 0) {
      var t = {type: "x_search", from_date: ymd(new Date(Date.now() - st.fresh * 864e5)), to_date: ymd(new Date())};
      var av = handles(st.avoid).slice(0, 20), fv = peopleHandles().concat(handles(st.favor)).slice(0, 20);
      if (av.length) t.excluded_x_handles = av;
      if (sec.id === "following" && peopleHandles().length) t.allowed_x_handles = peopleHandles().slice(0, 20);
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
    "4. Never invent or rewrite quotes, authors, jokes, memes, poems, recommendations, statistics or links. Never write jokes, memes, poems or reviews yourself.",
    "5. No more than two items from the same author. No duplicates. Skip ads, giveaways, outrage bait and anything crude or hateful.",
    "6. Reply with one JSON object and nothing else: {\"items\":[{\"kind\":\"post|article|passage|joke|puzzle\",\"headline\":\"web items only, else empty\",\"text\":\"...\",\"author\":\"...\",\"handle\":\"X handle without @, or empty\",\"outlet\":\"publication or site, or empty\",\"url\":\"https://...\",\"date\":\"YYYY-MM-DD or empty\",\"answer\":\"puzzles only, only if the source gives it\"}]}"
  ].join("\n");
  function userPrompt(sec, n, tools, used, extra) {
    var L = ["Section: " + sec.title, "Topic: " + (sec.brief || sec.title), "Find up to " + n + " item" + (n === 1 ? "" : "s") + " for this section."];
    if (sec.id === "following") L.push("Find recent posts or writing by these people the reader follows: " + peopleLabels() + ". Prefer posts they wrote, quoted verbatim. If a name has no X handle, search X and the web for something they recently wrote, and only keep it if you can link the source.");
    if (st.topic.trim()) L.push("The reader wants to read about: " + st.topic.trim());
    if (st.people.length && sec.id !== "following") L.push("The reader follows: " + peopleLabels() + ". Prefer these voices when they fit the topic.");
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
    if (!status) return "Could not reach api.x.ai from this browser (network or CORS). Try again, or set a proxy URL under More options.";
    var msg = ""; try { var j = JSON.parse(body); msg = (j.error && (j.error.message || j.error)) || j.message || j.detail || ""; if (typeof msg !== "string") msg = JSON.stringify(msg); } catch (x) { msg = String(body || "").slice(0, 160); }
    if (status === 401) return "That key was rejected. Check it and try again.";
    if (status === 403) return "xAI refused the request: " + (msg || "the key may lack credits or access to this model.");
    if (status === 429) return "Rate limited by xAI. Wait a moment and try again.";
    return "xAI error " + status + (msg ? ": " + msg.slice(0, 200) : "");
  }
  function callGrok(sec, n, used, extra, signal) {
    var tools = toolsFor(sec);
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
            return vetItems(parseItems(outputText(resp)), citedSet(resp));
          });
        }, function (e) { throw {status: 0, err: e}; });
    }
    return go();
  }

  // ---------- run ----------
  var run = null;
  function newRun() { return {abort: typeof AbortController !== "undefined" ? new AbortController() : {signal: undefined, abort: function () {}}, cancelled: false, items: {}, used: [], authors: {}}; }
  function dedupeInto(r, list, n) {
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
  function startMake() {
    readForm();
    if (!active().length) { setStatus("Add someone you follow, pick a topic, or pick something fun.", true); return; }
    if (!getKey()) { setStatus(""); showKeyPrompt(true); return; }
    generate("live");
  }
  function generate(mode) {
    readForm();
    var b = budgetFor(active());
    if (!b.secs.length) { setStatus("Pick at least one section.", true); return; }
    showKeyPrompt(false); setStatus("");
    if (run) run.abort.abort();
    var r = run = newRun(); r.mode = mode; r.cfg = JSON.parse(JSON.stringify(st)); r.cfg.name = paperName(); r.budget = b; r.helpingUsed = false; r.failed = {};
    r.secs = b.secs.map(function (s) { return {id: s.id, title: s.title, brief: s.brief, custom: s.custom}; });
    beginEdition(r);
    var queue = r.secs.slice(), done = 0, active_ = 0;
    function next() {
      if (r.cancelled) return;
      if (!queue.length) { if (active_ === 0) finish(r); return; }
      var sec = queue.shift(); active_++; markSection(r, sec, "working");
      var p = mode === "demo" ? Promise.resolve(demoSection(r, sec, b.per[sec.id]))
                              : callGrok(sec, b.per[sec.id], r.used.slice(), "", r.abort.signal).then(function (v) { return {items: v.items, dropped: v.dropped}; });
      p.then(function (v) {
        if (r.cancelled) return;
        var items = dedupeInto(r, v.items, b.per[sec.id]);
        r.items[sec.id] = items; r.failed[sec.id] = items.length ? "" : (v.note || (v.dropped ? "Nothing with a real source link was kept." : "Nothing with a real source was found for this section."));
        markSection(r, sec, "done"); fillSection(r, sec);
      }, function (e) {
        if (r.cancelled) return;
        r.items[sec.id] = []; r.failed[sec.id] = describeError(e && e.status, e && e.body, e && e.err);
        r.fatal = r.fatal || (e && (e.status === 401 || e.status === 403) ? r.failed[sec.id] : "");
        markSection(r, sec, "done"); fillSection(r, sec);
      }).then(function () { active_--; done++; progress(r, done, queue[0]); if (r.fatal && queue.length) { queue.length = 0; } next(); });
    }
    progress(r, 0, queue[0]);
    for (var i = 0; i < Math.min(mode === "demo" ? 1 : CONCURRENCY, r.secs.length); i++) next();
  }

  function demoPool(secId) { return sample.items.filter(function (i) { return i.sec === secId; }); }
  function demoSection(r, sec, n) {
    var pool = demoPool(sec.id);
    if (sec.id === "faith") pool = pool.slice().sort(function (a, b) { return (b.kind === "passage") - (a.kind === "passage"); });
    var out = pool.slice(0, n);
    r.demoTaken = r.demoTaken || {}; r.demoTaken[sec.id] = out.length;
    var note = "";
    if (sec.id === "following") { out = []; note = "A sample can't fetch posts from the people you added. Use your key for a fresh search."; }
    else if (sec.custom) note = "A sample can't fill a topic you added. Use your key for a fresh search.";
    else if (!sample.items.some(function (i) { return i.sec === sec.id; })) note = "The sample has nothing for this section. Use your key for a fresh search.";
    return {items: out.map(function (i) { var c = JSON.parse(JSON.stringify(i)); delete c.sec; return c; }), dropped: 0, note: note};
  }

  // ---------- edition view ----------
  var el = {};
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function sourceLine(r, items, emptyNote) {
    if (r.mode === "demo") {
      if (!items || !items.length) return emptyNote || "From your Field Notes and Signal Seeker papers.";
      return "From your Field Notes and Signal Seeker papers.";
    }
    var x = 0, web = 0;
    (items || []).forEach(function (it) { if (isXUrl(it.url)) x++; else web++; });
    if (x && web) return "From X posts and the web, found by Grok search.";
    if (x) return "From X posts found by Grok search.";
    if (web) return "From the web, found by Grok search.";
    return emptyNote || "Grok searched X and the web; nothing with a real source link was kept.";
  }
  function itemSource(it) {
    var who = isXUrl(it.url) ? (it.handle ? "@" + it.handle : it.author) : (it.outlet || hostOf(it.url) || it.author);
    var bits = [];
    if (who) bits.push(who);
    if (it.date) bits.push(it.date);
    return bits.join(" · ");
  }
  function beginEdition(r) {
    var box = $("qc-edition"); box.innerHTML = ""; el = {};
    var head = h("header", "qc-ehead");
    var home = h("a", "qc-home", "← MediaBot"); home.href = "../";
    el.title = h("h2", "qc-etitle", r.cfg.name || "Your paper");
    el.meta = h("p", "qc-emeta", "");
    el.progress = h("p", "qc-progress", "");
    var cancel = h("button", "qc-btn quiet qc-cancel", "Cancel"); cancel.type = "button";
    cancel.onclick = function () { r.cancelled = true; r.abort.abort(); setStatus("Cancelled."); el.progress.textContent = "Cancelled. What arrived is below."; cancel.remove(); finish(r, true); };
    el.cancel = cancel;
    head.appendChild(home); head.appendChild(el.title); head.appendChild(el.meta);
    if (r.mode === "demo") {
      var sb = h("p", "qc-sample", "Sample — these are posts already printed in your Field Notes and Signal Seeker papers, not a fresh search.");
      sb.setAttribute("role", "note"); head.appendChild(sb);
    }
    head.appendChild(el.progress); head.appendChild(cancel);
    box.appendChild(head);
    el.body = h("div", "qc-ebody"); box.appendChild(el.body);
    el.secs = {};
    r.secs.forEach(function (s) {
      var sec = h("section", "qc-esec"); sec.id = "qc-e-" + s.id;
      sec.appendChild(h("h3", "qc-esechead", s.title));
      var from = h("p", "qc-from", r.mode === "demo" ? "From your Field Notes and Signal Seeker papers." : "Grok is searching X and the web…");
      sec.appendChild(from);
      var stream = h("div", "qc-stream"); stream.appendChild(h("p", "qc-wait", "Looking…")); sec.appendChild(stream);
      el.body.appendChild(sec); el.secs[s.id] = {sec: sec, stream: stream, from: from};
    });
    el.foot = h("div", "qc-efoot"); box.appendChild(el.foot);
    updateMeta(r);
    box.scrollIntoView({behavior: "smooth", block: "start"}); box.focus({preventScroll: true});
  }
  function markSection(r, sec, state) {
    var e = el.secs[sec.id]; if (!e) return;
    if (state === "working") { e.stream.innerHTML = ""; e.stream.appendChild(h("p", "qc-wait", "Looking…")); }
  }
  function itemNode(it, links) {
    var art = h("article", "qc-item");
    if (it.headline) art.appendChild(h("h4", "qc-ihead", it.headline));
    var src = itemSource(it);
    if (src) art.appendChild(h("p", "qc-who", src));
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
  function fillSection(r, sec) {
    var e = el.secs[sec.id]; if (!e) return; e.stream.innerHTML = "";
    var items = r.items[sec.id] || [];
    e.from.textContent = sourceLine(r, items, r.failed[sec.id]);
    items.forEach(function (it) { e.stream.appendChild(itemNode(it, r.cfg.links)); });
    if (!items.length && e.from.textContent !== (r.failed[sec.id] || "Nothing to show here."))
      e.stream.appendChild(h("p", "qc-empty", r.failed[sec.id] || "Nothing to show here."));
    updateMeta(r);
  }
  function allItems(r) { var a = []; r.secs.forEach(function (s) { (r.items[s.id] || []).forEach(function (i) { a.push(i); }); }); return a.concat(r.helping || []); }
  function updateMeta(r) {
    var items = allItems(r), w = items.reduce(function (n, i) { return n + words(i.text) + words(i.headline) + words(i.author) + 3; }, 0);
    r.words = w; r.count = items.length;
    var min = Math.max(1, Math.round(w / WPM));
    el.meta.textContent = new Date().toLocaleDateString(undefined, {weekday: "long", month: "long", day: "numeric", year: "numeric"}) +
      (items.length ? " · " + min + " min read" : " · building");
  }
  function progress(r, done, nextSec) {
    if (!el.progress || r.finished) return;
    if (r.mode === "demo") { el.progress.textContent = ""; return; }
    el.progress.textContent = nextSec ? "Looking in " + nextSec.title + "…" : (done < r.secs.length ? "Looking…" : "");
  }

  function finish(r, early) {
    if (r.finished) return; r.finished = true;
    if (el.cancel) el.cancel.remove();
    var n = allItems(r).length;
    el.progress.textContent = r.fatal || "";
    el.foot.innerHTML = "";
    el.foot.appendChild(h("p", "qc-end", n ? "That’s the edition." : "Nothing sourced this time."));
    el.foot.appendChild(h("p", "qc-endnote", n ? "Every item has a real source. Nothing more to scroll." : "Every item had to link to a real source, and none did. Try again, or change what you want to read about."));
    if (r.fatal && (r.fatal.indexOf("key") >= 0 || r.fatal.indexOf("rejected") >= 0)) showKeyPrompt(true);
    var acts = h("div", "qc-actions qc-eactions");
    if (n) { var pb = h("button", "qc-btn", "Print or save PDF"); pb.type = "button"; pb.onclick = printEdition; acts.appendChild(pb); }
    var again = h("a", "qc-btn quiet", "Change what you asked for"); again.href = "#h-people"; acts.appendChild(again);
    el.foot.appendChild(acts);
    if (n && !early && !r.cancelled && canHelp(r)) {
      var more = h("div", "qc-more"); var mb = h("button", "qc-btn", "3 more, then done"); mb.type = "button";
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
    if (r.helpingUsed) return; r.helpingUsed = true; btn.disabled = true; btn.textContent = "Finding 3 more…";
    var done = function (items, note) {
      wrap.innerHTML = "";
      items = dedupeInto(r, items, HELPING); r.helping = items;
      if (items.length) {
        var s = h("section", "qc-esec qc-helping"); s.appendChild(h("h3", "qc-esechead", "Three more"));
        s.appendChild(h("p", "qc-from", sourceLine(r, items, "")));
        var st_ = h("div", "qc-stream"); items.forEach(function (it) { st_.appendChild(itemNode(it, r.cfg.links)); }); s.appendChild(st_); wrap.appendChild(s);
        wrap.appendChild(h("p", "qc-end", "That’s really the edition."));
      } else wrap.appendChild(h("p", "qc-endnote", note || "No more sourced items found. That’s the edition."));
      updateMeta(r);
    };
    if (r.mode === "demo") { done(demoReserve(r).map(function (i) { var c = JSON.parse(JSON.stringify(i)); delete c.sec; return c; })); return; }
    var picks = r.secs.filter(function (s) { return s.id !== "following" && !FUN_IDS[s.id]; }), sec = picks[0] || r.secs[0];
    var combined = {id: sec.id, title: "Three more", brief: "Three more items that fit this paper, each from a different section topic: " + r.secs.map(function (s) { return s.title; }).join(", ") + "."};
    callGrok(combined, HELPING, r.used.slice(), "Each item must be about something different from the others.", r.abort.signal).then(function (v) {
      done(v.items, v.dropped ? "Nothing with a real source link was kept. That’s the edition." : "");
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
  function exportConfig() {
    var c = JSON.parse(JSON.stringify(st)); c.interests = c.topic;
    if (c.delivery) c.delivery = deliveryPublic(c.delivery);
    return {format: "mediabot-quick-create/1", saved: ymd(new Date()), config: c};
  }
  function q(s) { return JSON.stringify(String(s)); }
  function toYaml(c) {
    c = normalize(c);
    var topics = [], fun = [];
    c.sections.forEach(function (sec) {
      if (!sec.on) return;
      if (sec.group === "fun" || (!sec.custom && FUN_IDS[sec.id])) fun.push(sec);
      else topics.push(sec);
    });
    var secs = ((c.people && c.people.length) ? [followingSec()] : []).concat(topics, fun);
    var b = budgetFor(secs, c.minutes), name = c.name || (c.topic || "").trim().split(/[\n,.]/)[0].slice(0, 40) || "Your paper", slug = slugify(name);
    var weights = {}; secs.forEach(function (sec, i) { weights[sec.id] = Math.max(1, 10 - i); });
    var L = ["# " + name + ": a paper made with MediaBot Quick Create (exported " + ymd(new Date()) + ").",
      "# Same shape as papers/*/paper.yaml. To adopt: copy to papers/" + slug + "/paper.yaml, set `reader`, then wire sources for new section ids.",
      "",
      "name: " + q(name), "slug: " + slug, "public: false", "reader: " + q("You"),
      "layout: slow",
      "description: " + q("A " + c.minutes + "-minute paper: " + (b.secs.map(function (s) { return s.title; }).join(", ") || "no sections") + ". Finite, sourced, with a clear end."),
      "",
      "masthead:", "  style: slow", "",
      "print:", "  size: medium", "  photos: false", "  qr: false", "",
      "web:", "  images: false", "  x_links: " + (c.links ? "true" : "false"), "  end_line: " + q("That’s the edition."), "  read_time: true", "",
      "total_max: " + b.total, "sections:"];
    var listed = secs.slice();
    c.sections.forEach(function (s) { if (!listed.some(function (x) { return x.id === s.id; })) listed.push(s); });
    listed.forEach(function (s) {
      var on = s.on && b.per[s.id] != null;
      L.push("  - {id: " + s.id + ", title: " + q(s.title) + ", enabled: " + (on ? "true" : "false") + ", weight: " + (on ? weights[s.id] : 1) + ", max_items: " + (on ? b.per[s.id] : 0) + (s.custom ? ", custom: true" : "") + "}");
    });
    var fav = (c.people || []).map(function (p) { return p.handle ? q("@" + p.handle) : q(p.label); }).concat(handles(c.favor).map(function (h_) { return q("@" + h_); }));
    var avoid = handles(c.avoid).map(function (h_) { return q("@" + h_); });
    L.push("", "sources:", "  x:", "    must_read: [" + fav.join(", ") + "]", "    avoid: [" + avoid.join(", ") + "]",
      "  web: [" + domains(c.favor).map(q).join(", ") + "]", "  web_avoid: [" + domains(c.avoid).map(q).join(", ") + "]", "",
      "filters:", "  novelty: strict", "", "quick_create:", "  version: 2", "  minutes: " + c.minutes,
      "  tone: [" + c.tone.map(q).join(", ") + "]", "  topic: " + q(c.topic.trim()), "  freshness_days: " + c.fresh,
      "  search: {x: " + c.x + ", web: " + c.web + ", only_favored_x: " + c.only + "}",
      "  people: [" + (c.people || []).map(function (p) { return q(p.label); }).join(", ") + "]",
      "  briefs:");
    c.sections.forEach(function (sec) { L.push("    " + sec.id + ": " + q(sec.brief)); });
    var del = deliveryPublic(c.delivery);
    L.push("", "delivery:", "  how: " + del.how, "  when: " + del.when);
    if (del.when !== "now") L.push("  time: " + q(del.time));
    if (del.when === "weekly") L.push("  weekday: " + del.weekday);
    L.push("# Email and phone stay on this phone and are never written to this file.");
    return L.join("\n") + "\n";
  }
  function b64e(s) { var by = new TextEncoder().encode(s), bin = ""; by.forEach(function (x) { bin += String.fromCharCode(x); }); return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); }
  function b64d(s) { s = s.replace(/-/g, "+").replace(/_/g, "/"); while (s.length % 4) s += "="; var bin = atob(s), by = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) by[i] = bin.charCodeAt(i); return new TextDecoder().decode(by); }
  function shareUrl() {
    var c = JSON.parse(JSON.stringify(st));
    if (c.delivery) c.delivery = deliveryPublic(c.delivery);
    return location.origin + location.pathname + "#c=" + b64e(JSON.stringify(c));
  }
  function fromHash() {
    var m = /[#&]c=([A-Za-z0-9_-]+)/.exec(location.hash || ""); if (!m) return null;
    try { return normalize(JSON.parse(b64d(m[1]))); } catch (e) { return null; }
  }

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

  function init() {
    var h0 = fromHash(), d = loadDraft();
    st = h0 || (d ? normalize(d) : fresh());
    $("qc-key").value = ""; $("qc-model").value = getModel(); $("qc-proxy").value = ls(K.proxy);
    renderForm();
    if (h0) setStatus("Loaded the paper from a shared link. Not saved until you press Save under More options.");
    $("qc-topic").addEventListener("input", function () { st.topic = $("qc-topic").value; saveDraft(); });
    ["qc-name", "qc-favor", "qc-avoid", "qc-demail", "qc-dphone"].forEach(function (id) { $(id).addEventListener("input", readForm); });
    ["qc-fresh", "qc-sx", "qc-sw", "qc-only", "qc-links", "qc-dtime", "qc-dday"].forEach(function (id) { $(id).addEventListener("change", readForm); });
    $("qc-padd").onclick = function () { if (addPeople($("qc-pinput").value)) $("qc-pinput").value = ""; else if ($("qc-pinput").value.trim()) setStatus("That person is already on the list.", true); $("qc-pinput").focus(); };
    $("qc-pinput").addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); $("qc-padd").click(); } });
    $("qc-go").onclick = startMake;
    $("qc-keygo").onclick = function () {
      var k = $("qc-key").value.trim();
      if (!k && !getKey()) { setStatus("Paste a key first, or choose a sample.", true); return; }
      if (k && !saveConn(k)) return;
      $("qc-key").value = ""; generate("live");
    };
    $("qc-demo").onclick = function () { generate("demo"); };
    $("qc-conn").onclick = function () {
      var k = $("qc-key").value.trim();
      if (!saveConn(k || undefined)) return;
      $("qc-key").value = ""; setStatus("Connection settings saved on this phone.");
    };
    $("qc-keyclear").onclick = function () { try { localStorage.removeItem(K.key); } catch (e) {} $("qc-key").value = ""; setStatus("Key removed from this phone."); };
    $("qc-save").onclick = function () {
      readForm(); var n = paperName(), p = papers(); p[n] = st;
      try { localStorage.setItem(K.papers, JSON.stringify(p)); } catch (e) { setStatus("This browser would not save.", true); return; }
      renderSaved(); $("qc-saved").value = n; setStatus("Saved “" + n + "” in this browser.");
    };
    $("qc-load").onclick = function () { var n = $("qc-saved").value, p = papers(); if (!n || !p[n]) { setStatus("Choose a saved paper first.", true); return; } st = normalize(p[n]); renderForm(); saveDraft(); setStatus("Loaded “" + n + "”."); };
    $("qc-del").onclick = function () { var n = $("qc-saved").value, p = papers(); if (!n || !p[n]) return; delete p[n]; try { localStorage.setItem(K.papers, JSON.stringify(p)); } catch (e) {} renderSaved(); setStatus("Deleted “" + n + "”."); };
    $("qc-json").onclick = function () { readForm(); download(slugify(paperName()) + ".quickcreate.json", JSON.stringify(exportConfig(), null, 2) + "\n", "application/json"); setStatus("Downloaded the config. It never includes your key, email or phone."); };
    $("qc-import").onclick = function () { $("qc-file").click(); };
    $("qc-file").onchange = function () {
      var f = this.files && this.files[0]; if (!f) return;
      if (f.size > 200000) { setStatus("That file is too big to be a paper config.", true); return; }
      var rd = new FileReader();
      rd.onload = function () { try { var j = JSON.parse(rd.result); st = normalize(j && j.config ? j.config : j); renderForm(); saveDraft(); setStatus("Imported “" + (paperName()) + "”."); } catch (e) { setStatus("That isn't a Quick Create JSON file.", true); } };
      rd.readAsText(f); this.value = "";
    };
    $("qc-yaml").onclick = function () { readForm(); download("paper.yaml", toYaml(st), "text/yaml"); setStatus("Downloaded paper.yaml."); };
    $("qc-link").onclick = function () {
      readForm(); var u = shareUrl();
      try { history.replaceState(null, "", u.slice(location.origin.length)); } catch (e) {}
      copyText(u).then(function () { setStatus("Share link copied. It holds the config only, never your key, email or phone."); }, function () { setStatus("Copy the link from your address bar."); });
    };
  }
  window.__qc = {normalize: normalize, normUrl: normUrl, citedSet: citedSet, vetItems: vetItems, parseItems: parseItems, outputText: outputText,
                 allocate: allocate, toYaml: toYaml, deliveryPublic: deliveryPublic, CAPS: CAPS, sourceLine: sourceLine, itemSource: itemSource, state: function () { return st; },
                 setState: function (s) { st = normalize(s); renderForm(); }};
  init();
})();
