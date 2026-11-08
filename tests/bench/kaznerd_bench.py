#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""Стенд на открытом корпусе KazNERD (ISSAI, Назарбаев Университет, CC BY 4.0): 22 474 предложения новостного текста.

Корпус не размечен на ошибки, зато написан профессионалами: всё, что набор в нём находит, — либо настоящий дефект
датасета (латинская «x» в казахском слове), либо ложное срабатывание. Стенд считает находки по правилам и точность
восстановления букв на независимом тексте. Подробности и измеренные числа — docs/BENCH.md.

    python3 tests/bench/kaznerd_bench.py --dict ПУТЬ/kk_KZ [--lm ПУТЬ/lm.json.gz] [--out report.json]

Our product uses ISSAI KazNERD (https://aclanthology.org/2022.lrec-1.44), which is available under a Creative Commons
Attribution 4.0 International License.
"""
import argparse
import collections
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = "https://raw.githubusercontent.com/IS2AI/KazNERD/HEAD/KazNERD/IOB2_{}.txt"


def fetch(cache, part):
    path = os.path.join(cache, f"IOB2_{part}.txt")
    if not os.path.exists(path):
        os.makedirs(cache, exist_ok=True)
        urllib.request.urlretrieve(RAW.format(part), path)
    return path


def sentences(path):
    cur = []
    for line in open(path, encoding="utf-8"):
        a = line.split()
        if not a:
            if cur:
                yield cur
                cur = []
        else:
            cur.append(a[0])
    if cur:
        yield cur


def detok(toks):
    s = " ".join(toks)
    s = re.sub(r"\s+([,.;:!?)»%])", r"\1", s)
    return re.sub(r"([(«])\s+", r"\1", s)


_STRIP = str.maketrans({"ә": "а", "ғ": "г", "қ": "к", "ң": "н", "ө": "о", "ұ": "у", "ү": "у", "і": "и", "һ": "х",
                        "Ә": "А", "Ғ": "Г", "Қ": "К", "Ң": "Н", "Ө": "О", "Ұ": "У", "Ү": "У", "І": "И", "Һ": "Х"})
_CYR = "А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі"


def strip_task(sents, a):
    """Обратная задача: у слов в N предложениях сняты казахские буквы; сколько подсказок S01 вернули исходное слово."""
    pick = random.Random(a.seed).sample(sents, min(a.strip, len(sents)))
    corr = [s.translate(_STRIP) for s in pick]
    want, changed = collections.defaultdict(set), 0
    for o, c in zip(pick, corr):
        for x, y in zip(o.split(), c.split()):
            x2, y2 = re.sub(rf"[^{_CYR}]", "", x).lower(), re.sub(rf"[^{_CYR}]", "", y).lower()
            if x2 != y2 and len(x2) >= 3:
                want[y2].add(x2)
                changed += 1
    tmp = tempfile.mkdtemp()
    src, js = os.path.join(tmp, "strip.txt"), os.path.join(tmp, "f.json")
    open(src, "w", encoding="utf-8").write("\n".join(corr) + "\n")
    cmd = [sys.executable, os.path.join(ROOT, "tools", "kk_lint.py"), src, "--glossary", a.glossary, "--only", "S01", "--json", js]
    for flag, val in (("--dict", a.dict), ("--lm", a.lm), ("--forms", a.forms)):
        if val:
            cmd += [flag, val]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    f = json.load(open(js, encoding="utf-8"))["findings"]
    ok = 0
    for x in f:
        for q, e in zip(x["quote"].split(), (x.get("edit") or "").split()):
            if q != e:
                q2, e2 = re.sub(rf"[^{_CYR}]", "", q).lower(), re.sub(rf"[^{_CYR}]", "", e).lower()
                ok += e2 in want.get(q2, ())
                break
    return {"предложений": len(pick), "слов со снятыми буквами": changed, "подсказок S01": len(f), "верных": ok,
            "доля верных": round(100 * ok / max(len(f), 1), 1), "полнота": round(100 * ok / max(changed, 1), 1)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dict", help="префикс словаря Hunspell (без .dic/.aff)")
    ap.add_argument("--lm", help="модель букв (kk_restore train); без неё S01 и точность восстановления не считаются")
    ap.add_argument("--forms", help="список форм (data/kk_forms_kaznerd.txt): открытый словарь вместо Hunspell")
    ap.add_argument("--strip", type=int, default=0, help="обратная задача: в N предложениях снять казахские буквы и посчитать подсказки S01")
    ap.add_argument("--seed", type=int, default=7, help="зерно выборки предложений для --strip")
    ap.add_argument("--glossary", default=os.path.join(ROOT, "data", "glossary.yaml"))
    ap.add_argument("--parts", nargs="+", default=["test", "valid"])
    ap.add_argument("--cache", default=os.path.expanduser("~/.cache/kk-redkollegiya/kaznerd"))
    ap.add_argument("--sample", type=int, default=3000, help="слов для проверки восстановления букв")
    ap.add_argument("--out", help="записать отчёт в JSON")
    a = ap.parse_args(argv)
    sents = [detok(s) for p in a.parts for s in sentences(fetch(a.cache, p))]
    text = "\n".join(sents) + "\n"
    words = len(re.findall(r"\w+", text))
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "kaznerd.txt")
    open(src, "w", encoding="utf-8").write(text)
    js = os.path.join(tmp, "findings.json")
    cmd = [sys.executable, os.path.join(ROOT, "tools", "kk_lint.py"), src, "--glossary", a.glossary, "--json", js]
    if a.dict:
        cmd += ["--dict", a.dict]
    if a.lm:
        cmd += ["--lm", a.lm]
    if a.forms:
        cmd += ["--forms", a.forms]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    f = json.load(open(js, encoding="utf-8"))["findings"]
    by = collections.Counter(x["rule"].split()[0] for x in f)
    rep = {"предложений": len(sents), "слов": words, "находок": len(f), "по правилам": dict(sorted(by.items())),
           "на тысячу слов": {k: round(1000 * v / words, 2) for k, v in sorted(by.items())}}
    for rule in ("H01", "H02", "H04", "S01", "T02"):
        xs = [x for x in f if x["rule"].startswith(rule)]
        if xs:
            rep.setdefault("примеры", {})[rule] = [[x["quote"][:48], x.get("edit") and x["edit"][:36]] for x in xs[:8]]
    if a.lm:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "kk_restore.py"), "eval", "--lm", a.lm, "--test", src,
                            "--sample", str(a.sample)], capture_output=True, text=True)
        rep["восстановление букв"] = [l.strip() for l in r.stdout.split("\n") if l.strip()]
    if a.strip:
        rep["обратная задача"] = strip_task(sents, a)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    if a.out:
        json.dump(rep, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
