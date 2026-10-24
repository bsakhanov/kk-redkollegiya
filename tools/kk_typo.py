#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""kk_typo — типограф казахского текста (слой Алтынсарина), казахский образец Мильчина.

Только детерминированные правила, где верный ответ не зависит от смысла фразы: лучше пропустить, чем сломать.
Юникод-гигиена (двойники, невидимые знаки, схва, легаси-кодировки) остаётся у kk_clean, орфография и пунктуация по
смыслу — за слоем Байтурсынова. Код, ссылки, фронтматтер и теги защищены; файлы .ini не трогаются без --ini.

Правила решены по обычаю вашего корпуса (частоты — docs/TYPOGRAPHY.md) и по решению автора от 24.10.2026:

  Y01 кавычки         прямые и английские → «ёлочки», вложенные → „лапки“ (незакрытые пропускаются)
  Y02 тире            дефис, короткое тире и «--» между словами → «—» (по умолчанию --dash em)
  Y03 пробел у тире   пробел перед «—» → неразрывный
  Y04 диапазон        «2020-2025» → «2020–2025» (даты, телефоны, номера не трогаем)
  Y05 единицы         неразрывный пробел между числом и единицей: «5 млн теңге», «2026 жыл», «2026 ж.»
  Y06 сокращения      «т. б.» → «т.б.», «т. с. с.» → «т.с.с.», «б. з. д.» → «б.з.д.»
  Y07 многоточие      «...» → «…»
  Y08 пробелы         двойной, перед знаком, после скобки, пропущенный после запятой
  Y09 «млн.»          «млн.», «млрд.» → «млн», «млрд» (перед строчной буквой)
  Y10 инициалы        «Қ. К. Тоқаев» → «Қ.К. Тоқаев», перед фамилией неразрывный пробел
  Y11 разряды         «1 085» через неразрывный пробел
  Y12 проценты        «78 %» → «78%» (--percent-space — наоборот)
  Y13 номер           «№ 5» → «№5» (--numero-space — наоборот)
  Y14 градусы         «20 °C» → «20°C» (--degree-space — наоборот)
