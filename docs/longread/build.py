#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""Сборка интерактивного лонгрида: docs/longread*.md → index.html, kk/index.html, en/index.html рядом со скриптом.

Текст берётся из Markdown (он остаётся первоисточником), всё остальное — оглавление, лупа двойников, схемы, кейсы,
обозреватель узуса, хроника и глоссарий — вставляется сборщиком. Нужны пакет markdown и плакаты docs/img/characters.
Запуск: python3 docs/longread/build.py
"""
import html as H
import json
import os
import re
import shutil
import sys

import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HERE)
ROOT = os.path.dirname(DOCS)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(DOCS, "img"))
from i18n import LANGS  # noqa: E402
from make_figures import ROWS  # noqa: E402

VER = open(os.path.join(ROOT, "VERSION")).read().strip()
BASE = "https://webmarka.kz/research/kk-redkollegiya/"
MD = {"ru": "longread.md", "kk": "longread.kk.md", "en": "longread.en.md"}
OUT = {"ru": "index.html", "kk": "kk/index.html", "en": "en/index.html"}
DEC = {"object": "объект", "partner": "партнёр", "concept": "концепция", "digital": "цифрлық", "ai": "жасанды интеллект", "abbr-refinery": "МӨЗ",
       "application": "мобильді қосымша", "website": "сайт", "database": "дерекқор"}
AUTHOR = {"object", "partner", "concept", "abbr-refinery", "application"}
E = H.escape


def split_md(text):
    text = re.sub(r"^# (.+)\n", "", text, count=1)
    title = re.search(r"^# (.+)$", open(os.path.join(DOCS, "longread.md"), encoding="utf-8").read(), re.M)
    parts = re.split(r"^## ", text, flags=re.M)
    head, secs = parts[0], parts[1:]
    head = re.sub(r"^\*\*.*·.*\n|^\[.*·.*\n", "", head, flags=re.M)
    head = re.sub(r"^\*[^*\n]+\*\n", "", head, count=1, flags=re.M)
    note = re.search(r"^> (.+)$", head, re.M)
    paras = [p.strip() for p in re.sub(r"^> .+\n?", "", head, flags=re.M).strip().split("\n\n") if p.strip()]
    return paras, (note.group(1) if note else ""), [(s.split("\n", 1)[0].strip(), s.split("\n", 1)[1]) for s in secs]


def md(s):
    h = markdown.markdown(s, extensions=["tables", "fenced_code", "sane_lists"])

    def link(m):
        href = m.group(1)
        if re.match(r"^(?:https?:|#|mailto:)", href):
            return m.group(0)
        return 'href="https://github.com/bsakhanov/kk-redkollegiya/blob/main/' + ("" if href.startswith("../") else "docs/") + href.replace("../", "") + '"'
    return re.sub(r'href="([^"]+)"', link, h)       # относительные ссылки Markdown ведут на репозиторий


def mark_terms(h, T, used):
    toks = re.split(r"(<[^>]+>)", h)
    skip, depth = {"h2", "h3", "summary", "code", "pre", "a", "button", "details"}, []
    for i, t in enumerate(toks):
        m = re.match(r"<(/?)(\w+)", t)
        if m:
            (depth.append if not m.group(1) and not t.endswith("/>") else (lambda x: depth.pop() if depth and depth[-1] == x else None))(m.group(2)) if m.group(2) in skip else None
            continue
        if depth:
            continue
        for tid, pat in T["term_re"].items():
            if tid in used:
                continue
            mm = re.search(rf"(?<![\w-])({pat})(?![\w-])", t, re.I)
            if mm:
                used.add(tid)
                t = t[:mm.start()] + f'<button class="term" type="button" data-t="{tid}">{mm.group(1)}</button>' + t[mm.end():]
        toks[i] = t
    return "".join(toks)


def pipeline_svg(T, A):
    S = T["pipe_svg"]

    def box(x, y, w, h, n, lines, main=False):
        tx = x + w / 2
        ts = "".join(f'<text x="{tx}" y="{y + 24 + i * 16}" text-anchor="middle" font-size="{13 if i == 0 else 11.5}" font-weight="{600 if i == 0 else 400}" fill="{"var(--ink)" if i < 2 else "var(--muted)"}">{E(l)}</text>' for i, l in enumerate(lines))
        return f'<g data-n="{n}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{"var(--soft)" if main else "var(--paper)"}" stroke="{"var(--pri)" if main else "var(--line2)"}" stroke-width="{2 if main else 1.4}"/>{ts}</g>'
    arrows = ["M134 180H158", "M334 180H358", "M534 180H558", "M446 104V136", "M246 224V256", "M446 224V256", "M646 224V256", "M246 304V336", "M446 304V336", "M646 304V336"]
    g = "".join(f'<path d="{a}" marker-end="url(#ar)"/>' for a in arrows)
    body = (f'<text x="20" y="28" font-size="15" font-weight="700" fill="var(--ink)">{E(S["title"])}</text>'
            f'<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--line2)"/></marker></defs>'
            f'<g fill="none" stroke="var(--line2)" stroke-width="1.4">{g}</g>'
            + box(24, 152, 110, 56, "in", S["inp"]) + box(358, 48, 176, 56, "orig", S["orig"])
            + box(158, 136, 176, 88, "L1", S["L1"]) + box(358, 136, 176, 88, "L2", S["L2"]) + box(558, 136, 176, 88, "L3", S["L3"])
            + box(158, 256, 576, 48, "find", [S["find"]])
            + box(158, 336, 176, 72, "o1", S["o1"]) + box(358, 336, 176, 72, "o2", S["o2"]) + box(558, 336, 176, 72, "o3", S["o3"], True))
    return (f'<figure class="fig pipe rv"><svg viewBox="0 0 760 420" role="img" aria-label="{E(S["title"])}">{body}</svg>'
            f'<div class="panel" aria-live="polite"></div><figcaption>{E(S["hint"])}</figcaption></figure>')


def look_fig(T):
    f = T["fig"]
    pairs = [("қ", "U+049B", "ҡ", "U+04A1"), ("ә", "U+04D9", "\u0259", "U+0259"), ("ң", "U+04A3", "\u04ca", "U+04CA"), ("ө", "U+04E9", "\u0275", "U+0275"),
             ("і", "U+0456", "i", "U+0069"), ("а", "U+0430", "a", "U+0061"), ("с", "U+0441", "c", "U+0063"), ("р", "U+0440", "p", "U+0070")]
    tiles = "".join(f'<div><b>{a}<em>{b}</em></b><code>{ca}</code> · <code>{cb}</code></div>' for a, ca, b, cb in pairs)
    return f'<figure class="fig rv"><h4>{E(f["look_t"])}</h4><div class="lg">{tiles}</div><figcaption>{E(f["look_c"])}</figcaption></figure>'


def pair_fig(title, a_label, a_val, b_label, b_val, cap):
    return (f'<figure class="fig rv"><h4>{E(title)}</h4><div class="pair"><div class="tile bad"><small>{E(a_label)}</small><div class="w">{E(a_val)}</div></div><div class="arrow">→</div>'
            f'<div class="tile ok"><small>{E(b_label)}</small><div class="w">{E(b_val)}</div></div></div><figcaption>{E(cap)}</figcaption></figure>')


def restore_fig(T):
    f = T["fig"]
    return (f'<figure class="fig rv"><h4>{E(f["rs_t"])}</h4><p class="hint">{E(f["rs_hint"])}</p><div class="pair"><div class="tile"><small>→</small><div class="w" id="rs-w"></div></div>'
            f'<div></div><div><button class="btn" id="rs-go" type="button">{E(f["rs_btn"])}</button></div></div><figcaption>{E(f["rs_c"])}</figcaption></figure>')


def calque_fig(T):
    f = T["fig"]
    vals = [0, 0.9, 15.3, 116.7]
    rows = "".join(f'<div class="m" style="border:0;padding:6px 0"><div style="display:flex;justify-content:space-between;font-size:14px"><span>{E(g)}</span><b style="font-family:var(--mono)">{str(v).replace(".", ",") if T["code"] != "en" else v}</b></div><div class="bar"><i style="--w:{max(v / 1.2, 0.6):.1f}%"></i></div></div>' for g, v in zip(f["cal_g"], vals))
    return f'<figure class="fig rv in"><h4>{E(f["cal_t"])}</h4>{rows}<figcaption>{E(f["cal_c"])}</figcaption></figure>'


def parity_fig(T):
    f = T["fig"]
    return (f'<figure class="fig rv"><h4>{E(f["par_t"])}</h4><div class="pair"><div class="tile"><small>{E(f["par_ru"])}</small><div class="w" style="font-family:var(--font)">{E(f["par_ru_t"])}</div></div>'
            f'<div class="arrow">⇄</div><div class="tile bad"><small>{E(f["par_kk"])}</small><div class="w" style="font-family:var(--font)">{E(f["par_kk_t"])}</div></div></div>'
            f'<p style="margin:14px 0 0"><span class="tag" style="background:var(--badbg);color:var(--bad)">{E(f["par_flag"])}</span></p><figcaption>{E(f["par_c"])}</figcaption></figure>')


def playground(T):
    p = T["pg"]
    chips = "".join(f'<button class="chip" type="button" aria-pressed="false">{E(l)}</button>' for l, _ in p["presets"])
    return (f'<div class="fig pg rv" id="pg"><h4>{E(p["title"])}</h4><p class="hint">{E(p["intro"])}</p><div class="chips" id="pg-presets">{chips}</div>'
            f'<textarea id="pg-in" spellcheck="false" aria-label="{E(p["title"])}" placeholder="{E(p["placeholder"])}"></textarea>'
            f'<div class="row-tools"><label class="sw"><input type="checkbox" id="pg-cp"> {E(p["codes"])}</label><button class="btn pri" type="button" id="pg-apply">{E(p["apply"])}</button>'
            f'<span class="hint" style="margin:0"><b id="pg-n">0</b> {E(p["n"])}</span></div>'
            f'<div class="out" id="pg-out" style="margin-top:12px"></div><ul class="fl" id="pg-list"></ul>'
            f'<h4 style="margin-top:16px;font-size:.95rem">{E(p["fixed"])}</h4><div class="out" id="pg-fixed"></div></div>')


def usage_block(T):
    u = T["ux"]
    chips = "".join(f'<button class="chip" type="button" data-f="{k}" aria-pressed="{str(k == "all").lower()}">{E(l)}</button>' for k, l in u["f"])
    return (f'<div class="fig ux rv"><h4>{E(u["t"])}</h4><p class="hint">{E(u["hint"])}</p><div class="chips" id="ux-f">{chips}</div><div id="ux-list" style="position:relative"></div><div class="detail" id="ux-det"></div>'
            f'<h4 style="margin:22px 0 4px">{E(u["calc_t"])}</h4><p class="hint">{E(u["calc_h"])}</p><div class="calc"><div><label for="c-a">{E(u["a"])}</label><input id="c-a" type="number" min="0" value="12"></div>'
            f'<div><label for="c-b">{E(u["b"])}</label><input id="c-b" type="number" min="0" value="130"></div></div><div class="verdict" id="c-v"></div></div>')


def layers_block(T, A):
    t = T["layers_t"]
    cards = ""
    for (g, name, role, on, tools, text), cid in zip(T["layers"], ["altynsarin", "valikhanov", "shakarim", "baitursynov", "auezov", "slopotron"]):
        cards += (f'<div class="card layer{"" if on else " plan"}" style="padding:0;overflow:hidden;display:block"><img src="{A}characters/{cid}.{T["code"]}.png" alt="{E(name)}" loading="lazy" style="width:100%;aspect-ratio:16/9;object-fit:cover;display:block">'
                  f'<div style="padding:14px 20px 20px"><span class="st {"on" if on else "pl"}">{E(t[1] if on else t[2])}</span><h4>{E(name)} · {E(role)}</h4><p>{E(text)}</p><p><code>{E(tools)}</code></p></div></div>')
    return f'<h3 style="margin-top:30px">{E(t[0])}</h3><div class="grid">{cards}</div>'


def cases_section(T):
    lb = T["case_labels"]
    cards = "".join(f'<div class="card case rv"><span class="tag">{E(tag)}</span><h4>{E(title)}</h4><p>{E(sm)}</p><details><summary>{E(lb[3])}</summary><dl><dt>{E(lb[0])}</dt><dd>{E(see)}</dd><dt>{E(lb[1])}</dt><dd>{did}</dd><dt>{E(lb[2])}</dt><dd>{E(res)}</dd></dl></details></div>'
                    for tag, title, sm, see, did, res in T["cases"])
    return f'<p>{E(T["cases_intro"])}</p><div class="grid">{cards}</div>'


def timeline(T):
    items = "".join(f'<li><b>v{v}</b><time>{E(d)}</time><span>{E(t)}</span></li>' for v, d, t in T["tl"])
    return f'<h3 style="margin-top:30px">{E(T["tl_t"])}</h3><ol class="tl" style="margin-left:0;padding-left:0;max-width:none">{items}</ol>'


def measures(h, T):
    rows = re.findall(r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>", h, re.S)
    cards = "".join(f'<div class="m rv"><h4>{a}</h4><div class="v">{b}</div><div class="bar"><i style="--w:{w}%"></i></div><div class="on">{c}</div></div>' for (a, b, c), w in zip(rows, T["meas_bars"] + [60] * 9))
    return re.sub(r"<table>.*?</table>", f'<div class="meas">{cards}</div>', h, count=1, flags=re.S)


def code_blocks(h, T):
    return re.sub(r"<pre><code[^>]*>(.*?)</code></pre>", lambda m: f'<div class="code"><button type="button">{E(T["ui"]["copy"])}</button><pre><code>{m.group(1)}</code></pre></div>', h, flags=re.S)


def build(lang):
    T = LANGS[lang]
    A = "assets/" if lang == "ru" else "../assets/"
    paras, note, secs = split_md(open(os.path.join(DOCS, MD[lang]), encoding="utf-8").read())
    title = re.search(r"^# (.+)$", open(os.path.join(DOCS, MD[lang]), encoding="utf-8").read(), re.M).group(1).strip()
    terms, used, notes = {}, set(), []
    for tid, name, text in T["gl_extra"] and [(a, b, c) for a, b, c in T["gl_extra"]]:
        terms[tid] = {"t": name, "d": f"<p>{E(text)}</p>", "more": False}
    sections = []
    for i, (h2, body) in enumerate(secs):
        h = md(body)

        def note_sub(m):
            ttl = re.sub(r"^[^:]+:\s*", "", re.sub(r"\.$", "", m.group(1))).strip()
            idx = len(notes)
            notes.append(ttl)
            for tid, tname in T["term_map"].get(idx, []):
                terms[tid] = {"t": tname, "d": f"<p>{m.group(2).strip()}</p>", "more": True}
            return f'<details class="callout"><summary>{m.group(1).rstrip(".")}</summary><p>{m.group(2).strip()}</p></details>'
        h = re.sub(r"<blockquote>\s*<p><strong>([^<]+)</strong>(.*?)</p>\s*</blockquote>", note_sub, h, flags=re.S)
        h = re.sub(r'<p><img alt="[^"]*" src="img/pipeline[^"]*" ?/?></p>', "@@PIPE@@", h)
        h = re.sub(r'<p><img alt="[^"]*" src="img/usage-share[^"]*" ?/?></p>', "@@UX@@", h)
        h = measures(h, T) if "<table>" in h else h
        h = code_blocks(h, T)
        h = mark_terms(h, T, used)
        if i == 1:      # «Зачем это нужно»: нумерованные подразделы и иллюстрации к каждому
            figs = [look_fig(T) + playground(T), pair_fig(T["fig"]["enc_t"], T["fig"]["enc_was"], "ìåêòåï", T["fig"]["enc_now"], "мектеп", T["fig"]["enc_c"]),
                    pair_fig(T["fig"]["ocr_t"], T["fig"]["ocr_was"], "жацеырыеу", T["fig"]["ocr_now"], "жаңғырығу", T["fig"]["ocr_c"]), restore_fig(T), calque_fig(T), parity_fig(T)]
            chunks = re.split(r"(?=<h3>)", h)
            out = chunks[0]
            for k, ch in enumerate(chunks[1:]):
                ch = re.sub(r"<h3>(.*?)</h3>", lambda m, k=k: f'<h3><span class="no">{k + 1}</span><span>{m.group(1)}</span></h3>', ch, count=1)
                out += ch + (figs[k] if k < len(figs) else "")
            h = out
        sections.append([h2, h])
    # вставки
    sections[3][1] = sections[3][1].replace("@@PIPE@@", pipeline_svg(T, A)) + layers_block(T, A)
    sections[4][1] = sections[4][1].replace("@@UX@@", usage_block(T))
    sections[7][1] = timeline(T) + sections[7][1]
    cases = (T["sec_cases"], cases_section(T))
    gl = (T["sec_gloss"], f'<p>{E(T["gl_h"])}</p><input class="gl-s" type="search" placeholder="{E(T["gl_s"])}" aria-label="{E(T["gl_s"])}"><div class="gl"><dl>'
          + "".join(f'<div class="e"><dt>{E(v["t"])}</dt><dd>{re.sub("^<p>|</p>$", "", v["d"])}</dd></div>' for v in sorted(terms.values(), key=lambda v: v["t"].lower())) + "</dl></div>")
    sections.insert(2, list(cases))
    sections.insert(len(sections) - 1, list(gl))
    # оболочка
    toc = "".join(f'<li><a href="#s{i + 1}"><i>{i + 1:02d}</i><span>{E(re.sub(r"^.*?: ", "", t) if False else t)}<small>{E(T["subs"][i])}</small></span></a></li>' for i, (t, _) in enumerate(sections))
    art = "".join(f'<section id="s{i + 1}" class="rv"><h2><span class="n">{i + 1:02d} / {len(sections):02d}</span>{t}</h2><p class="sub">{E(T["subs"][i])}</p>{b}</section>' for i, (t, b) in enumerate(sections))
    art = art.replace("@@PIPE@@", "").replace("@@UX@@", "")
    stats = "".join(f'<div class="stat"><b{f" data-count={n} data-suf={json.dumps(s, ensure_ascii=False)}" if n else ""}>{"" if n else E(s)}{f"0{E(s)}" if n else ""}</b><span>{E(lab)}</span></div>' for n, s, lab in T["stats"])
    usage = [dict(a=a, b=b, ca=ca, cb=cb, sh=sh, au=key in AUTHOR, dec=DEC.get(key, b)) for key, a, b, cb, ca, sh, _ in ROWS]
    data = dict(ui=T["ui"], rules=T["rules"], pg=dict(T["pg"], presets=[dict(label=l, text=t) for l, t in T["pg"]["presets"]]), rs=T["rs"], pipe={("in" if k == "_in" else k): v for k, v in T["pipe"].items()},
                usage=dict(rows=usage, share=T["ux"]["share"], author=T["ux"]["author"], byuse=T["ux"]["byuse"], v=T["ux"]["v"], total=T["ux"]["total"]), terms=terms)
    url = BASE + T["url_suffix"]
    alts = "".join(f'<link rel="alternate" hreflang="{c}" href="{BASE + LANGS[c]["url_suffix"]}">' for c in ("ru", "kk", "en")) + f'<link rel="alternate" hreflang="x-default" href="{BASE}">'
    rel = {"ru": {"kk": "kk/", "en": "en/"}, "kk": {"ru": "../", "en": "../en/"}, "en": {"ru": "../", "kk": "../kk/"}}[lang]
    seg = "".join((f'<a href="{rel[c]}" hreflang="{c}" lang="{c}">{LANGS[c]["name"]}</a>' if c != lang else f'<a aria-current="page" lang="{c}">{LANGS[c]["name"]}</a>') for c in ("ru", "kk", "en"))
    ld = {"@context": "https://schema.org", "@graph": [{"@type": "TechArticle", "@id": url + "#article", "headline": title, "inLanguage": lang, "datePublished": "2026-10-13", "dateModified": "2026-10-14",
          "author": {"@id": "https://webmarka.kz/#person"}, "mainEntityOfPage": url, "image": "https://webmarka.kz/assets/media/2026/kk-redkollegiya-og.jpg",
          "about": {"@type": "SoftwareSourceCode", "name": "kk-redkollegiya", "codeRepository": "https://github.com/bsakhanov/kk-redkollegiya", "license": "https://www.gnu.org/licenses/gpl-3.0.html"}}]}
    lead = "".join(f"<p>{re.sub(r'^<p>|</p>$', '', md(p))}</p>" for p in paras[:2])
    hero_svg = ('<svg class="lk" viewBox="0 0 520 300" aria-hidden="true"><text x="10" y="70" class="ghost">Ә Ғ Қ Ң Ө</text><text x="10" y="140" class="ghost">Ұ Ү Һ І ә</text>'
                '<text x="10" y="250">қорық<tspan fill="var(--bad)">\u0063\u0061</tspan></text><circle cx="330" cy="225" r="56" fill="none" stroke="var(--pri)" stroke-width="5"/><path d="M370 266L410 306" stroke="var(--pri)" stroke-width="7" stroke-linecap="round"/></svg>')
    page = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- build: kk-redkollegiya longread, набор v{VER}, 2026-10-14 -->
<!-- ссылка «все материалы исследования» уже есть в шапке страницы -->
<title>{E(T["title_tag"])}</title>
<meta name="description" content="{E(T["og_desc"])}">
<link rel="canonical" href="{url}">
{alts}
<meta name="theme-color" content="#ffffff">
<meta name="author" content="{E({"ru": "Бейбит Саханов", "kk": "Бейбіт Саханов", "en": "Beibit Sakhanov"}[lang])}">
<meta property="og:type" content="article"><meta property="og:site_name" content="Webmarka"><meta property="og:locale" content="{T["locale"]}">
<meta property="og:url" content="{url}"><meta property="og:title" content="{E(T["og_title"])}"><meta property="og:description" content="{E(T["og_desc"])}">
<meta property="og:image" content="https://webmarka.kz/assets/media/2026/kk-redkollegiya-og.jpg"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="https://webmarka.kz/assets/img/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{A}longread.css?v={VER}">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body>
<header class="bar-top"><div class="wrap"><a class="back" href="https://webmarka.kz/research/">{E(T["ui"]["back"])}</a><span class="sp"></span><nav class="seg" aria-label="language">{seg}</nav>
<button class="seg" id="theme" type="button" style="padding:8px 13px;font-weight:600;font-size:13px" aria-label="{E(T["ui"]["theme"])}">◐</button></div><div class="prog"></div></header>
<main>
<div class="hero"><div class="wrap">{hero_svg}<span class="kick">{E(T["kicker"])}</span><h1>{E(title)}</h1><div class="lead">{lead}</div>
<p class="meta">{E(T["meta"].format(ver=VER))}{f" · {E(note)}" if note else ""}</p>
<div class="cta"><a class="btn pri" href="https://github.com/bsakhanov/kk-redkollegiya">{E(T["cta"][0])}</a><a class="btn" href="https://github.com/bsakhanov/kk-redkollegiya/releases/latest">{E(T["cta"][1].format(ver=VER))}</a><a class="btn" href="#pg">{E(T["cta"][2])}</a></div>
<div class="stats">{stats}</div></div></div>
<div class="wrap layout"><aside class="toc" aria-label="{E(T["ui"]["toc"])}"><h2>{E(T["ui"]["toc"])}</h2><ol>{toc}</ol><p class="eta" id="eta" data-t="{E(T["ui"]["eta"])}"></p></aside>
<article>{art}</article></div>
<button class="toc-btn" type="button">☰ {E(T["ui"]["toc"])}</button>
</main>
<footer class="foot"><div class="wrap"><div>{E(T["foot"])}</div><div>© 2026 Бейбит Саханов · GPL-3.0-or-later</div></div></footer>
<script type="application/json" id="data">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>
<script src="{A}longread.js?v={VER}" defer></script>
</body>
</html>
"""
    path = os.path.join(HERE, OUT[lang])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(page)
    return path, len(page)


def main():
    dst = os.path.join(HERE, "assets", "characters")
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(os.path.join(DOCS, "img", "characters")):
        if f.endswith(".png"):
            shutil.copy2(os.path.join(DOCS, "img", "characters", f), dst)
    for lang in ("ru", "kk", "en"):
        p, n = build(lang)
        print("записан", os.path.relpath(p, ROOT), f"{n // 1024} КБ")


if __name__ == "__main__":
    main()
