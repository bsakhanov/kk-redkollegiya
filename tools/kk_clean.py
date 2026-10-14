#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""kk_clean.py — гигиена казахского текста (проход А-kk, часть 1: восстановление).

Что чинит (в этом порядке; каждый шаг пишет в журнал счётчик и примеры):
  1. nfc          — Юникод-нормализация NFC (разложенные й, ё и подобные).
  2. legacy       — старая кодировка казахских шрифтов (Windows-1251 с казахскими буквами
                    в ячейках 0xB0–0xBF; латинская «i» вместо «і»). Признак: текст из PDF читается
                    как «ñòåìäiãi» вместо «стемдігі». Определяется автоматически.
  3. schwa        — латинская «Ə/ə» вместо «Ә/ә», буквы «ӓ ӧ ӱ» вместо «ә ө ү».
  4. substitute   — буквы-заместители: управляющие символы на месте казахских букв («жо\\x08» → «жоқ»)
                    и латинские не-двойники в кириллических словах («Wрлық» → «Ұрлық»). Что стоит за кодом,
                    выводится по словарю: для каждого слова берётся комбинация, при которой оно есть
                    в словаре. Нужен словарь Hunspell.
  5. homoglyph    — латинские буквы-двойники внутри кириллических слов («қорықca», «coң», «Бipіншi»)
                    и наоборот («ІSBN»).
  6. dehyphenate  — по желанию: перенос «слово-\\nпродолжение» склеивается, если результат есть
                    в словаре (флаг --dehyphenate).
                     Знаки переноса «-», «¬» и мягкий перенос понимаются одинаково.
  7. ocr          — по желанию: путаница «ү» и «ұ» после распознавания книг («жүмыс» → «жұмыс»,
                     «қүттықтады» → «құттықтады»). Слово правится, только если его нет в словаре и либо с «ұ»
                     оно в словаре (запись ocr), либо «ү» стоит рядом с гласными заднего ряда — так в казахском
                     слове не бывает (запись ocr_harmony; флаг --ocr).
                     С моделью букв (--lm, см. kk_restore.py) шаг чинит и потерянные казахские буквы («кызметімен» →
                     «қызметімен», «жатуга» → «жатуға»): слово правится, только если его нет в словаре, модель
                     предлагает вариант с запасом (по умолчанию 2,0) и этот вариант есть в словаре, причём второго
                     словарного варианта рядом нет (запись ocr_lm). Неоднозначное («кол» — «қол» или «көл») не трогается.

Чего не делает: не правит орфографию, не восстанавливает «к → қ» (это kk_lint, где вердикт за человеком),
не трогает типографику.

Использование:
    kk_clean.py книга.txt -o чистое/ --dict /путь/к/kk_KZ --journal журнал.json
    kk_clean.py --selftest
Выход: 0 — ок; 1 — ошибка входа.

