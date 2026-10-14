#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""Плакаты-«персонажи» шести слоёв проверки (по образцу русской Редколлегии): по одному на слой и язык, 1280×720.

Запуск: python3 docs/img/characters/make_characters.py [--fonts КАТАЛОГ]
Нужны Playwright с Chromium и шрифты PT Serif Bold, PT Sans Regular и Bold (SIL OFL; казахские буквы в них есть):
https://github.com/google/fonts/tree/main/ofl/ptserif и /ptsans. Результат: <слой>.<язык>.png рядом со скриптом.
"""
import argparse
import os
from html import escape as E

HERE = os.path.dirname(os.path.abspath(__file__))
LATC, LATA = "\u0063", "\u0061"      # латинские c и a: двойники в слове «қорықса»

CH = [
    dict(id="altynsarin", bg="#f4ecd8", fg="#2b2118", ac="#a4332a", on=True,
         name=dict(ru="АЛТЫНСАРИН", kk="АЛТЫНСАРИН", en="ALTYNSARIN"),
         role=dict(ru="ГИГИЕНА И ТИПОГРАФИКА", kk="ГИГИЕНА ЖӘНЕ ТИПОГРАФИЯ", en="HYGIENE AND TYPOGRAPHY"),
         strike=[("қорық" + LATC + LATA, 96, 92, -3), ("Казакстан", 880, 84, 2), ("та\u04ca", 120, 520, -2), ("\u0259", 1090, 535, 3)],
         good=[("қорықса", 130, 138, -3), ("Қазақстан", 900, 130, 2), ("таң", 190, 512, -2), ("ә", 1130, 526, 3)],
         foot="Ә  Ғ  Қ  Ң  Ө  Ұ  Ү  Һ  І"),
    dict(id="valikhanov", bg="#0f2342", fg="#f2efe6", ac="#e3b341", on=True,
         name=dict(ru="ВАЛИХАНОВ", kk="УӘЛИХАНОВ", en="VALIKHANOV"),
         role=dict(ru="СВЕРКА С ОРИГИНАЛОМ", kk="ТҮПНҰСҚАМЕН САЛЫСТЫРУ", en="COMPARISON WITH THE ORIGINAL"),
         strike=[("15,3 млрд", 930, 100, 2)], good=[("15,8 млрд", 100, 100, -2), ("⇄", 600, 70, 0)],
         foot="Выручка 15,8 млрд  ·  Түсім 15,3 млрд"),
    dict(id="shakarim", bg="#5b2f21", fg="#f6ead7", ac="#f0b27a", on=True,
         name=dict(ru="ШАКАРИМ", kk="ШӘКӘРІМ", en="SHAKARIM"),
         role=dict(ru="ТЕРМИНЫ ПО УЗУСУ", kk="ҚОЛДАНЫС БОЙЫНША ТЕРМИНДЕР", en="TERMS BY USAGE"),
         strike=[("проект", 940, 500, 2)], good=[("жоба", 110, 500, -2), ("атом · мадда", 880, 110, 2)],
         foot="жоба 92 %   ·   проект 8 %"),
    dict(id="baitursynov", bg="#0d4c54", fg="#e9f5f3", ac="#ffd166", on=False,
         name=dict(ru="БАЙТУРСЫНОВ", kk="БАЙТҰРСЫНҰЛЫ", en="BAITURSYNOV"),
         role=dict(ru="НОРМА: ОРФОГРАФИЯ И ПУНКТУАЦИЯ", kk="НОРМА: ЕМЛЕ ЖӘНЕ ТЫНЫС БЕЛГІЛЕРІ", en="NORM: ORTHOGRAPHY AND PUNCTUATION"),
         strike=[("қыргүйек", 900, 480, 2), ("т.б.,", 110, 100, -2)], good=[("қыркүйек", 910, 530, 2), ("¶", 1120, 90, 0)],
         foot=dict(ru="правило 1983 года  ·  словарь 2013", kk="1983 жылғы ереже  ·  2013 жылғы сөздік", en="the 1983 rule  ·  the 2013 dictionary")),
    dict(id="auezov", bg="#e9b44c", fg="#2a1d0b", ac="#8a2b0f", on=False,
         name=dict(ru="АУЭЗОВ", kk="ӘУЕЗОВ", en="AUEZOV"),
         role=dict(ru="СМЫСЛ И ЖИВАЯ РЕЧЬ", kk="МАҒЫНА ЖӘНЕ ТІРІ СӨЙЛЕУ", en="MEANING AND LIVING SPEECH"),
         strike=[("сонымен қатар", 96, 96, -3), ("жүзеге асыру", 930, 110, 3), ("атап өту", 120, 520, 2)], good=[("тірі сөз", 940, 520, -2), ("❝", 600, 40, 0)],
         foot=dict(ru="калька  →  живая речь", kk="калька  →  тірі сөйлеу", en="calque  →  living speech")),
    dict(id="slopotron", bg="#07090d", fg="#e8ffe8", ac="#39ff88", on=False,
         name=dict(ru="СЛОПОТРОН-kk", kk="СЛОПОТРОН-kk", en="SLOPOTRON-kk"),
         role=dict(ru="СЛЕДЫ МАШИННОГО ПИСЬМА", kk="МАШИНАЛЫҚ ЖАЗУ ІЗДЕРІ", en="TRACES OF MACHINE WRITING"),
         strike=[("сонымен қатар", 96, 96, -3), ("атап өту", 940, 120, 3), ("жүзеге асыру", 110, 520, 2)], good=[("⌖", 600, 58, 0)],
         foot=dict(ru="одиночный маркер — на усмотрение; кластер — исправляется", kk="жалғыз белгі — автордың қалауына; шоғыр — түзетіледі", en="a single marker is left to the author; a cluster is fixed")),
]
BADGE = dict(ru=("РАБОТАЕТ", "В ПЛАНАХ"), kk=("ЖҰМЫС ІСТЕЙДІ", "ЖОСПАРДА"), en=("WORKING", "PLANNED"))
BRAND = dict(ru="kk-redkollegiya · казахская редколлегия", kk="kk-redkollegiya · қазақ редколлегиясы", en="kk-redkollegiya · the Kazakh editorial board")


def poster(c, lang, fonts):
    name = c["name"][lang]
    size = min(168, int(1020 / max(len(name), 1) * 1.42))
    rule = "".join(f'<i style="top:{y}px"></i>' for y in range(110, 700, 38)) if c["id"] == "baitursynov" else ""
    cross = ('<svg class="cx" viewBox="0 0 400 400"><circle cx="200" cy="200" r="150"/><circle cx="200" cy="200" r="80"/><path d="M200 20V380M20 200H380"/></svg>'
             if c["id"] == "slopotron" else "")
    words = "".join(f'<b class="x" style="left:{x}px;top:{y}px;transform:rotate({r}deg)">{E(t)}</b>' for t, x, y, r in c["strike"])
    words += "".join(f'<b class="g" style="left:{x}px;top:{y}px;transform:rotate({r}deg)">{E(t)}</b>' for t, x, y, r in c["good"])
    on, plan = BADGE[lang]
    return f"""<!doctype html><meta charset="utf-8"><style>
