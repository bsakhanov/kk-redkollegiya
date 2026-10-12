#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""kk_restore.py — восстановление казахских букв (қ ғ ң ә ө ұ ү һ і) в словах, набранных без них.

Задача знакомая по восстановлению диакритики: на русской раскладке «Қазақстан» набирают
«Казакстан». Словарь Hunspell тут слаб (аффиксные цепочки в нём неполны), поэтому буквы
восстанавливает символьная языковая модель: n-граммы букв внутри слов (n=5, «глупый откат»
по длине контекста), обученные на чистом казахском тексте, плюс поиск по лучу по вариантам
каждой буквы. Гласная гармония (қ рядом с твёрдыми гласными, к рядом с мягкими) модель ловит
сама, потому что видит соседние буквы.

Модель обучается на твоём корпусе локально и остаётся у тебя: книги под охраной, а модель —
производные частоты, которые лучше не публиковать.

Использование:
    kk_restore.py train чистое/*.txt -o lm.json.gz
    kk_restore.py eval --lm lm.json.gz --test чистое/Үш_анық.txt [--sample 3000] [--margin 2.0]
    kk_restore.py word --lm lm.json.gz Казакстан экспорттык
Из Python:
    lm = CharLM.load("lm.json.gz"); lm.suggest("Казакстан")  ->  ("Қазақстан", дельта)

Только стандартная библиотека.
"""

import argparse
import collections
import gzip
import json
import math
import random
import re
import sys
import unicodedata

CYRL = "а-яёәғқңөұүһі"
WORD = re.compile(rf"[{CYRL}]+", re.I)

# что можно вернуть на место: русская буква -> варианты казахских
SPECIAL = {"к": "қ", "г": "ғ", "н": "ң", "а": "ә", "о": "ө", "у": "ұү", "х": "һ", "и": "і", "э": "ә"}
# обратное отображение для проверки (порча)
CORRUPT = {"ә": "а", "ғ": "г", "қ": "к", "ң": "н", "ө": "о", "ұ": "у", "ү": "у", "һ": "х", "і": "и"}


def norm(t):
    t = unicodedata.normalize("NFC", t)
    return t.replace("\u018f", "Ә").replace("\u0259", "ә").replace("\u00ad", "")


class CharLM:
    def __init__(self, n=5):
        self.n = n
        self.ng = [collections.Counter() for _ in range(n + 1)]     # ng[k]: k-граммы
        self.tot = [collections.Counter() for _ in range(n + 1)]    # tot[k]: сумма по контексту длины k-1

    # ------------------------------------------------------------ обучение
    def train(self, words):
        n = self.n
        for w, c in words.items():
            if len(w) < 2:
                continue
            s = "^" * (n - 1) + w + "$"
            weight = min(c, 3)
            for i in range(n - 1, len(s)):
                for k in range(1, n + 1):
                    g = s[i - k + 1:i + 1]
                    self.ng[k][g] += weight
                    self.tot[k][g[:-1]] += weight

    # -------------------------------------------------------- оценка и поиск
    def logp(self, hist, ch):
        pen = 0.0
        for k in range(self.n, 0, -1):
            ctx = hist[len(hist) - (k - 1):] if k > 1 else ""
            num = self.ng[k].get(ctx + ch, 0)
            if num:
                return pen + math.log(num / self.tot[k][ctx])
            pen += math.log(0.4)
        return pen + math.log(1e-7)

    def score(self, word):
        hist = "^" * (self.n - 1)
        total = 0.0
        for ch in word + "$":
            total += self.logp(hist, ch)
            hist = (hist + ch)[-(self.n - 1):]
        return total

    def best(self, word, beam=40):
        low = word.lower()
        opts = [[c] + list(SPECIAL.get(c, "")) for c in low]
        states = [("^" * (self.n - 1), 0.0, "")]
        for o in opts:
            new = []
            for hist, sc, out in states:
                for ch in o:
                    new.append(((hist + ch)[-(self.n - 1):], sc + self.logp(hist, ch), out + ch))
            new.sort(key=lambda x: -x[1])
            states = new[:beam]
        fin = [(out, sc + self.logp(hist, "$")) for hist, sc, out in states]
        fin.sort(key=lambda x: -x[1])
        return fin

    def suggest(self, word, margin=2.0, beam=40):
        """(исправленное слово, выигрыш в лог-вероятности) или (None, 0.0)."""
        low = word.lower()
        if len(low) < 3 or not any(c in SPECIAL for c in low):
            return None, 0.0
        fin = self.best(word, beam)
        top, sc = fin[0]
        if top == low:
            return None, 0.0
        delta = sc - self.score(low)
        if delta < margin:
            return None, delta
        out = []
        for orig, new in zip(word, top):
            out.append(new.upper() if orig.isupper() else new)
        return "".join(out), delta

    # ------------------------------------------------------------ хранение
    def save(self, path):
        data = {"n": self.n, "ng": [dict(c) for c in self.ng]}
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    @classmethod
    def load(cls, path):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        lm = cls(data["n"])
        for k, d in enumerate(data["ng"]):
            lm.ng[k] = collections.Counter(d)
            for g, c in d.items():
                lm.tot[k][g[:-1]] += c
        return lm


def read_words(paths):
    cnt = collections.Counter()
    for p in paths:
        t = norm(open(p, encoding="utf-8", errors="replace").read())
        t = re.sub(r"-\n", "", t).lower()
        for w in WORD.findall(t):
            cnt[w] += 1
    return cnt


def cmd_train(a):
    words = read_words(a.files)
    lm = CharLM(a.n)
    lm.train(words)
    lm.save(a.out)
    print(f"обучено на {sum(words.values()):,} словах ({len(words):,} разных); n={a.n}; модель: {a.out}".replace(",", " "))


def corrupt(w):
    return "".join(CORRUPT.get(c, c) for c in w)


def cmd_eval(a):
    lm = CharLM.load(a.lm)
    words = read_words(a.test)
    rnd = random.Random(a.seed)
    # слова, где есть что восстанавливать, и слова без казахских букв (проверка «не навреди»)
    spec = [w for w in words if len(w) >= 3 and any(c in CORRUPT for c in w)]
    plain = [w for w in words if len(w) >= 3 and not any(c in CORRUPT for c in w) and any(c in SPECIAL for c in w)]
    # по типам и по токенам
    rnd.shuffle(spec)
    rnd.shuffle(plain)
    spec_s, plain_s = spec[:a.sample], plain[:a.sample]
    hit = top3 = nosug = 0
    for w in spec_s:
        c = corrupt(w)
        fin = lm.best(c)
        want = w
        got, delta = lm.suggest(c, a.margin)
        if got and got.lower() == want:
            hit += 1
        elif got is None:
            nosug += 1
        if want in [x for x, _ in fin[:3]]:
            top3 += 1
    changed = sum(1 for w in plain_s if lm.suggest(w, a.margin)[0] is not None)
    # то же по токенам (частотно взвешенно)
    tok_total = sum(words[w] for w in spec_s)
    tok_hit = sum(words[w] for w in spec_s if (lm.suggest(corrupt(w), a.margin)[0] or "").lower() == w)
    print(f"слов с казахскими буквами в выборке: {len(spec_s)}")
    print(f"  восстановлено верно с первой попытки: {hit} ({100*hit/max(len(spec_s),1):.1f}%)")
    print(f"  верное слово в тройке лучших:         {top3} ({100*top3/max(len(spec_s),1):.1f}%)")
    print(f"  модель промолчала (дельта ниже порога): {nosug} ({100*nosug/max(len(spec_s),1):.1f}%)")
    print(f"  по токенам (частотно): {100*tok_hit/max(tok_total,1):.1f}%")
    print(f"верных слов, которые модель зря «исправила»: {changed} из {len(plain_s)} ({100*changed/max(len(plain_s),1):.1f}%)")
    return 0


def cmd_word(a):
    lm = CharLM.load(a.lm)
    for w in a.words:
        s, d = lm.suggest(w, a.margin)
        top = lm.best(w)[:3]
        print(f"{w}\t->\t{s}\t(дельта {d:.1f}; лучшие: {', '.join(x for x, _ in top)})")
    return 0


def main(argv=None):
    import _version
    ap = argparse.ArgumentParser(description="Восстановление казахских букв символьной моделью")
    ap.add_argument("--version", action="version", version="%(prog)s " + _version.get())
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("files", nargs="+")
    t.add_argument("-o", "--out", required=True)
    t.add_argument("--n", type=int, default=5)
    t.set_defaults(fn=cmd_train)
    e = sub.add_parser("eval")
    e.add_argument("--lm", required=True)
    e.add_argument("--test", nargs="+", required=True)
    e.add_argument("--sample", type=int, default=3000)
    e.add_argument("--margin", type=float, default=2.0)
    e.add_argument("--seed", type=int, default=7)
    e.set_defaults(fn=cmd_eval)
    w = sub.add_parser("word")
    w.add_argument("--lm", required=True)
    w.add_argument("--margin", type=float, default=2.0)
    w.add_argument("words", nargs="+")
    w.set_defaults(fn=cmd_word)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
