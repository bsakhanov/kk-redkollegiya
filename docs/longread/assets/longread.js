/* SPDX-License-Identifier: GPL-3.0-or-later · © 2026 Бейбит Саханов · лонгрид kk-redkollegiya */
(function () {
  'use strict';
  var D = {}; try { D = JSON.parse(document.getElementById('data').textContent); } catch (e) {}
  var $ = function (s, r) { return (r || document).querySelector(s); }, $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var fmt = function (n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0'); };
  var cp = function (c) { return 'U+' + c.codePointAt(0).toString(16).toUpperCase().padStart(4, '0'); };

  /* тема */
  var root = document.documentElement, tb = $('#theme');
  try { var sv = localStorage.getItem('kk-theme'); if (sv) root.setAttribute('data-theme', sv); } catch (e) {}
  if (tb) tb.addEventListener('click', function () {
    var n = (root.getAttribute('data-theme') === 'dark' || (!root.getAttribute('data-theme') && matchMedia('(prefers-color-scheme:dark)').matches)) ? 'light' : 'dark';
    root.setAttribute('data-theme', n); try { localStorage.setItem('kk-theme', n); } catch (e) {}
  });

  /* прогресс чтения, оглавление, время чтения */
  var secs = $$('article > section[id]'), links = $$('.toc a'), pg = $('.prog');
  var words = secs.map(function (s) { return s.textContent.trim().split(/\s+/).length; }), total = words.reduce(function (a, b) { return a + b; }, 0);
  var eta = $('#eta'); if (eta) eta.textContent = eta.getAttribute('data-t').replace('{n}', Math.max(1, Math.round(total / 190)));
  secs.forEach(function (s, i) { var l = links[i]; if (l) { var m = Math.max(1, Math.round(words[i] / 190)); var sm = l.querySelector('small'); if (sm) sm.textContent += ' · ' + m + ' ' + (D.ui ? D.ui.min : 'min'); } });
  function onScroll() {
    var h = document.documentElement, p = h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight); if (pg) pg.style.width = (p * 100).toFixed(1) + '%';
    var cur = 0; secs.forEach(function (s, i) { if (s.getBoundingClientRect().top < innerHeight * 0.35) cur = i; });
    links.forEach(function (l, i) { l.classList.toggle('on', i === cur); l.classList.toggle('done', i < cur); });
  }
  addEventListener('scroll', onScroll, { passive: true }); onScroll();
  var tocbtn = $('.toc-btn'), toc = $('.toc');
  if (tocbtn) tocbtn.addEventListener('click', function () { toc.classList.toggle('open'); });
  links.forEach(function (l) { l.addEventListener('click', function () { toc && toc.classList.remove('open'); }); });

  /* появление и счётчики */
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting) return; e.target.classList.add('in'); io.unobserve(e.target);
      $$('[data-count]', e.target).concat(e.target.hasAttribute('data-count') ? [e.target] : []).forEach(function (el) {
        var to = +el.getAttribute('data-count'), t0 = performance.now(), suf = el.getAttribute('data-suf') || '';
        (function step(t) { var k = Math.min(1, (t - t0) / 1100), v = to * (1 - Math.pow(1 - k, 3)); el.textContent = fmt(v) + suf; if (k < 1) requestAnimationFrame(step); })(t0);
      });
    });
  }, { threshold: 0, rootMargin: '0px 0px -6% 0px' });   /* порог 0: раздел может быть в разы выше экрана телефона, и 15% его высоты на экран не помещаются */
  $$('.rv,.stat,.meas .m,.ux').forEach(function (el) { io.observe(el); });

  /* справки-всплывашки */
  var pop = null;
  function closePop() { if (pop) { pop.remove(); pop = null; } }
  function openPop(btn) {
    closePop(); var t = (D.terms || {})[btn.getAttribute('data-t')]; if (!t) return;
    pop = document.createElement('div'); pop.className = 'pop'; pop.setAttribute('role', 'tooltip');
    pop.innerHTML = '<b>' + esc(t.t) + '</b>' + t.d + (t.more ? '<p><a href="#glossary">' + esc(D.ui.more) + ' →</a></p>' : '');
    document.body.appendChild(pop);
    var r = btn.getBoundingClientRect(), w = pop.offsetWidth, x = Math.min(Math.max(12, r.left + scrollX - 8), scrollX + innerWidth - w - 12);
    pop.style.left = x + 'px'; pop.style.top = (r.bottom + scrollY + 10) + 'px';
  }
  document.addEventListener('click', function (e) { var b = e.target.closest && e.target.closest('.term'); if (b) { e.preventDefault(); openPop(b); } else if (!e.target.closest('.pop')) closePop(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePop(); });
  $$('.term').forEach(function (b) { b.setAttribute('tabindex', '0'); b.setAttribute('role', 'button'); b.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPop(b); } }); });

  /* копирование кода */
  $$('.code button').forEach(function (b) { b.addEventListener('click', function () {
    var t = b.parentNode.querySelector('pre').textContent; (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () { b.textContent = D.ui.copied; setTimeout(function () { b.textContent = D.ui.copy; }, 1400); }, function () {});
  }); });

  /* лупа двойников: порт правил H01, H02, H04, ocr и P01 */
  var CY = 'А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі', LAT2CYR = { A: 'А', B: 'В', C: 'С', E: 'Е', H: 'Н', I: 'І', K: 'К', M: 'М', O: 'О', P: 'Р', T: 'Т', X: 'Х', Y: 'У', a: 'а', c: 'с', e: 'е', o: 'о', p: 'р', x: 'х', y: 'у', i: 'і' };
  var FOR = { 'ə': 'ә', 'Ə': 'Ә', 'ӓ': 'ә', 'Ӓ': 'Ә', 'ӧ': 'ө', 'Ӧ': 'Ө', 'ӱ': 'ү', 'Ӱ': 'Ү', 'ӊ': 'ң', 'Ӊ': 'Ң', 'ҥ': 'ң', 'Ҥ': 'Ң', 'ɵ': 'ө', 'Ɵ': 'Ө', 'ҡ': 'қ', 'Ҡ': 'Қ' };
  var LOOK = { 'І': 'I', 'Х': 'X', 'С': 'C', 'М': 'M', 'Т': 'T' }, ROM = /^(?=[IVXLCDM])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})/;
  var INV = /[\u200b-\u200d\u2060\ufeff]/, ABBR = ['ауд', 'обл', 'көш', 'тел', 'бет', 'қаз', 'рес', 'проф', 'доц', 'акад', 'млн', 'млрд'];
  function isRomanOrIT(t) {
    var up = t.toUpperCase(), norm = Array.from(up).map(function (c) { return LOOK[c] || c; }).join('');
    if (norm === 'IT') return true;
    var m = norm.match(ROM); if (norm.length >= 2 && m && m[0].length === norm.length && Array.from(up).every(function (c) { return c.charCodeAt(0) < 128 || LOOK[c]; })) return true;
    m = t.match(ROM); return !!(m && m[0].length >= 2 && new RegExp('^[' + CY + ']{1,6}$').test(t.slice(m[0].length) || '-'));
  }
  function analyse(text) {
    var fin = [], re = new RegExp('[A-Za-z' + CY + 'ƏəӓӒӧӦӱӰӊӉҥҤɵƟҡҠ\\u200b-\\u200d\\u2060\\ufeff]+', 'g'), m, out = '', fixed = '', last = 0, showCp = $('#pg-cp') && $('#pg-cp').checked;
    while ((m = re.exec(text))) {
      var tok = m[0], chars = Array.from(tok), cls = chars.map(function () { return ''; }), rule = '', fx = null;
      var lat = chars.filter(function (c) { return /[A-Za-z]/.test(c); }).length, cyr = chars.filter(function (c) { return new RegExp('[' + CY + ']').test(c); }).length;
      var clean = chars.filter(function (c) { return !INV.test(c); });
      chars.forEach(function (c, i) { if (INV.test(c)) { cls[i] = 'i'; rule = rule || 'H04'; } if (FOR[c]) { cls[i] = 'w'; rule = rule || 'H02'; } });
      var base = clean.map(function (c) { return FOR[c] || c; });
      if (lat && cyr && !isRomanOrIT(tok)) { chars.forEach(function (c, i) { if (/[A-Za-z]/.test(c)) cls[i] = 'b'; }); rule = 'H01'; base = base.map(function (c) { return (cyr >= lat && LAT2CYR[c]) ? LAT2CYR[c] : c; }); }
      var s = base.join(''); if (!rule && /ү/.test(tok) && /[аыоұ]/.test(tok.toLowerCase()) && cyr === chars.length) { chars.forEach(function (c, i) { if (c === 'ү') cls[i] = 'w'; }); rule = 'OCR'; s = s.replace(/ү/g, 'ұ').replace(/Ү/g, 'Ұ'); }
      out += esc(text.slice(last, m.index));
      if (rule) {
        fin.push({ rule: rule, orig: tok, fix: s });
        out += chars.map(function (c, i) { var sym = INV.test(c) ? '\u2300' : c; return cls[i] ? '<mark class="' + (cls[i]) + '" title="' + cp(c) + '">' + esc(sym) + (showCp ? '<sup>' + cp(c) + '</sup>' : '') + '</mark>' : esc(c); }).join('');
        fixed += text.slice(last, m.index) + s;
      } else { out += esc(tok); fixed += text.slice(last, m.index) + tok; }
      last = m.index + tok.length;
    }
    out += esc(text.slice(last)); fixed += text.slice(last);
    var p1 = /([A-Za-zА-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһІі]+)(\.,)/g, q; while ((q = p1.exec(text))) { if (q[1].length > 3 && ABBR.indexOf(q[1].toLowerCase()) < 0) fin.push({ rule: 'P01', orig: q[0], fix: null }); }
    return { html: out, fin: fin, fixed: fixed };
  }
  var ta = $('#pg-in'); if (ta) {
    var P = D.pg || {};
    var render = function () {
      var r = analyse(ta.value); $('#pg-out').innerHTML = r.html || '<span style="color:var(--muted)">' + esc(P.empty) + '</span>';
      var c = {}; r.fin.forEach(function (f) { c[f.rule] = (c[f.rule] || 0) + 1; });
      $('#pg-list').innerHTML = r.fin.length ? r.fin.map(function (f) { return '<li><code>' + f.rule + '</code><span>' + esc(f.orig) + (f.fix && f.fix !== f.orig ? ' → <b>' + esc(f.fix) + '</b>' : '') + ' <small style="color:var(--muted)">' + esc((D.rules || {})[f.rule] || '') + '</small></span><span class="ok">' + (f.fix ? P.fix : P.flag) + '</span></li>'; }).join('') : '<li><span class="ok">✓</span><span>' + esc(P.clean) + '</span><span></span></li>';
      $('#pg-fixed').textContent = r.fixed; $('#pg-n').textContent = r.fin.length;
    };
    ta.addEventListener('input', render); $('#pg-cp').addEventListener('change', render);
    $$('#pg-presets .chip').forEach(function (b, i) { b.addEventListener('click', function () { ta.value = P.presets[i].text; $$('#pg-presets .chip').forEach(function (x) { x.setAttribute('aria-pressed', x === b); }); render(); }); });
    $('#pg-apply').addEventListener('click', function () { ta.value = analyse(ta.value).fixed; render(); });
    ta.value = P.presets[0].text; $('#pg-presets .chip').setAttribute('aria-pressed', 'true'); render();
  }

  /* «Казакстан» → «Қазақстан» */
  var rb = $('#rs-go'); if (rb) {
    var seq = [['К', 'Қ'], ['з', 'з'], ['к', 'қ']], word = D.rs.word, fixw = D.rs.fixed, box = $('#rs-w');
    var show = function (k) { box.innerHTML = Array.from(word).map(function (c, i) { var f = Array.from(fixw)[i]; return (c !== f && i < k) ? '<mark class="i">' + f + '</mark>' : esc(c); }).join(''); };
    var run = function () { var diff = Array.from(word).map(function (c, i) { return c !== Array.from(fixw)[i] ? i : -1; }).filter(function (i) { return i >= 0; }), k = 0; show(0); (function tick() { k += 1; show(diff.length ? diff[Math.min(k, diff.length) - 1] + 1 : 0); if (k < diff.length) setTimeout(tick, 700); })(); };
    rb.addEventListener('click', run); show(0);
  }

  /* конвейер */
  var pp = $('.pipe'); if (pp) {
    var panel = $('.panel', pp), pick = function (g) { $$('g[data-n]', pp).forEach(function (x) { x.classList.toggle('sel', x === g); }); panel.innerHTML = (D.pipe || {})[g.getAttribute('data-n')] || ''; };
    $$('g[data-n]', pp).forEach(function (g) { g.setAttribute('tabindex', '0'); g.setAttribute('role', 'button'); g.addEventListener('click', function () { pick(g); }); g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(g); } }); });
    pick($('g[data-n=L1]', pp));
  }

  /* обозреватель узуса и калькулятор */
  var ux = $('.ux'); if (ux) {
    var U = D.usage, rows = U.rows, cur = 'all', list = $('#ux-list'), det = $('#ux-det');
    var test = { all: function () { return true; }, kk: function (r) { return r.sh >= 70; }, mid: function (r) { return r.sh > 30 && r.sh < 70; }, intl: function (r) { return r.sh <= 30; }, au: function (r) { return r.au; } };
    var draw = function () {
      list.innerHTML = '<div class="zone" aria-hidden="true"></div>' ; list.style.position = 'relative'; list.innerHTML = '';
      rows.filter(test[cur]).forEach(function (r) {
        var d = document.createElement('div'); d.className = 'row' + (r.au ? ' au' : ''); d.tabIndex = 0;
        d.innerHTML = '<div class="nm"><b>' + esc(r.a) + '</b> — ' + esc(r.b) + '</div><div class="tr"><i style="width:0"></i></div><div class="pc">' + r.sh + '\u00a0%</div>';
        var sel = function () { $$('.row', list).forEach(function (x) { x.classList.toggle('sel', x === d); }); det.innerHTML = '<b>' + esc(r.b) + '</b>: ' + r.cb + ' · <b>' + esc(r.a) + '</b>: ' + r.ca + ' — ' + U.share + ' ' + r.sh + '\u00a0%.<br>' + (r.au ? U.author.replace('{f}', '<b>' + esc(r.dec) + '</b>') : U.byuse.replace('{f}', '<b>' + esc(r.dec) + '</b>')); };
        d.addEventListener('click', sel); d.addEventListener('keydown', function (e) { if (e.key === 'Enter') sel(); }); list.appendChild(d);
        requestAnimationFrame(function () { setTimeout(function () { d.querySelector('i').style.width = r.sh + '%'; }, 30); });
      });
    };
    $$('#ux-f .chip').forEach(function (b) { b.addEventListener('click', function () { cur = b.getAttribute('data-f'); $$('#ux-f .chip').forEach(function (x) { x.setAttribute('aria-pressed', x === b); }); draw(); }); });
    draw();
    var ca = $('#c-a'), cb = $('#c-b'), vd = $('#c-v');
    var calc = function () { var a = +ca.value || 0, b = +cb.value || 0, t = a + b, s = t ? b / t : 0, k;
      if (t < 10) k = U.v.silent; else if (s >= .7) k = U.v.kk; else if (s <= .3) k = U.v.intl; else k = U.v.mid;
      vd.innerHTML = k + ' <span style="font-weight:400;color:var(--muted)">(' + U.total + ' ' + t + ', ' + U.share + ' ' + Math.round(s * 100) + '\u00a0%)</span>'; };
    ca.addEventListener('input', calc); cb.addEventListener('input', calc); calc();
  }

  /* глоссарий */
  var gs = $('.gl-s'); if (gs) gs.addEventListener('input', function () { var q = gs.value.toLowerCase().trim(); $$('.gl .e').forEach(function (e) { e.hidden = q && e.textContent.toLowerCase().indexOf(q) < 0; }); });
})();
