#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""Выборка для gold-set: предложения казахского перевода с русским оригиналом, которые разметит носитель языка.

Берёт пары «пост — перевод» (pairs.jsonl от kk_pairs), делит абзацы на предложения, сопоставляет их по порядку
(только там, где число предложений в абзацах совпало и числа в предложениях те же), прогоняет казахскую часть через kk_clean
и kk_typo, чтобы разметчик не видел технического шума, и набирает страты:

  калька      есть оборот из списка русизмов («сонымен қатар», «болып табылады», «жүзеге асыру»…)
  термин      в русском предложении есть термин из глоссария
  техническое kk_lint нашёл дефект по правилам H, S01, T02, P, C
  контроль    ничего из перечисленного: частота проблем в «чистом» тексте

Страты разметчику не показываются: строки перемешаны, а страта лежит в отдельном ключе (goldset_key.csv).
Результат: goldset.xlsx (лист «Инструкция» и лист «Разметка» с выпадающими списками), goldset_key.csv, goldset.tsv.

    python3 tests/bench/goldset_sample.py --pairs pairs.jsonl --out-dir ВЫХОД [--dict kk_KZ --lm lm.json.gz]
"""
import argparse
import collections
import csv
import json
import math
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kk_clean import Dictionary, clean  # noqa: E402
from kk_lint import lint  # noqa: E402
from kk_typo import fix as typo_fix  # noqa: E402

CALQUES = ["сонымен қатар", "болып табылады", "жүзеге асыр", "аясында", "атап өт", "қолдау көрсет", "өз кезегінде", "бұл ретте"]
CATEGORIES = ["калька", "порядок слов", "управление", "норма", "термин", "смысл", "машинный след", "другое"]
LINT_RULES = ["H01", "H02", "H04", "S01", "T02", "P02", "P05", "C01"]
_ABBR = ["им", "г", "гг", "тыс", "млн", "млрд", "руб", "долл", "ул", "обл", "др", "пр", "стр", "рис", "ж", "жж", "тг", "т.д", "т.п", "т.е", "т.б", "т.с.с"]
SPLIT = re.compile(r"(?<![А-ЯӘҒҚҢӨҰҮҺІ]\.)" + "".join(rf"(?<!\b{a}\.)" if "." not in a else rf"(?<!{a}\.)" for a in _ABBR)
                   + r"(?<=[.!?…»])\s+(?=[А-ЯӘҒҚҢӨҰҮҺІA-Z«\"“(])")
BAD = re.compile(r"https?://|#\w|@\w|[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2705\u25A0-\u25FF\u2022\u2023]")
NUM = re.compile(r"\d+(?:[.,]\d+)?")


def sentences(par):
    """Предложения абзаца; куски склеиваются, пока кавычки «» и скобки не уравновешены."""
    out, buf = [], ""
    for part in SPLIT.split(par.strip()):
        buf = f"{buf} {part}".strip() if buf else part.strip()
        if buf.count("«") == buf.count("»") and buf.count("(") == buf.count(")"):
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def units(pairs):
    for p in pairs:
        if float(p.get("score", 0)) < 0.7:
            continue
        kk_pars = [x for x in re.split(r"\n\s*\n|\n", p["kk"]) if x.strip()]
        ru_pars = [x for x in re.split(r"\n\s*\n|\n", p["ru"]) if x.strip()]
        if len(kk_pars) != len(ru_pars):
            continue
        for pi, (kp, rp) in enumerate(zip(kk_pars, ru_pars)):
            ks, rs = sentences(kp), sentences(rp)
            if len(ks) != len(rs):
                continue
            for si, (k, r) in enumerate(zip(ks, rs)):
                nk, nr = len(k.split()), len(r.split())
                if not (8 <= nk <= 40 and 6 <= nr <= 40) or BAD.search(k) or BAD.search(r):
                    continue
                if not 0.45 <= nk / nr <= 1.4:                                   # длины несопоставимы: вероятно, сдвиг сопоставления
                    continue
                if k.count("«") != k.count("»") or r.count("«") != r.count("»") or k[-1] not in ".!?…»\"" or r[-1] not in ".!?…»\"":
                    continue
                if sorted(NUM.findall(k)) != sorted(NUM.findall(r)):
                    continue
                yield {"kk_id": p["kk_id"], "ru_id": p["ru_id"], "date": p["date"][:10], "par": pi + 1, "sent": si + 1, "ru": r, "kk": k}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--n", type=int, default=240)
    ap.add_argument("--seed", type=int, default=20261024)
    ap.add_argument("--glossary", default=os.path.join(ROOT, "data", "glossary.yaml"))
    ap.add_argument("--dict")
    ap.add_argument("--lm")
    ap.add_argument("--pool", type=int, default=9000, help="сколько предложений проверять линтером")
    ap.add_argument("--shared", type=int, default=24, help="сколько строк отметить для второго разметчика")
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    import yaml
    gl = yaml.safe_load(open(a.glossary, encoding="utf-8"))
    d = Dictionary(a.dict, ()) if a.dict else None
    lm = None
    if a.lm:
        from kk_restore import CharLM
        lm = CharLM.load(a.lm)
    pairs = [json.loads(l) for l in open(a.pairs, encoding="utf-8")]
    pool, seen = [], set()
    for u in units(pairs):
        key = re.sub(r"\W+", "", u["kk"].lower())
        if key in seen:
            continue
        seen.add(key)
        u["kk"] = typo_fix(clean(u["kk"], d)[0])[0]
        pool.append(u)
    rnd.shuffle(pool)
    print(f"подходящих предложений: {len(pool)}")
    terms = [(e["key"], re.compile(e["parity_ru"], re.I)) for e in gl.get("entries", []) if e.get("parity_ru")]
    for u in pool[:a.pool]:
        u["calque"] = next((c for c in CALQUES if c in u["kk"].lower()), "")
        u["terms"] = [k for k, rx in terms if rx.search(u["ru"])]
        f, _ = lint(u["kk"], d=d, lm=lm, gl=gl, only=LINT_RULES)
        u["flags"] = sorted({x["rule"].split()[0] for x in f})
    chosen = {"калька": [], "термин": [], "техническое": [], "контроль": []}
    quota = {"калька": round(a.n * 0.29), "термин": round(a.n * 0.17), "техническое": round(a.n * 0.17)}
    quota["контроль"] = a.n - sum(quota.values())
    per_term = collections.Counter()
    used = set()
    for name, test in (("техническое", lambda u: u["flags"]), ("калька", lambda u: u["calque"]), ("термин", lambda u: u["terms"])):
        for i, u in enumerate(pool[:a.pool]):
            if i in used or len(chosen[name]) >= quota[name] or not test(u):
                continue
            if name == "термин":
                k = u["terms"][0]
                if per_term[k] >= 4:
                    continue
                per_term[k] += 1
            used.add(i)
            chosen[name].append(u)
    quota["контроль"] += sum(quota[k] - len(chosen[k]) for k in ("калька", "термин", "техническое"))   # недобор страт — в контроль
    for i, u in enumerate(pool[:a.pool]):
        if len(chosen["контроль"]) >= quota["контроль"]:
            break
        if i not in used and not (u["flags"] or u["calque"] or u["terms"]):
            used.add(i)
            chosen["контроль"].append(u)
    rows = [dict(u, stratum=s) for s, us in chosen.items() for u in us]
    rnd.shuffle(rows)
    shared = set(rnd.sample(range(len(rows)), min(a.shared, len(rows))))
    for i, r in enumerate(rows):
        r["id"] = f"G{i + 1:03d}"
        r["shared"] = int(i in shared)
    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "goldset_key.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "stratum", "kk_id", "ru_id", "date", "par", "sent", "calque", "terms", "flags", "shared"])
        for r in rows:
            w.writerow([r["id"], r["stratum"], r["kk_id"], r["ru_id"], r["date"], r["par"], r["sent"], r["calque"], " ".join(r["terms"]), " ".join(r["flags"]), r["shared"]])
    with open(os.path.join(a.out_dir, "goldset.tsv"), "w", encoding="utf-8") as f:
        f.write("id\tru\tkk\tпроблема\tкатегория\tдоп. категория\tфрагмент\tисправление\tуверенность\tкомментарий\n")
        for r in rows:
            f.write(f"{r['id']}\t{r['ru']}\t{r['kk']}\t\t\t\t\t\t\t\n")
    write_xlsx(os.path.join(a.out_dir, "goldset.xlsx"), rows)
    cnt = collections.Counter(r["stratum"] for r in rows)
    print(f"в выборке {len(rows)}: {dict(cnt)}; для второго разметчика {sum(r['shared'] for r in rows)}")


def write_xlsx(path, rows):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "Инструкция"
    F = lambda **k: Font(name="Arial", size=k.pop("size", 10), **k)
    lines = [
        ("Разметка перевода на казахский: что нужно сделать", dict(bold=True, size=13)),
        ("", {}),
        ("Перед вами предложения из пресс-материалов: русский оригинал и казахский перевод. Ваша задача: прочитать казахское предложение глазами носителя языка и сказать,", {}),
        ("есть ли в нём проблема. Нужен ваш слух, а не словарь: если фраза звучит «по-русски» или режет ухо, это и надо отметить.", {}),
        ("", {}),
        ("Лист «Разметка», заполняйте только столбцы D–J (серые):", dict(bold=True)),
        ("D. Проблема: «чисто» или «есть проблема». Если сомневаетесь, выберите «есть проблема» и поставьте уверенность 1.", {}),
        ("E. Основная категория (только если есть проблема). F. Дополнительная категория, если проблем две разных.", {}),
        ("G. Фрагмент: скопируйте слово или оборот, где проблема. H. Исправление: как сказали бы вы (переписывайте только проблемное место).", {}),
        ("I. Уверенность: 3 — уверен, 2 — скорее да, 1 — не уверен. J. Комментарий — по желанию.", {}),
        ("", {}),
        ("Категории", dict(bold=True)),
        ("калька — русская конструкция или оборот, переведённый дословно, неестественный по-казахски (например, «болып табылады» там, где русское «является» лишнее).", {}),
        ("порядок слов — русский порядок вместо казахского (сказуемое не в конце, определение стоит неестественно).", {}),
        ("управление — падеж, послелог или согласование перенесены из русского и звучат неправильно.", {}),
        ("норма — орфографическая, пунктуационная или грамматическая ошибка независимо от перевода.", {}),
        ("термин — неточный, неустоявшийся или непоследовательный термин; русское слово там, где есть устоявшееся казахское, или наоборот.", {}),
        ("смысл — по сравнению с оригиналом смысл потерян, добавлен или искажён (числа и имена проверяются отдельно, их не ищите).", {}),
        ("машинный след — фраза выглядит написанной машиной: шаблонный зачин, пустой оборот, неестественно ровный ритм.", {}),
        ("другое — проблема есть, но она не подходит ни под одну категорию (опишите в комментарии).", {}),
        ("", {}),
        ("Как отвечать в спорных случаях", dict(bold=True)),
        ("Устоявшийся в прессе оборот, даже русизм по происхождению, — не ошибка, если вы сами так написали бы. Отметьте «чисто» или проблему с уверенностью 1–2.", {}),
        ("Не правьте вкус: «можно лучше» — не проблема. Проблема — когда носитель споткнулся или переписал бы.", {}),
        ("Каждое предложение оценивайте само по себе; если оно двусмысленно без соседних, пишите в комментарии.", {}),
        ("", {}),
        ("Время: около 45 секунд на строку, примерно 3–4 часа на лист. Перерывы лучше делать каждые 60 строк: усталость портит слух.", {}),
        ("Тексты взяты из пресс-материалов; прошу не пересылать файл третьим лицам. Часть строк помечена для второго разметчика, это нормально.", {}),
        ("", {}),
        ("Пример заполненной строки (в лист «Разметка» не входит)", dict(bold=True)),
        ("Русский: Компания является одним из крупнейших налогоплательщиков страны. — Казахский: Компания елдің ең ірі салық төлеушілерінің бірі болып табылады.", {}),
        ("D: есть проблема. E: калька. G: болып табылады. H: Компания — елдегі ең ірі салық төлеушілердің бірі. I: 2.", {}),
    ]
    for i, (t, st) in enumerate(lines, 1):
        c = ws.cell(row=i, column=1, value=t)
        c.font = F(**st)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 150
    wk = wb.create_sheet("Разметка")
    head = ["№", "Русский оригинал", "Казахский текст", "Проблема", "Основная категория", "Дополнительная категория", "Фрагмент", "Исправление", "Уверенность", "Комментарий"]
    wk.append(head)
    for r in rows:
        wk.append([r["id"], r["ru"], r["kk"], None, None, None, None, None, None, None])
    widths = [7, 55, 55, 14, 18, 18, 28, 45, 12, 30]
    grey = PatternFill("solid", fgColor="EDEDED")
    hfill = PatternFill("solid", fgColor="1F3864")
    for j, w in enumerate(widths, 1):
        wk.column_dimensions[chr(64 + j)].width = w
        h = wk.cell(row=1, column=j)
        h.font = F(bold=True, color="FFFFFF")
        h.fill = hfill
        h.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    for i in range(2, len(rows) + 2):
        n = max(len(str(wk.cell(row=i, column=2).value)), len(str(wk.cell(row=i, column=3).value)))
        wk.row_dimensions[i].height = max(32, 15 * math.ceil(n / 52))
        for j in range(1, 11):
            c = wk.cell(row=i, column=j)
            c.font = F()
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if j >= 4:
                c.fill = grey
    cats = ",".join(CATEGORIES)
    last = len(rows) + 1
    for rng, formula in ((f"D2:D{last}", '"чисто,есть проблема"'), (f"E2:F{last}", f'"{cats}"'), (f"I2:I{last}", '"1,2,3"')):
        dv = DataValidation(type="list", formula1=formula, allow_blank=True)
        wk.add_data_validation(dv)
        dv.add(rng)
    wk.freeze_panes = "D2"
    wb.save(path)


if __name__ == "__main__":
    main()
