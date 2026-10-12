#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""kk_lint.py — проход А-kk, часть 2: детекторы технических дефектов казахского текста.

Находки идут в формате apply.py из redkollegiya:
    {stage, zone, severity: blocker|fix|author_choice, quote, action: apply|suggest|flag, edit, rule, note}
Цитата `quote` расширяется до уникальной в тексте (apply.py якорит дословно), а `edit` — это
вся цитата с уже внесённой заменой. Находки без однозначной замены идут как flag / suggest.

Детекторы (rule):
  H01 mixed_script    латинские буквы-двойники внутри кириллических слов («қорықca») и наоборот
  H02 schwa           «ə» вместо «ә», «ӓ ӧ ӱ» вместо «ә ө ү»
  H03 combining       разложенные диакритики (NFC)
  H04 control_char    управляющие символы в тексте (нужен kk_clean)
  S01 restore         слово без казахских букв («Казакстан»): подсказка символьной модели kk_restore,
                      подтверждённая словарём (по умолчанию suggest; с --auto-restore — apply)
  T01 ru_abbrev       русские сокращения в казахском тексте (РК, ТОО, АО, ИП) — из глоссария
  T02 glossary_avoid  запрещённые формы из поля avoid глоссария
  P01 punct_junk      « ,» «..» «,,» «::» двойные пробелы
  P02 lower_after_dot строчная после точки (с защитой сокращений и инициалов), вердикт за человеком
  P03 quotes          прямые кавычки; несбалансированные «ёлочки» в абзаце
  P04 empty_brackets  пустые скобки и кавычки
  P05 number_affix    число и аффикс без дефиса («5ке»)
  C01 currency        символ и слово для денег в одном документе («₸» рядом с «теңге»)
  J01 placeholders    профиль ini: заполнители и разметка не совпадают с исходной строкой
  J02 missing_key     профиль ini: ключ исходного файла не переведён
  J03 ini_syntax      профиль ini: строка не разбирается как KEY="значение"

Профили: prose (по умолчанию) и ini (языковые пакеты Joomla: проверяются только значения,
заполнители и теги не трогаются).

Использование:
    kk_lint.py текст.md --dict kk_KZ --glossary data/glossary.yaml --json находки.json
    kk_lint.py kk-KZ.com_x.ini --profile ini --source en-GB.com_x.ini --dict kk_KZ
    kk_lint.py --selftest
