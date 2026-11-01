// Recipe editor: default settings in, a recipe file out. Saved in this browser only; nothing is sent anywhere.
(function () {
  var D = JSON.parse(document.getElementById("mb-data").textContent), KEY = "mb:recipe";
  var $ = function (id) { return document.getElementById(id); }, st;
  var paper = function () { return D.papers.filter(function (p) { return p.slug === st.paper; })[0] || D.papers[0]; };

  function fromRecipe(r) {
    var p = D.papers.filter(function (x) { return x.slug === r.paper; })[0] || D.papers[0], seen = {}, secs = [];
    var meta = {}; p.sections.forEach(function (s) { meta[s.id] = s; });
    (r.sections || []).forEach(function (e) {
      if (!meta[e.id]) return; seen[e.id] = 1;
      secs.push({id: e.id, on: true, max_items: e.max_items || meta[e.id].max_items, types: e.types || null});
    });
    p.sections.forEach(function (s) { if (!seen[s.id]) secs.push({id: s.id, on: false, max_items: s.max_items, types: null}); });
    return {preset: r.name, name: r.name, paper: p.slug, format: r.format || "print", size: r.size || "medium",
            pages: r.pages || 5, sections: secs, accounts: (r.accounts || []).join(" ")};
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} }
  function load() { try { return JSON.parse(localStorage.getItem(KEY)); } catch (e) { return null; } }

  function yaml() {
    var q = function (s) { return /^[\w .,+()-]*$/.test(s) && !/^[\s-]|:/.test(s) ? s : JSON.stringify(s); };
    var acc = st.accounts.split(/[\s,]+/).filter(Boolean).map(function (a) { return JSON.stringify("@" + a.replace(/^@/, "")); });
    var L = ["# MediaBot recipe", "recipe: 1", "name: " + q(st.name || "Custom"), "paper: " + st.paper,
             "format: " + st.format, "size: " + st.size, "pages: " + st.pages, "sections:"];
    st.sections.forEach(function (s) {
      if (!s.on) return;
      L.push("  - {id: " + s.id + ", max_items: " + s.max_items + (s.types ? ", types: [" + s.types.join(", ") + "]" : "") + "}");
    });
    L.push("accounts: [" + acc.join(", ") + "]");
    return L.join("\n") + "\n";
  }

  function render() {
    var p = paper(), meta = {}; p.sections.forEach(function (s) { meta[s.id] = s; });
    $("preset").value = st.preset; $("name").value = st.name; $("pages").value = st.pages; $("size").value = st.size;
    $("accounts").value = st.accounts;
    document.querySelectorAll("input[name=format]").forEach(function (r) { r.checked = r.value === st.format; });
    var ol = $("secs"); ol.innerHTML = "";
    st.sections.forEach(function (s, i) {
      var m = meta[s.id], li = document.createElement("li"), only = s.types && s.types.length === 1 ? s.types[0] : "";
      li.className = s.on ? "" : "off";
      li.innerHTML = '<input type="checkbox" aria-label="Include">' +
        '<span class="t"><b></b><span class="k"></span></span>' +
        '<label class="cap">up to <input type="number" min="1" max="30" aria-label="Most items"></label>' +
        '<span class="mv"><button type="button" aria-label="Move up">↑</button><button type="button" aria-label="Move down">↓</button></span>';
      li.querySelector("b").textContent = m.title;
      li.querySelector(".k").textContent = only === "post" ? "posts only" : only === "story" ? "stories only" : (m.kind === m.title ? "" : m.kind);
      var cb = li.querySelector("input[type=checkbox]"), cap = li.querySelector(".cap input"), b = li.querySelectorAll(".mv button");
      cb.checked = s.on; cap.value = s.max_items || "";
      cb.onchange = function () { s.on = cb.checked; changed(true); };
      cap.onchange = function () { s.max_items = Math.max(1, parseInt(cap.value, 10) || 1); changed(); };
      b[0].disabled = i === 0; b[1].disabled = i === st.sections.length - 1;
      b[0].onclick = function () { move(i, -1); }; b[1].onclick = function () { move(i, 1); };
      ol.appendChild(li);
    });
    $("out").value = yaml();
  }
  function move(i, d) {
    var a = st.sections, t = a[i]; a[i] = a[i + d]; a[i + d] = t; changed(true);
    var btn = $("secs").children[i + d].querySelectorAll(".mv button")[d < 0 ? 0 : 1];
    if (!btn.disabled) btn.focus();
  }
  function changed(redraw) {
    save(); if (redraw) render(); else $("out").value = yaml();
  }

  // controls
  var sel = $("preset");
  D.presets.forEach(function (r) { var o = document.createElement("option"); o.value = o.textContent = r.name; sel.appendChild(o); });
  D.papers[0].sizes.forEach(function (s) {
    var o = document.createElement("option"); o.value = s; o.textContent = s[0].toUpperCase() + s.slice(1); $("size").appendChild(o);
  });
  sel.onchange = function () { st = fromRecipe(D.presets.filter(function (r) { return r.name === sel.value; })[0]); save(); render(); };
  $("reset").onclick = function () { st = fromRecipe(D.presets[0] || D.papers[0].default); save(); render(); };
  $("name").oninput = function () { st.name = this.value; changed(); };
  $("pages").onchange = function () { st.pages = Math.min(20, Math.max(1, parseInt(this.value, 10) || 1)); this.value = st.pages; changed(); };
  $("size").onchange = function () { st.size = this.value; changed(); };
  $("accounts").oninput = function () { st.accounts = this.value; changed(); };
  document.querySelectorAll("input[name=format]").forEach(function (r) { r.onchange = function () { st.format = r.value; changed(); }; });

  function flash(t) { $("status").textContent = t; setTimeout(function () { $("status").textContent = ""; }, 1800); }
  $("copy").onclick = function () {
    var done = function () { flash("Copied"); };
    if (navigator.clipboard) navigator.clipboard.writeText(yaml()).then(done, function () { $("out").select(); document.execCommand("copy"); done(); });
    else { $("out").select(); document.execCommand("copy"); done(); }
  };
  $("dl").onclick = function () {
    var a = document.createElement("a"), slug = (st.name || "custom").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "custom";
    a.href = URL.createObjectURL(new Blob([yaml()], {type: "text/yaml"})); a.download = slug + ".yaml";
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  };

  st = load();
  if (!st || !st.sections) st = fromRecipe(D.presets[0] || D.papers[0].default);
  render();
})();
