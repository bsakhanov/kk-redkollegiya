#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""Собирает data/kk_attested.txt: слова, которые часто встречаются в обучающей части KazNERD (CC BY 4.0), но неизвестны
Hunspell и вето по основам (заимствования, имена, формы вроде «шынын»). Они не дают S01 «исправлять» живые слова.

Проверочные части (test, valid) в список не входят, поэтому стенд tests/bench/kaznerd_bench.py остаётся честным.
Слово отбрасывается, если замена одной буквы на казахскую даёт слово, которое в корпусе встречается в 20 раз чаще
(это опечатка вида «кызмет»).  Запуск: python3 tests/bench/build_attested.py --dict ПУТЬ/kk_KZ [--min 8]
Our product uses ISSAI KazNERD (https://aclanthology.org/2022.lrec-1.44), CC BY 4.0.
"""
import argparse
import collections
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kk_clean import Dictionary  # noqa: E402
from kk_stem import load_lexicon, strip  # noqa: E402

CY = "А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі"
FIX = {"к": "қ", "г": "ғ", "н": "ң", "а": "ә", "о": "ө", "у": "ұү", "и": "і", "х": "һ"}
RAW = "https://raw.githubusercontent.com/IS2AI/KazNERD/HEAD/KazNERD/IOB2_train.txt"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dict", required=True)
    ap.add_argument("--min", type=int, default=8)
    ap.add_argument("--cache", default=os.path.expanduser("~/.cache/kk-redkollegiya/kaznerd"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "kk_attested.txt"))
    a = ap.parse_args()
    path = os.path.join(a.cache, "IOB2_train.txt")
    if not os.path.exists(path):
        os.makedirs(a.cache, exist_ok=True)
        urllib.request.urlretrieve(RAW, path)
    cnt = collections.Counter()
    for line in open(path, encoding="utf-8"):
        t = line.split()
        if t and re.fullmatch(rf"[{CY}]{{3,}}", t[0]):
            cnt[t[0].lower()] += 1
    d = Dictionary(a.dict, (), attested=set())
    stems = load_lexicon()
    keep = []
    for w, c in cnt.items():
        if c < a.min or d.known(w) or strip(w, lambda s: s in stems or d.known(s), 5):
            continue
        typo = any(cnt.get(w[:i] + r + w[i + 1:], 0) >= 20 * c for i, ch in enumerate(w) for r in FIX.get(ch, ""))
        if not typo:
            keep.append(w)
    hdr = (f"# kk_attested.txt — {len(keep)} слов, которые встречаются в обучающей части KazNERD не реже {a.min} раз, но неизвестны Hunspell\n"
           "# и проверке основ (заимствования, имена, формы вроде «шынын»). Строит tests/bench/build_attested.py.\n"
           "# Источник: ISSAI KazNERD (https://aclanthology.org/2022.lrec-1.44), лицензия CC BY 4.0; список слов, не текст корпуса.\n")
    open(a.out, "w", encoding="utf-8").write(hdr + "\n".join(sorted(keep)) + "\n")
    print(f"записано {len(keep)} слов в {os.path.relpath(a.out, ROOT)}")


if __name__ == "__main__":
    main()
