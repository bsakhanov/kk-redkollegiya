#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""Открытая модель букв и открытый словарь: восстановление букв (S01) без своего корпуса и без Hunspell.

Скачивает обучающую часть KazNERD (ISSAI, CC BY 4.0), обучает модель kk_restore и собирает список форм, встреченных
в обучающей части не реже двух раз. Проверочные части (valid, test) не трогает: они остаются стендом kaznerd_bench.py.

    python3 tests/bench/train_kaznerd.py --out-dir open-model
    python3 tools/kk_lint.py текст.md --forms open-model/kk_forms_kaznerd.txt --lm open-model/lm-kaznerd.json.gz

Our product uses ISSAI KazNERD (https://aclanthology.org/2022.lrec-1.44), which is available under a Creative Commons
Attribution 4.0 International License.
"""
import argparse
import hashlib
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from kaznerd_bench import detok, fetch, sentences  # noqa: E402
from kk_restore import CharLM, read_words  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out-dir", default="open-model")
    ap.add_argument("--cache", default=os.path.expanduser("~/.cache/kk-redkollegiya/kaznerd"))
    ap.add_argument("--n", type=int, default=5, help="порядок n-граммной модели")
    ap.add_argument("--min-count", type=int, default=2, help="сколько раз форма должна встретиться, чтобы попасть в список")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    text = "\n".join(detok(s) for s in sentences(fetch(a.cache, "train"))) + "\n"
    tmp = os.path.join(tempfile.mkdtemp(), "kaznerd_train.txt")
    open(tmp, "w", encoding="utf-8").write(text)
    words = read_words([tmp])
    lm = CharLM(a.n)
    lm.train(words)
    lm_path = os.path.join(a.out_dir, "lm-kaznerd.json.gz")
    lm.save(lm_path)
    forms = sorted(w for w, c in words.items() if c >= a.min_count and len(w) >= 3)
    fp = os.path.join(a.out_dir, "kk_forms_kaznerd.txt")
    hdr = (f"# kk_forms_kaznerd.txt — {len(forms)} форм, которые встречаются в обучающей части KazNERD не реже {a.min_count} раз (длина от трёх букв).\n"
           "# Открытый словарь для kk_lint --forms: замена Hunspell для восстановления букв (S01). Строит tests/bench/train_kaznerd.py.\n"
           "# Источник: ISSAI KazNERD (https://aclanthology.org/2022.lrec-1.44), лицензия CC BY 4.0; список слов, не текст корпуса.\n")
    open(fp, "w", encoding="utf-8").write(hdr + "\n".join(forms) + "\n")
    print(f"слов в обучающей части {sum(words.values()):,}, разных {len(words):,}".replace(",", " "))
    for p in (lm_path, fp):
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        print(f"{os.path.relpath(p)}  {os.path.getsize(p) // 1024} КБ  sha256 {h[:16]}…")
    print(f"форм в списке: {len(forms)}")


if __name__ == "__main__":
    main()
