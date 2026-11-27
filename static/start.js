// /start/ (four short steps) and /profile/ (the same controls on one page). Reads and writes MediaBotProfile.
// Bluesky follows come from Bluesky's public API (no sign-in). X follows arrive only from the optional x-connect
// backend (docs/x-connect.md) as a #x=… fragment on return; nothing is sent anywhere else.
(function () {
  "use strict";
  var P = window.MediaBotProfile, $ = function (id) { return document.getElementById(id); };
  var main = $("ob"), EDIT = main.getAttribute("data-mode") === "edit";
  var PRESETS = ["Faith", "Family", "Health", "Nature", "Science", "Space", "History", "Books", "Music", "Movies & TV",
                 "Sports", "Food", "Travel", "Art & design", "Woodworking", "Local news", "Tech", "Good news"];
  var prof = P.load() || P.blank(), follows = P.loadFollows(), step = 1, LAST = 4, justConnected = false;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function persist() { try { prof.updated = P.save(prof).updated; return true; } catch (e) { banner("This browser wouldn't save. Private browsing can block it.", true); return false; } }
  function banner(msg, bad) { var b = $("ob-banner"); b.textContent = msg; b.className = "ob-banner" + (bad ? " bad" : ""); b.hidden = !msg; }
  var uid = 0;

  // A three-way choice in plain words: A little / Normal / A lot.
  function weightControl(item, label, onChange) {
    var g = el("div", "ob-weight"); g.setAttribute("role", "radiogroup"); g.setAttribute("aria-label", "How much of " + label);
    var name = "w" + (++uid);
    [1, 2, 3].forEach(function (n) {
      var l = el("label"), i = el("input"), s = el("span", null, P.WEIGHTS[n]);
      i.type = "radio"; i.name = name; i.value = n; i.checked = item.weight === n;
      i.onchange = function () { item.weight = n; onChange(); };
      l.appendChild(i); l.appendChild(s); g.appendChild(l);
    });
    return g;
  }
  function row(title, sub, item, onRemove) {
    var li = el("li", "ob-row"), top = el("div", "ob-rowtop"), t = el("div", "ob-who");
    t.appendChild(el("b", null, title)); if (sub) t.appendChild(el("span", "ob-sub", sub));
    var x = el("button", "ob-x", "\u00d7"); x.type = "button"; x.setAttribute("aria-label", "Remove " + title); x.onclick = onRemove;
    top.appendChild(t); top.appendChild(x); li.appendChild(top);
    li.appendChild(weightControl(item, title, changed));
    return li;
  }

  // ---------- Step 1: accounts ----------
  function renderAccounts() {
    $("ob-xhandle").value = prof.accounts.x.handle;
    $("ob-bhandle").value = prof.accounts.bluesky.handle;
    if (prof.accounts.bluesky.handle) $("ob-bsky").open = true;
    var st = $("ob-xstatus"), n = (follows.x || []).length;
    st.hidden = !prof.accounts.x.connected;
    if (prof.accounts.x.connected) st.textContent = "Connected as @" + prof.accounts.x.handle + (n ? ". " + n + " people you follow are ready in step 2." : ".");
  }
  $("ob-xhandle").addEventListener("input", function () {
    var v = this.value.trim().replace(/^@+/, ""), ok = !v || !!P.xHandle(v);
    $("ob-xerr").hidden = ok;
    if (ok) { if (v !== prof.accounts.x.handle) prof.accounts.x.connected = false; prof.accounts.x.handle = v; changed(); renderAccounts(); nextLabel(); }
  });
  $("ob-bhandle").addEventListener("change", function () {
    var v = P.bskyHandle(this.value); prof.accounts.bluesky.handle = v; changed();
  });
  $("ob-bimport").onclick = function () {
    var h = P.bskyHandle($("ob-bhandle").value), st = $("ob-bstatus"), btn = this;
    if (!h) { st.textContent = "Type your Bluesky handle first, like name.bsky.social."; return; }
    prof.accounts.bluesky.handle = h; changed();
    btn.disabled = true; st.textContent = "Looking up who you follow…";
    var all = [], cursor = "", pages = 0;
    (function next() {
      var u = "https://public.api.bsky.app/xrpc/app.bsky.graph.getFollows?limit=100&actor=" + encodeURIComponent(h) + (cursor ? "&cursor=" + encodeURIComponent(cursor) : "");
      fetch(u).then(function (r) { if (!r.ok) throw new Error(r.status === 400 ? "notfound" : "http"); return r.json(); }).then(function (d) {
        (d.follows || []).forEach(function (f) { if (f.handle) all.push([f.handle, (f.displayName || "").slice(0, 80)]); });
        cursor = d.cursor || ""; pages++;
        if (cursor && pages < 10) return next();
        follows.bluesky = all; follows.bluesky_at = new Date().toISOString(); P.saveFollows(follows);
        st.textContent = all.length ? "Found " + all.length + " people. Pick from them in step 2." : "That account doesn't follow anyone yet.";
        btn.disabled = false; renderPicks();
      }).catch(function (e) {
        st.textContent = e.message === "notfound" ? "Couldn't find that Bluesky handle." : "Bluesky didn't answer. Try again in a minute.";
        btn.disabled = false;
      });
    })();
  };
  // Return from x-connect: #x=<base64url JSON> or #x-error=<reason>
  function readXReturn() {
    var h = location.hash || "", m;
    if ((m = h.match(/^#x-error=([a-z_]+)/))) {
      banner(m[1] === "denied" ? "X connection was cancelled. You can still type your handle." : "X didn't connect this time. Your handle still works.", true);
    } else if ((m = h.match(/^#x=([A-Za-z0-9_-]+)$/))) {
      try {
        var b = atob(m[1].replace(/-/g, "+").replace(/_/g, "/")), bytes = new Uint8Array(b.length);
        for (var i = 0; i < b.length; i++) bytes[i] = b.charCodeAt(i);
        var d = JSON.parse(new TextDecoder().decode(bytes));
        var me = P.xHandle(d.me && d.me.username);
        if (me) {
          prof.accounts.x = { handle: me, connected: true, imported: new Date().toISOString() };
          follows.x = (d.following || []).filter(function (f) { return P.xHandle(f[0]); }).slice(0, 5000);
          follows.x_topics = (d.topics || []).map(function (t) { return String(t[0] || "").slice(0, 40); }).filter(Boolean).slice(0, 30);
          follows.x_at = prof.accounts.x.imported;
          P.saveFollows(follows); persist(); justConnected = true;
          banner("Connected as @" + me + ". Pick people from who you follow in step 2.");
        }
      } catch (e) { banner("Couldn't read what X sent back. Your handle still works.", true); }
    }
    if (h.indexOf("#x") === 0) history.replaceState(null, "", location.pathname + location.search);
  }

  // ---------- Step 2: people ----------
  function renderPeople() {
    var ul = $("ob-people"); ul.textContent = "";
    prof.people.forEach(function (p, i) {
      var title = p.handle ? (p.platform === "bluesky" ? p.handle : "@" + p.handle) : p.name;
      var sub = p.handle ? (p.name ? p.name + " · " : "") + (p.platform === "bluesky" ? "Bluesky" : "X") : "Anywhere they publish";
      ul.appendChild(row(title, sub, p, function () { prof.people.splice(i, 1); changed(); renderPeople(); renderPicks(); }));
    });
    $("ob-pempty").hidden = prof.people.length > 0;
  }
  function addPerson(x, quiet) {
    var k = P.personKey(x);
    if (prof.people.some(function (p) { return P.personKey(p) === k; })) { if (!quiet) banner("Already in your list."); return false; }
    if (prof.people.length >= P.LIMITS.people) { banner("That's the most people one profile holds (" + P.LIMITS.people + ").", true); return false; }
    prof.people.unshift({ name: x.name || "", handle: x.handle || "", platform: x.platform, weight: 2, from: x.from || "you" });
    banner(""); changed(); renderPeople(); renderPicks(); return true;
  }
  function addTyped() {
    var inp = $("ob-padd"), v = inp.value.trim(); if (!v) return;
    var x = P.parsePerson(v);
    if (!x || (v[0] === "@" && x.platform === "web")) { banner("That handle doesn't look right. X handles use letters, numbers or _ and are 15 characters at most.", true); return; }
    if (addPerson(x)) inp.value = "";
    inp.focus();
  }
  $("ob-paddbtn").onclick = addTyped;
  $("ob-padd").addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); addTyped(); } });
  var SHOW = 12;
  function renderPicks() {
    var pool = [];
    (follows.x || []).forEach(function (f) { pool.push({ platform: "x", handle: f[0], name: f[1] || "", from: "x" }); });
    (follows.bluesky || []).forEach(function (f) { pool.push({ platform: "bluesky", handle: f[0], name: f[1] || "", from: "bluesky" }); });
    $("ob-pimport").hidden = !pool.length;
    if (!pool.length) return;
    var have = {}; prof.people.forEach(function (p) { have[P.personKey(p)] = 1; });
    var q = $("ob-pfilter").value.trim().toLowerCase().replace(/^@/, "");
    var left = pool.filter(function (x) { return !have[P.personKey(x)]; });
    var hits = q ? left.filter(function (x) { return x.handle.toLowerCase().indexOf(q) >= 0 || x.name.toLowerCase().indexOf(q) >= 0; }) : left;
    $("ob-pimport-h").textContent = "From who you follow (" + left.length + ")";
    var ul = $("ob-picks"); ul.textContent = "";
    hits.slice(0, SHOW).forEach(function (x) {
      var li = el("li"), b = el("button", "ob-pick"); b.type = "button";
      b.appendChild(el("span", "ob-plus", "+"));
      var t = el("span", "ob-who"); t.appendChild(el("b", null, x.name || (x.platform === "x" ? "@" : "") + x.handle));
      t.appendChild(el("span", "ob-sub", (x.platform === "x" ? "@" + x.handle : x.handle + " · Bluesky")));
      b.appendChild(t); b.setAttribute("aria-label", "Add " + (x.name || x.handle));
      b.onclick = function () { addPerson(x, true); };
      li.appendChild(b); ul.appendChild(li);
    });
    $("ob-pickmore").textContent = hits.length > SHOW ? "Showing " + SHOW + " of " + hits.length + ". Search to find someone." : (q && !hits.length ? "No one matches." : "");
  }
  $("ob-pfilter").addEventListener("input", renderPicks);

  // ---------- Step 3: topics ----------
  function hasTopic(label) { return prof.topics.some(function (t) { return t.label.toLowerCase() === label.toLowerCase(); }); }
  function toggleTopic(label, from) {
    if (hasTopic(label)) prof.topics = prof.topics.filter(function (t) { return t.label.toLowerCase() !== label.toLowerCase(); });
    else if (prof.topics.length < P.LIMITS.topics) prof.topics.push({ label: label, weight: 2, from: from });
    changed(); renderTopics();
  }
  function chips(box, labels, from) {
    box.textContent = "";
    labels.forEach(function (l) {
      var b = el("button", "ob-chip", l); b.type = "button"; b.setAttribute("aria-pressed", hasTopic(l) ? "true" : "false");
      b.onclick = function () { toggleTopic(l, from); }; box.appendChild(b);
    });
  }
  function renderTopics() {
    chips($("ob-presets"), PRESETS, "preset");
    var sug = (follows.x_topics || []).filter(function (t) { return PRESETS.indexOf(t) < 0; });
    $("ob-tsuggest").hidden = !sug.length;
    if (sug.length) { chips($("ob-tsuggest"), sug, "x"); $("ob-tsuggest").insertBefore(el("p", "ob-help small full", "From your X"), $("ob-tsuggest").firstChild); }
    var ul = $("ob-topics"); ul.textContent = "";
    prof.topics.forEach(function (t, i) {
      ul.appendChild(row(t.label, null, t, function () { prof.topics.splice(i, 1); changed(); renderTopics(); }));
    });
    $("ob-tempty").hidden = prof.topics.length > 0;
  }
  function addTopic() {
    var inp = $("ob-tadd"), v = inp.value.trim().replace(/\s+/g, " ").slice(0, 40); if (!v) return;
    if (hasTopic(v)) { banner("Already in your topics."); return; }
    toggleTopic(v, "you"); inp.value = ""; inp.focus(); banner("");
  }
  $("ob-taddbtn").onclick = addTopic;
  $("ob-tadd").addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); addTopic(); } });

  // ---------- Step 4: fun ----------
  function renderFun() {
    var ul = $("ob-fun"); ul.textContent = "";
    P.FUN.forEach(function (f) {
      var li = el("li"), l = el("label", "ob-toggle"), i = el("input"), t = el("span", "ob-who");
      i.type = "checkbox"; i.checked = !!prof.fun[f.id]; i.setAttribute("role", "switch");
      i.onchange = function () { prof.fun[f.id] = i.checked; changed(); };
      t.appendChild(el("b", null, f.label)); t.appendChild(el("span", "ob-sub", f.help));
      l.appendChild(t); l.appendChild(i); l.appendChild(el("span", "ob-sw")); li.appendChild(l); ul.appendChild(li);
    });
  }

  // ---------- saving and steps ----------
  var dirty = false;
  function changed() {
    if (EDIT) { dirty = true; $("ob-saved").textContent = "Not saved yet"; }
    else persist();      // onboarding saves as you go, so a reload never loses work
  }
  function show(n) {
    step = n;
    Array.prototype.forEach.call(document.querySelectorAll(".ob-step"), function (s) { s.hidden = +s.getAttribute("data-step") !== n; });
    var done = n > LAST;
    $("ob-count").textContent = done ? "All set" : "Step " + n + " of " + LAST;
    Array.prototype.forEach.call(document.querySelectorAll(".ob-dots li"), function (d, i) { d.className = i < n ? "on" : ""; });
    $("ob-nav").hidden = done;
    $("ob-back").hidden = n === 1;
    nextLabel();
    if (done) summary();
    try { sessionStorage.setItem("mediabot.start.step", String(n)); } catch (e) {}
    window.scrollTo(0, 0);
  }
  function and(l) { return l.length < 2 ? l.join("") : l.slice(0, -1).join(", ") + " and " + l[l.length - 1]; }
  function nextLabel() {
    if (EDIT) return;
    var skip = step === 1 && !prof.accounts.x.handle;
    $("ob-next").textContent = skip ? "Skip for now" : step === LAST ? "Finish" : "Next";
    $("ob-next").className = "ob-btn" + (skip ? "" : " primary");
  }
  function summary() {
    var f = P.FUN.filter(function (x) { return prof.fun[x.id]; }).map(function (x) { return x.label.toLowerCase(); });
    var parts = [prof.people.length + (prof.people.length === 1 ? " person" : " people"), prof.topics.length + (prof.topics.length === 1 ? " topic" : " topics")];
    $("ob-summary").textContent = "Your paper will lead with " + and(parts) + (f.length ? ", and end with " + and(f) : "") +
      ". It's saved in this browser for Quick Create to use.";
  }
  if (!EDIT) {
    $("ob-back").onclick = function () { show(Math.max(1, step - 1)); };
    $("ob-next").onclick = function () {
      if (step === 1 && !$("ob-xerr").hidden) { $("ob-xhandle").focus(); return; }
      if (step === LAST) { prof.onboarded = true; if (!persist()) return; }
      show(step + 1);
    };
  } else {
    $("ob-save").onclick = function () {
      if (!$("ob-xerr").hidden) { $("ob-xhandle").focus(); return; }
      prof.onboarded = true;
      if (persist()) { dirty = false; $("ob-saved").textContent = "Saved"; }
    };
    $("ob-forget").onclick = function () {
      if (!confirm("Forget your profile in this browser?")) return;
      P.forget(); prof = P.blank(); follows = {}; dirty = false; renderAll(); $("ob-saved").textContent = "Profile removed";
    };
    window.addEventListener("beforeunload", function (e) { if (dirty) { e.preventDefault(); e.returnValue = ""; } });
  }
  function renderAll() { renderAccounts(); renderPeople(); renderPicks(); renderTopics(); renderFun(); }

  readXReturn();
  renderAll();
  if (!EDIT) {
    var s = 1; try { s = +sessionStorage.getItem("mediabot.start.step") || 1; } catch (e) {}
    if (justConnected) s = (follows.x || []).length ? 2 : 1;
    if (prof.onboarded && s === 1 && !$("ob-banner").textContent) banner("You already have a profile. Change anything below, or open Your profile to see it all at once.");
    show(Math.min(Math.max(1, s), LAST));
  }
})();
