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

  // The "Anything else" box in "Tune tomorrow's paper" doubles as this edition's note in the exported feedback.
  var form = document.getElementById("tune");
  if (form) {
    var ta = form.querySelector("textarea");
    ta.value = state.note || "";
    ta.addEventListener("change", function () { state.note = ta.value.trim(); save(); });
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

// "Tune tomorrow's paper": compose a prefilled GitHub issue (checked chips + free text) and open it in a new tab.
// The body is plain lines so the morning routine can parse it (docs/routine.md). Without JS the form still
// submits the free text as the issue body.
(function () {
  var f = document.getElementById('tune');
  if (!f) return;
  f.addEventListener('submit', function (e) {
    e.preventDefault();
    var picks = [].map.call(f.querySelectorAll('.chips input:checked'), function (c) { return c.value; });
    var text = f.elements.body.value.trim();
    if (!picks.length && !text) { f.elements.body.focus(); return; }
    var body = 'Edition: ' + f.dataset.edition + '\n\nPicked:\n' +
               (picks.length ? picks.map(function (p) { return '- ' + p; }).join('\n') : '- (none)') +
               '\n\nAnything else:\n' + (text || '(nothing)') +
               '\n\n---\nFrom: ' + f.dataset.paper + (f.dataset.url ? ' (' + f.dataset.url + ')' : '') +
               '\nTune notes are public. The next morning edition reads open edition-request issues.';
    var title = 'Edition request: tune ' + f.dataset.edition + (picks.length ? ' (' + picks.join(', ') + ')' : '');
    if (title.length > 120) title = title.slice(0, 117) + '…';
    var q = 'title=' + encodeURIComponent(title) + '&body=' + encodeURIComponent(body) +
            '&labels=' + encodeURIComponent(f.elements.labels.value) +
            (f.elements.template ? '&template=' + encodeURIComponent(f.elements.template.value) : '');
    window.open(f.action + '?' + q, '_blank', 'noopener');
  });
})();

// "One more helping": reveal the pre-built extra serving once. The button goes away; nothing else loads.
(function () {
  var box = document.getElementById('seconds');
  if (!box) return;
  var btn = box.querySelector('.more-btn'), body = document.getElementById('seconds-body');
  function reveal(scroll) {
    body.hidden = false; btn.remove();
    var h = body.querySelector('h3'); if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: !scroll }); }
  }
  btn.addEventListener('click', function () { reveal(false); });
  if (location.hash === '#seconds-body') reveal(true);  // deep link straight to the extra serving
})();