@font-face{{font-family:S;font-weight:700;src:url('file://{fonts}/PT_Serif-Web-Bold.ttf')}}
@font-face{{font-family:P;font-weight:400;src:url('file://{fonts}/PT_Sans-Web-Regular.ttf')}}
@font-face{{font-family:P;font-weight:700;src:url('file://{fonts}/PT_Sans-Web-Bold.ttf')}}
*{{margin:0;box-sizing:border-box}}body{{width:1280px;height:720px;position:relative;overflow:hidden;background:{c['bg']};color:{c['fg']};font-family:P}}
.fr{{position:absolute;inset:26px;border:1.5px solid {c['fg']}55}}
.name{{position:absolute;left:0;right:0;top:238px;text-align:center;font:700 {size}px/1 S;letter-spacing:.01em;text-shadow:0 2px 0 {c['ac']}22}}
.role{{position:absolute;left:0;right:0;top:{238 + size + 32}px;text-align:center;font:700 25px/1.2 P;letter-spacing:.34em;color:{c['fg']}cc}}
.x,.g{{position:absolute;font:700 40px/1 S;white-space:nowrap}}.x{{color:{c['fg']}73;text-decoration:line-through;text-decoration-color:{c['ac']};text-decoration-thickness:4px;font-weight:400;font-family:P;font-size:42px}}
.g{{color:{c['ac']};font-style:italic;font-size:44px}}
.ft{{position:absolute;left:0;right:0;bottom:100px;text-align:center;font:400 22px/1 P;letter-spacing:.18em;color:{c['fg']}99}}
.br{{position:absolute;left:52px;bottom:44px;font:700 15px/1 P;letter-spacing:.16em;color:{c['fg']}80;text-transform:uppercase}}
.bd{{position:absolute;right:52px;top:48px;font:700 15px/1 P;letter-spacing:.2em;padding:9px 14px;border-radius:999px;background:{c['ac']};color:{c['bg']}}}
.bd.pl{{background:none;border:1.5px dashed {c['ac']};color:{c['ac']}}}
i{{position:absolute;left:52px;right:52px;height:1px;background:{c['fg']}22}}
.cx{{position:absolute;left:440px;top:160px;width:400px;height:400px;opacity:.32}}.cx *{{fill:none;stroke:{c['ac']};stroke-width:3}}
</style><div class="fr"></div>{rule}{cross}{words}
<div class="name">{E(name)}</div><div class="role">{E(c['role'][lang])}</div>
<div class="ft">{E(c['foot'] if isinstance(c['foot'], str) else c['foot'][lang])}</div><div class="br">{E(BRAND[lang])}</div><div class="bd{'' if c['on'] else ' pl'}">{on if c['on'] else plan}</div>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default=os.path.expanduser("~/fonts"))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 720})
        for c in CH:
            for lang in ("ru", "kk", "en"):
                pg.set_content(poster(c, lang, a.fonts))
                pg.evaluate("document.fonts.ready")
                pg.wait_for_timeout(250)
                path = os.path.join(HERE, f"{c['id']}.{lang}.png")
                pg.screenshot(path=path, type="png")
                print("записан", os.path.relpath(path))
        b.close()


if __name__ == "__main__":
    main()
