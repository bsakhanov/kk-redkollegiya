#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""Рисунки лонгрида (docs/longread*.md): конвейер проверки и доли казахской формы по парам.

Запуск: python3 docs/img/make_figures.py
Пишет по два SVG на язык (ru, en, kk): pipeline.<язык>.svg и usage-share.<язык>.svg.
Только стандартная библиотека. Цвета заданы явно, фон белый: рисунки читаются и на светлой, и на тёмной странице.
"""

import os
from xml.sax.saxutils import escape

OUT = os.path.dirname(os.path.abspath(__file__))
INK, QUIET, EDGE, ACCENT = "#1f2328", "#59636e", "#9aa1a9", "#2563eb"
MUTED, TINT, REF = "#c8c9bd", "#efeeea", "#7d8590"
FONT = "-apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'DejaVu Sans', sans-serif"

# ── подписи ────────────────────────────────────────────────────────────────────────────────────
PIPE = {
    "ru": dict(
        title="Текст проходит три проверки, а последнее слово остаётся за человеком",
        inp=("Казахский", "текст"), orig=("Русский оригинал", "если он есть"),
        hyg=("Алтынсарин", "гигиена", "kk_clean · kk_restore", "kk_lint (линтер)"),
        par=("Валиханов", "сверка с оригиналом", "kk_parity · kk_pairs", "числа, даты, имена"),
        ter=("Шакарим", "термины", "kk_usage · глоссарий", "узус корпуса"),
        find="Находки с цитатами: у каждой свой уровень",
        o1=("Блокирующие", "публиковать нельзя", "код возврата 2"),
        o2=("Исправимые", "apply.py вносит", "в текст по цитате"),
        o3=("Решает человек", "в текст не вносится", "читающий по-казахски")),
    "en": dict(
        title="A text passes three checks, and the last word stays with a person",
        inp=("Kazakh", "text"), orig=("Russian original", "if there is one"),
        hyg=("Altynsarin", "hygiene", "kk_clean · kk_restore", "kk_lint (linter)"),
        par=("Valikhanov", "comparison", "kk_parity · kk_pairs", "numbers, dates, names"),
        ter=("Shakarim", "terms", "kk_usage · glossary", "corpus usage"),
        find="Findings with quotes: each has its own severity",
        o1=("Blocking", "do not publish", "exit code 2"),
        o2=("Fixable", "apply.py applies", "to the text by quote"),
        o3=("A person decides", "not applied to the text", "a reader of Kazakh")),
    "kk": dict(
        title="Мәтін үш тексеруден өтеді, ал соңғы сөз адамда қалады",
        inp=("Қазақша", "мәтін"), orig=("Орыс түпнұсқасы", "егер бар болса"),
        hyg=("Алтынсарин", "гигиена", "kk_clean · kk_restore", "kk_lint (линтер)"),
        par=("Уәлиханов", "түпнұсқамен салыстыру", "kk_parity · kk_pairs", "сандар, күндер, атаулар"),
        ter=("Шәкәрім", "терминдер", "kk_usage · глоссарий", "корпус қолданысы"),
        find="Дәйексөзі бар ескертулер: әрқайсысының өз деңгейі бар",
        o1=("Блоктаушы", "жариялауға болмайды", "қайтару коды 2"),
        o2=("Түзетілетін", "apply.py мәтінге", "дәйексөзбен енгізеді"),
        o3=("Адам шешеді", "мәтінге енгізілмейді", "қазақша оқитын адам")),
}

CHART = {
    "ru": dict(title="Узус выбрал казахское слово в 20 парах из 25; в трёх автор оставил международное",
               sub="Доля казахской формы среди вхождений пары в корпусе из 840 тысяч слов, %",
               key="синий — слова, которые автор оставил международными вопреки узусу", band="спорная зона"),
    "en": dict(title="Usage chose the Kazakh word in 20 of 25 pairs; the author overrode three",
               sub="Share of the Kazakh form among occurrences of the pair, corpus of 840 thousand words, %",
               key="blue — words the author kept international against usage", band="disputed zone"),
    "kk": dict(title="Қолданыс 25 жұптың 20-сінде қазақ сөзін таңдады; үшеуін автор өзгертті",
               sub="Жұптың кездесулері ішіндегі қазақ формасының үлесі, 840 мың сөздік корпус, %",
               key="көк — қолданысқа қарамастан автор халықаралық қалдырған сөздер", band="таласты аймақ"),
}

# (ключ, международная форма, казахская форма, вхождений казахской, вхождений международной, доля казахской, выделить)
ROWS = [
    ("refining", "нефтепереработка", "мұнай өңдеу", 2048, 18, 99, 0), ("pipeline", "трубопровод", "құбыр", 1143, 43, 96, 0),
    ("drilling", "бурение", "бұрғылау", 662, 34, 95, 0), ("equipment", "оборудование", "жабдық", 1116, 82, 93, 0),
    ("project", "проект", "жоба", 4193, 368, 92, 0), ("indicator", "показатель", "көрсеткіш", 891, 77, 92, 0),
    ("partner", "партнёр", "серіктес", 598, 56, 91, 1), ("initiative", "инициатива", "бастама", 510, 53, 91, 0),
    ("labor-safety", "охрана труда", "еңбекті қорғау", 220, 21, 91, 0), ("field", "месторождение", "кен орны", 1866, 201, 90, 0),
    ("modernization", "модернизация", "жаңғырту", 372, 42, 90, 0), ("capacity", "мощность", "қуат", 771, 88, 90, 0),
    ("concept", "концепция", "тұжырымдама", 59, 7, 89, 1), ("petrochem", "нефтехимия", "мұнайхимия", 461, 56, 89, 0),
    ("enterprise", "предприятие", "кәсіпорын", 1575, 223, 88, 0), ("abbr-ltd", "ТОО", "ЖШС", 2512, 336, 88, 0),
    ("well", "скважина", "ұңғыма", 803, 124, 87, 0), ("object", "объект", "нысан", 753, 146, 84, 1),
    ("abbr-country", "РК", "ҚР", 513, 145, 78, 0), ("database", "деректер базасы", "дерекқор", 7, 3, 70, 0),
    ("abbr-refinery", "НПЗ", "МӨЗ", 224, 107, 68, 0), ("application", "мобильді қосымша", "қолданба", 21, 15, 58, 0),
    ("website", "сайт", "торап", 26, 296, 8, 0), ("digital", "цифрлық", "сандық", 8, 467, 2, 0),
    ("ai", "жасанды интеллект", "жасанды зерде", 0, 225, 0, 0),
]


def t(x, y, s, size=13, weight=400, fill=INK, anchor="middle"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}">{escape(s)}</text>')


def box(x, y, w, h, main=False):
    if main:
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{ACCENT}" fill-opacity="0.12" '
                f'stroke="{ACCENT}" stroke-width="2"/>')
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="none" stroke="{EDGE}" stroke-width="1.25"/>'


def svg(width, height, title, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'role="img" aria-labelledby="t" font-family="{FONT}">\n<title id="t">{escape(title)}</title>\n'
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>\n{body}\n</svg>\n')


def pipeline(lang):
    L = PIPE[lang]
    p = [t(24, 30, L["title"], 15, 600, INK, "start")]
    p.append(f'<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
             f'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{EDGE}"/></marker></defs>')
    arrows = ["M134 180H158", "M334 180H358", "M534 180H558", "M446 104V136", "M246 224V256", "M446 224V256",
              "M646 224V256", "M246 304V336", "M446 304V336", "M646 304V336"]
    p.append(f'<g fill="none" stroke="{EDGE}" stroke-width="1.25">' +
             "".join(f'<path d="{a}" marker-end="url(#a)"/>' for a in arrows) + "</g>")
    p += [box(24, 152, 110, 56), t(79, 176, L["inp"][0], 13, 600), t(79, 194, L["inp"][1], 13, 600)]
    p += [box(358, 48, 176, 56), t(446, 72, L["orig"][0], 13, 600), t(446, 88, L["orig"][1], 11.5, 400, QUIET)]
    for x, k in ((158, "hyg"), (358, "par"), (558, "ter")):
        cx = x + 88
        p += [box(x, 136, 176, 88), t(cx, 160, L[k][0], 13, 600), t(cx, 176, L[k][1], 11.5, 400, INK),
              t(cx, 192, L[k][2], 11.5, 400, QUIET), t(cx, 208, L[k][3], 11.5, 400, QUIET)]
    p += [box(158, 256, 576, 48), t(446, 285, L["find"], 13, 600)]
    for x, k in ((158, "o1"), (358, "o2"), (558, "o3")):
        cx = x + 88
        p += [box(x, 336, 176, 72, k == "o3"), t(cx, 360, L[k][0], 13, 600), t(cx, 376, L[k][1], 11.5, 400, QUIET),
              t(cx, 392, L[k][2], 11.5, 400, QUIET)]
    return svg(760, 432, L["title"], "\n".join(p))


def usage_share(lang):
    L = CHART[lang]
    x0, w, y0, step = 250, 470, 112, 20
    n = len(ROWS)
    bottom = y0 + n * step

    def x(pct):
        return x0 + pct * w / 100

    p = [t(24, 30, L["title"], 15, 600, INK, "start"), t(24, 52, L["sub"], 11.5, 400, QUIET, "start"),
         f'<rect x="24" y="60" width="10" height="10" rx="2" fill="{ACCENT}"/>',
         t(42, 69, L["key"], 11.5, 400, QUIET, "start")]
    p.append(f'<rect x="{x(30)}" y="{y0 - 8}" width="{x(70) - x(30)}" height="{n * step + 8}" fill="{TINT}"/>')
    p.append(t((x(30) + x(70)) / 2, y0 - 22, L["band"], 11.5, 400, QUIET))
    for pct in (30, 70):
        p.append(f'<line x1="{x(pct)}" x2="{x(pct)}" y1="{y0 - 16}" y2="{bottom}" stroke="{REF}" stroke-width="1.25" '
                 f'stroke-dasharray="4 4"/>')
        p.append(t(x(pct), y0 - 22, f"{pct}%", 11.5, 400, QUIET))
    p.append(f'<line x1="{x0}" x2="{x0}" y1="{y0 - 8}" y2="{bottom}" stroke="{EDGE}" stroke-width="1.25"/>')
    for i, (_, a, b, cb, ca, share, acc) in enumerate(ROWS):
        yy = y0 + i * step
        p.append(t(x0 - 10, yy + 14, f"{a} — {b}", 11.5, 600 if acc else 400, INK if acc else QUIET, "end"))
        p.append(f'<rect x="{x0}" y="{yy + 4}" width="{share * w / 100}" height="12" '
                 f'fill="{ACCENT if acc else MUTED}"><title>{escape(a)} — {escape(b)}: {cb} / {ca}; {share}%</title></rect>')
        if acc or share < 30:
            p.append(t(x(share) + 6, yy + 14, f"{share}%", 11.5, 400, INK, "start"))
    return svg(760, 640, L["title"], "\n".join(p))


if __name__ == "__main__":
    for lang in ("ru", "en", "kk"):
        for name, fn in (("pipeline", pipeline), ("usage-share", usage_share)):
            path = os.path.join(OUT, f"{name}.{lang}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(fn(lang))
            print("записан", os.path.relpath(path))