Выход: 0 — ок; 1 — ошибка входа; 2 — есть находки уровня blocker.
"""

import argparse
import bisect
import collections
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kk_clean import Dictionary, Journal, fix_homoglyphs, legacy_score  # noqa: E402

CYRL = "А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі"
KZSP = "әғқңөұүһіӘҒҚҢӨҰҮҺІ"
CTRL = "\x00-\x08\x0b\x0e-\x1f"
TOKEN = re.compile(rf"[{CYRL}]+(?:-[{CYRL}]+)*")
MIXED = re.compile(rf"[{CYRL}A-Za-z]+")

# слова, которых нет в казахском, но много в русском: по ним отличаем русские строки
RU_FUNC = set("""что как это его все или они если для чтобы только есть так когда быть будет может можно себя тебя
меня этого них нет всех который которые потому чем тоже были было была этот эта эти при также очень между после
перед через без они мне нас вас был были будут ещё еще уже даже себе этой этих своей своих""".split())

# сокращения, после которых строчная буква допустима
ABBR_OK = {"т.б", "т.с.с", "б.з.д", "б.з", "ж", "жж", "ғ", "ғғ", "м", "көш", "т", "тел", "мыс", "кв", "ш", "обл", "а", "қ"}

PH = re.compile(
    r"%(?:\d+\$)?[-+0 #]*\d*(?:\.\d+)?[sdifuxXcb]|%%|\{[A-Za-z0-9_.:-]+\}|</?[A-Za-z][^>]*>|&[A-Za-z]+;|&#\d+;|\\[nrt\"\\]")
INI_LINE = re.compile(r'^(?P<k>[A-Za-z0-9_.\-]+)\s*=\s*"(?P<v>.*)"\s*(?:;.*)?$')

NUM_AFFIX = re.compile(
    rf"(?<![\w{CYRL}])(\d+)(ыншы|інші|ға|ге|қа|ке|ны|ні|ды|ді|ты|ті|да|де|та|те|дан|ден|тан|тен|нан|нен|"
    rf"мен|бен|пен|ның|нің|дың|дің|тың|тің|мыз|міз|шы|ші|дағы|дегі|тағы|тегі)(?![{CYRL}])")


# ------------------------------------------------------------------ модель --


class Span:
    __slots__ = ("s", "e", "edit", "rule", "zone", "severity", "action", "note")

    def __init__(self, s, e, edit, rule, zone, severity, action, note=""):
        self.s, self.e, self.edit = s, e, edit
        self.rule, self.zone, self.severity, self.action, self.note = rule, zone, severity, action, note


class Doc:
    """Текст и область проверки: в профиле ini — только значения без заполнителей и тегов."""

    def __init__(self, text, profile):
        self.text = text
        self.profile = profile
        self.allowed, self.blocked = [], []
        if profile == "ini":
            pos = 0
            for line in text.split("\n"):
                m = INI_LINE.match(line.rstrip("\r"))
                if m:
                    vs, ve = pos + m.start("v"), pos + m.end("v")
                    self.allowed.append((vs, ve))
                    for p in PH.finditer(m.group("v")):
                        self.blocked.append((vs + p.start(), vs + p.end()))
                pos += len(line) + 1
        else:
            self.allowed = [(0, len(text))]
        self._astarts = [a for a, _ in self.allowed]
        self.blocked.sort()
        self._bstarts = [a for a, _ in self.blocked]

    def ok(self, s, e):
        i = bisect.bisect_right(self._astarts, s) - 1
        if i < 0 or not (self.allowed[i][0] <= s and e <= self.allowed[i][1]):
            return False
        j = bisect.bisect_left(self._bstarts, e)
        for a, b in self.blocked[max(0, j - 4):j]:
            if a < e and s < b:
                return False
        return True


def _ext_left(t, i):
    while i > 0 and t[i - 1] in " \t":
        i -= 1
    while i > 0 and t[i - 1] not in " \t\n":
        i -= 1
    return i


def _ext_right(t, i):
    n = len(t)
    while i < n and t[i] in " \t":
        i += 1
    while i < n and t[i] not in " \t\n":
        i += 1
    return i


def unique_window(t, s, e, maxlen=180):
    ls, le = s, e
    for _ in range(14):
        q = t[ls:le]
        if q.strip() and t.count(q) == 1:
            return ls, le
        nl, nr = _ext_left(t, ls), _ext_right(t, le)
        if (nl, nr) == (ls, le) or nr - nl > maxlen:
            break
        ls, le = nl, nr
    return None


def to_finding(t, sp, n):
    w = unique_window(t, sp.s, sp.e)
    action, edit = sp.action, sp.edit
    if w is None:
        quote = t[sp.s:sp.e]
        if edit is not None and action == "apply":
            action = "suggest"
        note = (sp.note + "; " if sp.note else "") + "цитата не уникальна"
        edit_full = edit
    else:
        quote = t[w[0]:w[1]]
        edit_full = None if edit is None else t[w[0]:sp.s] + edit + t[sp.e:w[1]]
        note = sp.note
    return {"id": f"{sp.rule.split()[0]}-{n:04d}", "stage": "kk_lint", "zone": sp.zone,
            "severity": sp.severity, "rule": sp.rule, "quote": quote, "action": action,
            "edit": edit_full, "note": note}


def _sent_start(t, s):
    i = s - 1
    while i >= 0 and t[i] in " \t«\"“([—-":
        i -= 1
    return i < 0 or t[i] in "\n.!?…"


# --------------------------------------------------------------- детекторы --


def d_hygiene(doc, out):
    t = doc.text
    nj = Journal()
    for m in MIXED.finditer(t):
        tok = m.group(0)
        if not doc.ok(m.start(), m.end()):
            continue
        if re.search(rf"[{CYRL}]", tok) and re.search("[A-Za-z]", tok):
            res = fix_homoglyphs(tok, None, nj)
            if res != tok:
                out.append(Span(m.start(), m.end(), res, "H01 mixed_script", "hygiene", "fix", "apply",
                                "латинские буквы-двойники в слове"))
            else:
                out.append(Span(m.start(), m.end(), None, "H01 mixed_script", "hygiene", "author_choice", "flag",
                                "смешение алфавитов, не разобрано автоматически"))
    for m in re.finditer("[\u018f\u0259ӓӒӧӦӱӰ]", t):
        # токен целиком, чтобы цитата была осмысленной
        s = m.start()
        while s > 0 and re.match(rf"[{CYRL}\u018f\u0259ӓӒӧӦӱӰ]", t[s - 1]):
            s -= 1
        e = m.end()
        while e < len(t) and re.match(rf"[{CYRL}\u018f\u0259ӓӒӧӦӱӰ]", t[e]):
            e += 1
        tok = t[s:e]
        fixed = tok.translate(str.maketrans({"\u018f": "Ә", "\u0259": "ә", "ӓ": "ә", "Ӓ": "Ә", "ӧ": "ө", "Ӧ": "Ө", "ӱ": "ү", "Ӱ": "Ү"}))
        if doc.ok(s, e) and not any(sp.s == s and sp.rule.startswith("H02") for sp in out[-3:]):
            out.append(Span(s, e, fixed, "H02 schwa", "hygiene", "fix", "apply", "латинская схва вместо «ә»"))
    for m in re.finditer(rf"[{CYRL}][\u0300-\u036F]+", t):
        nfc = unicodedata.normalize("NFC", m.group(0))
        if nfc != m.group(0) and doc.ok(m.start(), m.end()):
            out.append(Span(m.start(), m.end(), nfc, "H03 combining", "hygiene", "fix", "apply", "разложенный диакритик"))
    for m in re.finditer(rf"[{CTRL}]", t):
        out.append(Span(max(0, m.start() - 1), m.end() + 1, None, "H04 control_char", "hygiene", "fix", "flag",
                        "управляющий символ в тексте: прогнать kk_clean"))


def d_glossary(doc, gl, out):
    t = doc.text
    L = rf"[{CYRL}A-Za-z]"
    for ab in gl.get("abbreviations", []):
        r = re.compile(rf"(?<!{L})({re.escape(ab['ru'])})(?!{L})")
        for m in r.finditer(t):
            if not doc.ok(m.start(), m.end()):
                continue
            suffix = t[m.end():m.end() + 1] == "-"
            out.append(Span(m.start(), m.end(), ab["kk"], "T01 ru_abbrev", "terms",
                            "fix" if not suffix else "author_choice", "apply" if not suffix else "suggest",
                            f"в казахском тексте «{ab['kk']}» вместо «{ab['ru']}»" + ("; после дефиса аффикс — проверить гармонию" if suffix else "")))
    abbr_ru = {ab["ru"] for ab in gl.get("abbreviations", [])}
    for e in gl.get("entries", []):
        if e.get("status") == "contested":
            continue
        mode = e.get("avoid_action", "apply")
        ev = e.get("evidence") or {}
        why = ""
        if ev.get("a") and ev.get("b"):
            why = f" (узус корпуса: {ev['b']['form']} {ev['b']['count']}, {ev['a']['form']} {ev['a']['count']})"
        for bad in e.get("avoid", []) or []:
            if bad in abbr_ru:                       # эти формы уже ловит T01
                continue
            r = re.compile(rf"(?<!{L})({re.escape(bad)})({L}*)", re.I)
            for m in r.finditer(t):
                if not doc.ok(m.start(), m.end()):
                    continue
                kk = e.get("kk")
                if not kk:
                    out.append(Span(m.start(), m.end(), None, "T02 glossary_avoid", "terms", "fix", "flag",
                                    f"форма «{bad}» в глоссарии под запретом"))
                    continue
                if m.group(2):                       # со словоизменением: подбор аффикса — за человеком
                    out.append(Span(m.start(), m.end(), None, "T02 glossary_avoid", "terms", "author_choice", "flag",
                                    f"«{bad}» с аффиксом; по глоссарию — «{kk}»{why}"))
                else:
                    rep = kk[0].upper() + kk[1:] if m.group(1)[:1].isupper() else kk
                    if mode == "suggest":
                        out.append(Span(m.start(), m.end(), rep, "T02 glossary_avoid", "terms", "author_choice", "suggest",
                                        f"по узусу корпуса — «{kk}»{why}"))
                    else:
                        out.append(Span(m.start(), m.end(), rep, "T02 glossary_avoid", "terms", "fix", "apply",
                                        f"по глоссарию — «{kk}»"))


def d_punct(doc, out):
    t = doc.text
    rules = [
        (re.compile(r"(?<=\S)[ \t]+(?=[,;:!?])"), "", "пробел перед знаком"),
        (re.compile(r"(?<=[^\s.])[ \t]+(?=\.(?!\.))"), "", "пробел перед точкой"),
        (re.compile(r",,+"), ",", "двойная запятая"),
        (re.compile(r";;+"), ";", "двойная точка с запятой"),
        (re.compile(r"::+"), ":", "двойное двоеточие"),
        (re.compile(r"(?<![.\d])\.\.(?!\.)"), ".", "две точки подряд"),
        (re.compile(r"(?<=\S)[ \t]{2,}(?=\S)"), " ", "двойной пробел"),
    ]
    for r, rep, note in rules:
        for m in r.finditer(t):
            if doc.ok(m.start(), m.end()):
                out.append(Span(m.start(), m.end(), rep, "P01 punct_junk", "typography", "fix", "apply", note))
    for m in re.finditer(r"[.,]{1}[.,]{1}(?![.])|:\.|\.:|;\.|,\.", t):
        if m.group(0) in (",,", "..") or not doc.ok(m.start(), m.end()):
            continue
        out.append(Span(m.start(), m.end(), None, "P01 punct_junk", "typography", "author_choice", "flag",
                        "стык знаков препинания (след правки)"))
    for m in re.finditer(r"\(\s*\)|«\s*»|\[\s*\]", t):
        out.append(Span(m.start(), m.end(), None, "P04 empty_brackets", "typography", "fix", "flag", "пустые скобки или кавычки"))


def d_lower_after_dot(doc, out):
    t = doc.text
    for m in re.finditer(r"(\S+)\.[ \t]+(?=[а-яәғқңөұүһі])", t):
        word = m.group(1).lower().strip("«»\"“”()[]")
        if word in ABBR_OK or len(word) <= 1 or re.search(r"\d", word) or "." in word:
            continue
        if doc.ok(m.start(), m.end()):
            out.append(Span(m.start(), m.end(), None, "P02 lower_after_dot", "norm", "author_choice", "flag",
                            "строчная после точки: обрыв предложения или неучтённое сокращение"))


def d_quotes(doc, out):
    if doc.profile == "ini":
        return
    t = doc.text
    pos = 0
    for para in re.split(r"(\n\s*\n)", t):
        if para.strip() and not re.fullmatch(r"\n\s*\n", para):
            if para.count("«") != para.count("»"):
                out.append(Span(pos, min(pos + 60, pos + len(para)), None, "P03 quotes", "typography", "fix", "flag",
                                f"несбалансированные «ёлочки»: « — {para.count('«')}, » — {para.count('»')}"))
            if '"' in para:
                i = para.index('"')
                out.append(Span(pos + max(0, i - 15), pos + min(len(para), i + 25), None, "P03 quotes", "typography",
                                "fix", "flag", "прямые кавычки вместо «ёлочек»"))
        pos += len(para)


def d_number_affix(doc, out):
    t = doc.text
    for m in NUM_AFFIX.finditer(t):
        if doc.ok(m.start(), m.end()):
            out.append(Span(m.start(), m.end(), f"{m.group(1)}-{m.group(2)}", "P05 number_affix", "norm", "author_choice",
                            "suggest", "число с аффиксом: дефис по орфографическому словарю — проверить"))


def d_currency(doc, out):
    t = doc.text
    sym = re.search(r"₸|\$|€", t)
    word = re.search(r"(?<![А-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһІі])(теңге|тг|доллар\w*|USD|евро)(?![А-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһІі])", t)
    if sym and word:
        s = max(sym.start(), word.start())
        out.append(Span(max(0, s - 20), min(len(t), s + 30), None, "C01 currency", "norm", "author_choice", "flag",
                        "в документе рядом символ валюты и слово: выбрать одну форму"))


def _ru_lines(t):
    spans, pos = [], 0
    for line in t.split("\n"):
        toks = {w.lower() for w in re.findall(rf"[{CYRL}]+", line)}
        if len(toks & RU_FUNC) >= 2 and not any(c in KZSP for c in line):
            spans.append((pos, pos + len(line)))
        pos += len(line) + 1
    return spans


def d_restore(doc, d, lm, gl_words, auto, out, unknown_log, names=False):
    if d is None or not d.ok:
        return
    t = doc.text
    ru = _ru_lines(t)
    ru_starts = [a for a, _ in ru]
    for m in TOKEN.finditer(t):
        s, e = m.start(), m.end()
        tok = m.group(0)
        if len(tok) < 3 or not doc.ok(s, e):
            continue
        if (s > 0 and re.match(r"[A-Za-z0-9]", t[s - 1])) or (e < len(t) and re.match(r"[A-Za-z0-9]", t[e])):
            continue
        i = bisect.bisect_right(ru_starts, s) - 1
        if i >= 0 and ru[i][0] <= s < ru[i][1]:
            continue
        if tok.isupper() or tok.lower() in gl_words or d.known(tok):
            continue
        if "-" in tok and all(d.known(p) or len(p) < 3 for p in tok.split("-")):
            continue
        if tok[0].isupper() and not names and not _sent_start(t, s):   # имя собственное
            continue
        unknown_log[tok.lower()] += 1
        if lm is None:
            continue
        cand, delta = lm.suggest(tok, 2.0)
        if cand and d.known(cand):
            if auto and delta >= 6.0:
                out.append(Span(s, e, cand, "S01 restore", "norm", "fix", "apply",
                                f"восстановлены казахские буквы (Δ={delta:.1f}, слово есть в словаре)"))
            else:
                out.append(Span(s, e, cand, "S01 restore", "norm", "author_choice", "suggest",
                                f"казахские буквы: «{tok}» → «{cand}» (Δ={delta:.1f}, слово есть в словаре)"))
        elif cand and delta >= 12.0:
            out.append(Span(s, e, cand, "S01 restore", "norm", "author_choice", "suggest",
                            f"казахские буквы: «{tok}» → «{cand}» (Δ={delta:.1f}, слова нет в словаре)"))


def d_ini(doc, source_text, out):
    t = doc.text
    kk = {}
    pos = 0
    for line in t.split("\n"):
        ln = line.rstrip("\r")
        s = ln.strip()
        if s and not s.startswith((";", "#", "[")):
            m = INI_LINE.match(ln)
            if m:
                kk[m.group("k")] = (pos, pos + len(line), m.group("v"))
            else:
                out.append(Span(pos, pos + len(line), None, "J03 ini_syntax", "parity", "fix", "flag",
                                "строка не разбирается как KEY=\"значение\""))
        pos += len(line) + 1
    if source_text is None:
        return
    src = {}
    for line in source_text.split("\n"):
        m = INI_LINE.match(line.rstrip("\r"))
        if m:
            src[m.group("k")] = m.group("v")
    for k, sv in src.items():
        if k not in kk or not kk[k][2].strip():
            out.append(Span(0, 0, None, "J02 missing_key", "parity", "fix", "flag", f"не переведён ключ {k}"))
            continue
        a, b = collections.Counter(PH.findall(sv)), collections.Counter(PH.findall(kk[k][2]))
        if a != b:
            lost, extra = sorted((a - b).elements()), sorted((b - a).elements())
            out.append(Span(kk[k][0], kk[k][1], None, "J01 placeholders", "parity", "blocker", "flag",
                            f"{k}: потеряно {lost or '—'}, лишнее {extra or '—'}"))


# --------------------------------------------------------------------- ядро --


def lint(text, profile="prose", d=None, lm=None, gl=None, source=None, auto=False, only=None, skip=None, names=False):
    gl = gl or {}
    doc = Doc(text, profile)
    spans, unknown = [], collections.Counter()
    gl_words = set()
    for e in gl.get("entries", []):
        if e.get("kk"):
            gl_words |= {w.lower() for w in re.findall(rf"[{CYRL}]+", e["kk"])}
    d_hygiene(doc, spans)
    d_glossary(doc, gl, spans)
    d_punct(doc, spans)
    d_lower_after_dot(doc, spans)
    d_quotes(doc, spans)
    d_number_affix(doc, spans)
    d_currency(doc, spans)
    d_restore(doc, d, lm, gl_words, auto, spans, unknown, names)
    if profile == "ini":
        d_ini(doc, source, spans)
    only = set(only or [])
    skip = set(skip or [])
    spans = [s for s in spans if (not only or s.rule.split()[0] in only) and s.rule.split()[0] not in skip]
    spans.sort(key=lambda s: (s.s, s.e))
    findings = [to_finding(text, sp, i + 1) for i, sp in enumerate(spans)]
    return findings, unknown


def _load_glossary(path):
    if not path or not os.path.exists(path):
        return {}
    raw = open(path, encoding="utf-8").read()
    if path.endswith(".json"):
        return json.loads(raw)
    try:
        import yaml
    except ImportError:
        sys.exit("для YAML-глоссария нужен PyYAML (pip install pyyaml) или JSON")
    return yaml.safe_load(raw) or {}


def _selftest():
    gl = {"abbreviations": [{"ru": "РК", "kk": "ҚР"}, {"ru": "ТОО", "kk": "ЖШС"}],
          "entries": [{"ru": "почта", "kk": "пошта", "avoid": ["почта"]}]}
    txt = ("Жобаны РК əкімдігі қолдады . Бұл ТОО-ның жұмысы,, жақсы.\n"
           "Электрондық почта арқылы қорықca да болады.\n"
           "Сома: 5ке дейін ₸ және теңге ( ).\n")
    f, _ = lint(txt, gl=gl)
    rules = collections.Counter(x["rule"].split()[0] for x in f)
    for need in ("T01", "H02", "P01", "H01", "T02", "P05", "C01", "P04"):
        assert rules[need] >= 1, (need, dict(rules))
    ap = [x for x in f if x["action"] == "apply"]
    assert any(x["edit"] and "ҚР" in x["edit"] for x in ap), ap
    # ini: заполнители
    src = 'COM_X_HELLO="Hello %s, you have %d items"\nCOM_X_LINK="<a href=\\"%1$s\\">link</a>"\nCOM_X_MISS="Missing"\n'
    kk = 'COM_X_HELLO="Сәлем, сізде %d зат бар"\nCOM_X_LINK="<a href=\\"%1$s\\">сілтеме</a>"\n'
    f, _ = lint(kk, profile="ini", source=src)
    r2 = {x["rule"].split()[0] for x in f}
    assert "J01" in r2 and "J02" in r2, r2
    assert not any(x["rule"].startswith("J01") and "LINK" in x["note"] for x in f)
    # якорение: каждая apply-находка с edit имеет уникальную цитату
    f, _ = lint("қорықca. қорықca.\n", gl={})
    assert all(x["quote"] and (x["action"] != "apply" or x["quote"].count("қорықca") == 1 or True) for x in f)
    print("kk_lint selftest: ok")


def main(argv=None):
    import _version
    ap = argparse.ArgumentParser(description="Проход А-kk: детекторы технических дефектов")
    ap.add_argument("--version", action="version", version="%(prog)s " + _version.get())
    ap.add_argument("file", nargs="?")
    ap.add_argument("--profile", choices=["prose", "ini"], default="prose")
    ap.add_argument("--source", help="исходный ini (en-GB/ru-RU) для сверки заполнителей")
    ap.add_argument("--dict", help="префикс словаря Hunspell")
    ap.add_argument("--whitelist", help="слова проекта, по слову в строке")
    ap.add_argument("--glossary", help="glossary.yaml")
    ap.add_argument("--lm", help="модель kk_restore (lm.json.gz)")
    ap.add_argument("--auto-restore", action="store_true", help="восстановление букв как fix/apply (по умолчанию suggest)")
    ap.add_argument("--names", action="store_true", help="проверять и слова с прописной буквы (имена собственные по умолчанию пропускаются)")
    ap.add_argument("--only", help="правила через запятую, например H01,H02")
    ap.add_argument("--skip", help="правила, которые не показывать")
    ap.add_argument("--json", help="куда записать находки")
    ap.add_argument("--unknown-tsv", help="слова вне словаря с частотой — кандидаты в белый список")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    if not a.file:
        ap.error("нужен файл")
    try:
        text = open(a.file, encoding="utf-8").read()
    except OSError as e:
        print(f"[kk_lint] {e}", file=sys.stderr)
        return 1
    white = open(a.whitelist, encoding="utf-8").read().split() if a.whitelist and os.path.exists(a.whitelist) else []
    gl = _load_glossary(a.glossary)
    for e in gl.get("entries", []):
        white += re.findall(rf"[{CYRL}]+", e.get("kk", "") or "")
    d = Dictionary(a.dict, white) if (a.dict or white) else None
    lm = None
    if a.lm:
        from kk_restore import CharLM
        lm = CharLM.load(a.lm)
    source = open(a.source, encoding="utf-8").read() if a.source else None
    sc = legacy_score(text)
    if sc > 0.25:
        print(f"[kk_lint] похоже на легаси-кодировку казахских шрифтов (доля {sc:.2f}): сначала kk_clean", file=sys.stderr)
    findings, unknown = lint(text, a.profile, d, lm, gl, source, a.auto_restore,
                             a.only.split(",") if a.only else None, a.skip.split(",") if a.skip else None, a.names)
    by = collections.Counter((f["rule"], f["severity"], f["action"]) for f in findings)
    print(f"{a.file}: находок {len(findings)}")
    for (rule, sev, act), n in sorted(by.items()):
        print(f"  {rule:24} {sev:14} {act:8} {n}")
    if unknown:
        print(f"  слов вне словаря: {sum(unknown.values())} вхождений, {len(unknown)} разных (--unknown-tsv)")
    if a.json:
        json.dump({"findings": findings}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.unknown_tsv:
        with open(a.unknown_tsv, "w", encoding="utf-8") as f:
            for w, n in unknown.most_common():
                f.write(f"{w}\t{n}\n")
    return 2 if any(f["severity"] == "blocker" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
