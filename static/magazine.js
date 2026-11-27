// The magazine editions (body.mag): a slim sticky app bar with reading progress and the current section, and a gentle
// fade-in on scroll. The app bar always runs; the fades are skipped for prefers-reduced-motion. Without JS the page is a plain document.
(function () {
  if (!document.body.classList.contains('mag')) return;
  document.documentElement.classList.add('js');
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- app bar: appears after the first screen, shows progress and where you are ----
  var bar = document.querySelector('.appbar');
  if (bar) {
    var fill = bar.querySelector('.ab-bar i'), meter = bar.querySelector('.ab-bar'), cur = bar.querySelector('.ab-cur');
    var secs = [].slice.call(document.querySelectorAll('main > section.front, main > section.part, main > section.sec, main > .jokewrap, .end'));
    function titleOf(s) {
      if (s.classList.contains('end')) return 'The end';
      var h = s.querySelector('.part-h, .sec-head, .lbl, h2');
      return h ? h.textContent.replace(/\s+/g, ' ').trim() : '';
    }
    var titles = secs.map(titleOf);
    var ticking = false;
    function update() {
      ticking = false;
      var y = window.pageYOffset, vh = window.innerHeight, max = document.documentElement.scrollHeight - vh;
      var pct = max > 0 ? Math.min(100, Math.max(0, y / max * 100)) : 0;
      fill.style.width = pct + '%'; meter.setAttribute('aria-valuenow', Math.round(pct));
      bar.classList.toggle('on', y > Math.min(160, vh * 0.25));
      var ec = document.querySelector('.endcard'), done = max > 0 && (y >= max - 6 || (ec && ec.getBoundingClientRect().top < vh * 0.45)), label = '';
      for (var i = 0; i < secs.length; i++) { if (secs[i].getBoundingClientRect().top <= 90) label = titles[i]; else break; }
      if (done) { label = 'Done for today'; }
      cur.textContent = label || 'Contents';
      bar.classList.toggle('done', done);
    }
    function onScroll() { if (!ticking) { ticking = true; requestAnimationFrame(update); } }
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    update();
  }

  // ---- gentle fades: only elements still below the fold, never under reduced motion ----
  if (reduce || !('IntersectionObserver' in window)) return;
  var sel = '.story, .post, .ever, .part-h, .sec-head, .topic, .passage, .jokecard, .jokewrap, .funnies .joke, .comic, .game, .endcard, .tune, .answered, .toc, .contents, .sectionnav';
  var els = [].slice.call(document.querySelectorAll(sel)).filter(function (e) {
    return e.getBoundingClientRect().top > window.innerHeight * 0.9;
  });
  els.forEach(function (e) { e.classList.add('fade'); });
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (x) { if (x.isIntersecting) { x.target.classList.add('in'); io.unobserve(x.target); } });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
  els.forEach(function (e) { io.observe(e); });
  // a link to #anchor must never land on a faded-out block
  window.addEventListener('hashchange', function () {
    var t = document.getElementById(location.hash.slice(1)); if (!t) return;
    [t].concat([].slice.call(t.querySelectorAll('.fade'))).forEach(function (e) { e.classList.add('in'); });
  });
})();