"""
import argparse
import bisect
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _layers  # noqa: E402
from kk_lint import Doc, Span, to_finding  # noqa: E402

NB = "\u00a0"
CYR = "А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі"
LET = rf"[{CYR}A-Za-z]"
KU, KL = "А-ЯӘҒҚҢӨҰҮҺІ", "а-яәғқңөұүһі"
STAGE = "kk_typo"

NAMES = {
    "Y01": "quotes", "Y02": "dash", "Y03": "dash_space", "Y04": "range", "Y05": "unit_space", "Y06": "abbr", "Y07": "ellipsis",
    "Y08": "spaces", "Y09": "mln", "Y10": "initials", "Y11": "thousands", "Y12": "percent", "Y13": "numero", "Y14": "degree",
}

_PROTECT = [
    re.compile(r"(?s)\A---\n.*?\n---[ \t]*(?:\n|\Z)"),                      # фронтматтер
    re.compile(r"(?ms)^(```|~~~).*?^\1[^\n]*$"),                              # огороженный код
    re.compile(r"`[^`\n]+`"),                                                 # встроенный код
    re.compile(r"https?://[^\s<>)\]]+|www\.[^\s<>)\]]+|[\w.+-]+@[\w-]+\.[\w.-]+"),   # адреса
    re.compile(r"\]\([^)\s]*\)"),                                             # цель markdown-ссылки
    re.compile(r"<[^>\n]+>"),                                                 # теги
    re.compile(r"(?<![\w])[@#][\w.-]+"),                                      # упоминания и хештеги
    re.compile(r"(?m)^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(?:\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$"),   # разделитель таблицы, «---»
]


def _doc(text):
    doc = Doc(text, "prose")
    spans = sorted((m.start(), m.end()) for r in _PROTECT for m in r.finditer(text))
    doc.blocked = spans
    doc._bstarts = [a for a, _ in spans]
    return doc


def _add(out, doc, s, e, edit, rule, note):
    t = doc.text
    if t[s:e] != edit and doc.ok(s, e):
        out.append(Span(s, e, edit, f"{rule} {NAMES[rule]}", "typography", "fix", "apply", note))


# ------------------------------------------------------------------ Y01 -----

_OPEN_CTX = set(" \t" + NB + "([{—–-:;,«„")


def d_quotes(doc, out, opts):
    t = doc.text
    pos = 0
    for line in t.split("\n"):
        ls, pos = pos, pos + len(line) + 1
        if '"' not in line and "“" not in line and "”" not in line:
            continue
        nested_style = "„" in line
        toks, bad = [], False
        for i, ch in enumerate(line):
            if ch not in '"“”«»„':
                continue
            a = ls + i
            if not doc.ok(a, a + 1):
                continue
            prev = line[i - 1] if i else " "
            nxt = line[i + 1] if i + 1 < len(line) else " "
            if ch == "«" or ch == "„":
                toks.append((a, ch, "open", False))
            elif ch == "»":
                toks.append((a, ch, "close", False))
            elif ch == "“" and nested_style:
                toks.append((a, ch, "close", False))
            elif ch == "”" and nested_style:
                bad = True
            elif ch == "“":
                toks.append((a, ch, "open", True))
            elif ch == "”":
                toks.append((a, ch, "close", True))
            else:
                if prev.isdigit() and (nxt.isspace() or nxt in ",.;:)"):
                    continue                                             # дюймы: 5"
                open_ctx = i == 0 or prev in _OPEN_CTX
                close_ctx = (not prev.isspace()) and (nxt.isspace() or nxt in ".,;:!?)]}»—–-…")
                if open_ctx and not nxt.isspace():
                    toks.append((a, ch, "open", True))
                elif close_ctx:
                    toks.append((a, ch, "close", True))
                else:
                    bad = True
        if bad or not toks:
            continue
        depth, plan = 0, []
        for a, ch, role, rep in toks:
            if role == "open":
                new = "«" if depth == 0 else "„"
                depth += 1
            else:
                depth -= 1
                new = "»" if depth == 0 else "“"
                if depth < 0:
                    break
            plan.append((a, ch, new, rep))
        if depth != 0:
            continue
        for a, ch, new, rep in plan:
            if rep:
                _add(out, doc, a, a + 1, new, "Y01", "кавычки-«ёлочки»")


# ------------------------------------------------------------- Y02, Y03 -----

_DASH = re.compile(rf"(?<=[{CYR}A-Za-z»)\"”%\d])([ {NB}]+)(---|--|-|–)(?=[ {NB}]+[{CYR}A-Za-z«(\"“„\d])")


def d_dash(doc, out, opts):
    t = doc.text
    if opts.get("dash", "em") == "em":
        for m in _DASH.finditer(t):
            rest = t[m.end():]
            left, right = t[m.start() - 1], rest.lstrip(" " + NB)[:1]
            if m.group(2) == "-" and left.isdigit():
                continue
            if m.group(2) == "–" and left.isdigit() and right.isdigit():
                continue
            _add(out, doc, m.start(), m.end(), NB + "—", "Y02", "тире вместо дефиса или короткого тире")
    for m in re.finditer(rf"(?<=\S)[ ]+(?=—[ {NB}])", t):
        _add(out, doc, m.start(), m.end(), NB, "Y03", "неразрывный пробел перед тире")


# ------------------------------------------------------------------ Y04 -----

_RANGE = re.compile(rf"(?<![\w№.,:/\-–—])(\d{{1,4}})([-—])(\d{{1,4}})(?![\w.,:/\-–—])")


def d_range(doc, out, opts):
    for m in _RANGE.finditer(doc.text):
        a, b = m.group(1), m.group(3)
        if len(a) == 4 and len(b) == 2 and 1 <= int(b) <= 12:             # возможная дата 2025-10
            continue
        _add(out, doc, m.start(2), m.end(2), "–", "Y04", "диапазон: короткое тире")


# ------------------------------------------------------------------ Y05 -----

_UNITS = ("млрд", "млн", "трлн", "мың", "тонна", "баррель", "кг", "км", "см", "мм", "га", "МВт", "кВт", "ГВт", "Вт",
          "теңге", "тг", "доллар", "евро", "сағат", "минут", "секунд", "пайыз", "м", "л")
_UNIT = re.compile(rf"(?<=\d)[ ]+(?=(?:{'|'.join(_UNITS)})(?![{CYR}A-Za-z])|жыл|ж\.)")
_CHAIN = re.compile(rf"\b(?:млрд|млн|трлн|мың)\.?([ ]+)(?=(?:теңге|тг|доллар|евро|тонна|баррель)(?![{CYR}A-Za-z]))")


def d_units(doc, out, opts):
    for m in _UNIT.finditer(doc.text):
        _add(out, doc, m.start(), m.end(), NB, "Y05", "неразрывный пробел между числом и единицей")
    for m in _CHAIN.finditer(doc.text):
        _add(out, doc, m.start(1), m.end(1), NB, "Y05", "неразрывный пробел между счётным словом и единицей")


# ------------------------------------------------------------------ Y06 -----

_ABBR = ("т.б.", "т.с.с.", "б.з.д.", "б.з.")


def d_abbr(doc, out, opts):
    t = doc.text
    for canon in _ABBR:
        letters = canon.rstrip(".").split(".")
        body = (r"\.[ " + NB + r"]*").join(letters) + r"\."
        tail = rf"(?![ {NB}]*[{KL}]\.)" if canon == "б.з." else ""
        for m in re.finditer(rf"(?<![{CYR}])" + body + tail, t):
            _add(out, doc, m.start(), m.end(), canon, "Y06", "сокращение слитно")


# ------------------------------------------------------------------ Y07 -----


def d_ellipsis(doc, out, opts):
    for m in re.finditer(r"(?<!\.)\.\.\.(?!\.)", doc.text):
        _add(out, doc, m.start(), m.end(), "…", "Y07", "многоточие одним знаком")


# ------------------------------------------------------------------ Y08 -----


def d_spaces(doc, out, opts):
    t = doc.text
    nxt = rf"[{CYR}A-Za-z«(\"“„]"
    for m in re.finditer(rf"(?<=\S)[ \t]+([,;!?])(?={nxt})", t):                # пробел перед знаком и нет пробела после
        _add(out, doc, m.start(), m.end(), m.group(1) + " ", "Y08", "пробел перед знаком, нет пробела после")
    for m in re.finditer(rf"(?<=\S)[ \t]+(?=[,;:!?](?!{nxt}))", t):
        _add(out, doc, m.start(), m.end(), "", "Y08", "пробел перед знаком")
    for m in re.finditer(r"(?<=[^\s.])[ \t]+(?=\.(?:[ \t]|\n|$))", t):
        _add(out, doc, m.start(), m.end(), "", "Y08", "пробел перед точкой")
    for m in re.finditer(r"(?<=[(«„])[ \t]+(?=\S)", t):
        _add(out, doc, m.start(), m.end(), "", "Y08", "пробел после открывающей скобки или кавычки")
    for m in re.finditer(r"(?<=\S)[ \t]+(?=[)»])", t):
        _add(out, doc, m.start(), m.end(), "", "Y08", "пробел перед закрывающей скобкой или кавычкой")
    for m in re.finditer(rf"(?<={LET})([,;!?])(?=[{CYR}A-Za-z«(\"“„])", t):
        _add(out, doc, m.start(), m.end(), m.group(1) + " ", "Y08", "пропущен пробел после знака")
    for m in re.finditer(r"(?<=\S)[ ]{2,}(?=\S)", t):
        _add(out, doc, m.start(), m.end(), " ", "Y08", "двойной пробел")


# ------------------------------------------------------------------ Y09 -----


def d_mln(doc, out, opts):
    for m in re.finditer(rf"\b(?:млн|млрд|трлн)(\.)(?= [{KL}])", doc.text):
        _add(out, doc, m.start(1), m.end(1), "", "Y09", "«млн» и «млрд» без точки")


# ------------------------------------------------------------------ Y10 -----


def d_initials(doc, out, opts):
    t = doc.text
    for m in re.finditer(rf"(?<![{KU}{KL}])[{KU}]\.([ {NB}]+)(?=[{KU}]\.)", t):
        _add(out, doc, m.start(1), m.end(1), "", "Y10", "инициалы слитно")
    for m in re.finditer(rf"(?<![{KU}{KL}])(?:[{KU}]\.)+( +)(?=[{KU}][{KL}]{{2,}})", t):
        _add(out, doc, m.start(1), m.end(1), NB, "Y10", "неразрывный пробел между инициалами и фамилией")


# ------------------------------------------------------------------ Y11 -----


def d_thousands(doc, out, opts):
    for m in re.finditer(r"(?<![\d.,\w])\d{1,3}(?:[ ]+\d{3})+(?![\d]|[.,]\d)", doc.text):
        for sp in re.finditer("[ ]+", m.group(0)):
            _add(out, doc, m.start() + sp.start(), m.start() + sp.end(), NB, "Y11", "разряды неразрывным пробелом")


# ------------------------------------------------------- Y12, Y13, Y14 -----


def d_percent(doc, out, opts):
    if opts.get("percent_space"):
        for m in re.finditer(rf"(?<=\d)(?:[ ]|)%", doc.text):
            _add(out, doc, m.start(), m.end(), NB + "%", "Y12", "неразрывный пробел перед «%»")
    else:
        for m in re.finditer(rf"(?<=\d)[ {NB}]+%", doc.text):
            _add(out, doc, m.start(), m.end(), "%", "Y12", "«%» слитно с числом")


def d_numero(doc, out, opts):
    if opts.get("numero_space"):
        for m in re.finditer(rf"№[ {NB}]*(?=\d)", doc.text):
            _add(out, doc, m.start(), m.end(), "№" + NB, "Y13", "неразрывный пробел после «№»")
    else:
        for m in re.finditer(rf"№[ {NB}]+(?=\d)", doc.text):
            _add(out, doc, m.start(), m.end(), "№", "Y13", "«№» слитно с числом")


def d_degree(doc, out, opts):
    t = doc.text
    for m in re.finditer(rf"(?<=\d)[ {NB}]*[º˚](?=[CF])", t):
        _add(out, doc, m.start(), m.end(), NB + "°" if opts.get("degree_space") else "°", "Y14", "знак градуса")
    if opts.get("degree_space"):
        for m in re.finditer(r"(?<=\d)[ ]?(?=°[CF])", t):
            _add(out, doc, m.start(), m.end(), NB, "Y14", "неразрывный пробел перед «°C»")
    else:
        for m in re.finditer(rf"(?<=\d)[ {NB}]+(?=°[CF])", t):
            _add(out, doc, m.start(), m.end(), "", "Y14", "«°C» слитно с числом")


# d_spaces — последним: специальные правила (Y03, Y05, Y10, Y11) раньше общей чистки пробелов, иначе их правка теряется
DETECTORS = [d_quotes, d_dash, d_range, d_units, d_abbr, d_ellipsis, d_mln, d_initials, d_thousands, d_percent, d_numero, d_degree, d_spaces]


# --------------------------------------------------------------- ядро ------


def typo(text, only=None, skip=None, **opts):
    """Находки (словари формата kk_lint) и сами правки (спаны)."""
    doc = _doc(text)
    spans = []
    for d in DETECTORS:
        d(doc, spans, opts)
    only, skip = set(only or []), set(skip or [])
    spans = [s for s in spans if (not only or s.rule.split()[0] in only) and s.rule.split()[0] not in skip]
    spans.sort(key=lambda s: (s.s, s.rule.startswith("Y08"), s.s - s.e))      # при общем начале: частное правило важнее чистки пробелов
    kept, last = [], -1
    for s in spans:                                    # пересекающиеся правки: остаётся первая
        if s.s >= last:
            kept.append(s)
            last = s.e
    findings = []
    for i, sp in enumerate(kept):
        f = to_finding(text, sp, i + 1)
        f["stage"] = STAGE
        findings.append(f)
    return findings, kept


def fix(text, **kw):
    findings, spans = typo(text, **kw)
    out, pos = [], 0
    for s in spans:
        out.append(text[pos:s.s])
        out.append(s.edit)
        pos = s.e
    out.append(text[pos:])
    return "".join(out), collections.Counter(s.rule.split()[0] for s in spans)


def _selftest():
    def f(s, **kw):
        return fix(s, **kw)[0]
    assert f('Ол "Қазақ" деді') == "Ол «Қазақ» деді"
    assert f('Ол "біз "Алма" жедік" деді') == "Ол «біз „Алма“ жедік» деді"
    assert f('Ол "Қазақ деді') == 'Ол "Қазақ деді'                                   # незакрытая — пропускаем
    assert f('экран 5" и 7"') == 'экран 5" и 7"'                                      # дюймы
    assert f("Ол “Қазақ” деді") == "Ол «Қазақ» деді"
    assert f("Астана - астана") == "Астана" + NB + "— астана"
    assert f("Астана – астана") == "Астана" + NB + "— астана"
    assert f("Астана — астана") == "Астана" + NB + "— астана"
    assert f("- пункт\n- пункт") == "- пункт\n- пункт"                                  # маркеры списка
    assert f("5 - 3") == "5 - 3" and f("2020 – 2025") == "2020 – 2025"
    assert f("2020-2025 жылдары") == "2020–2025" + NB + "жылдары"
    assert f("10-12 қазан") == "10–12 қазан"
    assert f("2025-10-12 және 8-701-123-45-67, COVID-19, №12-34") == "2025-10-12 және 8-701-123-45-67, COVID-19, №12-34"
    assert f("5 млн теңге") == f"5{NB}млн{NB}теңге"
    assert f("2026 жыл және 2026 ж.") == f"2026{NB}жыл және 2026{NB}ж."
    assert f("мысалы, т. б. және т. с. с.") == "мысалы, т.б. және т.с.с."
    assert f("күту...") == "күту…" and f("күту....") == "күту...."
    assert f("жақсы  болды ,мысалы ( бар )") == "жақсы болды, мысалы (бар)"
    assert f("ақша,мысалы және 0,75") == "ақша, мысалы және 0,75"
    assert f("5 млн. теңге") == f"5{NB}млн{NB}теңге"
    assert f("Бұл 5 млн. Келесі") == f"Бұл 5{NB}млн. Келесі"
    assert f("Қ. К. Тоқаев және Қ. Тоқаев") == f"Қ.К.{NB}Тоқаев және Қ.{NB}Тоқаев"
    assert f("1 085 тонна") == f"1{NB}085{NB}тонна" and f("2025 100 тонна") == f"2025 100{NB}тонна"
    assert f("16  129 мың және арманы  — Қазақ") == f"16{NB}129{NB}мың және арманы{NB}— Қазақ"
    assert f("78 %") == "78%" and f(f"78{NB}%") == "78%"
    assert f("№ 5") == "№5" and f("№5", numero_space=True) == "№" + NB + "5" and f("№ 5", numero_space=True) == "№" + NB + "5"
    assert f("78%", percent_space=True) == "78" + NB + "%" and f("20°C", degree_space=True) == "20" + NB + "°C"
    assert f("2026 жылдың және 2026 ж.") == f"2026{NB}жылдың және 2026{NB}ж."
    assert f("20 °C және 20 ºC") == "20°C және 20°C"
    assert f("`a - b \"x\"` және https://example.com/a-b/2020-2025") == "`a - b \"x\"` және https://example.com/a-b/2020-2025"
    assert f("---\ntitle: \"a - b\"\n---\nМәтін - мәтін") == "---\ntitle: \"a - b\"\n---\nМәтін" + NB + "— мәтін"
    assert f("| a | b |\n|---|---|\n| 1 | 2 |") == "| a | b |\n|---|---|\n| 1 | 2 |"
    once = f('Ол "Қазақ" - 5 % 2020-2025 ,т. б.')
    assert f(once) == once, (once, f(once))                                            # идемпотентность
    print("kk_typo selftest: ok")


def main(argv=None):
    import _version
    ap = argparse.ArgumentParser(description="Типограф казахского текста (слой Алтынсарина)")
    ap.add_argument("--version", action="version", version="%(prog)s " + _version.get())
    ap.add_argument("file", nargs="?")
    ap.add_argument("--json", help="куда записать находки (формат kk_lint, для apply.py)")
    ap.add_argument("--check", action="store_true", help="только проверка: код возврата 1, если есть что править")
    ap.add_argument("--fix", action="store_true", help="напечатать исправленный текст (или записать: -o ФАЙЛ, --in-place)")
    ap.add_argument("-o", "--out", help="куда записать исправленный текст")
    ap.add_argument("--in-place", action="store_true", help="исправить файл на месте")
    ap.add_argument("--only", help="правила через запятую, например Y01,Y02")
    ap.add_argument("--skip", help="правила, которые не применять")
    ap.add_argument("--dash", choices=["em", "keep"], default="em", help="em — везде «—» (по умолчанию); keep — не менять дефис и «–»")
    ap.add_argument("--percent-space", action="store_true", help="«78 %%» с неразрывным пробелом вместо «78%%»")
    ap.add_argument("--numero-space", action="store_true", help="«№ 5» с неразрывным пробелом вместо «№5»")
    ap.add_argument("--degree-space", action="store_true", help="«20 °C» с неразрывным пробелом вместо «20°C»")
    ap.add_argument("--ini", action="store_true", help="разбирать и файлы .ini (по умолчанию пропускаются: подстановки)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    if not a.file:
        ap.error("нужен файл")
    if a.file.endswith(".ini") and not a.ini:
        print(f"{a.file}: файл .ini пропущен (подстановки %s, %1$s, теги); --ini, чтобы проверить значения")
        return 0
    try:
        text = open(a.file, encoding="utf-8").read()
    except OSError as e:
        print(f"[kk_typo] {e}", file=sys.stderr)
        return 1
    kw = dict(only=a.only.split(",") if a.only else None, skip=a.skip.split(",") if a.skip else None, dash=a.dash,
              percent_space=a.percent_space, numero_space=a.numero_space, degree_space=a.degree_space)
    findings, _ = typo(text, **kw)
    if a.fix:
        new, cnt = fix(text, **kw)
        if a.in_place:
            open(a.file, "w", encoding="utf-8").write(new)
        elif a.out:
            open(a.out, "w", encoding="utf-8").write(new)
        else:
            sys.stdout.write(new)
        print(f"{a.file}: правок {sum(cnt.values())} " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())), file=sys.stderr)
    else:
        by = collections.Counter(f["rule"] for f in findings)
        print(f"{a.file}: находок {len(findings)}")
        if findings:
            print("  по слоям: " + _layers.summary(findings))
        for rule, n in sorted(by.items()):
            print(f"  {rule:20} {n}")
    if a.json:
        json.dump({"findings": findings}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 1 if (a.check and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
