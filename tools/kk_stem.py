#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""Осторожный разбор словоизменения казахского существительного: слово = основа из словаря + цепочка суффиксов.

Зачем. Hunspell не умеет снимать цепочки суффиксов, поэтому почти любая редкая форма («шығынын», «полигонын»)
попадает в «неизвестные», и подсказчик восстановления букв (S01, ocr_lm) предлагает ей ложные замены. Этот модуль
отвечает на один вопрос: «похоже ли слово на правильную форму известной основы?» — и служит только вето:
он ничего не исправляет и не признаёт слово правильным в орфографическом смысле.

Цепочка: [множественное] [притяжательное] [падеж], с гармонией гласных, выбором согласного по последнему звуку
(«-лар/-дар/-тар», «-ның/-дың/-тың», «-ға/-қа», «-да/-та», «-дан/-тан/-нан», «-мен/-бен/-пен»), формами на «н» после
притяжательного 3-го лица и чередованием «п→б, к→г, қ→ғ» на стыке с гласным. Словообразование, глаголы и
причастные формы не разбираются: чего модуль не знает, того он не вето.

Словарь основ — data/kk_stems.txt (21 791 основа; происхождение и лицензия — в заголовке файла).
Правило «основа от пяти букв» подобрано измерением, см. docs/BENCH.md.
"""
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
LEXICON_PATH = os.path.normpath(os.path.join(_DIR, "..", "data", "kk_stems.txt"))
ATTESTED_PATH = os.path.normpath(os.path.join(_DIR, "..", "data", "kk_attested.txt"))

BACKV = set("аоұыя")
FRONTV = set("әөүіе")
VOWELS = set("аәеёиоөұүыіэюя")
VOICELESS = set("кқпстфхцчшщһ")
VOICED_STOP = set("бвгғджз")
MUTATE = {"б": "п", "г": "к", "ғ": "қ"}


def load_lexicon(path=None):
    path = path or LEXICON_PATH
    try:
        with open(path, encoding="utf-8") as f:
            return {w.strip().lower() for w in f if w.strip() and not w.startswith("#")}
    except OSError:
        return set()


def _classes(w):
    """Ряд гласных по последней опорной гласной; у слов без неё допускаем оба."""
    for ch in reversed(w):
        if ch in BACKV:
            return ("b",)
        if ch in FRONTV:
            return ("f",)
    return ("b", "f")


def _sound(w):
    c = w[-1]
    if c in VOWELS:
        return "V"
    if c in "уй":
        return "J"
    if c == "р":
        return "R"
    if c in "мнң":
        return "S"
    if c in VOICELESS:
        return "U"
    return "L"


def _plural(w, h):
    s = _sound(w)
    ini = "л" if s in "VRJ" else ("т" if s == "U" else "д")
    return ini + ("ар" if h == "b" else "ер")


def _possessives(w, h):
    a = "ы" if h == "b" else "і"
    if _sound(w) == "V":
        return [("м", "1"), ("ң", "2"), ("ң" + a + "з", "2f"), ("сы" if h == "b" else "сі", "3"),
                ("мыз" if h == "b" else "міз", "1pl")]
    return [(a + "м", "1"), (a + "ң", "2"), (a + "ң" + a + "з", "2f"), (a, "3"), (a + ("мыз" if h == "b" else "міз"), "1pl")]


def _cases(w, h, pk):
    f = (lambda b, fr: b if h == "b" else fr)
    if pk == "3":                       # после 3-го лица падежные формы начинаются на «н»
        return [f("ның", "нің"), "н", f("на", "не"), f("нда", "нде"), f("нан", "нен"), "мен"]
    s = _sound(w)
    gen = "ның" if s in "VS" else ("тың" if s == "U" else "дың")
    acc = "ны" if s == "V" else ("ты" if s == "U" else "ды")
    if h == "f":
        gen, acc = gen.replace("ы", "і"), acc.replace("ы", "і")
    dat = f("а", "е") if pk in ("1", "2", "2f") else (f("қа", "ке") if s == "U" else f("ға", "ге"))
    loc = f("та", "те") if s == "U" else f("да", "де")
    abl = f("нан", "нен") if s == "S" else (f("тан", "тен") if s == "U" else f("дан", "ден"))
    last = w[-1]
    ins = "бен" if last in VOICED_STOP else ("пен" if last in VOICELESS else "мен")
    return [gen, acc, dat, loc, abl, ins]


def valid_ending(stem, ending, both=False):
    """Можно ли получить «основа + ending» цепочкой [мн.] [притяж.] [падеж] по правилам гармонии и стыков.

    both=True — для заимствований: ряд гласных у них определяют на слух, поэтому допускаем оба.
    У основ с группой согласных на «т» («турист») удвоенное «т» не пишут: «туристер», «туристен» вместо «туристтер»."""
    if not ending:
        return False
    if len(stem) >= 2 and stem[-1] == "т" and stem[-2] not in VOWELS and ending[0] in VOWELS and _valid(stem, "т" + ending, both):
        return True
    return _valid(stem, ending, both)


def _valid(stem, ending, both):
    for h in (("b", "f") if both else _classes(stem)):
        for pl in ("", _plural(stem, h)):
            if pl and not ending.startswith(pl):
                continue
            w1 = stem + pl
            r1 = ending[len(pl):]
            for pos, pk in [("", None)] + _possessives(w1, h):
                if pos and not r1.startswith(pos):
                    continue
                r2 = r1[len(pos):]
                if not r2:
                    if pl or pos:
                        return True
                    continue
                w2 = w1 + pos
                if r2 in _cases(w2, h, pk):
                    return True
    return False


def strip(word, is_stem, minstem=5, maxending=14):
    """(основа, суффиксы), если слово — правильная форма известной основы длиной не короче minstem; иначе None."""
    w = word.lower()
    if len(w) < minstem + 1:
        return None
    for k in range(1, min(len(w) - minstem, maxending) + 1):
        stem, end = w[:-k], w[-k:]
        cands = [stem]
        if stem[-1] in MUTATE and end[0] in VOWELS:
            cands.append(stem[:-1] + MUTATE[stem[-1]])
        for s in cands:
            if is_stem(s) and valid_ending(s, end):
                return s, end
    return None


def _selftest():
    lex = {"шығын", "мектеп", "кітап", "жұмыс", "қала", "пункт", "полигон", "сөз", "көше", "адам"}
    isst = lex.__contains__
    assert strip("шығынын", isst) == ("шығын", "ын")                 # притяжательное 3-го лица + винительный на «н»
    assert strip("мектептерімізде", isst) == ("мектеп", "терімізде")  # множественное + притяжательное + местный
    assert strip("кітабымен", isst) == ("кітап", "ымен")              # чередование б↔п
    assert strip("жұмысқа", isst) == ("жұмыс", "қа")                  # после глухого — «қа»
    assert strip("пунктін", isst) == ("пункт", "ін")                  # в слове без опорной гласной подходят оба ряда
    assert strip("қалаларда", isst, minstem=4) == ("қала", "ларда")
    assert strip("жұмысқе", isst) is None                             # нарушена гармония
    assert strip("қүттықтады", isst) is None                          # искажённое слово
    assert strip("полигонын", isst) == ("полигон", "ын")
    assert strip("адамның", isst, minstem=4) == ("адам", "ның")
    assert strip("сөздердің", isst, minstem=3) == ("сөз", "дердің")
    assert strip("көшеге", isst, minstem=4) == ("көше", "ге")
    assert strip("туристер", {"турист"}.__contains__) == ("турист", "ер")     # без удвоения «т»
    assert strip("туристен", {"турист"}.__contains__) == ("турист", "ен")
    print("kk_stem selftest: ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        lex = load_lexicon()
        for w in sys.argv[1:]:
            r = strip(w, lex.__contains__)
            print(f"{w}\t{r[0] + ' + ' + r[1] if r else '-'}")
