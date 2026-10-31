// Reader marks, reactions and edition feedback.
// v1: stored in this browser (localStorage) and exported as a JSON file for papers/<slug>/feedback/.
// Later: the same records POST to the reader's account (see README, "Sign-in later").
(function () {
  var SG = window.SG || {}, KEY = "sg:" + SG.paper + "/" + SG.edition;
  var state = {};
  try { state = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) {}
  state.items = state.items || {};
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }

  function paint(el) {
    var s = state.items[el.dataset.id] || {};
    el.classList.toggle("is-read", !!s.read);
    el.classList.toggle("is-skip", s.r === "skip");
    el.querySelectorAll(".ctl button").forEach(function (b) {
      var on = b.hasAttribute("data-read") ? !!s.read : s.r === b.dataset.r;
      b.setAttribute("aria-pressed", on ? "true" : "false");
      if (b.hasAttribute("data-read")) b.title = on ? "Read" : "Mark read";
    });
  }
  document.querySelectorAll(".story[data-id], .post[data-id]").forEach(paint);

  document.addEventListener("click", function (e) {
    var b = e.target.closest(".ctl button"); if (!b) return;
    var el = b.closest("[data-id]"), id = el.dataset.id;
    var s = state.items[id] = state.items[id] || {};
    if (b.hasAttribute("data-read")) s.read = !s.read;
    else { s.r = s.r === b.dataset.r ? null : b.dataset.r; if (s.r) s.read = true; }
    s.t = new Date().toISOString();
    save(); paint(el);
  });

  var ok = document.querySelector(".saved");
  function flash(msg) { if (!ok) return; ok.textContent = msg; setTimeout(function () { ok.textContent = ""; }, 2200); }

  var form = document.getElementById("feedback");
  if (form) {
    var ta = form.querySelector("textarea");
    ta.value = state.note || "";
    form.addEventListener("submit", function (e) {
      e.preventDefault(); state.note = ta.value.trim(); save(); flash("Saved");
    });
  }

  function describe(id) {
    var el = document.querySelector('[data-id="' + id + '"]'); if (!el) return {};
    var sec = el.closest("[data-sec]"), h = el.querySelector("h3"), p = el.querySelector(".ptext");
    var a = el.querySelector(".src a, a.open");
    var t = h ? h.textContent : (p ? el.querySelector(".who b").textContent + ": " + p.textContent.slice(0, 120) : "");
    return { section: sec ? sec.dataset.sec : "", title: t.trim(), url: a ? a.href : "" };
  }
  var ex = document.getElementById("export");
  if (ex) ex.addEventListener("click", function () {
    if (form) { state.note = form.querySelector("textarea").value.trim(); save(); }
    var items = Object.keys(state.items).filter(function (id) {
      var s = state.items[id]; return s.read || s.r;
    }).map(function (id) {
      var s = state.items[id], d = describe(id);
      return { id: id, section: d.section, title: d.title, url: d.url, read: !!s.read, reaction: s.r || null, at: s.t };
    });
    var out = { format: "mediabot-feedback/1", paper: SG.paper, edition: SG.edition,
                exported_at: new Date().toISOString(), note: state.note || "", items: items };
    var txt = JSON.stringify(out, null, 1);
    try { navigator.clipboard && navigator.clipboard.writeText(txt); } catch (e) {}
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([txt], { type: "application/json" }));
    a.download = SG.paper + "-" + SG.edition + "-feedback.json";
    document.body.appendChild(a); a.click(); a.remove();
    flash(items.length + " marks exported");
  });
})();