Только стандартная библиотека; словарь — через spylls (pip install spylls) либо без него
(тогда шаг substitute пропускается, остальные работают).
"""

import argparse
import collections
import functools
import itertools
import json
import os
import re
import sys
import unicodedata

KZ_LOW = "әғқңөұүһі"
KZ_UP = "ӘҒҚҢӨҰҮҺІ"
CYR = "А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі"
LAT = "A-Za-z"
CTRL = "\x00-\x08\x0b\x0e-\x1f"          # без \t \n \f \r

# ---------------------------------------------------------------- словарь ---


class Dictionary:
    """Тонкая обёртка над Hunspell (spylls) и проектным белым списком."""

    def __init__(self, prefix=None, whitelist=()):
        self._d = None
        self.white = {w.strip().lower() for w in whitelist if w.strip()}
        if prefix:
            try:
                from spylls.hunspell import Dictionary as HS
                self._d = HS.from_files(prefix)
            except Exception as e:                       # noqa: BLE001
                print(f"[kk] словарь не загружен: {e}", file=sys.stderr)
        self._cache = {}

    @property
    def ok(self):
        return self._d is not None or bool(self.white)

    def known(self, w):
        r = self._cache.get(w)
        if r is not None:
            return r
        lw = w.lower()
        r = lw in self.white
        if not r and self._d is not None:
            try:
                r = bool(self._d.lookup(w) or self._d.lookup(lw) or self._d.lookup(w.capitalize()))
            except Exception:                            # noqa: BLE001
                r = False
        self._cache[w] = r
        return r


class Journal:
    def __init__(self):
        self.steps = collections.OrderedDict()

    def add(self, step, before=None, after=None, n=1):
        s = self.steps.setdefault(step, {"count": 0, "examples": []})
        s["count"] += n
        if before is not None and len(s["examples"]) < 6:
            s["examples"].append([before, after])

    def note(self, step, text):
        self.steps.setdefault(step, {"count": 0, "examples": []})["note"] = text

    def to_dict(self):
        return self.steps


# ------------------------------------------------------------ 2. legacy -----

_LEG_LOW = dict(zip(range(0xB8, 0xC0), "әғқңөұүһ"))
_LEG_UP = dict(zip(range(0xB0, 0xB8), "ӘҒҚҢӨҰҮҺ"))
LEGACY = {**_LEG_LOW, **_LEG_UP}


def legacy_score(text):
    """Доля латинских букв из блока U+00C0–U+00FF среди всех букв, если кириллицы мало."""
    letters = sum(1 for c in text if c.isalpha())
    if not letters:
        return 0.0
    cyr = len(re.findall(rf"[{CYR}]", text))
    if cyr / letters >= 0.15:
        return 0.0
    l1 = sum(1 for c in text if 0xC0 <= ord(c) <= 0xFF)
    return l1 / letters


def decode_legacy(text, J=None):
    out = []
    n = 0
    for ch in text:
        o = ord(ch)
        if ch == "i":
            out.append("і"); n += 1
        elif ch == "I":
            out.append("І"); n += 1
        elif o in LEGACY:
            out.append(LEGACY[o]); n += 1
        elif 0xC0 <= o <= 0xFF:
            out.append(bytes([o]).decode("cp1251")); n += 1
        else:
            out.append(ch)
    s = "".join(out)
    s = s.replace("\u00ad\n", "").replace("\u00ad", "")
    if J is not None:
        J.add("legacy", n=n)
    return s


# ----------------------------------------------------- 3. схва и диерезис ----

_SCHWA = str.maketrans({"\u018f": "Ә", "\u0259": "ә"})
_DIAER = str.maketrans({"ӓ": "ә", "Ӓ": "Ә", "ӧ": "ө", "Ӧ": "Ө", "ӱ": "ү", "Ӱ": "Ү"})


def fix_schwa(text, J=None):
    n = sum(text.count(c) for c in "\u018f\u0259ӓӒӧӦӱӰ")
    if n:
        text = text.translate(_SCHWA).translate(_DIAER)
        if J is not None:
            J.add("schwa", "ə", "ә", n=n)
    return text


# -------------------------------- 4. «буквы-заместители»: управляющие и латинские

# Некоторые PDF прячут казахские буквы за управляющими символами (\x08 вместо «қ»), а прописные —
# за латинскими («F» вместо «Ғ», «W» вместо «Ұ»). Что именно стоит за кодом, видно по словарю.

_SUBCH = re.compile(rf"[{CTRL}]")
_TOKSUB = re.compile(rf"[{CYR}{LAT}{CTRL}]+")
_LAT_TWIN = set("ABCEHIKMOPTXYaceopxyi")


def _subs_in(tok):
    """Позиции букв-заместителей в слове: управляющие символы и латинские не-двойники,
    если рядом есть кириллическая буква, у которой нет латинского двойника."""
    pos = [i for i, c in enumerate(tok) if _SUBCH.match(c)]
    cyr_non = any(re.match(rf"[{CYR}]", c) and c not in "АВСЕНІКМОРТХУасеорхуі" for c in tok)
    if cyr_non:
        pos += [i for i, c in enumerate(tok) if re.match(rf"[{LAT}]", c) and c not in _LAT_TWIN]
    return sorted(pos)


def _twins_to_cyr(w):
    return "".join(_LAT2CYR_MAP.get(c, c) for c in w)


_LAT2CYR_MAP = dict(zip("ABCEHIKMOPTXYaceopxyi", "АВСЕНІКМОРТХУасеорхуі"))


def repair_substitutes(text, d, J):
    toks = []
    for m in _TOKSUB.finditer(text):
        w = m.group(0)
        pos = _subs_in(w)
        if pos:
            toks.append((m, pos))
    if not toks:
        return text
    if d is None or not d.ok:
        J.note("substitute", "в тексте есть буквы-заместители, но словаря нет: оставлены как есть")
        J.add("substitute", n=0)
        return text

    def put(w, pos, letters, su=False):
        cand = list(w)
        for i, k in zip(pos, letters):
            c = w[i]
            if _SUBCH.match(c):                       # управляющий символ: регистр по соседям и месту в предложении
                up = (i == 0 and (su or w[1:2].isupper())) or (
                    i > 0 and w[i - 1:i].isupper() and w[i + 1:i + 2].isupper())
            else:                                      # латинская буква несёт регистр сама
                up = c.isupper()
            cand[i] = k.upper() if up else k
        return "".join(cand)

    score = collections.defaultdict(collections.Counter)
    for m, pos in toks:
        if len(pos) != 1:
            continue
        w = m.group(0)
        c = w[pos[0]]
        for k in KZ_LOW:
            if d.known(_twins_to_cyr(put(w, pos, [k]))):
                score[c.lower() if c.isupper() else c][k] += 1
    prior = {}
    for c, cnt in score.items():
        order = [k for k, _ in cnt.most_common()]
        prior[c] = order + [k for k in KZ_LOW if k not in order]
    J.steps.setdefault("substitute", {"count": 0, "examples": []})["codes"] = {
        (f"0x{ord(c):02X}" if _SUBCH.match(c) else c): v[:3] for c, v in sorted(prior.items())}

    def letters_for(c):
        key = c.lower() if c.isupper() else c
        return prior.get(key, list(KZ_LOW))

    # проход 1: слова, где комбинация подтверждена словарём; заодно копим контекст «код + соседи → буква»
    ctx = collections.defaultdict(collections.Counter)
    resolved, pending = {}, []
    for idx, (m, pos) in enumerate(toks):
        w = m.group(0)
        prev = text[:m.start()].rstrip(" \t")
        su = (not prev) or prev[-1] in ".!?\n"
        if len(pos) > 3:
            resolved[idx] = w
            continue
        opts = [letters_for(w[i])[:6] for i in pos]
        chosen = None
        for combo in itertools.product(*opts):
            if d.known(_twins_to_cyr(put(w, pos, combo, su))):
                chosen = combo
                break
        if chosen is not None:
            res = _twins_to_cyr(put(w, pos, chosen, su))
            J.add("substitute", w.encode("unicode_escape").decode(), res)
            resolved[idx] = res
            for i, k in zip(pos, chosen):
                c = w[i].lower()
                l = w[i - 1:i].lower() if i else "^"
                r = w[i + 1:i + 2].lower() if i + 1 < len(w) else "$"
                ctx[(c, l, r)][k] += 1
                ctx[(c, "*", r)][k] += 1
                ctx[(c, l, "*")][k] += 1
        else:
            pending.append((idx, w, pos, su))

    # проход 2: остальные — по контексту, а без него по общему приоритету; латинские без подтверждения не трогаем
    for idx, w, pos, su in pending:
        if not any(_SUBCH.match(w[i]) for i in pos):
            resolved[idx] = w
            continue
        chosen = []
        for i in pos:
            c = w[i].lower()
            l = w[i - 1:i].lower() if i else "^"
            r = w[i + 1:i + 2].lower() if i + 1 < len(w) else "$"
            pick = None
            for key in ((c, l, r), (c, "*", r), (c, l, "*")):
                if ctx.get(key):
                    pick = ctx[key].most_common(1)[0][0]
                    break
            chosen.append(pick or letters_for(w[i])[0])
        res = _twins_to_cyr(put(w, pos, chosen, su))
        J.add("substitute_guess", w.encode("unicode_escape").decode(), res)
        resolved[idx] = res

    out, last = [], 0
    for idx, (m, pos) in enumerate(toks):
        out.append(text[last:m.start()])
        out.append(resolved[idx])
        last = m.end()
    out.append(text[last:])
    return "".join(out)


# ------------------------------------------------------------ 5. омоглифы ---

_LAT2CYR = dict(zip("ABCEHIKMOPTXYaceopxyi", "АВСЕНІКМОРТХУасеорхуі"))
_CYR2LAT = {v: k for k, v in _LAT2CYR.items()}
_TWIN_CYR = set(_CYR2LAT)
_TOKEN = re.compile(rf"[{CYR}{LAT}]+")
_RE_CYR = re.compile(rf"[{CYR}]")
_RE_LAT = re.compile(rf"[{LAT}]")


def _to_cyr(tok, d):
    base = "".join(_LAT2CYR.get(c, c) for c in tok)
    if d is not None and d.ok and re.search("[yY]", tok):
        pos = [i for i, c in enumerate(tok) if c in "yY"]
        for combo in itertools.product(*[("уү" if tok[i] == "y" else "УҮ") for i in pos]):
            cand = list(base)
            for i, k in zip(pos, combo):
                cand[i] = k
            cand = "".join(cand)
            if d.known(cand):
                return cand
    return base


def _to_lat(tok):
    return "".join(_CYR2LAT.get(c, c) for c in tok)


_ROMAN = r"(?=[IVXLCDM])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
_LOOK2LAT = dict(zip("ІХСМТ", "IXCMT"))             # кириллические двойники римских цифр и «IT»


def is_roman_or_it(tok):
    """Римская цифра («IV», «ХІV», «XVIIIғ» — с кириллическим окончанием) или «IT»: это не слово с двойниками."""
    norm = "".join(_LOOK2LAT.get(c, c) for c in tok.upper())
    if norm == "IT":
        return True
    if len(norm) >= 2 and re.fullmatch(_ROMAN, norm) and all(ord(c) < 128 or c in _LOOK2LAT for c in tok.upper()):
        return True
    m = re.match(_ROMAN, tok)
    return bool(m and len(m.group(0)) >= 2 and re.fullmatch(rf"[{CYR}]{{1,6}}", tok[len(m.group(0)):] or "-"))


def fix_homoglyphs(text, d, J):
    def repl(m):
        tok = m.group(0)
        if is_roman_or_it(tok):
            return tok
        cy = _RE_CYR.findall(tok)
        la = _RE_LAT.findall(tok)
        if not cy or not la:
            return tok
        cy_non = any(c not in _TWIN_CYR for c in cy)
        la_non = any(c not in _LAT2CYR for c in la)
        if cy_non and la_non:
            J.add("homoglyph_ambiguous", tok, tok)
            return tok
        if cy_non or (not la_non and len(cy) >= len(la)):
            res = _to_cyr(tok, d)
        else:
            res = _to_lat(tok)
        if res != tok:
            J.add("homoglyph", tok, res)
        return res
    return _TOKEN.sub(repl, text)


# ----------------------------------------------------------- 6. переносы ----

_HYPH = re.compile(rf"([{CYR}]+)[-¬\u00ad][ \t]*\n[ \t]*([а-яәғқңөұүһі]+)")


def dehyphenate(text, d, J):
    def repl(m):
        a, b = m.group(1), m.group(2)
        joined = a + b
        if d is not None and d.ok and not d.known(joined) and d.known(a + "-" + b):
            res = a + "-" + b
        else:
            res = joined
        J.add("dehyphenate", m.group(0).replace("\n", "↵"), res)
        return res
    return _HYPH.sub(repl, text)


# ------------------------------------------------------------- 7. ocr ----

_BACK = set("аыоұ")                                    # гласные заднего ряда
_OCRTOK = re.compile(rf"[{CYR}]+")


def fix_ocr(text, d, J):
    def repl(m):
        w = m.group(0)
        lw = w.lower()
        if "ү" not in lw or (d is not None and d.ok and d.known(w)):
            return w
        if d is not None and d.ok and d.known(lw.replace("ү", "ұ")):
            step = "ocr"
        elif any(c in _BACK for c in lw):
            step = "ocr_harmony"
        else:
            return w
        res = w.replace("ү", "ұ").replace("Ү", "Ұ")
        J.add(step, w, res)
        return res
    return _OCRTOK.sub(repl, text)


def fix_ocr_lm(text, d, lm, J, margin=2.0):
    """Потерянные казахские буквы после распознавания: исправление по модели букв, подтверждённое словарём."""
    def repl(m):
        w = m.group(0)
        low = w.lower()
        if len(low) < 3 or d is None or not d.ok or d.known(w) or d.known(low):
            return w
        fin = lm.best(low)
        base = lm.score(low)
        cands = [(v, sc) for v, sc in fin[:10] if v != low and d.known(v)]
        if not cands or cands[0][1] - base < margin:
            return w
        if len(cands) > 1 and cands[0][1] - cands[1][1] < 3.0:       # два словарных варианта: решать человеку
            return w
        res = "".join(n.upper() if o.isupper() else n for o, n in zip(w, cands[0][0]))
        J.add("ocr_lm", w, res)
        return res
    return _OCRTOK.sub(repl, text)


# ------------------------------------------------------------------ ядро ----


def clean(text, d=None, legacy=True, dehyph=False, ocr=False, lm=None):
    J = Journal()
    t0 = text
    text = unicodedata.normalize("NFC", text)
    changed = (len(t0) - len(text)) if len(t0) != len(text) else sum(1 for a, b in zip(t0, text) if a != b)
    if changed:
        J.add("nfc", n=changed)
    if legacy:
        sc = legacy_score(text)
        if sc > 0.25:
            J.note("legacy", f"доля латинских букв U+00C0–U+00FF: {sc:.2f}; применён декодер")
            text = decode_legacy(text, J)
    text = fix_schwa(text, J)
    text = repair_substitutes(text, d, J)
    text = fix_homoglyphs(text, d, J)
    if dehyph:
        text = dehyphenate(text, d, J)
    if ocr:
        text = fix_ocr(text, d, J)
        if lm is not None:
            text = fix_ocr_lm(text, d, lm, J)
    return text, J


def _selftest():
    class FakeD:
        ok = True
        words = {"қол", "жоқ", "түзей", "қаласы", "болған", "құрылыс", "уақыт", "соң", "ұрлықпен", "ғарифолла", "жұмыс", "басқарма"}

        def known(self, w):
            return w.lower() in self.words

    d = FakeD()
    # schwa
    t, J = clean("əуелде Əрберден жəне", d)
    assert t == "әуелде Әрберден және", t
    # homoglyph
    t, J = clean("қорықca coң Heгe таyap", d)
    assert t == "қорықса соң Неге тауар", t
    t, J = clean("ISBN XIX", d)                       # чисто латинские токены не трогаем
    assert t == "ISBN XIX", t
    t, J = clean("ІSBN", d)                           # кириллическая І в латинском слове
    assert t == "ISBN", t
    # legacy: «стемдігі» → mojibake
    moj = "ñòåìäiãi áîë¹àí æîº ïà"
    t, J = clean(moj, d)
    assert t == "стемдігі болған жоқ па", t
    # управляющие символы по словарю
    t, J = clean("жо\x08 бол\x12ан т\x0fзей \x08аласы " * 4, d)
    assert t.split()[:4] == ["жоқ", "болған", "түзей", "қаласы"], t
    t, J = clean("Алматы \x08аласы. \x08аласы", d)
    assert t == "Алматы қаласы. Қаласы", t
    t, J = clean("XVIIIғ. IVтарау IT ХІV Iшкі", d)       # римские цифры и «IT» не трогаем, а «Iшкі» — двойник
    assert t == "XVIIIғ. IVтарау IT ХІV Ішкі", t
    t, J = clean("Wрлықпен Fарифолла", d)             # латинские заместители прописных
    assert t.split()[0] == "Ұрлықпен", t
    # ocr: ү → ұ по словарю и по гармонии гласных; слова с «ү» в гармоничном окружении не трогаем
    t, J = clean("Жүмыс қүттықтады үстаз мазмүнына күн түзей", d, ocr=True)
    assert t == "Жұмыс құттықтады ұстаз мазмұнына күн түзей", t
    assert J.steps["ocr"]["count"] == 1 and J.steps["ocr_harmony"]["count"] == 3, J.steps
    t, J = clean("бас-\nқарма бас¬\nқарма", d, dehyph=True)       # перенос «-» и «¬»
    assert t == "басқарма басқарма", t

    class FakeLM:                                       # модель букв: варианты и оценки заданы вручную
        table = {"автоматтык": [("автоматтық", -10.0), ("автоматтык", -15.0)],
                 "кол": [("көл", -6.0), ("қол", -6.5), ("кол", -9.0)],
                 "қызметімен": [("қызметімен", -8.0)]}

        def best(self, w):
            return self.table.get(w, [(w, -9.0)])

        def score(self, w):
            return dict(self.table.get(w, [(w, -9.0)])).get(w, -9.0)

    d.words |= {"автоматтық", "көл", "қол"}
    t, J = clean("автоматтык кол Автоматтык", d, ocr=True, lm=FakeLM())
    assert t == "автоматтық кол Автоматтық", t                    # «кол» неоднозначно — не тронуто
    assert J.steps["ocr_lm"]["count"] == 2, J.steps
    print("kk_clean selftest: ok")


def main(argv=None):
    import _version
    ap = argparse.ArgumentParser(description="Гигиена казахского текста (А-kk, часть 1)")
    ap.add_argument("--version", action="version", version="%(prog)s " + _version.get())
    ap.add_argument("files", nargs="*")
    ap.add_argument("-o", "--out", help="файл или каталог для результата")
    ap.add_argument("--dict", help="префикс словаря Hunspell (…/kk_KZ без расширения)")
    ap.add_argument("--whitelist", help="файл со словами проекта, по слову в строке")
    ap.add_argument("--journal", help="куда записать журнал (JSON)")
    ap.add_argument("--dehyphenate", action="store_true")
    ap.add_argument("--ocr", action="store_true", help="починить путаницу «ү» и «ұ» после распознавания книг")
    ap.add_argument("--lm", help="модель букв (kk_restore.py train): с --ocr чинит и потерянные казахские буквы")
    ap.add_argument("--no-legacy", action="store_true")
    ap.add_argument("--check", action="store_true", help="только журнал, без записи")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    if not a.files:
        ap.error("нужен хотя бы один файл")
    white = []
    if a.whitelist and os.path.exists(a.whitelist):
        white = open(a.whitelist, encoding="utf-8").read().split()
    d = Dictionary(a.dict, white)
    lm = None
    if a.lm:
        from kk_restore import CharLM
        lm = CharLM.load(a.lm)
    full = {}
    for f in a.files:
        try:
            raw = open(f, encoding="utf-8", errors="replace").read()
        except OSError as e:
            print(f"[kk_clean] {f}: {e}", file=sys.stderr)
            return 1
        text, J = clean(raw, d, legacy=not a.no_legacy, dehyph=a.dehyphenate, ocr=a.ocr, lm=lm)
        full[os.path.basename(f)] = J.to_dict()
        summary = ", ".join(f"{k}:{v['count']}" for k, v in J.steps.items() if v["count"]) or "правок нет"
        print(f"{os.path.basename(f)}: {summary}")
        if not a.check and a.out:
            target = a.out
            if len(a.files) > 1 or os.path.isdir(a.out) or a.out.endswith("/"):
                os.makedirs(a.out, exist_ok=True)
                target = os.path.join(a.out, os.path.basename(f))
            open(target, "w", encoding="utf-8").write(text)
    if a.journal:
        json.dump(full, open(a.journal, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
