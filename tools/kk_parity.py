#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""kk_parity.py — проход parity (скриптовая часть): сверка казахской версии с русским оригиналом.

Сверяет по абзацам (блоки, разделённые пустой строкой):
  1. число абзацев в обеих версиях;
  2. числа: «15,3», «543,5», «2026», «1 234,5» приводятся к одному виду (пробелы тысяч убираются,
     запятая становится точкой) и сравниваются как мультимножества. Если в абзаце потеряно и добавлено
     поровну чисел, это изменённое значение (blocker, зона facts): «15,3» стало «15,8»;
     потерянное число без пары — fix/flag, лишнее — author_choice/flag (в казахском числительное
     могло быть записано словом);
  3. латинские имена и сокращения (Joomla, KPI, ISO): потеря в казахской версии — fix/flag.

Что скрипт не делает: не оценивает смысл, не сверяет числа, записанные словами, не выполняет
обратный перевод — это LLM-часть проходa parity.

Находки идут в формате apply.py (stage, zone, severity, quote, action, edit=None, rule, note).

Использование:
    kk_parity.py --ru оригинал.md --kk казахский.md [--json находки.json]
    kk_parity.py --selftest
Выход: 0 — ок; 2 — есть blocker; 1 — ошибка входа.
"""

import _layers
import argparse
import collections
import json
import re
import sys

NUM = re.compile(r"(?<![\w])\d[\d\u00a0\u202f ]*(?:[.,]\d+)?(?![\w])|\d")
LATIN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9.+&-]{1,}")
CYR = "А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі"
# латинские сокращения (IPO, KPI) в казахской версии часто набраны кириллическими двойниками («ІРО»)
_TWIN = dict(zip("АВСЕНІКМОРТХУ", "ABCEHIKMOPTXY"))
_TWIN_ONLY = re.compile(rf"(?<![{CYR}A-Za-z])[АВСЕНІКМОРТХУ]{{2,}}(?![{CYR}A-Za-z])")

_MONTHS = [("январ", "қаңтар"), ("феврал", "ақпан"), ("март", "наурыз"), ("апрел", "сәуір"), ("ма[йя]", "мамыр"),
           ("июн", "маусым"), ("июл", "шілде"), ("август", "тамыз"), ("сентябр", "қыркүйек"), ("октябр", "қазан"),
           ("ноябр", "қараша"), ("декабр", "желтоқсан")]
_MONTH_RE = [(re.compile(rf"(?<![{CYR}])(?:{ru}\w*|{kk}\w*)", re.I), n) for n, (ru, kk) in enumerate(_MONTHS, start=1)]
_SCALE = [(re.compile(r"\s*(?:трлн\.?|триллион\w*)", re.I), 1e12), (re.compile(r"\s*(?:млрд\.?|миллиард\w*)", re.I), 1e9),
          (re.compile(r"\s*(?:млн\.?|миллион\w*)", re.I), 1e6), (re.compile(r"\s*(?:тыс\.?|тысяч\w*|мың\w*)", re.I), 1e3)]
_DATE = re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?(?![\d])")


def norm_num(s):
    s = s.replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
    s = s.replace(",", ".")
    return s.rstrip(".")


def _fmt(x):
    return str(int(x)) if abs(x - round(x)) < 1e-9 else repr(round(x, 6))


_BARE_URL = re.compile(r"\b(?:www\.|(?:bit\.ly|t\.me|goo\.gl|clck\.ru|youtu\.be)/)\S*|\b[\w-]+(?:\.[\w-]+)*\.(?:kz|com|ru|org|net|me)\b\S*", re.I)
_LAT2CYR = dict(zip("ABCEHIKMOPTXYaceopxyi", "АВСЕНІКМОРТХУасеорхуі"))
_MIX = re.compile(rf"[{CYR}A-Za-z]+")


def prep(par):
    """Адреса без схемы убираются (их цифры — шум); латинские двойники внутри кириллических слов («тыc.») чинятся."""
    par = _BARE_URL.sub(" ", par)

    def fix(m):
        w = m.group(0)
        if re.search(rf"[{CYR}]", w) and re.search("[A-Za-z]", w) and any(c not in _LAT2CYR and c.isalpha() and c.isascii() for c in w) is False:
            return "".join(_LAT2CYR.get(c, c) for c in w)
        return w
    return _MIX.sub(fix, par)


def numbers(par):
    par = prep(par)
    res = []
    # даты вида 12.12.2025 → день, месяц, год (иначе «12.12» читается как десятичная дробь)
    def date(m):
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            y = m.group(3)
            if y and len(y) == 2:
                y = "20" + y
            res.extend([str(d), f"m{mo}"] + ([y] if y else []))
            return " "
        return m.group(0)
    par = _DATE.sub(date, par)
    for m in NUM.finditer(par):
        raw = m.group(0).strip()
        parts = re.split(r"[\u00a0\u202f ]+", raw)
        vals = [norm_num(raw)] if not (len(parts) > 1 and not all(len(p) == 3 for p in parts[1:])) else [norm_num(p) for p in parts]
        if len(vals) == 1:
            tail = re.sub(r"^-[а-яa-z]{1,3}(?=[\s.])", "", par[m.end():m.end() + 18])
            for rx, k in _SCALE:
                sm = rx.match(tail)
                if sm:
                    try:
                        vals = [_fmt(float(vals[0]) * k)]
                    except ValueError:
                        pass
                    break
            # число перед названием месяца → день и месяц
            tail2 = par[m.end():m.end() + 16].lstrip(" \u00a0-–го")
            for rx, n in _MONTH_RE:
                if rx.match(tail2):
                    res.append(f"m{n}")
                    break
        res.extend(vals)
    return [x for x in res if x]


def latin(par, twins=False):
    """Латинские имена и сокращения; с twins=True добавляются слова из кириллических двойников («ІРО» → ipo)
    — для казахской стороны, чтобы набранное кириллицей «ІРО» засчитывалось как найденное «IPO»."""
    toks = [m.group(0).lower().rstrip(".") for m in LATIN.finditer(par)]
    if twins:
        toks += ["".join(_TWIN[c] for c in m.group(0)).lower() for m in _TWIN_ONLY.finditer(par)]
    return toks


def paragraphs(t):
    return [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]


def term_findings(a, b, gl, i):
    """PR06: в русском абзаце есть понятие из глоссария, а выбранной казахской формы в казахском нет."""
    out = []
    al, bl = a.lower(), b.lower()
    for e in (gl or {}).get("entries", []):
        if e.get("status") != "usage" or not e.get("parity_ru") or not e.get("kk_re") or e.get("parity_check") is False:
            continue
        if re.search(e["parity_ru"], al) and not re.search(rf"(?<![{CYR}A-Za-z])(?:{e['kk_re']})", bl):
            out.append({"stage": "kk_parity", "zone": "terms", "severity": "author_choice", "rule": "PR06 term_mismatch",
                        "quote": b[:80].replace("\n", " "), "action": "flag", "edit": None, "key": e["key"],
                        "note": f"абзац {i}: в русском «{e['ru']}», в казахском нет «{e['kk']}» (узус корпуса)"})
    return out


def compare(ru_text, kk_text, gl=None):
    ru, kk = paragraphs(ru_text), paragraphs(kk_text)
    out = []
    if len(ru) != len(kk):
        out.append({"stage": "kk_parity", "zone": "parity", "severity": "author_choice", "rule": "PR01 paragraphs",
                    "quote": "", "action": "flag", "edit": None,
                    "note": f"число абзацев не совпадает: русский {len(ru)}, казахский {len(kk)}; числа сверены по документу целиком"})
        ru, kk = ["\n\n".join(ru)], ["\n\n".join(kk)]
    for i, (a, b) in enumerate(zip(ru, kk), start=1):
        na, nb = collections.Counter(numbers(a)), collections.Counter(numbers(b))
        lost, extra = sorted((na - nb).elements()), sorted((nb - na).elements())
        q = b[:80].replace("\n", " ")
        if lost and len(lost) == len(extra):
            out.append({"stage": "kk_parity", "zone": "facts", "severity": "blocker", "rule": "PR02 number_changed",
                        "quote": q, "action": "flag", "edit": None,
                        "note": f"абзац {i}: значения изменены: русский {lost} → казахский {extra}"})
        else:
            if lost:
                out.append({"stage": "kk_parity", "zone": "parity", "severity": "fix", "rule": "PR03 number_lost",
                            "quote": q, "action": "flag", "edit": None,
                            "note": f"абзац {i}: в казахской версии нет чисел {lost} (возможно, записаны словом)"})
            if extra:
                out.append({"stage": "kk_parity", "zone": "parity", "severity": "author_choice", "rule": "PR04 number_extra",
                            "quote": q, "action": "flag", "edit": None,
                            "note": f"абзац {i}: лишние числа в казахской версии: {extra}"})
        out.extend(term_findings(a, b, gl, i))
        la, lb = collections.Counter(latin(a)), collections.Counter(latin(b, True))
        lost_l = sorted((la - lb).elements())
        if lost_l:
            out.append({"stage": "kk_parity", "zone": "parity", "severity": "fix", "rule": "PR05 latin_lost",
                        "quote": q, "action": "flag", "edit": None,
                        "note": f"абзац {i}: в казахской версии нет имён и сокращений {lost_l}"})
    for n, f in enumerate(out, start=1):
        f["id"] = f"PR-{n:04d}"
        f["layer"] = _layers.layer_of(f["zone"])
    return out


def _selftest():
    ru = "Объём вырос на 15,3% до 543,5 млн юаней. Joomla и KPI.\n\nВ 2026 году выпущено 1 234,5 тыс. тонн."
    kk = "Көлем 15,8%-ға өсіп, 543,5 млн юань болды. Joomla.\n\n2026 жылы 1234,5 мың тонна шығарылды."
    f = compare(ru, kk)
    rules = {x["rule"].split()[0] for x in f}
    assert "PR02" in rules and "PR05" in rules, f
    assert not any("1234.5" in x["note"] or "1 234,5" in x["note"] for x in f), f
    f = compare("Один.\n\nДва 5.", "Бір.")
    assert any(x["rule"].startswith("PR01") for x in f)
    print("kk_parity selftest: ok")


def main(argv=None):
    import _version
    ap = argparse.ArgumentParser(description="Сверка казахской версии с русским оригиналом")
    ap.add_argument("--version", action="version", version="%(prog)s " + _version.get())
    ap.add_argument("--ru")
    ap.add_argument("--kk")
    ap.add_argument("--json")
    ap.add_argument("--glossary", help="glossary.yaml: включает PR06 (термин из глоссария)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    if not (a.ru and a.kk):
        ap.error("нужны --ru и --kk")
    try:
        ru, kk = open(a.ru, encoding="utf-8").read(), open(a.kk, encoding="utf-8").read()
    except OSError as e:
        print(f"[kk_parity] {e}", file=sys.stderr)
        return 1
    gl = None
    if a.glossary:
        import yaml
        gl = yaml.safe_load(open(a.glossary, encoding="utf-8"))
    f = compare(ru, kk, gl)
    by = collections.Counter((x["rule"], x["severity"]) for x in f)
    print(f"находок {len(f)}")
    if f:
        print("  по слоям: " + _layers.summary(f))
    for (r, s), n in sorted(by.items()):
        print(f"  {r:24} {s:14} {n}")
    for x in f:
        print(f"  - {x['note']}")
    if a.json:
        json.dump({"findings": f}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 2 if any(x["severity"] == "blocker" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
