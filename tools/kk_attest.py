#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""kk_attest.py — засвидетельствованность: сколько раз слово или оборот встречается в группах корпуса.

Критерий терминологической политики (методология, раздел «Регистр, профили и терминология»):
слово допускается, если оно засвидетельствовано в эталонном корпусе и в узусе аудитории. Скрипт
считает частоту на 100 тыс. слов по каждой группе (например, «классика», «советская проза»,
«современная») и показывает контексты, потому что одна частота не различает «занять место»
и «иметь место» — вердикт выносит человек.

Использование:
    kk_attest.py --groups data/corpus_groups.yaml --terms data/terms_calques.yaml [--context 3]
                 [--json результат.json]

groups.yaml:                                   terms.yaml:
  classic:                                       - label: «сонымен қатар»
    label: классика (Абай, Шәкәрім)                regex: "сонымен\\s+қатар"
    files: [чистое/Abay_kk_only.txt, ...]

Корпус перед подсчётом чистят kk_clean.py (иначе латинская «ə» и легаси-кодировка прячут слова).
Двуязычные издания очищают от русских строк заранее (в «Қара сөздер» ими занято около половины текста).
Только стандартная библиотека; YAML — если стоит PyYAML, иначе подойдёт JSON.
"""

import argparse
import json
import os
import random
import re
import sys
import unicodedata

L = "А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі"


def _load_cfg(path):
    raw = open(path, encoding="utf-8").read()
    if path.endswith(".json"):
        return json.loads(raw)
    try:
        import yaml
    except ImportError:
        sys.exit("для YAML нужен PyYAML (pip install pyyaml) или JSON-файл")
    return yaml.safe_load(raw)


def load_text(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    t = unicodedata.normalize("NFC", t)
    t = t.replace("\u018f", "Ә").replace("\u0259", "ә").replace("\u00ad", "")
    t = re.sub(r"-\n", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.lower()


def pat(core):
    return re.compile(rf"(?<![{L}]){core}(?![{L}])")


def main(argv=None):
    import _version
    ap = argparse.ArgumentParser(description="Засвидетельствованность оборотов по группам корпуса")
    ap.add_argument("--version", action="version", version="%(prog)s " + _version.get())
    ap.add_argument("--groups", required=True)
    ap.add_argument("--terms", required=True)
    ap.add_argument("--context", type=int, default=0, help="сколько случайных контекстов показать")
    ap.add_argument("--width", type=int, default=48)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json")
    a = ap.parse_args(argv)

    groups = _load_cfg(a.groups)
    terms = _load_cfg(a.terms)
    base = os.path.dirname(os.path.abspath(a.groups))
    texts, sizes = {}, {}
    for key, g in groups.items():
        parts = []
        for f in g["files"]:
            p = f if os.path.isabs(f) else os.path.join(base, f)
            parts.append(load_text(p))
        texts[key] = " ".join(parts)
        sizes[key] = len(re.findall(rf"[{L}]+", texts[key]))

    print("слов в группах: " + "; ".join(f"{groups[k]['label']} — {sizes[k]:,}".replace(",", " ")[:0] + groups[k]['label'] + " — " + f"{sizes[k]:,}".replace(",", " ") for k in groups))
    head = f"{'оборот':30}" + "".join(f"{groups[k]['label'][:22]:>26}" for k in groups)
    print(head)
    out = []
    rnd = random.Random(a.seed)
    for t in terms:
        r = pat(t["regex"])
        row, rec = [], {"label": t["label"], "groups": {}}
        for k in groups:
            ms = list(r.finditer(texts[k]))
            rate = 1e5 * len(ms) / max(sizes[k], 1)
            row.append(f"{len(ms):>5} ({rate:6.1f}/100к)".replace(".", ","))
            rec["groups"][k] = {"count": len(ms), "per100k": round(rate, 2)}
            if a.context:
                sample = rnd.sample(ms, min(a.context, len(ms)))
                rec["groups"][k]["contexts"] = [
                    "…" + texts[k][max(0, m.start() - a.width):m.end() + a.width] + "…" for m in sample]
        print(f"{t['label']:30}" + "".join(f"{x:>26}" for x in row))
        out.append(rec)
        if a.context:
            for k in groups:
                for c in rec["groups"][k].get("contexts", []):
                    print(f"      [{groups[k]['label'][:14]}] {c}")
    if a.json:
        json.dump({"sizes": sizes, "terms": out}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
